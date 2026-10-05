"""Bounded, caller-supplied execution evidence. No observer or execution authority.

Paths are logical, network targets are origins, and secret targets must be opaque
references supplied by a trusted adapter. Nothing here authenticates an adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, InitVar
from enum import Enum
from itertools import islice
import math
from types import MappingProxyType

import runtime_safety_envelope as rse
import security_authority_chain as sc

MAX_EVENTS = 128
MAX_EFFECTS = 128
MAX_CAUSAL_DEPTH = 32
MAX_FINDINGS = 128


class CriticalEventType(str, Enum):
    FILE_READ = 'FILE_READ'
    FILE_WRITE = 'FILE_WRITE'
    FILE_CREATE = 'FILE_CREATE'
    FILE_DELETE = 'FILE_DELETE'
    FILE_MOVE = 'FILE_MOVE'
    PROCESS_START = 'PROCESS_START'
    PROCESS_EXIT = 'PROCESS_EXIT'
    NETWORK_REQUEST = 'NETWORK_REQUEST'
    SECRET_ACCESS = 'SECRET_ACCESS'
    PACKAGE_INSTALL = 'PACKAGE_INSTALL'
    CONFIG_CHANGE = 'CONFIG_CHANGE'
    SERVICE_START = 'SERVICE_START'
    SERVICE_STOP = 'SERVICE_STOP'
    GIT_STAGE = 'GIT_STAGE'
    GIT_COMMIT = 'GIT_COMMIT'
    GIT_PUSH = 'GIT_PUSH'
    GIT_EFFECT = 'GIT_EFFECT'
    REMOTE_EFFECT = 'REMOTE_EFFECT'
    PR_CREATE = 'PR_CREATE'
    PR_MERGE = 'PR_MERGE'
    RELEASE = 'RELEASE'
    DEPLOY = 'DEPLOY'
    POLICY_DECISION = 'POLICY_DECISION'
    AUTHORIZATION_DECISION = 'AUTHORIZATION_DECISION'
    CAPABILITY_USE = 'CAPABILITY_USE'


class ObservationSource(str, Enum):
    DECLARED = 'DECLARED'
    ADAPTER_OBSERVED = 'ADAPTER_OBSERVED'
    RECONCILIATION_OBSERVED = 'RECONCILIATION_OBSERVED'
    HOST_OBSERVED = 'HOST_OBSERVED'


class EventStatus(str, Enum):
    ATTEMPTED = 'ATTEMPTED'
    OBSERVED = 'OBSERVED'
    COMPLETED = 'COMPLETED'


class TraceCompleteness(str, Enum):
    COMPLETE = 'COMPLETE'
    PARTIAL = 'PARTIAL'
    UNKNOWN = 'UNKNOWN'


class DivergenceType(str, Enum):
    UNDECLARED_READ = 'UNDECLARED_READ'
    UNDECLARED_WRITE = 'UNDECLARED_WRITE'
    UNDECLARED_CREATE = 'UNDECLARED_CREATE'
    UNDECLARED_DELETE = 'UNDECLARED_DELETE'
    UNDECLARED_MOVE = 'UNDECLARED_MOVE'
    UNDECLARED_PROCESS = 'UNDECLARED_PROCESS'
    UNDECLARED_NETWORK = 'UNDECLARED_NETWORK'
    UNDECLARED_SECRET_ACCESS = 'UNDECLARED_SECRET_ACCESS'
    UNDECLARED_GIT_ACTION = 'UNDECLARED_GIT_ACTION'
    UNDECLARED_EXTERNAL_ACTION = 'UNDECLARED_EXTERNAL_ACTION'
    OBSERVED_EFFECT_CONTRADICTS_RSE_DECISION = 'OBSERVED_EFFECT_CONTRADICTS_RSE_DECISION'


class RiskType(str, Enum):
    SENSITIVE_READ_TO_EXTERNAL_NETWORK = 'SENSITIVE_READ_TO_EXTERNAL_NETWORK'
    SECRET_ACCESS_TO_EXTERNAL_NETWORK = 'SECRET_ACCESS_TO_EXTERNAL_NETWORK'
    SENSITIVE_READ_TO_PROCESS_TO_EXTERNAL_NETWORK = 'SENSITIVE_READ_TO_PROCESS_TO_EXTERNAL_NETWORK'
    SECRET_ACCESS_TO_PROCESS_TO_EXTERNAL_NETWORK = 'SECRET_ACCESS_TO_PROCESS_TO_EXTERNAL_NETWORK'
    UNDECLARED_NETWORK_AFTER_SENSITIVE_READ = 'UNDECLARED_NETWORK_AFTER_SENSITIVE_READ'
    UNDECLARED_PROCESS_AFTER_SECRET_ACCESS = 'UNDECLARED_PROCESS_AFTER_SECRET_ACCESS'


def _require(condition):
    if not condition:
        raise ValueError('CET_INVALID')


def _text(value):
    return (type(value) is str and 0 < len(value) <= 1024
            and all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value))


def _time(value):
    return type(value) in (int, float) and 0 <= value <= 2**53 and math.isfinite(value)


def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _bounded(values, limit=MAX_EFFECTS):
    _require(not isinstance(values, (str, bytes, dict)))
    try:
        result = tuple(islice(iter(values), limit + 1))
    except TypeError:
        raise ValueError('CET_INVALID') from None
    _require(len(result) <= limit)
    return result


def _refs(values):
    result = _bounded(values, 16)
    _require(all(_text(v) for v in result))
    return tuple(sorted(set(result)))


def _origin(value):
    _require(_text(value))
    return rse._url(value)[0]


@dataclass(frozen=True, repr=False)
class TraceContext:
    trace_id: str
    installation_id: str
    project_id: str | None
    task_id: str | None
    run_id: str | None
    action_id: str
    parent_action_id: str | None
    provider: str
    model: str | None
    runtime: str

    def __post_init__(self):
        _require(all(_text(getattr(self, n)) for n in
                     ('trace_id', 'installation_id', 'action_id', 'provider', 'runtime')))
        _require(all(getattr(self, n) is None or _text(getattr(self, n)) for n in
                     ('project_id', 'task_id', 'run_id', 'parent_action_id', 'model')))
        _require(self.task_id is None or self.project_id is not None)
        _require(self.run_id is None or self.task_id is not None)
        _require(self.parent_action_id != self.action_id)


ACTION_EVENTS = MappingProxyType({k: CriticalEventType[{
    'READ_FILE': 'FILE_READ', 'WRITE_FILE': 'FILE_WRITE', 'CREATE_FILE': 'FILE_CREATE',
    'DELETE_FILE': 'FILE_DELETE', 'MOVE_FILE': 'FILE_MOVE',
    'EXECUTE_PROCESS': 'PROCESS_START'}.get(k.name, k.name)] for k in rse.ActionClass})
_PATH_EVENTS = frozenset(ACTION_EVENTS[k] for k in rse.PATH_ACTIONS)
_NETWORK_EVENTS = frozenset(ACTION_EVENTS[k] for k in rse.EGRESS_ACTIONS)
_HOST_EVENT_TOKEN = object()
_HOST_EVENT_TYPES = frozenset(CriticalEventType[name] for name in (
    'FILE_READ', 'FILE_WRITE', 'FILE_CREATE', 'FILE_DELETE', 'FILE_MOVE',
    'PROCESS_START', 'PROCESS_EXIT', 'NETWORK_REQUEST', 'GIT_EFFECT', 'REMOTE_EFFECT'))


def _target(kind, target):
    _require(_text(target))
    if kind in _PATH_EVENTS:
        return rse._path(target)
    if kind in _NETWORK_EVENTS:
        return _origin(target)
    return target


@dataclass(frozen=True, repr=False)
class CriticalEvent:
    event_id: str
    event_type: CriticalEventType
    context: TraceContext
    source: ObservationSource
    timestamp: float
    target: str
    data_classification: rse.DataClass
    capability: str | None = None
    status: EventStatus = EventStatus.OBSERVED
    evidence_refs: tuple = ()
    exit_code: int | None = None
    destination: str | None = None
    _host_token: InitVar[object] = None

    def __post_init__(self, _host_token):
        _require(_text(self.event_id) and type(self.context) is TraceContext)
        _require(type(self.event_type) is CriticalEventType and type(self.source) is ObservationSource)
        _require(type(self.data_classification) is rse.DataClass and type(self.status) is EventStatus)
        _require(_time(self.timestamp) and (self.capability is None or _text(self.capability)))
        host = self.source == ObservationSource.HOST_OBSERVED
        _require(not host or (_host_token is _HOST_EVENT_TOKEN and self.event_type in _HOST_EVENT_TYPES))
        _require(host or self.event_type not in (CriticalEventType.GIT_EFFECT, CriticalEventType.REMOTE_EFFECT))
        _require(not host or (self.destination is None and self.capability is None
                             and self.status == EventStatus.OBSERVED and self.exit_code is None))
        _require(host or ((self.event_type == CriticalEventType.FILE_MOVE) == (self.destination is not None)))
        _require(self.exit_code is None or (self.event_type == CriticalEventType.PROCESS_EXIT
                     and type(self.exit_code) is int and -255 <= self.exit_code <= 255))
        if host:
            _require(type(self.target) is str and self.target.startswith('sha256:')
                     and _digest(self.target[7:]))
        else:
            object.__setattr__(self, 'target', _target(self.event_type, self.target))
        if self.destination is not None:
            _require(_text(self.destination))
            object.__setattr__(self, 'destination', rse._path(self.destination))
        object.__setattr__(self, 'evidence_refs', _refs(self.evidence_refs))


def _host_observed_event(**kwargs):
    """Private trusted ingestion path; not a hostile-Python isolation boundary."""
    return CriticalEvent(source=ObservationSource.HOST_OBSERVED,
                         _host_token=_HOST_EVENT_TOKEN, **kwargs)


_CATEGORIES = ('reads', 'writes', 'creates', 'deletes', 'moves', 'processes',
               'network_targets', 'secret_refs', 'git_actions', 'external_actions')
_DIVERGENCES = tuple(DivergenceType)[:10]
_GIT = frozenset((CriticalEventType.GIT_STAGE, CriticalEventType.GIT_COMMIT, CriticalEventType.GIT_PUSH))
_EXTERNAL = frozenset((CriticalEventType.PACKAGE_INSTALL, CriticalEventType.CONFIG_CHANGE,
    CriticalEventType.SERVICE_START, CriticalEventType.SERVICE_STOP, CriticalEventType.PR_CREATE,
    CriticalEventType.PR_MERGE, CriticalEventType.RELEASE, CriticalEventType.DEPLOY))


def _effect_value(category, value):
    if category in ('moves', 'git_actions', 'external_actions'):
        pair = _bounded(value, 2)
        _require(len(pair) == 2 and all(_text(v) for v in pair))
        if category == 'moves':
            return tuple(rse._path(v) for v in pair)
        try:
            kind = CriticalEventType(pair[0])
        except ValueError:
            raise ValueError('CET_INVALID') from None
        _require(kind in (_GIT if category == 'git_actions' else _EXTERNAL))
        return kind.value, _target(kind, pair[1])
    _require(_text(value))
    if category in ('reads', 'writes', 'creates', 'deletes'):
        return rse._path(value)
    return _origin(value) if category == 'network_targets' else value


@dataclass(frozen=True, repr=False)
class DeclaredEffects:
    context: TraceContext
    reads: tuple = ()
    writes: tuple = ()
    creates: tuple = ()
    deletes: tuple = ()
    moves: tuple = ()
    processes: tuple = ()
    network_targets: tuple = ()
    secret_refs: tuple = ()
    git_actions: tuple = ()
    external_actions: tuple = ()

    def __post_init__(self):
        _require(type(self.context) is TraceContext)
        total = 0
        for category in _CATEGORIES:
            raw = _bounded(getattr(self, category))
            total += len(raw)
            _require(total <= MAX_EFFECTS)
            object.__setattr__(self, category, tuple(sorted(set(_effect_value(category, v) for v in raw))))


@dataclass(frozen=True, repr=False)
class ObservedEffects(DeclaredEffects):
    source: ObservationSource = ObservationSource.ADAPTER_OBSERVED

    def __post_init__(self):
        super().__post_init__()
        _require(type(self.source) is ObservationSource and self.source in (
            ObservationSource.ADAPTER_OBSERVED, ObservationSource.RECONCILIATION_OBSERVED))


def effect_count(effects):
    _require(type(effects) in (DeclaredEffects, ObservedEffects))
    return sum(len(getattr(effects, c)) for c in _CATEGORIES)


@dataclass(frozen=True, repr=False)
class TraceDivergence:
    context: TraceContext
    divergence_type: DivergenceType
    target: str | tuple
    declared_digest: str
    observed_digest: str
    severity: str = 'WARNING'

    def __post_init__(self):
        _require(type(self.context) is TraceContext and type(self.divergence_type) is DivergenceType)
        _require(_digest(self.declared_digest) and _digest(self.observed_digest))
        _require(self.severity in ('WARNING', 'HIGH'))
        if self.divergence_type in _DIVERGENCES:
            category = _CATEGORIES[_DIVERGENCES.index(self.divergence_type)]
            object.__setattr__(self, 'target', _effect_value(category, self.target))
        else:
            _require(_text(self.target))


@dataclass(frozen=True, repr=False)
class EffectComparison:
    declared_digest: str
    observed_digest: str
    divergences: tuple


def compare_effects(declared, observed):
    _require(type(declared) is DeclaredEffects and type(observed) is ObservedEffects)
    _require(declared.context == observed.context)
    dd, od = sc.artifact_digest(declared), sc.artifact_digest(observed)
    differences = tuple(TraceDivergence(declared.context, kind, target, dd, od)
        for category, kind in zip(_CATEGORIES, _DIVERGENCES)
        for target in sorted(set(getattr(observed, category)) - set(getattr(declared, category))))
    return EffectComparison(dd, od, differences)


def _event_effect(event):
    if event.source == ObservationSource.HOST_OBSERVED:
        return {}  # Phase 3A does not compare opaque host evidence with concrete effects.
    kind, target = event.event_type, event.target
    basic = {CriticalEventType.FILE_READ: 'reads', CriticalEventType.FILE_WRITE: 'writes',
        CriticalEventType.FILE_CREATE: 'creates', CriticalEventType.FILE_DELETE: 'deletes',
        CriticalEventType.PROCESS_START: 'processes', CriticalEventType.NETWORK_REQUEST: 'network_targets',
        CriticalEventType.SECRET_ACCESS: 'secret_refs'}
    if kind in basic:
        return {basic[kind]: (target,)}
    if kind == CriticalEventType.FILE_MOVE:
        return {'moves': ((target, event.destination),)}
    if kind in _GIT or kind in _EXTERNAL:
        return {'git_actions' if kind in _GIT else 'external_actions': ((kind.value, target),)}
    return {}


def _match_action(action, context):
    _require(rse._valid_action(action) and type(context) is TraceContext)
    _require(all(getattr(action, n) == getattr(context, n) for n in
                 ('action_id', 'task_id', 'run_id', 'provider', 'runtime')))


def declared_from_action(action, context):
    _match_action(action, context)
    event = CriticalEvent('declaration', ACTION_EVENTS[action.action_class], context,
        ObservationSource.DECLARED, 0, action.target, action.data_classification,
        capability=action.capability, destination=action.destination)
    return DeclaredEffects(context, **_event_effect(event))


def _observed(event):
    return event.source in (ObservationSource.ADAPTER_OBSERVED,
                           ObservationSource.RECONCILIATION_OBSERVED) and event.status != EventStatus.ATTEMPTED


@dataclass(frozen=True)
class StructureResult:
    completeness: TraceCompleteness
    root_action_count: int
    orphan_action_count: int


class CriticalTrace:
    """In-memory evidence collector, not a recorder of real host activity."""

    def __init__(self, trace_id, installation_id, *, completeness=TraceCompleteness.UNKNOWN, coverage_refs=()):
        _require(_text(trace_id) and _text(installation_id) and type(completeness) is TraceCompleteness)
        refs = _refs(coverage_refs)
        _require(completeness != TraceCompleteness.COMPLETE or bool(refs))
        self.trace_id, self.installation_id = trace_id, installation_id
        self.completeness, self.coverage_refs = completeness, refs
        self._events = ()

    def events(self):
        return tuple(sorted(self._events, key=lambda e: (e.timestamp, e.event_id)))

    def events_for_action(self, action_id):
        return tuple(e for e in self.events() if e.context.action_id == action_id)

    def children_of(self, action_id):
        return tuple(sorted({e.context.action_id for e in self._events if e.context.parent_action_id == action_id}))

    def _structure(self, events):
        _require(type(self.completeness) is TraceCompleteness)
        _require(self.completeness != TraceCompleteness.COMPLETE or bool(_refs(self.coverage_refs)))
        contexts, times, ids = {}, {}, set()
        for e in events:
            _require(type(e) is CriticalEvent)
            c = e.context
            _require(c.trace_id == self.trace_id and c.installation_id == self.installation_id)
            _require(e.event_id not in ids and (c.action_id not in contexts or contexts[c.action_id] == c))
            ids.add(e.event_id)
            contexts[c.action_id] = c
            times[c.action_id] = min(times.get(c.action_id, e.timestamp), e.timestamp)
        for action, context in contexts.items():
            seen, parent = {action}, context.parent_action_id
            while parent is not None:
                _require(parent not in seen)
                seen.add(parent)
                _require(len(seen) - 1 <= MAX_CAUSAL_DEPTH)
                if parent not in contexts:
                    break
                ancestor = contexts[parent]
                _require(all(getattr(context, n) == getattr(ancestor, n) for n in ('project_id', 'task_id', 'run_id')))
                _require(times[parent] <= times[action])
                parent = ancestor.parent_action_id
        orphans = sum(c.parent_action_id is not None and c.parent_action_id not in contexts for c in contexts.values())
        return StructureResult(TraceCompleteness.PARTIAL if orphans else self.completeness,
            sum(c.parent_action_id is None for c in contexts.values()), orphans)

    def append(self, event):
        _require(len(self._events) < MAX_EVENTS)
        candidate = self._events + (event,)
        self._structure(candidate)
        self._events = candidate

    def verify_structure(self):
        _require(len(self._events) <= MAX_EVENTS)
        return self._structure(self._events)


@dataclass(frozen=True, repr=False)
class TraceRiskFinding:
    context: TraceContext
    finding_type: RiskType
    event_ids: tuple
    action_ids: tuple
    target: str
    data_classification: rse.DataClass
    reason: str
    evidence_digest: str
    severity: str = 'HIGH'

    def __post_init__(self):
        _require(type(self.context) is TraceContext and type(self.finding_type) is RiskType)
        event_ids, action_ids = _bounded(self.event_ids, 3), _bounded(self.action_ids, 3)
        _require(2 <= len(event_ids) <= 3 and len(action_ids) == len(event_ids))
        _require(all(_text(v) for v in event_ids + action_ids))
        _require(len(set(event_ids)) == len(event_ids) and len(set(action_ids)) == len(action_ids))
        _require(action_ids[-1] == self.context.action_id)
        _require(type(self.data_classification) is rse.DataClass and self.severity == 'HIGH')
        _require(_text(self.target) and _text(self.reason) and _digest(self.evidence_digest))
        object.__setattr__(self, 'event_ids', event_ids)
        object.__setattr__(self, 'action_ids', action_ids)


def _declarations(trace, declarations):
    result = {}
    contexts = {e.context.action_id: e.context for e in trace.events()}
    for d in _bounded(declarations):
        _require(type(d) is DeclaredEffects and d.context.action_id not in result)
        _require(contexts.get(d.context.action_id) == d.context)
        result[d.context.action_id] = d
    return result


def detect_trace_risks(trace, declarations=(), *, internal_network_origins, approved_network_origins):
    _require(type(trace) is CriticalTrace)
    trace.verify_structure()
    declared = _declarations(trace, declarations)
    internal = tuple(sorted({_origin(v) for v in _bounded(internal_network_origins)}))
    approved = tuple(sorted({_origin(v) for v in _bounded(approved_network_origins)}))
    trusted = set(internal) | set(approved)
    legacy_events = tuple(e for e in trace.events() if e.source != ObservationSource.HOST_OBSERVED)
    events = tuple(e for e in legacy_events if _observed(e))
    parents = {e.context.action_id: e.context.parent_action_id for e in legacy_events}
    ancestors = {}
    for action in parents:
        chain, parent = set(), parents[action]
        while parent is not None:
            chain.add(parent)
            parent = parents.get(parent)
        ancestors[action] = chain

    def precedes(a, b):
        return a.context.action_id in ancestors[b.context.action_id] and a.timestamp <= b.timestamp

    findings = []

    def add(kind, evidence):
        first, last = evidence[0], evidence[-1]
        path = [last.context.action_id]
        while path[-1] != first.context.action_id:
            path.append(parents[path[-1]])
        # Bind every supplied event on the connecting path, not just endpoints.
        # Retain input artifacts outside the chain to reproduce this commitment.
        basis = {
            'finding_type': kind,
            'causal_path': tuple(reversed(path)),
            'path_event_digests': tuple(sc.artifact_digest(e) for e in legacy_events
                                       if e.context.action_id in path),
            'declaration_digest': sc.artifact_digest(declared.get(last.context.action_id)),
            'internal_origins': internal,
            'approved_origins': approved,
        }
        findings.append(TraceRiskFinding(last.context, RiskType[kind], tuple(e.event_id for e in evidence),
            tuple(e.context.action_id for e in evidence), last.target, first.data_classification,
            'Candidate causal pattern in supplied observations; not proof of transfer or malicious intent.',
            sc.artifact_digest(basis)))
        _require(len(findings) <= MAX_FINDINGS)

    def undeclared(event, field):
        d = declared.get(event.context.action_id)
        return d is not None and event.target not in getattr(d, field)

    for first in events:
        secret = first.event_type == CriticalEventType.SECRET_ACCESS
        sensitive = first.event_type == CriticalEventType.FILE_READ and first.data_classification in (
            rse.DataClass.SENSITIVE, rse.DataClass.LOCAL_ONLY, rse.DataClass.SECRET)
        if not secret and not sensitive:
            continue
        prefix = 'SECRET_ACCESS' if secret else 'SENSITIVE_READ'
        for last in events:
            if not precedes(first, last):
                continue
            if secret and last.event_type == CriticalEventType.PROCESS_START and undeclared(last, 'processes'):
                add('UNDECLARED_PROCESS_AFTER_SECRET_ACCESS', (first, last))
            if last.event_type != CriticalEventType.NETWORK_REQUEST or last.target in trusted:
                continue
            add(prefix + '_TO_EXTERNAL_NETWORK', (first, last))
            if sensitive and undeclared(last, 'network_targets'):
                add('UNDECLARED_NETWORK_AFTER_SENSITIVE_READ', (first, last))
            for middle in events:
                if middle.event_type == CriticalEventType.PROCESS_START and precedes(first, middle) and precedes(middle, last):
                    add(prefix + '_TO_PROCESS_TO_EXTERNAL_NETWORK', (first, middle, last))
    return tuple(sorted(findings, key=lambda f: (f.finding_type.value, f.event_ids)))


@dataclass(frozen=True, repr=False)
class RSECorrelation:
    """Preserves the authoritative receipt states; no new execution state machine."""
    divergences: tuple
    receipt_digest: str
    attempt_linked: bool
    policy_disposition: str
    execution_state: str
    reconciliation_state: str
    final_disposition: str


def correlate_rse(action, receipt, event, *, attempt_linked=False):
    """Caller attests same-attempt linkage; action identity alone is insufficient."""
    _require(type(event) is CriticalEvent and type(receipt) is rse.SecurityReceipt)
    _require(type(attempt_linked) is bool)
    _match_action(action, event.context)
    expected = rse._receipt(action, rse.PolicyDecision(receipt.policy_disposition, receipt.policy_reason))
    names = ('receipt_version', 'action_id', 'task_id', 'run_id', 'provider', 'runtime',
             'action_class', 'target_locator', 'authorization_ref', 'capability')
    _require(all(getattr(expected, n) == getattr(receipt, n) for n in names))
    _require(receipt.policy_disposition in ('ALLOW', 'DENY', 'INVALID',
                                          'REQUIRE_AUTHORIZATION', 'REQUIRE_RECONCILIATION'))
    def result(divergences=()):
        return RSECorrelation(divergences, sc.artifact_digest(receipt), attempt_linked,
            receipt.policy_disposition, receipt.execution_state, receipt.reconciliation_state,
            receipt.final_disposition)

    if not _observed(event) or not _event_effect(event):
        return result()
    declared = declared_from_action(action, event.context)
    observed = ObservedEffects(event.context, source=event.source, **_event_effect(event))
    comparison = compare_effects(declared, observed)
    # A repeat denial, reconciliation or unknown result describes lifecycle, not
    # proof that a prior effect violated policy. Without attempt linkage, only
    # the structural action/effect mismatch can be established.
    policy_contradiction = (attempt_linked and receipt.execution_state == 'NOT_ATTEMPTED'
        and receipt.reconciliation_state == 'NOT_REQUIRED'
        and receipt.policy_disposition in ('DENY', 'INVALID', 'REQUIRE_AUTHORIZATION')
        and receipt.policy_reason not in ('ALREADY_COMPLETED', 'REEVALUATION_REQUIRED',
                                         'RECONCILIATION_NOT_PENDING', 'ACTION_ID_CONFLICT'))
    if policy_contradiction or comparison.divergences:
        return result((TraceDivergence(event.context, DivergenceType.OBSERVED_EFFECT_CONTRADICTS_RSE_DECISION,
            event.target, sc.artifact_digest((receipt, attempt_linked)), sc.artifact_digest(event), 'HIGH'),))
    return result()


@dataclass(frozen=True, repr=False)
class TraceAnalysis:
    trace_id: str
    event_count: int
    observed_event_count: int
    declared_effect_count: int
    declared_digest: str
    observed_digest: str
    divergences: tuple
    risk_findings: tuple
    completeness: TraceCompleteness
    root_action_count: int
    orphan_action_count: int
    divergence_count: int
    risk_finding_count: int
    undeclared_baseline_action_count: int
    no_findings_statement: str


def analyze_trace(trace, declarations=(), *, internal_network_origins, approved_network_origins):
    _require(type(trace) is CriticalTrace)
    structure = trace.verify_structure()
    declared = _declarations(trace, declarations)
    events = trace.events()
    observed = tuple(e for e in events if _observed(e))
    divergences = []
    for action, d in sorted(declared.items()):
        # Preserve source attribution; deduplicate identical divergences across observations.
        seen = set()
        for event in observed:
            if event.context.action_id != action:
                continue
            o = ObservedEffects(event.context, source=event.source, **_event_effect(event))
            for divergence in compare_effects(d, o).divergences:
                key = (divergence.divergence_type, divergence.target)
                if key not in seen:
                    seen.add(key)
                    divergences.append(divergence)
        _require(len(divergences) <= MAX_FINDINGS)
    risks = detect_trace_risks(trace, tuple(declared.values()), internal_network_origins=internal_network_origins,
                              approved_network_origins=approved_network_origins)
    missing = len({e.context.action_id for e in observed if _event_effect(e)} - declared.keys())
    return TraceAnalysis(trace.trace_id, len(events), len(observed), sum(effect_count(d) for d in declared.values()),
        sc.artifact_digest(tuple(sc.artifact_digest(d) for _, d in sorted(declared.items()))),
        sc.artifact_digest(tuple(sc.artifact_digest(e) for e in observed)), tuple(divergences), risks,
        structure.completeness, structure.root_action_count, structure.orphan_action_count,
        len(divergences), len(risks), missing,
        'SUPPLIED_OBSERVATIONS_ONLY: no findings is not proof of safety; missing declarations are not empty baselines.')


def _record(chain, actor, artifact, kind, identity, now):
    context = artifact.context
    _require(type(context) is TraceContext and _time(now) and chain.verify().valid)
    decision = sc.authorize_management_change(actor, sc.ManagementAction.RSE_RECEIPT_RECORD,
        installation_id=context.installation_id, project_id=context.project_id, task_id=context.task_id, now=now)
    _require(decision.disposition == 'ALLOW')
    return chain.append(sc.SecurityEventDraft(identity, kind, now, context.installation_id,
        actor.role, actor.authority_id, 'CET_SUPPLIED_EVIDENCE', project_id=context.project_id,
        task_id=context.task_id, run_id=context.run_id, action_id=context.action_id,
        artifact_digest=sc.artifact_digest(artifact), authority_digest=sc.artifact_digest(actor)))


def record_critical_event(chain, actor, event, *, now):
    _require(type(event) is CriticalEvent and _time(now) and now >= event.timestamp)
    identity = 'cet:event:' + sc.artifact_digest((event.context.trace_id, event.event_id))
    return _record(chain, actor, event, sc.EventType.CRITICAL_TRACE_EVENT, identity, now)


def record_trace_divergence(chain, actor, divergence, *, now):
    _require(type(divergence) is TraceDivergence)
    return _record(chain, actor, divergence, sc.EventType.TRACE_DIVERGENCE,
                   'cet:divergence:' + sc.artifact_digest(divergence), now)


def record_trace_risk(chain, actor, finding, *, now):
    _require(type(finding) is TraceRiskFinding)
    return _record(chain, actor, finding, sc.EventType.TRACE_RISK_FINDING,
                   'cet:risk:' + sc.artifact_digest(finding), now)
