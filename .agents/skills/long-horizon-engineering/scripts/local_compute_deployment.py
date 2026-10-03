"""Packaged opt-in Beta API; no provider installation recipe bundled.

Readers and effect adapters are trusted, explicitly supplied integration boundaries.
No discovery, network, installs, configuration writes or inference occurs on import.
Budgets reserve declared upper bounds before effects; adapters must enforce them.
Concrete subprocess execution requires a journal with load(node_id) and synchronous
writes. DurableJournal supplies atomic POSIX persistence and exclusive controller
ownership. Generic journal integrations must provide equivalent guarantees. Pending
fingerprints rebind only to current approved_effects for explicit reconcile(), never
minting authority. PoolBudgetLedger shares durable conservative reservations across
node runners. No provider-specific deployment recipes ship in this module.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
from pathlib import Path
import signal
import subprocess
import threading
import tempfile
import time


PROBE_FIELDS = frozenset({
    'os', 'architecture', 'cpu_soc', 'memory_total_gb', 'memory_available_gb',
    'unified_memory', 'accelerator', 'gpu_memory_gb', 'free_storage_gb',
    'codex_cli', 'provider', 'provider_version', 'existing_models',
    'static_responses_compatible',
})


def collect_probe(node_id, consent, reader):
    """Read allowlisted metadata only after explicit node-set inspection consent.

    The supplied reader must itself be read-only and return non-sensitive metadata.
    This field filter is not a sandbox or a content/secret sanitizer.
    """
    if not node_id or node_id not in consent:
        raise PermissionError('node inspection not authorized')
    metadata = reader(node_id)
    return {'node_id': node_id, **{k: v for k, v in metadata.items() if k in PROBE_FIELDS}}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def minimum_value_gate(probe, criteria=None):
    """Require project-specific resource, task-value and operational evidence."""
    criteria = criteria or {}
    minimum_memory_gb = criteria.get('minimum_memory_gb')
    minimum_disk_gb = criteria.get('minimum_disk_gb')
    operational = [criteria.get(key) for key in
                   ('task_value', 'provider_compatible', 'correction_burden_acceptable')]
    if any(value is False for value in operational):
        return 'NOT_MET'
    values = [(probe.get('memory_available_gb'), minimum_memory_gb),
              (probe.get('free_storage_gb'), minimum_disk_gb)]
    if any(_number(value) and _number(threshold) and value < threshold for value, threshold in values):
        return 'NOT_MET'
    if (any(not _number(value) or not _number(threshold) for value, threshold in values)
            or any(value is not True for value in operational)):
        return 'INSUFFICIENT_EVIDENCE'
    return 'POTENTIALLY_VIABLE'


def select_candidate(probe, candidates, approved_ids):
    """Select first safe fit from at most three capability-ranked candidates.

    Callers must bind unique candidate IDs to immutable provider/model/config
    recipes. Selection is a fit recommendation, not deployment authorization.
    """
    if not isinstance(candidates, (tuple, list)) or len(candidates) > 3:
        raise ValueError('supply at most three ranked candidates')
    ids = [c.get('id') for c in candidates]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('candidate IDs must be unique and explicit')
    memory, disk = probe.get('memory_available_gb'), probe.get('free_storage_gb')
    if not _number(memory) or not _number(disk):
        return None
    fitting = [c for c in candidates if c.get('id') in approved_ids
               and _number(c.get('memory_gb')) and _number(c.get('disk_gb'))
               and c['memory_gb'] <= memory and c['disk_gb'] <= disk]
    return dict(fitting[0]) if fitting else None


@dataclass(frozen=True)
class Effect:
    """peak_disk_gb is the TOTAL node footprint at this stage, not added bytes.

    Estimates include existing models, partial downloads, unpacking and temporary
    files. The adapter must enforce the approved bound during the operation.
    """
    node_id: str
    action: str
    target: str
    download_gb: float = 0
    peak_disk_gb: float = 0
    recipe_digest: str = ''

    def __post_init__(self):
        if (not self.node_id or not self.target or self.action not in
                {'install', 'download', 'start', 'configure', 'smoke', 'tune', 'restart'}
                or not all(_number(v) for v in (self.download_gb, self.peak_disk_gb))):
            raise ValueError('invalid effect')

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Budget:
    max_download_gb: float
    max_peak_disk_gb: float
    max_iterations: int
    max_restarts: int
    max_seconds: float

    def __post_init__(self):
        if not all(_number(v) for v in self.__dict__.values()):
            raise ValueError('invalid budget')
        if any(type(v) is not int for v in (self.max_iterations, self.max_restarts)):
            raise ValueError('counts must be integers')


@dataclass(frozen=True)
class Approval:
    node_id: str
    effect_fingerprints: frozenset
    budget: Budget


class UnsupportedAdapter:
    def __call__(self, effect, timeout):
        return 'UNSUPPORTED'


def recipe_digest(argv, cwd):
    """Bind the exact literal command and working directory into approval."""
    return hashlib.sha256(json.dumps([list(argv), str(cwd)], separators=(',', ':')).encode()).hexdigest()


class SubprocessAdapter:
    """Exact opt-in local command recipes, not a provider-specific integration.

    Recipes map effect fingerprints to (absolute argv tuple, absolute cwd), with
    the recipe_digest bound inside Effect and an explicit trusted local_node_id.
    The caller approves these recipes separately, including executable trust,
    arguments, environment-independent behavior, resource estimates and effects.
    Commands must remain foreground and not daemonize. This is not a sandbox;
    arbitrary programs can exceed declared disk/network budgets or escape a
    process group. No recipes for real install/download/start ship in this module.
    """
    def __init__(self, local_node_id, approved_recipes):
        if not isinstance(local_node_id, str) or not local_node_id:
            raise ValueError('explicit local node identity required')
        self.local_node_id = local_node_id
        self._recipes = {}
        for fingerprint, (argv, cwd) in approved_recipes.items():
            argv = tuple(argv)
            if (not argv or not Path(argv[0]).is_absolute()
                    or not Path(cwd).is_absolute() or not Path(cwd).is_dir()
                    or not all(isinstance(arg, str) and '\x00' not in arg for arg in argv)):
                raise ValueError('recipe requires absolute executable/cwd and literal argv')
            self._recipes[fingerprint] = (argv, str(cwd))

    def __call__(self, effect, timeout):
        if effect.node_id != self.local_node_id:
            return 'NOT_APPLIED'
        recipe = self._recipes.get(effect.fingerprint())
        if recipe is None or os.name != 'posix':
            return 'UNSUPPORTED'
        argv, cwd = recipe
        if effect.recipe_digest != recipe_digest(argv, cwd):
            return 'NOT_APPLIED'
        try:
            process = subprocess.Popen(argv, cwd=cwd, shell=False, env={},
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return 'NOT_APPLIED'
        try:
            code = process.wait(timeout=timeout)
            # A failing command may already have changed the machine.
            return 'SUCCEEDED' if code == 0 else 'UNKNOWN'
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            return 'UNKNOWN'


class DeploymentRunner:
    """Serial per-node bounded controller with conservative resource reservation.

    Adapters receive remaining wall-clock seconds and must honor cancellation.
    Python callables cannot be forcibly sandboxed or stopped by this controller.
    Smoke success never grants task qualification. No implicit rollback/retry.
    Journal load returns state, download_gb, peak_disk_gb, iterations, restarts,
    elapsed_seconds; writes must atomically merge fields and persist before return.
    A new ledger/approval cannot reset an existing node's outstanding operations.
    """
    def __init__(self, approval, adapter=None, clock=time.monotonic, journal=None,
                 approved_effects=(), pool_budget=None):
        self.approval = approval
        self.adapter = adapter or UnsupportedAdapter()
        self.clock = clock
        self.started = clock()
        self.download_gb = 0
        self.peak_disk_gb = 0
        self.iterations = 0
        self.restarts = 0
        self.pending = None
        self.journal = journal
        self._lock = threading.RLock()
        self.recovery_required = False
        self.elapsed_before = 0
        self.pool_budget = pool_budget
        if journal is not None:
            try:
                if isinstance(journal, DurableJournal):
                    journal.claim_owner()
                saved = journal.load(approval.node_id)
                keys = ('download_gb', 'peak_disk_gb', 'iterations', 'restarts', 'elapsed_seconds')
                if not all(_number(saved.get(key)) for key in keys):
                    raise ValueError('invalid journal budget snapshot')
                self.download_gb = saved['download_gb']
                self.peak_disk_gb = saved['peak_disk_gb']
                self.iterations = saved['iterations']
                self.restarts = saved['restarts']
                self.elapsed_before = saved['elapsed_seconds']
                self.recovery_required = saved.get('state') not in {'CLEAN', 'SUCCEEDED', 'NOT_APPLIED', 'UNSUPPORTED', 'APPLIED'}
                if self.recovery_required:
                    for effect in approved_effects:
                        if (effect.node_id == approval.node_id
                                and effect.fingerprint() in approval.effect_fingerprints
                                and effect.fingerprint() == saved.get('effect')):
                            self.pending = effect
                            break
            except Exception:
                self.recovery_required = True

    def _result(self, state):
        return {'state': state, 'task_qualified': False}

    def run(self, effect):
        with self._lock:
            return self._run(effect)

    def _run(self, effect):
        if self.pending is not None or self.recovery_required:
            return self._result('RECONCILIATION_REQUIRED')
        if effect.node_id != self.approval.node_id or effect.fingerprint() not in self.approval.effect_fingerprints:
            return self._result('NOT_AUTHORIZED')
        if isinstance(self.adapter, SubprocessAdapter) and self.journal is None:
            return self._result('JOURNAL_REQUIRED')
        budget = self.approval.budget
        remaining = budget.max_seconds - self.elapsed_before - (self.clock() - self.started)
        if (remaining <= 0 or self.iterations >= budget.max_iterations
                or self.download_gb + effect.download_gb > budget.max_download_gb
                or max(self.peak_disk_gb, effect.peak_disk_gb) > budget.max_peak_disk_gb
                or self.restarts + (effect.action == 'restart') > budget.max_restarts):
            return self._result('BUDGET_EXCEEDED')
        if self.pool_budget is not None:
            try:
                if not self.pool_budget.reserve(effect):
                    return self._result('BUDGET_EXCEEDED')
            except Exception:
                self.recovery_required = True
                return self._result('RECONCILIATION_REQUIRED')
        self.iterations += 1
        self.restarts += effect.action == 'restart'
        self.download_gb += effect.download_gb
        self.peak_disk_gb = max(self.peak_disk_gb, effect.peak_disk_gb)
        self.pending = effect
        if self.journal is not None:
            try:
                self.journal({'state': 'PENDING', 'effect': effect.fingerprint(),
                              'download_gb': self.download_gb, 'peak_disk_gb': self.peak_disk_gb,
                              'iterations': self.iterations, 'restarts': self.restarts,
                              'elapsed_seconds': self.approval.budget.max_seconds})
            except Exception:
                return self._result('RECONCILIATION_REQUIRED')
        try:
            outcome = self.adapter(effect, remaining)
        except Exception:
            outcome = 'UNKNOWN'
        if outcome not in {'SUCCEEDED', 'NOT_APPLIED', 'UNSUPPORTED'}:
            return self._result('UNKNOWN_OUTCOME')
        if self.journal is not None:
            try:
                self.journal({'state': outcome, 'effect': effect.fingerprint(),
                              'elapsed_seconds': self.elapsed_before + self.clock() - self.started})
            except Exception:
                return self._result('RECONCILIATION_REQUIRED')
        self.pending = None
        return self._result(outcome)

    def reconcile(self, reader):
        """Use trusted read-only reconciliation; never repeat an unknown effect."""
        with self._lock:
            return self._reconcile(reader)

    def _reconcile(self, reader):
        if self.pending is None:
            return self._result('RECONCILIATION_REQUIRED' if self.recovery_required else 'NOT_REQUIRED')
        try:
            outcome = reader(self.pending)
        except Exception:
            outcome = 'UNKNOWN'
        if outcome not in {'APPLIED', 'NOT_APPLIED'}:
            return self._result('RECONCILIATION_REQUIRED')
        if self.journal is not None:
            try:
                self.journal({'state': outcome, 'effect': self.pending.fingerprint()})
            except Exception:
                return self._result('RECONCILIATION_REQUIRED')
        self.pending = None
        self.recovery_required = False
        return self._result('RECONCILED')

    def tune(self, effects):
        """Try only explicitly approved finite configurations within shared budget."""
        results = []
        for effect in effects:
            if effect.action != 'tune':
                results.append(self._result('NOT_AUTHORIZED'))
                break
            result = self.run(effect)
            results.append(result)
            if result['state'] != 'SUCCEEDED':
                break
        return results


    def execute_plan(self, effects):
        """Execute exact approved stages; no provider recipe or implicit retry."""
        if not isinstance(effects, (tuple, list)) or len(effects) > self.approval.budget.max_iterations:
            return [self._result('BUDGET_EXCEEDED')]
        if any(e.node_id != self.approval.node_id or e.fingerprint() not in self.approval.effect_fingerprints for e in effects):
            return [self._result('NOT_AUTHORIZED')]
        results = []
        for effect in effects:
            result = self.run(effect)
            results.append(result)
            if result['state'] != 'SUCCEEDED':
                break
        return results


class DurableJournal:
    """POSIX exclusive-owner atomic JSON journal in an explicitly approved path.

    No commands, model names, payloads, credentials or argv are persisted. Node
    identity is hashed; effect fingerprints refer back to current approved plans.
    The parent directory must be trusted/private and on a local filesystem with
    working flock, atomic rename and fsync. A journal is not approval evidence.
    """
    def __init__(self, path, node_id):
        if os.name != 'posix':
            raise RuntimeError('durable journal requires POSIX locking')
        import fcntl
        self.path = Path(path).absolute()
        self.node_key = hashlib.sha256(node_id.encode()).hexdigest()
        self._mutex = threading.RLock()
        self._closed = False
        self._claimed = False
        lock_path = self.path.with_name(self.path.name + '.lock')
        self._fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            raise RuntimeError('journal already owned') from None
        try:
            if self.path.is_symlink():
                raise ValueError('journal symlink rejected')
            if self.path.exists():
                if self.path.stat().st_size > 1024 * 1024:
                    raise ValueError('journal too large')
                self._snapshot = json.loads(self.path.read_text())
                if self._snapshot.get('node_key') != self.node_key:
                    raise ValueError('journal node mismatch')
            else:
                self._snapshot = {'node_key': self.node_key, 'state': 'CLEAN',
                                  'download_gb': 0, 'peak_disk_gb': 0,
                                  'iterations': 0, 'restarts': 0, 'elapsed_seconds': 0}
        except Exception:
            self.close()
            raise

    def load(self, node_id):
        with self._mutex:
            if self._closed or hashlib.sha256(node_id.encode()).hexdigest() != self.node_key:
                raise ValueError('journal unavailable or node mismatch')
            return json.loads(json.dumps(self._snapshot))

    def claim_owner(self):
        """Prevent two controllers from holding stale snapshots in one process."""
        with self._mutex:
            if self._closed or self._claimed:
                raise RuntimeError('journal controller already owned')
            self._claimed = True

    def __call__(self, event):
        with self._mutex:
            if self._closed:
                raise RuntimeError('journal closed')
            allowed = {'state', 'effect', 'download_gb', 'peak_disk_gb', 'iterations',
                       'restarts', 'elapsed_seconds', 'pool_download_gb', 'pool_node_disk'}
            if set(event) - allowed:
                raise ValueError('journal event field not permitted')
            if 'state' in event and event['state'] not in {'CLEAN', 'PENDING', 'SUCCEEDED', 'NOT_APPLIED', 'UNSUPPORTED', 'APPLIED'}:
                raise ValueError('invalid journal state')
            if 'effect' in event and (not isinstance(event['effect'], str) or not re.fullmatch('[0-9a-f]{64}', event['effect'])):
                raise ValueError('invalid effect fingerprint')
            for key in allowed - {'state', 'effect', 'pool_node_disk'}:
                if key in event and not _number(event[key]):
                    raise ValueError('invalid resource counter')
            if 'pool_node_disk' in event:
                disk = event['pool_node_disk']
                if not isinstance(disk, dict) or not all(isinstance(k, str) and re.fullmatch('[0-9a-f]{64}', k) and _number(v) for k, v in disk.items()):
                    raise ValueError('invalid node disk snapshot')
            snapshot = self._snapshot | event
            encoded = json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()
            if len(encoded) > 1024 * 1024:
                raise ValueError('journal too large')
            fd, temporary = tempfile.mkstemp(prefix='.deployment-', dir=self.path.parent)
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                self._snapshot = snapshot
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def close(self):
        with self._mutex:
            if not self._closed:
                os.close(self._fd)
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PoolBudgetLedger:
    """Shared conservative reservations, durably retained even on unknown effects.

    One ledger instance shared across node runners; its DurableJournal owns the
    pool exclusively across processes. Disk means sum of per-node peak footprints,
    downloads are cumulative and reservations are never refunded automatically.
    """
    def __init__(self, journal, max_download_gb, max_disk_gb, pool_id='pool'):
        if not _number(max_download_gb) or not _number(max_disk_gb):
            raise ValueError('invalid pool budget')
        self.journal = journal
        self.max_download_gb = max_download_gb
        self.max_disk_gb = max_disk_gb
        self._lock = threading.RLock()
        if isinstance(journal, DurableJournal):
            journal.claim_owner()
        snapshot = journal.load(pool_id)
        self.download_gb = snapshot.get('pool_download_gb', 0)
        self.node_disk = snapshot.get('pool_node_disk', {})
        if not _number(self.download_gb) or not isinstance(self.node_disk, dict) or not all(_number(v) for v in self.node_disk.values()):
            raise ValueError('invalid pool snapshot')
        self.blocked = False

    def reserve(self, effect):
        with self._lock:
            if self.blocked:
                raise RuntimeError('pool ledger reconciliation required')
            node = hashlib.sha256(effect.node_id.encode()).hexdigest()
            proposed = self.node_disk | {node: max(self.node_disk.get(node, 0), effect.peak_disk_gb)}
            download = self.download_gb + effect.download_gb
            if download > self.max_download_gb or sum(proposed.values()) > self.max_disk_gb:
                return False
            try:
                self.journal({'pool_download_gb': download, 'pool_node_disk': proposed})
            except Exception:
                self.blocked = True
                raise
            self.download_gb = download
            self.node_disk = proposed
            return True
