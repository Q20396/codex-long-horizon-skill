"""Experimental scoped management + tamper-evident history, not a security sandbox.

Trusted host supplies current authorities, scope relationships and time. Records
do not authenticate actors. Low-level chain append is a trusted storage API, not
an authorization entrypoint. No runtime effects or import-time I/O.
"""
from dataclasses import dataclass, fields, is_dataclass, asdict
from enum import Enum
import hashlib
import json
import math
import os
import re
import stat
from threading import RLock

SCHEMA = '20396-security-chain/v1'
GENESIS = '0' * 64
MAX_BREAK_GLASS_SECONDS = 3600
MAX_RECORD_BYTES = 16384
MAX_RECORDS = 10000


class AuthorityRole(str, Enum):
    ROOT_OWNER = 'ROOT_OWNER'
    INSTALLATION_ADMIN = 'INSTALLATION_ADMIN'
    PROJECT_AUTHORITY = 'PROJECT_AUTHORITY'
    TASK_AUTHORITY = 'TASK_AUTHORITY'
    RUNTIME = 'RUNTIME'


class ManagementAction(str, Enum):
    INSTALLATION_POLICY_CHANGE = 'INSTALLATION_POLICY_CHANGE'
    ORGANIZATION_POLICY_CHANGE = 'ORGANIZATION_POLICY_CHANGE'
    PROJECT_POLICY_CHANGE = 'PROJECT_POLICY_CHANGE'
    TASK_POLICY_CHANGE = 'TASK_POLICY_CHANGE'
    RUN_POLICY_CHANGE = 'RUN_POLICY_CHANGE'
    ACTION_POLICY_CHANGE = 'ACTION_POLICY_CHANGE'
    AUTHORIZATION_GRANT = 'AUTHORIZATION_GRANT'
    AUTHORIZATION_REVOKE = 'AUTHORIZATION_REVOKE'
    AUTHORITY_GRANT = 'AUTHORITY_GRANT'
    AUTHORITY_REVOKE = 'AUTHORITY_REVOKE'
    BREAK_GLASS_GRANT = 'BREAK_GLASS_GRANT'
    BREAK_GLASS_USE = 'BREAK_GLASS_USE'
    BREAK_GLASS_EXPIRE = 'BREAK_GLASS_EXPIRE'
    RSE_RECEIPT_RECORD = 'RSE_RECEIPT_RECORD'


class EventType(str, Enum):
    POLICY_CREATED = 'POLICY_CREATED'
    POLICY_SUPERSEDED = 'POLICY_SUPERSEDED'
    POLICY_REVOKED = 'POLICY_REVOKED'
    AUTHORIZATION_GRANTED = 'AUTHORIZATION_GRANTED'
    AUTHORIZATION_REVOKED = 'AUTHORIZATION_REVOKED'
    AUTHORITY_GRANTED = 'AUTHORITY_GRANTED'
    AUTHORITY_REVOKED = 'AUTHORITY_REVOKED'
    BREAK_GLASS_GRANTED = 'BREAK_GLASS_GRANTED'
    BREAK_GLASS_USED = 'BREAK_GLASS_USED'
    BREAK_GLASS_EXPIRED = 'BREAK_GLASS_EXPIRED'
    RSE_RECEIPT_RECORDED = 'RSE_RECEIPT_RECORDED'
    SECURITY_ALERT = 'SECURITY_ALERT'
    MODEL_USAGE = 'MODEL_USAGE'
    TOKEN_BUDGET_CREATED = 'TOKEN_BUDGET_CREATED'
    TOKEN_BUDGET_SUPERSEDED = 'TOKEN_BUDGET_SUPERSEDED'
    TOKEN_BUDGET_EXTENSION_REQUESTED = 'TOKEN_BUDGET_EXTENSION_REQUESTED'
    TOKEN_BUDGET_EXTENSION_GRANTED = 'TOKEN_BUDGET_EXTENSION_GRANTED'
    TOKEN_BUDGET_WARNING = 'TOKEN_BUDGET_WARNING'
    TOKEN_BUDGET_EXCEEDED = 'TOKEN_BUDGET_EXCEEDED'
    TOKEN_ANOMALY = 'TOKEN_ANOMALY'
    CRITICAL_TRACE_EVENT = 'CRITICAL_TRACE_EVENT'
    TRACE_DIVERGENCE = 'TRACE_DIVERGENCE'
    TRACE_RISK_FINDING = 'TRACE_RISK_FINDING'


@dataclass(frozen=True, repr=False)
class SecurityAuthority:
    authority_id: str
    role: AuthorityRole
    installation_id: str
    project_id: str = None
    task_id: str = None
    expires_at: float = None
    revoked: bool = False
    parent_authority_ref: str = None


@dataclass(frozen=True)
class AuthorityDecision:
    disposition: str
    reason: str


@dataclass(frozen=True, repr=False)
class BreakGlassGrant:
    grant_id: str
    installation_id: str
    granted_by_authority_id: str
    allowed_actions: frozenset
    allowed_capabilities: frozenset
    allowed_targets: tuple
    reason: str
    issued_at: float
    expires_at: float
    project_id: str = None
    task_id: str = None
    revoked: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'allowed_actions', frozenset(self.allowed_actions))
        object.__setattr__(self, 'allowed_capabilities', frozenset(self.allowed_capabilities))
        object.__setattr__(self, 'allowed_targets', tuple(self.allowed_targets))


@dataclass(frozen=True, repr=False)
class SecurityEventDraft:
    event_id: str
    event_type: EventType
    timestamp: float
    installation_id: str
    actor_role: AuthorityRole
    actor_id: str
    reason: str
    project_id: str = None
    task_id: str = None
    run_id: str = None
    action_id: str = None
    subject_id: str = None
    artifact_digest: str = None
    previous_artifact_digest: str = None
    authority_digest: str = None
    evidence_refs: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, 'evidence_refs', tuple(self.evidence_refs))


@dataclass(frozen=True)
class SecurityRecord:
    schema_version: str
    chain_id_ref: str
    sequence: int
    timestamp: float
    event_type: str
    event_ref: str
    installation_ref: str
    project_ref: str
    task_ref: str
    run_ref: str
    action_ref: str
    actor_role: str
    actor_ref: str
    subject_ref: str
    artifact_digest: str
    previous_artifact_digest: str
    authority_digest: str
    reason_ref: str
    evidence_refs: tuple
    previous_hash: str
    record_hash: str


@dataclass(frozen=True)
class SecurityChainVerification:
    valid: bool
    reason: str
    record_count: int
    head_sequence: int
    head_hash: str
    failed_sequence: int = None


def _text(value):
    return (type(value) is str and 0 < len(value) <= 4096 and value.strip() == value
            and all(32 <= ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF for c in value))


def _time(value):
    return type(value) in (int, float) and 0 <= value <= 2**53 and math.isfinite(value)


def _scope(installation, project, task):
    return (_text(installation) and (project is None or _text(project))
            and (task is None or (_text(task) and project is not None)))


def _hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _ref(value):
    return None if value is None else hashlib.sha256(value.encode('utf-8')).hexdigest()


def _normalize(value, depth=0, budget=None):
    if budget is None:
        budget = [4096]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise ValueError('ARTIFACT_INVALID')
    if isinstance(value, Enum):
        return _normalize(value.value, depth + 1, budget)
    if value is None or type(value) is bool:
        return value
    if type(value) is str and len(value) <= 4096:
        value.encode('utf-8')
        return value
    if type(value) in (int, float) and abs(value) <= 2**53 and math.isfinite(value):
        return int(value) if int(value) == value else value
    if is_dataclass(value) and not isinstance(value, type):
        value = {f.name: getattr(value, f.name) for f in fields(value)}
    if type(value) is dict and len(value) <= 128 and all(type(k) is str and len(k) <= 128 for k in value):
        return {k: _normalize(v, depth + 1, budget) for k, v in value.items()}
    if type(value) in (tuple, list, set, frozenset) and len(value) <= 128:
        normalized = [_normalize(v, depth + 1, budget) for v in value]
        if type(value) in (set, frozenset):
            normalized.sort(key=lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
        return normalized
    raise ValueError('ARTIFACT_INVALID')


def canonical_bytes(value):
    """Bounded deterministic normalization; set-like collections sort by encoding."""
    try:
        return json.dumps(_normalize(value), sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except Exception:
        raise ValueError('ARTIFACT_INVALID') from None


def artifact_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _authority_valid(actor):
    return (type(actor) is SecurityAuthority and type(actor.role) is AuthorityRole
            and _text(actor.authority_id) and _scope(actor.installation_id, actor.project_id, actor.task_id)
            and type(actor.revoked) is bool and (actor.expires_at is None or _time(actor.expires_at))
            and (actor.parent_authority_ref is None or _text(actor.parent_authority_ref))
            and (actor.role != AuthorityRole.PROJECT_AUTHORITY or actor.project_id is not None)
            and (actor.role != AuthorityRole.TASK_AUTHORITY or actor.task_id is not None)
            and (actor.role not in (AuthorityRole.ROOT_OWNER, AuthorityRole.INSTALLATION_ADMIN)
                 or (actor.project_id is None and actor.task_id is None)))


def authorize_management_change(actor, action, *, installation_id, now, project_id=None,
                                task_id=None, subject_authority=None, root_invariant_change=False):
    """Pure check of trusted current snapshots; no bootstrap/authentication or state mutation."""
    deny = lambda reason: AuthorityDecision('DENY', reason)
    if root_invariant_change is not False:
        return deny('ROOT_INVARIANT_IMMUTABLE')
    if (not _authority_valid(actor) or type(action) is not ManagementAction or not _time(now)
            or not _scope(installation_id, project_id, task_id)):
        return AuthorityDecision('INVALID', 'AUTHORITY_INVALID')
    if actor.revoked:
        return deny('AUTHORITY_REVOKED')
    if actor.expires_at is not None and now >= actor.expires_at:
        return deny('AUTHORITY_EXPIRED')
    if (actor.installation_id != installation_id or
            (actor.project_id is not None and actor.project_id != project_id) or
            (actor.task_id is not None and actor.task_id != task_id)):
        return deny('AUTHORITY_SCOPE_MISMATCH')
    role = actor.role
    if action == ManagementAction.RSE_RECEIPT_RECORD:
        return AuthorityDecision('ALLOW', 'AUTHORIZED')
    if role == AuthorityRole.RUNTIME:
        return deny('CHANGE_OUT_OF_SCOPE')
    if action in (ManagementAction.BREAK_GLASS_GRANT, ManagementAction.BREAK_GLASS_USE,
                  ManagementAction.BREAK_GLASS_EXPIRE):
        if role not in (AuthorityRole.ROOT_OWNER, AuthorityRole.INSTALLATION_ADMIN):
            return deny('BREAK_GLASS_NOT_ALLOWED')
    if action in (ManagementAction.INSTALLATION_POLICY_CHANGE, ManagementAction.ORGANIZATION_POLICY_CHANGE):
        if role not in (AuthorityRole.ROOT_OWNER, AuthorityRole.INSTALLATION_ADMIN) or project_id or task_id:
            return deny('CHANGE_OUT_OF_SCOPE')
    if action == ManagementAction.PROJECT_POLICY_CHANGE:
        if project_id is None or task_id is not None or role == AuthorityRole.TASK_AUTHORITY:
            return deny('CHANGE_OUT_OF_SCOPE')
    if action in (ManagementAction.TASK_POLICY_CHANGE, ManagementAction.RUN_POLICY_CHANGE,
                  ManagementAction.ACTION_POLICY_CHANGE) and task_id is None:
        return deny('CHANGE_OUT_OF_SCOPE')
    if action in (ManagementAction.AUTHORITY_GRANT, ManagementAction.AUTHORITY_REVOKE):
        subject = subject_authority
        if not _authority_valid(subject):
            return AuthorityDecision('INVALID', 'AUTHORITY_INVALID')
        permitted = {AuthorityRole.ROOT_OWNER: {AuthorityRole.INSTALLATION_ADMIN, AuthorityRole.PROJECT_AUTHORITY,
                     AuthorityRole.TASK_AUTHORITY, AuthorityRole.RUNTIME},
                     AuthorityRole.INSTALLATION_ADMIN: {AuthorityRole.PROJECT_AUTHORITY, AuthorityRole.TASK_AUTHORITY},
                     AuthorityRole.PROJECT_AUTHORITY: {AuthorityRole.TASK_AUTHORITY}}
        if subject.role not in permitted.get(role, set()):
            return deny('ROLE_ESCALATION_DENIED')
        if (subject.installation_id != installation_id or subject.project_id != project_id
                or subject.task_id != task_id):
            return deny('AUTHORITY_SCOPE_MISMATCH')
        if action == ManagementAction.AUTHORITY_GRANT:
            if subject.revoked or (subject.expires_at is not None and subject.expires_at <= now):
                return deny('AUTHORITY_INVALID')
            if actor.expires_at is not None and (subject.expires_at is None or subject.expires_at > actor.expires_at):
                return deny('ROLE_ESCALATION_DENIED')
    return AuthorityDecision('ALLOW', 'AUTHORIZED')


# Matches Phase 1 names without importing or changing its execution module.
_ACTION_CAPABILITY = {
    'READ_FILE': 'filesystem.read', 'WRITE_FILE': 'filesystem.write',
    'CREATE_FILE': 'filesystem.write', 'DELETE_FILE': 'filesystem.write',
    'MOVE_FILE': 'filesystem.write', 'EXECUTE_PROCESS': 'process.execute',
    'NETWORK_REQUEST': 'network.request', 'SECRET_ACCESS': 'secret.read',
    'PACKAGE_INSTALL': 'package.install', 'CONFIG_CHANGE': 'config.write',
    'SERVICE_START': 'service.control', 'SERVICE_STOP': 'service.control',
    'GIT_STAGE': 'git.stage', 'GIT_COMMIT': 'git.commit', 'GIT_PUSH': 'git.push',
    'PR_CREATE': 'github.pr.create', 'PR_MERGE': 'github.pr.merge',
    'RELEASE': 'release.publish', 'DEPLOY': 'deploy.execute',
}


def _grant_valid(grant):
    return (type(grant) is BreakGlassGrant and _text(grant.grant_id) and _text(grant.granted_by_authority_id)
            and _scope(grant.installation_id, grant.project_id, grant.task_id) and _text(grant.reason)
            and type(grant.revoked) is bool and _time(grant.issued_at) and _time(grant.expires_at)
            and 0 < grant.expires_at - grant.issued_at <= MAX_BREAK_GLASS_SECONDS
            and 0 < len(grant.allowed_actions) <= len(_ACTION_CAPABILITY)
            and all(type(a) is str and a in _ACTION_CAPABILITY for a in grant.allowed_actions)
            and 0 < len(grant.allowed_capabilities) <= len(_ACTION_CAPABILITY)
            and all(type(c) is str and c in _ACTION_CAPABILITY.values() for c in grant.allowed_capabilities)
            and 0 < len(grant.allowed_targets) <= 32 and all(_text(t) for t in grant.allowed_targets))


def validate_break_glass(grant, *, installation_id, now, action, capability, target,
                         project_id=None, task_id=None, root_invariant_change=False):
    if root_invariant_change is not False:
        return AuthorityDecision('DENY', 'ROOT_INVARIANT_IMMUTABLE')
    if not _grant_valid(grant) or not _time(now) or not _scope(installation_id, project_id, task_id):
        return AuthorityDecision('INVALID', 'BREAK_GLASS_NOT_ALLOWED')
    if now >= grant.expires_at:
        return AuthorityDecision('DENY', 'BREAK_GLASS_EXPIRED')
    if (grant.revoked or now < grant.issued_at or grant.installation_id != installation_id
            or (grant.project_id is not None and grant.project_id != project_id)
            or (grant.task_id is not None and grant.task_id != task_id)
            or type(action) is not str or action not in grant.allowed_actions
            or type(capability) is not str or capability not in grant.allowed_capabilities
            or _ACTION_CAPABILITY.get(action) != capability or not _text(target)
            or target not in grant.allowed_targets):
        return AuthorityDecision('DENY', 'BREAK_GLASS_NOT_ALLOWED')
    return AuthorityDecision('ALLOW', 'AUTHORIZED')


def seal_event(event, chain_id, installation_id, sequence, previous_hash):
    if (type(event) is not SecurityEventDraft or not _text(chain_id) or not _text(installation_id)
            or type(sequence) is not int or not 1 <= sequence <= MAX_RECORDS or not _hash(previous_hash)
            or type(event.event_type) is not EventType or type(event.actor_role) is not AuthorityRole
            or not _time(event.timestamp) or not _scope(event.installation_id, event.project_id, event.task_id)
            or not all(_text(v) for v in (event.event_id, event.actor_id, event.reason))
            or not all(v is None or _text(v) for v in (event.run_id,event.action_id,event.subject_id))
            or not all(v is None or _hash(v) for v in (event.artifact_digest,event.previous_artifact_digest,event.authority_digest))
            or len(event.evidence_refs) > 32 or not all(_text(v) for v in event.evidence_refs)):
        raise ValueError('EVENT_INVALID')
    if event.installation_id != installation_id:
        raise ValueError('CHAIN_ID_MISMATCH')
    payload = dict(schema_version=SCHEMA,chain_id_ref=_ref(chain_id),sequence=sequence,
                   timestamp=int(event.timestamp) if int(event.timestamp)==event.timestamp else event.timestamp,
                   event_type=event.event_type.value,event_ref=_ref(event.event_id),installation_ref=_ref(installation_id),
                   actor_role=event.actor_role.value,actor_ref=_ref(event.actor_id),reason_ref=_ref(event.reason),
                   evidence_refs=tuple(_ref(v) for v in event.evidence_refs),previous_hash=previous_hash,
                   artifact_digest=event.artifact_digest,previous_artifact_digest=event.previous_artifact_digest,
                   authority_digest=event.authority_digest)
    for name in ('project','task','run','action','subject'):
        payload[name+'_ref'] = _ref(getattr(event,name+'_id'))
    return SecurityRecord(**payload,record_hash=artifact_digest(payload))


def verify_chain(records, chain_id, installation_id):
    """Structural integrity only. A rebuilt valid history remains structurally valid."""
    def fail(reason,index=None):
        return SecurityChainVerification(False,reason,len(records),0,GENESIS,index)
    if type(records) not in (tuple,list) or len(records)>MAX_RECORDS:
        return SecurityChainVerification(False,'MALFORMED_RECORD',0,0,GENESIS)
    if not _text(chain_id) or not _text(installation_id):
        return fail('CHAIN_ID_MISMATCH')
    previous=GENESIS
    seen=set()
    for sequence,record in enumerate(records,1):
        if type(record) is not SecurityRecord:
            return fail('MALFORMED_RECORD',sequence)
        # Do not recursively copy unvalidated fields: malformed cyclic input is data.
        p={field.name:getattr(record,field.name) for field in fields(SecurityRecord)}
        if (type(record.schema_version) is not str or record.schema_version != SCHEMA or type(record.event_type) is not str
                or record.event_type not in {v.value for v in EventType}
                or type(record.actor_role) is not str or record.actor_role not in {v.value for v in AuthorityRole}
                or type(record.evidence_refs) is not tuple or len(record.evidence_refs)>32):
            return fail('SCHEMA_INVALID',sequence)
        required=('chain_id_ref','event_ref','installation_ref','actor_ref','reason_ref','previous_hash','record_hash')
        optional=('project_ref','task_ref','run_ref','action_ref','subject_ref','artifact_digest',
                  'previous_artifact_digest','authority_digest')
        if (not all(_hash(p[n]) for n in required) or not all(p[n] is None or _hash(p[n]) for n in optional)
                or not all(_hash(v) for v in record.evidence_refs) or (record.task_ref and not record.project_ref)):
            return fail('SCHEMA_INVALID',sequence)
        if record.chain_id_ref != _ref(chain_id) or record.installation_ref != _ref(installation_id):
            return fail('CHAIN_ID_MISMATCH',sequence)
        if type(record.sequence) is not int or record.sequence != sequence:
            return fail('SEQUENCE_INVALID',sequence)
        if not _time(record.timestamp):
            return fail('TIMESTAMP_INVALID',sequence)
        if record.event_ref in seen:
            return fail('DUPLICATE_EVENT_ID',sequence)
        if record.previous_hash != previous:
            return fail('PREVIOUS_HASH_MISMATCH',sequence)
        p.pop('record_hash')
        if artifact_digest(p) != record.record_hash:
            return fail('RECORD_HASH_MISMATCH',sequence)
        previous=record.record_hash
        seen.add(record.event_ref)
    return SecurityChainVerification(True,'VALID' if records else 'EMPTY_CHAIN',len(records),len(records),previous)


class InMemorySecurityChain:
    """Single object/controller locking. Private Python state is not host-protected."""
    def __init__(self, chain_id, installation_id):
        if not _text(chain_id) or not _text(installation_id):
            raise ValueError('CHAIN_ID_MISMATCH')
        self._chain_id=chain_id
        self._installation_id=installation_id
        self._records=[]
        self._lock=RLock()

    def records(self):
        with self._lock:
            return tuple(self._records)

    def verify(self):
        with self._lock:
            return verify_chain(self.records(),self._chain_id,self._installation_id)

    def head(self):
        with self._lock:
            result=self.verify()
            if not result.valid:
                raise ValueError('CHAIN_INTEGRITY_FAILURE')
            return result.head_sequence,result.head_hash

    def verify_against(self, expected_sequence, expected_head):
        with self._lock:
            result=self.verify()
            if not result.valid:
                return result
            records=self.records()
            if (type(expected_sequence) is not int or not 0<=expected_sequence<=len(records)
                    or not _hash(expected_head) or expected_head !=
                    (GENESIS if expected_sequence==0 else records[expected_sequence-1].record_hash)):
                return SecurityChainVerification(False,'CHAIN_ROLLBACK_OR_DIVERGENCE',result.record_count,
                                                  result.head_sequence,result.head_hash)
            return result

    def _next(self,event,records):
        result=verify_chain(records,self._chain_id,self._installation_id)
        if not result.valid:
            raise ValueError('CHAIN_INTEGRITY_FAILURE')
        record=seal_event(event,self._chain_id,self._installation_id,result.head_sequence+1,result.head_hash)
        if any(r.event_ref==record.event_ref for r in records):
            raise ValueError('DUPLICATE_EVENT_ID')
        return record

    def append(self,event):
        with self._lock:
            record=self._next(event,self.records())
            self._records.append(record)
            return record


def _json_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('MALFORMED_RECORD')
        result[key]=value
    return result


class JsonlSecurityChain(InMemorySecurityChain):
    """Explicit experimental file store. One trusted controller per file, no process locks.

    Parent directory must be trusted. No protection against hostile path replacement,
    privileged rewrites, complete deletion, or multiple object/controller races.
    A failed append is uncertain: this object latches closed; inspect/reopen explicitly.
    """
    def __init__(self,chain_id,installation_id,path,*,create=False):
        super().__init__(chain_id,installation_id)
        self._path=os.fspath(path)
        self._uncertain=False
        try:
            if create:
                fd=os.open(self._path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(fd,'wb') as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
            result=self.verify()
        except (OSError,TypeError):
            raise ValueError('CHAIN_IO_FAILURE') from None
        if not result.valid:
            raise ValueError('CHAIN_IO_FAILURE' if result.reason=='CHAIN_IO_FAILURE' else 'CHAIN_INTEGRITY_FAILURE')

    def _open(self,write=False):
        fd=os.open(self._path,(os.O_RDWR|os.O_APPEND if write else os.O_RDONLY)
                   |getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValueError('MALFORMED_RECORD')
        return os.fdopen(fd,'r+b' if write else 'rb')

    def _read(self,stream):
        rows=[]
        while True:
            line=stream.readline(MAX_RECORD_BYTES+1)
            if not line:
                return tuple(rows)
            if len(rows)>=MAX_RECORDS or len(line)>MAX_RECORD_BYTES or not line.endswith(b'\n'):
                raise ValueError('MALFORMED_RECORD')
            try:
                value=json.loads(line,object_pairs_hook=_json_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                if type(value) is not dict or set(value)!={f.name for f in fields(SecurityRecord)}:
                    raise ValueError()
                if type(value['evidence_refs']) is not list:
                    raise ValueError()
                value['evidence_refs']=tuple(value['evidence_refs'])
                row=SecurityRecord(**value)
                if canonical_bytes(value)+b'\n' != line:
                    raise ValueError()
                rows.append(row)
            except Exception:
                raise ValueError('MALFORMED_RECORD') from None

    def records(self):
        with self._lock:
            try:
                with self._open() as stream:
                    return self._read(stream)
            except OSError:
                raise ValueError('CHAIN_IO_FAILURE') from None

    def verify(self):
        with self._lock:
            try:
                return verify_chain(self.records(),self._chain_id,self._installation_id)
            except ValueError as error:
                return SecurityChainVerification(False,str(error),0,0,GENESIS)

    def append(self,event):
        with self._lock:
            if self._uncertain:
                raise ValueError('CHAIN_IO_UNCERTAIN')
            try:
                with self._open(write=True) as stream:
                    try:
                        records=self._read(stream)
                    except ValueError:
                        raise ValueError('CHAIN_INTEGRITY_FAILURE') from None
                    record=self._next(event,records)
                    encoded=canonical_bytes(asdict(record))+b'\n'
                    self._uncertain=True
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._uncertain=False
                return record
            except OSError:
                raise ValueError('CHAIN_IO_UNCERTAIN' if self._uncertain else 'CHAIN_IO_FAILURE') from None


def record_management_event(chain,actor,action,event_type,*,event_id,now,artifact,project_id=None,
                            task_id=None,previous_artifact=None,subject_authority=None,
                            reason='security management change',root_invariant_change=False):
    decision=authorize_management_change(actor,action,installation_id=chain._installation_id,
        project_id=project_id,task_id=task_id,now=now,subject_authority=subject_authority,
        root_invariant_change=root_invariant_change)
    if decision.disposition!='ALLOW':
        raise ValueError(decision.reason)
    allowed={ManagementAction.AUTHORIZATION_GRANT:{EventType.AUTHORIZATION_GRANTED},
             ManagementAction.AUTHORIZATION_REVOKE:{EventType.AUTHORIZATION_REVOKED},
             ManagementAction.AUTHORITY_GRANT:{EventType.AUTHORITY_GRANTED},
             ManagementAction.AUTHORITY_REVOKE:{EventType.AUTHORITY_REVOKED}}
    for item in ManagementAction:
        if item.value.endswith('_POLICY_CHANGE'):
            allowed[item]={EventType.POLICY_CREATED,EventType.POLICY_SUPERSEDED,EventType.POLICY_REVOKED}
    if type(event_type) is not EventType or event_type not in allowed.get(action,set()):
        raise ValueError('EVENT_INVALID')
    if event_type==EventType.POLICY_SUPERSEDED and previous_artifact is None:
        raise ValueError('EVENT_INVALID')
    if subject_authority is not None and artifact_digest(artifact)!=artifact_digest(subject_authority):
        raise ValueError('EVENT_INVALID')
    return chain.append(SecurityEventDraft(event_id,event_type,now,chain._installation_id,actor.role,
        actor.authority_id,reason,project_id=project_id,task_id=task_id,
        subject_id=subject_authority.authority_id if subject_authority else None,
        artifact_digest=artifact_digest(artifact),previous_artifact_digest=(artifact_digest(previous_artifact)
        if previous_artifact is not None else None),authority_digest=artifact_digest(actor)))


def record_break_glass(chain,actor,grant,event_type,*,event_id,now,action=None,capability=None,target=None,
                       project_id=None,task_id=None,root_invariant_change=False):
    if not _grant_valid(grant) or not _time(now):
        raise ValueError('BREAK_GLASS_NOT_ALLOWED')
    management={EventType.BREAK_GLASS_GRANTED:ManagementAction.BREAK_GLASS_GRANT,
                EventType.BREAK_GLASS_EXPIRED:ManagementAction.BREAK_GLASS_EXPIRE,
                EventType.BREAK_GLASS_USED:ManagementAction.RSE_RECEIPT_RECORD}
    if type(event_type) is not EventType or event_type not in management:
        raise ValueError('EVENT_INVALID')
    if event_type==EventType.BREAK_GLASS_USED:
        project_id=grant.project_id if project_id is None else project_id
        task_id=grant.task_id if task_id is None else task_id
    else:
        if project_id is not None or task_id is not None:
            raise ValueError('EVENT_INVALID')
        project_id,task_id=grant.project_id,grant.task_id
    decision=authorize_management_change(actor,management[event_type],installation_id=grant.installation_id,
        project_id=project_id,task_id=task_id,now=now,root_invariant_change=root_invariant_change)
    if decision.disposition!='ALLOW':
        raise ValueError(decision.reason)
    if event_type==EventType.BREAK_GLASS_GRANTED:
        if actor.authority_id!=grant.granted_by_authority_id or grant.revoked or now!=grant.issued_at:
            raise ValueError('BREAK_GLASS_NOT_ALLOWED')
        if actor.expires_at is not None and grant.expires_at>actor.expires_at:
            raise ValueError('BREAK_GLASS_NOT_ALLOWED')
    elif event_type==EventType.BREAK_GLASS_EXPIRED:
        if now<grant.expires_at:
            raise ValueError('BREAK_GLASS_NOT_ALLOWED')
    else:
        decision=validate_break_glass(grant,installation_id=chain._installation_id,now=now,action=action,
            capability=capability,target=target,project_id=project_id,task_id=task_id,
            root_invariant_change=root_invariant_change)
        if decision.disposition!='ALLOW':
            raise ValueError(decision.reason)
    digest=artifact_digest(grant)
    with chain._lock:
        records=chain.records()
        if event_type!=EventType.BREAK_GLASS_GRANTED and not any(
            r.event_type==EventType.BREAK_GLASS_GRANTED.value and r.artifact_digest==digest for r in records):
            raise ValueError('BREAK_GLASS_NOT_ALLOWED')
        if event_type==EventType.BREAK_GLASS_USED and any(
            r.event_type==EventType.BREAK_GLASS_EXPIRED.value and r.artifact_digest==digest for r in records):
            raise ValueError('BREAK_GLASS_EXPIRED')
        return chain.append(SecurityEventDraft(event_id,event_type,now,grant.installation_id,actor.role,
            actor.authority_id,grant.reason,project_id=project_id,task_id=task_id,
            subject_id=grant.grant_id,artifact_digest=digest,authority_digest=artifact_digest(actor),
            evidence_refs=() if event_type!=EventType.BREAK_GLASS_USED else (action,capability,target)))


def record_receipt(chain,actor,receipt,*,event_id,now,project_id=None,task_id=None):
    decision=authorize_management_change(actor,ManagementAction.RSE_RECEIPT_RECORD,
        installation_id=chain._installation_id,now=now,project_id=project_id,task_id=task_id)
    if decision.disposition!='ALLOW':
        raise ValueError(decision.reason)
    if (not is_dataclass(receipt) or isinstance(receipt,type)
            or getattr(receipt,'receipt_version',None)!='20396-rse-receipt/v1'):
        raise ValueError('EVENT_INVALID')
    return chain.append(SecurityEventDraft(event_id,EventType.RSE_RECEIPT_RECORDED,now,chain._installation_id,
        actor.role,actor.authority_id,'RSE receipt reference',project_id=project_id,task_id=task_id,
        artifact_digest=artifact_digest(receipt),authority_digest=artifact_digest(actor)))
