"""Experimental, in-memory policy kernel. No real runtime bindings.

Trusted host code supplies policies, authorizations, broker, journal and reconciler.
Model proposals must never populate those trusted arguments. Python object types do
not authenticate a human or sandbox hostile Python code. No effects occur on import.
All paths are logical POSIX paths; no filesystem or DNS inspection is performed.
"""
from dataclasses import dataclass, fields
from contextlib import ExitStack
from enum import Enum
import hashlib
import ipaddress
import json
import math
import posixpath
import re
from threading import RLock
from types import MappingProxyType
from urllib.parse import urlsplit, urlunsplit


class ActionClass(str, Enum):
    READ_FILE = 'READ_FILE'
    WRITE_FILE = 'WRITE_FILE'
    CREATE_FILE = 'CREATE_FILE'
    DELETE_FILE = 'DELETE_FILE'
    MOVE_FILE = 'MOVE_FILE'
    EXECUTE_PROCESS = 'EXECUTE_PROCESS'
    NETWORK_REQUEST = 'NETWORK_REQUEST'
    SECRET_ACCESS = 'SECRET_ACCESS'
    PACKAGE_INSTALL = 'PACKAGE_INSTALL'
    CONFIG_CHANGE = 'CONFIG_CHANGE'
    SERVICE_START = 'SERVICE_START'
    SERVICE_STOP = 'SERVICE_STOP'
    GIT_STAGE = 'GIT_STAGE'
    GIT_COMMIT = 'GIT_COMMIT'
    GIT_PUSH = 'GIT_PUSH'
    PR_CREATE = 'PR_CREATE'
    PR_MERGE = 'PR_MERGE'
    RELEASE = 'RELEASE'
    DEPLOY = 'DEPLOY'


class DataClass(str, Enum):
    PUBLIC = 'PUBLIC'
    NON_SENSITIVE = 'NON_SENSITIVE'
    SENSITIVE = 'SENSITIVE'
    LOCAL_ONLY = 'LOCAL_ONLY'
    SECRET = 'SECRET'
    UNKNOWN = 'UNKNOWN'


class PolicyLevel(str, Enum):
    CORE = 'CORE'
    INSTALLATION = 'INSTALLATION'
    ORGANIZATION = 'ORGANIZATION'
    PROJECT = 'PROJECT'
    TASK = 'TASK'
    RUN = 'RUN'
    ACTION = 'ACTION'


class NetworkMode(str, Enum):
    DENY_ALL = 'DENY_ALL'
    ALLOWLIST = 'ALLOWLIST'


class ExecutionState(str, Enum):
    KNOWN_SUCCESS = 'KNOWN_SUCCESS'
    KNOWN_FAILURE = 'KNOWN_FAILURE'
    UNKNOWN_OUTCOME = 'UNKNOWN_OUTCOME'


class ReconciliationOutcome(str, Enum):
    EFFECT_APPLIED = 'EFFECT_APPLIED'
    EFFECT_NOT_APPLIED = 'EFFECT_NOT_APPLIED'
    STILL_UNKNOWN = 'STILL_UNKNOWN'


class JournalState(str, Enum):
    PROPOSED = 'PROPOSED'
    BLOCKED = 'BLOCKED'
    AUTHORIZED = 'AUTHORIZED'
    ATTEMPTED = 'ATTEMPTED'
    KNOWN_SUCCESS = 'KNOWN_SUCCESS'
    KNOWN_FAILURE = 'KNOWN_FAILURE'
    UNKNOWN_OUTCOME = 'UNKNOWN_OUTCOME'
    RECONCILIATION_REQUIRED = 'RECONCILIATION_REQUIRED'
    RECONCILED_SUCCESS = 'RECONCILED_SUCCESS'
    RECONCILED_NOT_APPLIED = 'RECONCILED_NOT_APPLIED'


CAPABILITIES = MappingProxyType({
    ActionClass.READ_FILE: 'filesystem.read',
    ActionClass.WRITE_FILE: 'filesystem.write',
    ActionClass.CREATE_FILE: 'filesystem.write',
    ActionClass.DELETE_FILE: 'filesystem.write',
    ActionClass.MOVE_FILE: 'filesystem.write',
    ActionClass.EXECUTE_PROCESS: 'process.execute',
    ActionClass.NETWORK_REQUEST: 'network.request',
    ActionClass.SECRET_ACCESS: 'secret.read',
    ActionClass.PACKAGE_INSTALL: 'package.install',
    ActionClass.CONFIG_CHANGE: 'config.write',
    ActionClass.SERVICE_START: 'service.control',
    ActionClass.SERVICE_STOP: 'service.control',
    ActionClass.GIT_STAGE: 'git.stage',
    ActionClass.GIT_COMMIT: 'git.commit',
    ActionClass.GIT_PUSH: 'git.push',
    ActionClass.PR_CREATE: 'github.pr.create',
    ActionClass.PR_MERGE: 'github.pr.merge',
    ActionClass.RELEASE: 'release.publish',
    ActionClass.DEPLOY: 'deploy.execute',
})
EGRESS_ACTIONS = frozenset({ActionClass.NETWORK_REQUEST, ActionClass.GIT_PUSH,
                          ActionClass.PR_CREATE, ActionClass.PR_MERGE,
                          ActionClass.RELEASE, ActionClass.DEPLOY, ActionClass.PACKAGE_INSTALL})
PATH_ACTIONS = frozenset({ActionClass.READ_FILE, ActionClass.WRITE_FILE,
                        ActionClass.CREATE_FILE, ActionClass.DELETE_FILE,
                        ActionClass.MOVE_FILE, ActionClass.CONFIG_CHANGE,
                        ActionClass.GIT_STAGE, ActionClass.GIT_COMMIT})


@dataclass(frozen=True, repr=False)
class ActionRequest:
    action_id: str
    run_id: str
    task_id: str
    action_class: ActionClass
    target: str
    provider: str
    runtime: str
    data_classification: DataClass
    authorization_ref: str
    capability: str
    expected_effect: str
    idempotency_key: str = None
    destination: str = None


@dataclass(frozen=True, repr=False)
class Policy:
    policy_id: str
    level: PolicyLevel
    allowed_actions: frozenset = frozenset()
    denied_actions: frozenset = frozenset()
    read_roots: tuple = ()
    write_roots: tuple = ()
    network_mode: NetworkMode = NetworkMode.DENY_ALL
    network_allowlist: tuple = ()
    allowed_egress_classes: frozenset = frozenset()
    allowed_capabilities: frozenset = frozenset()
    expires_at: float = None
    revoked: bool = False

    def __post_init__(self):
        for name in ('allowed_actions', 'denied_actions', 'allowed_egress_classes', 'allowed_capabilities'):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        for name in ('read_roots', 'write_roots', 'network_allowlist'):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, repr=False)
class Authorization:
    authorization_id: str
    task_id: str
    allowed_actions: frozenset
    allowed_targets: tuple
    allowed_capabilities: frozenset
    expires_at: float
    revoked: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'allowed_actions', frozenset(self.allowed_actions))
        object.__setattr__(self, 'allowed_targets', tuple(self.allowed_targets))
        object.__setattr__(self, 'allowed_capabilities', frozenset(self.allowed_capabilities))


@dataclass(frozen=True)
class PolicyDecision:
    disposition: str
    reason: str


class CapabilityBroker:
    """Explicit trusted caller registrations, not discovery or authorization."""
    def __init__(self):
        self._adapters = {}

    def register(self, name, adapter):
        if (type(name) is not str or name not in CAPABILITIES.values()
                or name in self._adapters or not callable(getattr(adapter, 'execute', None))):
            raise ValueError('invalid or duplicate capability registration')
        self._adapters[name] = adapter

    def has(self, name):
        return name in self._adapters

    def get(self, name):
        if not self.has(name):
            raise LookupError('capability unavailable')
        return self._adapters[name]


@dataclass(frozen=True, repr=False)
class ExecutionResult:
    """KNOWN_FAILURE attests no unresolved effect; otherwise use UNKNOWN_OUTCOME.

    Evidence refs attest the configured adapter's observations, not host reality.
    Summaries are never copied into receipts, journals or exception messages.
    """
    state: ExecutionState
    evidence_refs: tuple = ()
    redacted_summary: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'evidence_refs', tuple(self.evidence_refs))


@dataclass(frozen=True)
class JournalEntry:
    action_id: str  # opaque digest, not original input
    request_ref: str
    state: JournalState
    reason: str = 'NONE'
    evidence_refs: tuple = ()


class InMemorySecurityJournal:
    """Trusted serial transaction + append/latest/history journal implementation.

    No persistence, cross-process coordination, cryptographic chain or tamper
    resistance. Keep one journal for the entire action lifecycle. Replacing it
    discards retry protection. Alternative trusted journals must implement the
    same transaction() context manager and atomic append/history/latest contract.
    """
    def __init__(self):
        self._entries = []
        self._lock = RLock()
        self._action_locks = {}

    def transaction(self):
        return self._lock

    def action_transaction(self, action_id):
        """Optional per-action serialization; no network call holds _lock.

        Legacy transaction() retains its original semantics. Entries and lock
        lookup remain protected by the short data lock. Locks share the same
        lifetime as journal identities, not a separate remote journal.
        """
        legacy_owned = self._lock._is_owned()
        with self._lock:
            lock = self._action_locks.setdefault(_ref(action_id), RLock())
        # A legacy transaction may not wait for a remote action whose result
        # needs the legacy lock. Fail closed instead of reversing lock order.
        if legacy_owned:
            if not lock.acquire(blocking=False):
                raise ValueError('JOURNAL_LOCK_ORDER')
            # Keep the acquisition through context exit; a probe-and-release
            # would reopen the inversion race before __enter__.
            held = ExitStack()
            held.callback(lock.release)
            return held
        return lock

    def append(self, entry):
        with self._lock:
            self._entries.append(entry)

    def history(self, action_id):
        with self._lock:
            key = _ref(action_id)
            return tuple(e for e in self._entries if e.action_id == key)

    def latest(self, action_id):
        entries = self.history(action_id)
        return entries[-1] if entries else None


@dataclass(frozen=True)
class SecurityReceipt:
    receipt_version: str
    action_id: str
    task_id: str
    run_id: str
    provider: str
    runtime: str
    action_class: str
    target_locator: str
    policy_disposition: str
    policy_reason: str
    authorization_ref: str
    capability: str
    execution_state: str
    reconciliation_state: str
    evidence_refs: tuple
    final_disposition: str


def _text(value):
    return (type(value) is str and 0 < len(value) <= 4096
            and value.strip() == value and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _time(value):
    return (type(value) in (int, float) and 0 <= value <= 2**53
            and math.isfinite(value))


def _path(value):
    if not _text(value) or not value.startswith('/') or value.startswith('//') or '\\' in value:
        raise ValueError('invalid logical path')
    return posixpath.normpath(value)


def _url(value):
    if not _text(value) or any(c.isspace() for c in value) or '\\' in value:
        raise ValueError('invalid logical network target')
    parts = urlsplit(value)
    host = parts.hostname
    if (parts.scheme not in ('http', 'https') or not host or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or '%' in host or not host.isascii() or host.endswith('.')):
        raise ValueError('invalid logical network target')
    if ':' in host:
        ipaddress.IPv6Address(host)
    elif (len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                               for label in host.split('.'))):
        raise ValueError('invalid logical network hostname')
    port = parts.port if parts.port is not None else (443 if parts.scheme == 'https' else 80)
    if not 1 <= port <= 65535:
        raise ValueError('invalid logical network port')
    authority = ('[' + host + ']' if ':' in host else host) + ':' + str(port)
    origin = parts.scheme + '://' + authority
    return origin, urlunsplit((parts.scheme, authority, parts.path or '/', '', ''))


def _targets(action):
    values = (action.target, action.destination) if action.action_class == ActionClass.MOVE_FILE else (action.target,)
    if action.action_class in PATH_ACTIONS:
        return tuple(_path(v) for v in values)
    if action.action_class in EGRESS_ACTIONS:
        return (_url(action.target)[1],)
    return values


def _valid_action(action):
    if type(action) is not ActionRequest:
        return False
    required = ('action_id', 'run_id', 'task_id', 'target', 'provider', 'runtime', 'capability', 'expected_effect')
    if not all(_text(getattr(action, name)) for name in required):
        return False
    if (type(action.action_class) is not ActionClass or type(action.data_classification) is not DataClass
            or action.capability != CAPABILITIES[action.action_class]):
        return False
    if not all(v is None or _text(v) for v in (action.authorization_ref, action.idempotency_key, action.destination)):
        return False
    if (action.action_class == ActionClass.MOVE_FILE) != (action.destination is not None):
        return False
    try:
        _targets(action)
        return True
    except (ValueError, TypeError):
        return False


def _within(target, roots):
    return any(target == root or target.startswith(root.rstrip('/') + '/') for root in roots)


def _valid_policy(policy):
    if (type(policy) is not Policy or not _text(policy.policy_id) or type(policy.level) is not PolicyLevel
            or type(policy.network_mode) is not NetworkMode or type(policy.revoked) is not bool
            or (policy.expires_at is not None and not _time(policy.expires_at))):
        return False
    if (any(type(a) is not ActionClass for a in policy.allowed_actions | policy.denied_actions)
            or any(type(d) is not DataClass for d in policy.allowed_egress_classes)
            or any(type(c) is not str or c not in CAPABILITIES.values() for c in policy.allowed_capabilities)):
        return False
    try:
        for root in policy.read_roots + policy.write_roots:
            _path(root)
        for origin in policy.network_allowlist:
            normalized, full = _url(origin)
            if full != normalized + '/':
                return False
        return True
    except (TypeError, ValueError):
        return False


def evaluate_policy(action, policy_stack, authorization, now):
    """Pure deterministic evaluation; ALLOW still requires a registered capability.

    Stack must include CORE, be ordered by level and have no duplicate levels/IDs.
    Every layer is a complete restrictive envelope, never an overriding patch.
    Authorization targets are exact normalized targets, not prefixes or globs.
    """
    if not _valid_action(action):
        return PolicyDecision('INVALID', 'MALFORMED_ACTION')
    if (not _time(now) or type(policy_stack) not in (tuple, list) or not policy_stack
            or not all(_valid_policy(p) for p in policy_stack)):
        return PolicyDecision('DENY', 'POLICY_INVALID')
    levels = [list(PolicyLevel).index(p.level) for p in policy_stack]
    if (levels[0] != 0 or levels != sorted(set(levels))
            or len({p.policy_id for p in policy_stack}) != len(policy_stack)):
        return PolicyDecision('DENY', 'POLICY_INVALID')
    targets = _targets(action)
    for policy in policy_stack:
        if policy.revoked or (policy.expires_at is not None and now >= policy.expires_at):
            return PolicyDecision('DENY', 'POLICY_INACTIVE')
        if action.action_class in policy.denied_actions:
            return PolicyDecision('DENY', 'ACTION_DENIED')
        if action.action_class not in policy.allowed_actions:
            return PolicyDecision('DENY', 'ACTION_NOT_IN_SCOPE')
        if action.capability not in policy.allowed_capabilities:
            return PolicyDecision('DENY', 'CAPABILITY_MISSING')
        if action.action_class in EGRESS_ACTIONS:
            if (action.data_classification not in (DataClass.PUBLIC, DataClass.NON_SENSITIVE)
                    or action.data_classification not in policy.allowed_egress_classes):
                return PolicyDecision('DENY', 'DATA_EGRESS_DENIED')
            if (policy.network_mode == NetworkMode.DENY_ALL or _url(action.target)[0]
                    not in tuple(_url(v)[0] for v in policy.network_allowlist)):
                return PolicyDecision('DENY', 'NETWORK_TARGET_DENIED')
        if action.action_class in PATH_ACTIONS:
            roots = policy.read_roots if action.action_class == ActionClass.READ_FILE else policy.write_roots
            if not all(_within(t, tuple(_path(r) for r in roots)) for t in targets):
                return PolicyDecision('DENY', 'PATH_OUT_OF_SCOPE')
    if type(authorization) is not Authorization:
        return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_MISSING')
    if authorization.revoked is not False:
        return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_REVOKED')
    if not _time(authorization.expires_at) or now >= authorization.expires_at:
        return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_EXPIRED')
    if (not _text(authorization.authorization_id) or not _text(authorization.task_id)
            or authorization.authorization_id != action.authorization_ref
            or authorization.task_id != action.task_id
            or any(type(a) is not ActionClass for a in authorization.allowed_actions)
            or action.action_class not in authorization.allowed_actions
            or action.capability not in authorization.allowed_capabilities):
        return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_MISSING')
    try:
        allowed = authorization.allowed_targets
        if not all(_text(t) for t in allowed):
            raise ValueError('invalid authorization target')
        if action.action_class in PATH_ACTIONS:
            allowed = tuple(_path(t) for t in allowed)
        elif action.action_class in EGRESS_ACTIONS:
            allowed = tuple(_url(t)[1] for t in allowed)
        if not all(t in allowed for t in targets):
            return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_MISSING')
    except (ValueError, TypeError):
        return PolicyDecision('REQUIRE_AUTHORIZATION', 'AUTHORIZATION_MISSING')
    return PolicyDecision('ALLOW', 'AUTHORIZED')


def _ref(value):
    # No raw caller/adapter text in journal or receipt, including identifiers.
    if type(value) is not str:
        return 'REDACTED'
    return 'sha256:' + hashlib.sha256(value.encode('utf-8', errors='replace')).hexdigest()


def _request_ref(action):
    # Authority can be renewed without changing the proposed effect identity.
    values = {f.name: getattr(action, f.name) for f in fields(action) if f.name != 'authorization_ref'}
    return _ref(json.dumps(values, sort_keys=True))


def _receipt(action, decision, execution='NOT_ATTEMPTED', reconciliation='NOT_REQUIRED', evidence=(), final=None):
    def value(name):
        return getattr(action, name, None) if type(action) is ActionRequest else None
    action_class = value('action_class')
    capability = value('capability')
    return SecurityReceipt('20396-rse-receipt/v1', *(_ref(value(n)) for n in
                           ('action_id', 'task_id', 'run_id', 'provider', 'runtime')),
                           action_class.value if type(action_class) is ActionClass else 'INVALID',
                           _ref(value('target')), decision.disposition, decision.reason,
                           _ref(value('authorization_ref')),
                           capability if type(capability) is str and capability in CAPABILITIES.values() else 'INVALID',
                           execution, reconciliation, tuple(evidence), final or decision.disposition)


def _append(journal, action, state, reason='NONE', evidence=()):
    journal.append(JournalEntry(_ref(action.action_id), _request_ref(action), state, reason, tuple(evidence)))


def _prior(action, journal):
    history = journal.history(action.action_id)
    if any(e.request_ref != _request_ref(action) for e in history):
        return 'IDENTITY_CONFLICT'
    for entry in reversed(history):
        if entry.state not in (JournalState.BLOCKED, JournalState.PROPOSED):
            return entry.state.value
    return None


def action_transaction(journal, action_id):
    """Optional journal capability, with conservative legacy serialization."""
    scoped = getattr(journal, 'action_transaction', None)
    return scoped(action_id) if callable(scoped) else journal.transaction()


def evaluate_and_execute(action, policy_stack, authorization, capability_broker, journal, now, *, action_scoped=False):
    """One transaction, one attempt; never auto-retry. Trusted adapters only.

    Caller must keep journal ownership and supply current authority on every call.
    Journal exceptions fail closed; after ATTEMPTED, uncertain bookkeeping remains
    pending. Arbitrary adapters cannot be forcibly stopped by this Python kernel.
    """
    if not _valid_action(action):
        return _receipt(action, PolicyDecision('INVALID', 'MALFORMED_ACTION'))
    execution = 'UNKNOWN_OUTCOME'  # History may be unavailable at the boundary.
    try:
        with (action_transaction(journal, action.action_id) if action_scoped else journal.transaction()):
            # Atomic reservation shared with legacy callers. Only the adapter
            # operation is released from the global lock in scoped mode.
            with journal.transaction():
                previous = _prior(action, journal)
                if previous == 'IDENTITY_CONFLICT':
                    return _receipt(action, PolicyDecision('DENY', 'ACTION_ID_CONFLICT'))
                if previous in ('KNOWN_SUCCESS', 'RECONCILED_SUCCESS'):
                    return _receipt(action, PolicyDecision('DENY', 'ALREADY_COMPLETED'),
                                    execution=previous, final='ALREADY_COMPLETED')
                if previous in ('AUTHORIZED', 'ATTEMPTED', 'UNKNOWN_OUTCOME', 'RECONCILIATION_REQUIRED'):
                    return _receipt(action, PolicyDecision('REQUIRE_RECONCILIATION', 'UNKNOWN_OUTCOME_PENDING'),
                                    execution='UNKNOWN_OUTCOME',
                                    reconciliation='RECONCILIATION_REQUIRED')
                execution = 'NOT_ATTEMPTED'
                _append(journal, action, JournalState.PROPOSED)
                decision = evaluate_policy(action, policy_stack, authorization, now)
                if decision.disposition == 'ALLOW' and not capability_broker.has(action.capability):
                    decision = PolicyDecision('DENY', 'CAPABILITY_MISSING')
                if decision.disposition != 'ALLOW':
                    _append(journal, action, JournalState.BLOCKED, decision.reason)
                    return _receipt(action, decision)
                adapter = capability_broker.get(action.capability)
                _append(journal, action, JournalState.AUTHORIZED, 'AUTHORIZED')
                _append(journal, action, JournalState.ATTEMPTED)
            execution = 'UNKNOWN_OUTCOME'
            try:
                result = adapter.execute(action)
                if (type(result) is not ExecutionResult or type(result.state) is not ExecutionState
                        or not all(_text(e) for e in result.evidence_refs)
                        or (result.state == ExecutionState.KNOWN_SUCCESS and not result.evidence_refs)):
                    result = ExecutionResult(ExecutionState.UNKNOWN_OUTCOME)
            except Exception:
                result = ExecutionResult(ExecutionState.UNKNOWN_OUTCOME)
            evidence = tuple(_ref(e) for e in result.evidence_refs)
            _append(journal, action, JournalState(result.state.value), evidence=evidence)
            if result.state == ExecutionState.UNKNOWN_OUTCOME:
                _append(journal, action, JournalState.RECONCILIATION_REQUIRED)
                return _receipt(action, decision, result.state.value, 'RECONCILIATION_REQUIRED', evidence,
                                'REQUIRE_RECONCILIATION')
            return _receipt(action, decision, result.state.value, evidence=evidence, final=result.state.value)
    except Exception:
        return _receipt(action, PolicyDecision('REQUIRE_RECONCILIATION', 'JOURNAL_OR_BOUNDARY_FAILURE'),
                        execution=execution,
                        reconciliation='RECONCILIATION_REQUIRED')


def reconcile(action, journal, reconciler):
    """Trusted read-only injected reconciler, never model text or an effect retry.

    EFFECT_NOT_APPLIED only clears uncertainty. The next execute call re-evaluates
    the complete current policy, authorization, expiry, revocation and capability.
    Optional per-action journal serialization also protects legacy callers from
    clearing a scoped attempt while its remote adapter is still running.
    """
    if not _valid_action(action):
        return _receipt(action, PolicyDecision('INVALID', 'MALFORMED_ACTION'))
    try:
        with action_transaction(journal, action.action_id):
            previous = _prior(action, journal)
            if previous not in ('AUTHORIZED', 'ATTEMPTED', 'UNKNOWN_OUTCOME', 'RECONCILIATION_REQUIRED'):
                return _receipt(action, PolicyDecision('DENY', 'RECONCILIATION_NOT_PENDING'))
            try:
                outcome = reconciler(action)
            except Exception:
                outcome = ReconciliationOutcome.STILL_UNKNOWN
            state = JournalState.RECONCILIATION_REQUIRED
            if type(outcome) is ReconciliationOutcome:
                if outcome == ReconciliationOutcome.EFFECT_APPLIED:
                    state = JournalState.RECONCILED_SUCCESS
                elif outcome == ReconciliationOutcome.EFFECT_NOT_APPLIED:
                    state = JournalState.RECONCILED_NOT_APPLIED
            _append(journal, action, state)
            return _receipt(action, PolicyDecision('REQUIRE_RECONCILIATION', 'UNKNOWN_OUTCOME_PENDING')
                            if state == JournalState.RECONCILIATION_REQUIRED else PolicyDecision('DENY', 'REEVALUATION_REQUIRED'),
                            execution=state.value if state != JournalState.RECONCILIATION_REQUIRED else 'UNKNOWN_OUTCOME',
                            reconciliation=state.value, final=state.value)
    except Exception:
        return _receipt(action, PolicyDecision('REQUIRE_RECONCILIATION', 'JOURNAL_OR_BOUNDARY_FAILURE'),
                        execution='UNKNOWN_OUTCOME',
                        reconciliation='RECONCILIATION_REQUIRED')
