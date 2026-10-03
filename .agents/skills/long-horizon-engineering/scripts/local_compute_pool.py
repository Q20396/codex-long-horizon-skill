"""Packaged opt-in Beta API; no discovery, network or model runtime.

Callers supply explicit node snapshots and BoundWorker adapters. An adapter is
trusted executable code, not a sandbox: it must enforce its actual endpoint,
credentials, per-call timeout and cancellation. Identity checks here prevent
accidental routing to a differently configured binding; they do not authenticate
a remote machine. Consent/probe/qualification evidence is supplied by the caller.
Task inputs and outputs are returned only in memory and never logged.

KnownFailure promises no unresolved execution or side effects and allows another
local attempt. Every other exception is an unknown outcome, requiring explicit
reconciliation before reuse. run() serializes pool access but executes independent
workers concurrently. It does not persist state across process restarts.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field, replace
from itertools import islice
import math
from threading import Event, Lock
from time import monotonic
from types import MappingProxyType
from typing import Callable


def _positive(value, name, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError('invalid ' + name)


@dataclass(frozen=True)
class Qualification:
    node_id: str
    provider: str
    model: str
    config: str
    task_class: str
    provider_version: str = 'UNKNOWN'


@dataclass(frozen=True)
class Node:
    node_id: str
    provider: str = ''
    model: str = ''
    config: str = ''
    consent: bool = False
    deployment_authorized: bool = False
    probed: bool = False
    runtime_validated: bool = False
    privacy_scopes: frozenset = frozenset()
    qualifications: frozenset = frozenset()
    memory_available: float = 0
    max_concurrent_tasks: int = 1
    current_load: float = 0
    latency: float = 0
    correction_burden: float = 0
    state: str = 'HEALTHY'
    platform_family: str = 'UNKNOWN'
    architecture: str = 'UNKNOWN'
    cpu_soc: str = 'UNKNOWN'
    accelerator: str = 'UNKNOWN'
    provider_version: str = 'UNKNOWN'
    last_validated_at: str = ''
    memory_pressure: float = None
    main_correction_rate: float = None

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError('node identity required')
        for name in ('memory_available', 'current_load', 'latency', 'correction_burden'):
            _positive(getattr(self, name), name, zero=True)
        if type(self.max_concurrent_tasks) is not int or self.max_concurrent_tasks < 1:
            raise ValueError('invalid node concurrency')
        for name in ('memory_pressure', 'main_correction_rate'):
            value = getattr(self, name)
            if value is not None:
                _positive(value, name, zero=True)
                if value > 1:
                    raise ValueError('metric must be a fraction')
        object.__setattr__(self, 'privacy_scopes', frozenset(self.privacy_scopes))
        object.__setattr__(self, 'qualifications', frozenset(self.qualifications))

    def qualifies(self, task):
        return (self.consent is True and self.deployment_authorized is True and
                self.probed is True and self.runtime_validated is True and
                self.provider_version not in ('', 'UNKNOWN') and
                task.data_scope in self.privacy_scopes and
                Qualification(self.node_id, self.provider, self.model, self.config, task.task_class, self.provider_version)
                in self.qualifications)


@dataclass(frozen=True)
class Task:
    task_id: str
    task_class: str
    data_scope: str
    privacy: str = 'LOCAL_ONLY'
    output_privacy: str = 'LOCAL_ONLY'
    memory_required: float = 1
    payload: object = field(default=None, repr=False)

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (self.task_id, self.task_class, self.data_scope)):
            raise ValueError('task identity and scope required')
        if self.privacy not in ('LOCAL_ONLY', 'CLOUD_ALLOWED') or self.output_privacy not in ('LOCAL_ONLY', 'CLOUD_ALLOWED'):
            raise ValueError('invalid privacy policy')
        _positive(self.memory_required, 'task memory')

    @property
    def cloud_allowed(self):
        return self.privacy == self.output_privacy == 'CLOUD_ALLOWED'


@dataclass(frozen=True)
class PoolBudget:
    max_concurrent_tasks: int
    max_active_nodes: int
    max_tasks: int = 100
    timeout_seconds: float = 60

    def __post_init__(self):
        for value in (self.max_concurrent_tasks, self.max_active_nodes, self.max_tasks):
            if type(value) is not int or value < 1:
                raise ValueError('budgets must be positive integers')
        _positive(self.timeout_seconds, 'timeout')


@dataclass(frozen=True)
class BoundWorker:
    node_id: str
    provider: str
    model: str
    config: str
    execute: Callable = field(repr=False)
    provider_version: str = 'UNKNOWN'

    def matches(self, node):
        return ((self.node_id, self.provider, self.model, self.config, self.provider_version) ==
                (node.node_id, node.provider, node.model, node.config, node.provider_version) and callable(self.execute))


@dataclass(frozen=True)
class WorkerResult:
    output: object = field(default=None, repr=False)


@dataclass(frozen=True)
class TaskResult:
    state: str
    output: object = field(default=None, repr=False)
    attempted_nodes: tuple = ()
    reconciliation_required: bool = False
    output_withheld: bool = False


class KnownFailure(Exception):
    """Adapter attests execution stopped and no unresolved effects remain."""


class UnknownOutcome(Exception):
    """Adapter cannot attest whether execution occurred or completed."""


@dataclass(frozen=True)
class NodeHealth:
    """Content-free session observations, separate from caller-supplied metrics.

    Counts refer to submitted attempts. Timeouts and unknowns are subsets of
    failures; assignment failures never enter execution rates. Observed latency
    measures submission to scheduler observation, including queue/wait overhead.
    last_healthy_at uses process monotonic time, not a portable wall-clock date.
    """
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    unknown_count: int = 0
    assignment_failure_count: int = 0
    elapsed_total: float = 0
    last_healthy_at: float = None
    external_memory_pressure: float = None
    external_main_correction_rate: float = None

    @property
    def success_rate(self):
        total = self.success_count + self.failure_count
        return self.success_count / total if total else None

    @property
    def failure_rate(self):
        total = self.success_count + self.failure_count
        return self.failure_count / total if total else None

    @property
    def timeout_rate(self):
        total = self.success_count + self.failure_count
        return self.timeout_count / total if total else None

    @property
    def observed_latency(self):
        total = self.success_count + self.failure_count
        return self.elapsed_total / total if total else None


class TaskPool:
    """Explicit node-set activation and bounded load-aware execution.

    Each run accepts {node_id: BoundWorker}, a bounded list of independent
    tasks and optionally a cloud callable(Task)->WorkerResult. Providing that
    callable authorizes use only for CLOUD_ALLOWED input AND output. Per-node
    memory units must match task memory units. Download/disk setup budgets belong
    to the deployment layer, which must produce deployment_authorized evidence.
    """

    def __init__(self, nodes, budget, authorized_nodes=()):
        items = list(nodes)
        if len({n.node_id for n in items}) != len(items):
            raise ValueError('duplicate node identity')
        self.nodes = MappingProxyType({n.node_id: n for n in items})
        self.budget = budget
        self.authorized_nodes = frozenset(authorized_nodes)
        if not self.authorized_nodes.issubset(self.nodes):
            raise ValueError('authorization names an unregistered node')
        self.node_states = {n.node_id: n.state for n in items}
        self._records = {}
        self._held = {}
        self._run_lock = Lock()
        self._health = {n.node_id: NodeHealth(external_memory_pressure=n.memory_pressure,
                                            external_main_correction_rate=n.main_correction_rate) for n in items}

    @property
    def health(self):
        """Immutable snapshots; no prompts, results, exceptions or credentials."""
        return MappingProxyType(dict(self._health))

    @property
    def pool_state(self):
        healthy = [n for n in self.nodes.values() if self.node_states[n.node_id] == 'HEALTHY'
                   and n.consent is True and n.deployment_authorized is True and n.probed is True
                   and n.runtime_validated is True and n.privacy_scopes
                   and n.provider_version not in ('', 'UNKNOWN')
                   and any(isinstance(q, Qualification) and q.task_class and
                           q == Qualification(n.node_id, n.provider, n.model, n.config, q.task_class, n.provider_version)
                           for q in n.qualifications)]
        active = [n for n in healthy if n.node_id in self.authorized_nodes]
        if any(s == 'DEGRADED' for s in self.node_states.values()):
            return 'PARTIALLY_AVAILABLE' if active else 'DEGRADED'
        if len(active) >= 2:
            return 'MULTI_NODE_ACTIVE'
        if len(active) == 1:
            return 'SINGLE_NODE'
        return 'MULTI_NODE_CANDIDATE' if len(healthy) >= 2 else ('OFFLINE' if self.nodes else 'DISABLED')

    def remove_node(self, node_id):
        """Exclude a node; do not delete its data, models or other resources."""
        if not self._run_lock.acquire(blocking=False):
            raise ValueError('pool running')
        try:
            if node_id not in self.nodes:
                raise ValueError('unknown node')
            self.node_states[node_id] = 'OFFLINE'
        finally:
            self._run_lock.release()

    def reconcile(self, task_id, disposition):
        """External evidence required: NOT_EXECUTED permits retry; COMPLETED closes.

        This is an explicit caller assertion, not an automatic verification.
        A degraded node remains excluded until a new validated pool is built.
        """
        if not self._run_lock.acquire(blocking=False):
            raise ValueError('pool running')
        try:
            record = self._records.get(task_id)
            if record is None or not record.reconciliation_required or disposition not in ('NOT_EXECUTED', 'COMPLETED'):
                raise ValueError('invalid reconciliation')
            held = self._held.get(task_id)
            if held is not None and not held[0].done():
                raise ValueError('worker still executing')
            self._held.pop(task_id, None)
            if disposition == 'NOT_EXECUTED':
                del self._records[task_id]
            else:
                self._records[task_id] = TaskResult('COMPLETED', attempted_nodes=record.attempted_nodes)
        finally:
            self._run_lock.release()

    def run(self, tasks, workers, cloud_worker=None, *, local_output_authorized=False):
        """Release LOCAL_ONLY output only to an explicitly attested local caller.

        The caller is a trusted local controller, not untrusted task JSON. A cloud
        controller must leave local_output_authorized false. This is a library
        policy boundary, not OS isolation or proof of the caller's location.
        """
        if not self._run_lock.acquire(blocking=False):
            raise ValueError('pool already running')
        try:
            return self._run(tasks, workers, cloud_worker, local_output_authorized)
        finally:
            self._run_lock.release()

    def _run(self, tasks, workers, cloud_worker, local_output_authorized):
        tasks = list(islice(tasks, self.budget.max_tasks + 1))
        if len(tasks) > self.budget.max_tasks or len({t.task_id for t in tasks}) != len(tasks):
            raise ValueError('task batch exceeds budget or has duplicate identity')
        if any(t.task_id in self._records for t in tasks):
            raise ValueError('task already executed or awaiting reconciliation')
        workers = dict(workers)
        for node_id, worker in workers.items():
            if node_id not in self.nodes or not isinstance(worker, BoundWorker) or not worker.matches(self.nodes[node_id]):
                raise ValueError('worker binding does not match node')
        pending = list(tasks)
        attempts = {t.task_id: [] for t in tasks}
        reservations = {n: [0, 0] for n in self.nodes}
        for future, node_id, memory in self._held.values():
            if node_id is not None:
                reservations[node_id][0] += 1
                reservations[node_id][1] += memory
        results = {}
        running = {}
        started = {}

        def observe(future, node_id, *, success=False, timeout=False, unknown=False):
            if node_id is None or future not in started:
                return
            elapsed = max(0, monotonic() - started.pop(future))
            previous = self._health[node_id]
            self._health[node_id] = replace(previous,
                success_count=previous.success_count + int(success),
                failure_count=previous.failure_count + int(not success),
                timeout_count=previous.timeout_count + int(timeout),
                unknown_count=previous.unknown_count + int(unknown),
                elapsed_total=previous.elapsed_total + elapsed,
                last_healthy_at=monotonic() if success else previous.last_healthy_at)

        def eligible(task):
            return [n for n in self.nodes.values() if n.node_id in self.authorized_nodes and
                    n.node_id in workers and n.node_id not in attempts[task.task_id] and
                    self.node_states[n.node_id] == 'HEALTHY' and n.qualifies(task) and
                    n.memory_available >= task.memory_required]

        def finish(task, state, output=None, unknown=False):
            withheld = output is not None and not task.cloud_allowed and local_output_authorized is not True
            result = TaskResult(state, None if withheld else output, tuple(attempts[task.task_id]), unknown, withheld)
            results[task.task_id] = result
            self._records[task.task_id] = result

        executor = ThreadPoolExecutor(max_workers=self.budget.max_concurrent_tasks)

        def submit(execute, *args):
            # A submit failure can occur after an executor enqueues its wrapper.
            # Open the execution gate only once ownership of its Future exists.
            gate, accepted = Event(), False
            def invoke():
                gate.wait()
                if not accepted:
                    raise KnownFailure()
                return execute(*args)
            try:
                future = executor.submit(invoke)
                accepted = True
                return future
            finally:
                gate.set()

        deadline = monotonic() + self.budget.timeout_seconds
        try:
            while pending or running:
                for task in pending[:]:
                    if monotonic() >= deadline:
                        break
                    if len(running) + len(self._held) >= self.budget.max_concurrent_tasks:
                        break
                    candidates = eligible(task)
                    active_nodes = sum(count > 0 for count, memory in reservations.values())
                    available = [n for n in candidates if
                                 reservations[n.node_id][0] < n.max_concurrent_tasks and
                                 reservations[n.node_id][1] + task.memory_required <= n.memory_available and
                                 (reservations[n.node_id][0] or active_nodes < self.budget.max_active_nodes)]
                    if available:
                        node = min(available, key=lambda n: (n.current_load + reservations[n.node_id][0],
                                                             n.latency, n.correction_burden, n.node_id))
                        reservations[node.node_id][0] += 1
                        reservations[node.node_id][1] += task.memory_required
                        attempts[task.task_id].append(node.node_id)
                        submitted_at = monotonic()
                        try:
                            future = submit(workers[node.node_id].execute, node, task)
                        except BaseException:
                            reservations[node.node_id][0] -= 1
                            reservations[node.node_id][1] -= task.memory_required
                            attempts[task.task_id].pop()
                            health = self._health[node.node_id]
                            self._health[node.node_id] = replace(health, assignment_failure_count=health.assignment_failure_count + 1)
                            raise
                        started[future] = submitted_at
                        running[future] = (task, node.node_id)
                        pending.remove(task)
                    elif not candidates:
                        pending.remove(task)
                        if task.cloud_allowed and cloud_worker is not None:
                            future = submit(cloud_worker, task)
                            running[future] = (task, None)
                        else:
                            finish(task, 'FAILED' if task.cloud_allowed else 'BLOCKED_BY_PRIVACY')
                if not running:
                    for task in pending:
                        results[task.task_id] = TaskResult('QUEUED', attempted_nodes=tuple(attempts[task.task_id]))
                    break
                completed, _ = wait(running, timeout=max(0, deadline - monotonic()), return_when=FIRST_COMPLETED)
                if not completed:
                    for future, (task, node_id) in running.items():
                        observe(future, node_id, timeout=True, unknown=True)
                        self._held[task.task_id] = (future, node_id, task.memory_required)
                        if node_id is not None:
                            self.node_states[node_id] = 'DEGRADED'
                        finish(task, 'FAILED', unknown=True)
                    for task in pending:
                        results[task.task_id] = TaskResult('QUEUED', attempted_nodes=tuple(attempts[task.task_id]))
                    break
                for future in completed:
                    task, node_id = running[future]
                    if node_id is not None:
                        reservations[node_id][0] -= 1
                        reservations[node_id][1] -= task.memory_required
                    try:
                        value = future.result()
                        if not isinstance(value, WorkerResult):
                            raise UnknownOutcome()
                    except KnownFailure:
                        observe(future, node_id)
                        if node_id is not None:
                            self.node_states[node_id] = 'DEGRADED'
                            pending.append(task)
                        else:
                            finish(task, 'FAILED')
                    except Exception as error:
                        observe(future, node_id, timeout=isinstance(error, TimeoutError), unknown=True)
                        if node_id is not None:
                            self.node_states[node_id] = 'DEGRADED'
                            reservations[node_id][0] += 1
                            reservations[node_id][1] += task.memory_required
                        self._held[task.task_id] = (future, node_id, task.memory_required)
                        finish(task, 'FAILED', unknown=True)
                    else:
                        observe(future, node_id, success=True)
                        finish(task, 'COMPLETED' if node_id is not None else 'FALLBACK_OPENAI', value.output)
                    del running[future]
        except BaseException:
            # Preserve every owned Future before propagating interruption or an
            # assignment failure; a caller must never unknowingly duplicate it.
            for future, (task, node_id) in running.items():
                observe(future, node_id, unknown=True)
                self._held[task.task_id] = (future, node_id, task.memory_required)
                if node_id is not None:
                    self.node_states[node_id] = 'DEGRADED'
                finish(task, 'FAILED', unknown=True)
            raise
        finally:
            # Python cannot kill executing threads. Unknown workers retain their
            # pool reservation; adapters must implement bounded cancellation.
            executor.shutdown(wait=False)
        return {task.task_id: results[task.task_id] for task in tasks}


def migrate_node(old_node, new_node_id):
    """Carry model/config hints only; never consent, probe, runtime or qualification."""
    if old_node.node_id == new_node_id:
        raise ValueError('migration requires a new node identity')
    return Node(new_node_id, provider=old_node.provider, model=old_node.model, config=old_node.config)


@dataclass(frozen=True)
class DistributedCandidate:
    exceeds_single_node: bool = False
    material_benefit: bool = False
    compatible_nodes: bool = False
    suitable_interconnect: bool = False
    framework_supported: bool = False
    privacy_satisfied: bool = False
    explicitly_authorized: bool = False

    @property
    def validated(self):
        return all(value is True for value in vars(self).values())


def plan_topology(nodes, tasks, budget, distributed=None):
    """Recommend only; independent task batches, no graph execution or cluster.

    Cluster gates are caller-supplied evidence assertions, not measured runtime
    validation. No capacity summing, network creation or trust transfer occurs.
    OPENAI_ONLY is a recommendation; TaskPool still enforces cloud policy.
    """
    nodes, tasks = list(nodes), list(islice(tasks, budget.max_tasks + 1))
    if len(tasks) > budget.max_tasks:
        raise ValueError('task graph exceeds planning budget')
    eligible = {task.task_id: [n for n in nodes if n.state == 'HEALTHY' and n.qualifies(task)
                              and n.memory_available >= task.memory_required] for task in tasks}
    usable = {n.node_id for group in eligible.values() for n in group}
    if tasks and all(eligible.values()):
        if any(all(n in group for group in eligible.values()) and
               n.max_concurrent_tasks >= min(len(tasks), budget.max_concurrent_tasks) and
               n.memory_available >= sum(t.memory_required for t in tasks) and n.current_load == 0
               for n in nodes):
            return 'SINGLE_NODE'
        if len(tasks) > 1 and len(usable) > 1 and budget.max_active_nodes > 1 and budget.max_concurrent_tasks > 1:
            return 'MULTI_NODE_TASK_POOL'
        if any(all(n in group for group in eligible.values()) for n in nodes):
            return 'SINGLE_NODE'
        # Disjoint qualifications still form a task pool when budgets require
        # serial execution. Pool sufficiency never justifies a model cluster.
        return 'MULTI_NODE_TASK_POOL'
    if distributed is not None and distributed.validated and len(nodes) >= 2:
        return 'DISTRIBUTED_MODEL_CLUSTER_CANDIDATE'
    return 'HYBRID' if usable else 'OPENAI_ONLY'
