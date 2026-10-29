"""Bounded experimental remote effects through RSE; trusted host transports only.

No network, discovery, registration or credentials on import. The journal is
same-process only. An allowlisted host is not proof of public IP space, DNS
integrity or server trust. Credentials never belong in RemoteRuntimePayload.
"""
from __future__ import annotations
from dataclasses import dataclass, fields, replace
import base64
import errno
import hashlib
import http.client
import ipaddress
import json
import secrets
import math
import os
import re
import selectors
import signal
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import MappingProxyType
from urllib.parse import quote, urlsplit
import uuid

import runtime_safety_envelope as rse
import runtime_binding as local
import critical_execution_trace as cet
import security_authority_chain as sc

MAX_BODY = 8 * 1024 * 1024
MAX_HEADERS = 64 * 1024
BOUND_ACTIONS = frozenset((rse.ActionClass.NETWORK_REQUEST, rse.ActionClass.GIT_PUSH, rse.ActionClass.PR_CREATE))
_METHODS = frozenset(('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'))
_HEADERS = frozenset(('accept', 'content-type', 'x-github-api-version'))


def _require(condition, reason='MALFORMED_REMOTE_PAYLOAD'):
    if not condition:
        raise ValueError(reason)


def _text(value, limit=4096, empty=False):
    return (type(value) is str and (empty or bool(value)) and len(value.encode('utf-8')) <= limit
        and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _url(value):
    """Conservative ASCII URLs; reject ambiguous paths, preserve query ordering.

    Percent escapes in query remain exact octets (hex normalized to uppercase).
    Paths deliberately exclude escapes/dot segments instead of guessing server
    normalization. Queries are separate from RSE's query-free target contract.
    """
    _require(_text(value) and value.isascii() and not any(c.isspace() for c in value)
        and '\\' not in value, 'INVALID_REMOTE_DESTINATION')
    try:
        p = urlsplit(value)
        host, port = p.hostname, p.port if p.port is not None else 443
        _require(p.scheme == 'https' and host and p.username is None and p.password is None
            and not p.fragment and 0 < port <= 65535, 'INVALID_REMOTE_DESTINATION')
        if ':' in host:
            host = '[' + ipaddress.IPv6Address(host).compressed + ']'
        else:
            _require(len(host) <= 253 and not host.endswith('.') and all(
                re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', s) for s in host.split('.')),
                'INVALID_REMOTE_DESTINATION')
        path = p.path or '/'
        _require(path.startswith('/') and not path.startswith('//') and '%' not in path
            and all(s not in ('.', '..') for s in path.split('/'))
            and '//' not in path, 'INVALID_REMOTE_DESTINATION')
        _require(not re.search(r'%(?![0-9a-fA-F]{2})', p.query), 'INVALID_REMOTE_DESTINATION')
        query = re.sub(r'%[0-9a-fA-F]{2}', lambda m: m[0].upper(), p.query)
        origin = 'https://' + host + ':' + str(port)
        return origin, origin + path, query
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('INVALID_REMOTE_DESTINATION') from None


def _endpoint(target, query=''):
    origin, path, existing = _url(target)
    _require(not existing, 'INVALID_REMOTE_DESTINATION')
    _require(type(query) is str and len(query) <= 4096 and '#' not in query)
    _, _, canonical_query = _url(path + ('?' + query if query else ''))
    return path + ('?' + canonical_query if canonical_query else '')


def _ref(value):
    return (type(value) is str and value.startswith('refs/heads/') and len(value) <= 256
        and all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', s) and not s.endswith(('.', '.lock'))
            for s in value[11:].split('/')) and '..' not in value)


@dataclass(frozen=True, repr=False)
class RemoteRuntimePayload:
    action_id: str
    action_class: rse.ActionClass
    target: str
    method: str | None = None
    query: str = ''
    headers: tuple = ()
    body: bytes = b''
    request_identity: str | None = None
    timeout: float = 30
    response_limit: int = MAX_BODY
    readback_target: str | None = None
    readback_query: str = ''
    expected_readback_digest: str | None = None
    repository: str | None = None
    remote_name: str | None = None
    local_ref: str | None = None
    remote_ref: str | None = None
    expected_local_oid: str | None = None
    expected_remote_oid: str | None = None
    provider: str | None = None
    head: str | None = None
    base: str | None = None
    title: str | None = None
    draft: bool | None = None

    def __post_init__(self):
        _require(_text(self.action_id, 1024) and type(self.action_class) is rse.ActionClass)
        origin, target, query = _url(self.target)
        _require(not query)
        object.__setattr__(self, 'target', target)
        _endpoint(target, self.query)
        _require(type(self.headers) is tuple and all(type(h) is tuple and len(h) == 2
            and type(h[0]) is str and h[0].lower() in _HEADERS and _text(h[1], MAX_HEADERS) for h in self.headers))
        normalized = tuple(sorted((k.lower(), v) for k, v in self.headers))
        _require(len({k for k, v in normalized}) == len(normalized)
            and sum(len(k.encode()) + len(v.encode()) + 4 for k, v in normalized) <= MAX_HEADERS)
        object.__setattr__(self, 'headers', normalized)
        _require(type(self.body) is bytes and len(self.body) <= MAX_BODY)
        _require(self.request_identity is None or (type(self.request_identity) is str
            and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', self.request_identity) is not None))
        _require(type(self.timeout) in (int, float) and math.isfinite(self.timeout) and 0 < self.timeout <= 120)
        _require(type(self.response_limit) is int and 0 < self.response_limit <= MAX_BODY)
        if self.readback_target is not None:
            ro, rt, rq = _url(self.readback_target)
            _require(ro == origin and not rq and sc._hash(self.expected_readback_digest))
            object.__setattr__(self, 'readback_target', rt)
            _endpoint(rt, self.readback_query)
        else:
            _require(not self.readback_query and self.expected_readback_digest is None)
        git_values = (self.remote_name, self.local_ref, self.remote_ref, self.expected_local_oid, self.expected_remote_oid)
        pr_values = (self.provider, self.head, self.base, self.title, self.draft)
        if self.action_class == rse.ActionClass.NETWORK_REQUEST:
            _require(self.method in _METHODS and self.repository is None and all(v is None for v in git_values + pr_values))
            _require(self.method not in ('GET', 'HEAD') or not self.body)
            _require(self.method in ('GET', 'HEAD') or self.request_identity is not None)
        elif self.action_class == rse.ActionClass.GIT_PUSH:
            _require(self.method is None and not self.body and not self.headers and not self.query
                and self.readback_target is None and self.request_identity is None and all(v is None for v in pr_values))
            _require(_text(self.repository) and self.repository.startswith('/')
                and type(self.remote_name) is str and re.fullmatch('[A-Za-z0-9_-]{1,64}', self.remote_name)
                and _ref(self.local_ref) and _ref(self.remote_ref)
                and local._git_oid(self.expected_local_oid, 40) and local._git_oid(self.expected_remote_oid, 40)
                and self.expected_remote_oid != '0' * 40 and self.expected_local_oid != '0' * 40)
        elif self.action_class == rse.ActionClass.PR_CREATE:
            _require(self.method is None and not self.query and not self.headers and self.readback_target is None
                and all(v is None for v in git_values) and self.provider == 'github'
                and type(self.repository) is str and re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', self.repository)
                and _ref('refs/heads/' + (self.head or '')) and _ref('refs/heads/' + (self.base or ''))
                and _text(self.title, 256) and len(self.body) <= 65536 and type(self.draft) is bool
                and self.request_identity is not None)
            _require(target == origin + '/repos/' + self.repository + '/pulls')
            try:
                self.body.decode('utf-8')
            except UnicodeError:
                raise ValueError('MALFORMED_REMOTE_PAYLOAD') from None

    def digest(self):
        values = {f.name: getattr(self, f.name) for f in fields(self)}
        values['body'] = _digest(self.body)
        return sc.artifact_digest(values)

    def validate_for(self, action):
        _require(type(action) is rse.ActionRequest and self.action_id == action.action_id
            and self.action_class == action.action_class and self.target == _url(action.target)[1]
            and not _url(action.target)[2] and self.request_identity == action.idempotency_key)


@dataclass(frozen=True)
class RemoteOperationEvidence:
    payload_digest: str
    destination_digest: str
    reason: str
    request_identity_digest: str | None = None
    request_attempted: bool = False
    response_observed: bool = False
    response_digest: str | None = None
    resource_digest: str | None = None
    status_code: int | None = None
    reconciliation: str | None = None
    response_body_complete: bool | None = None
    response_parse_status: str = 'NOT_ATTEMPTED'


@dataclass(frozen=True, repr=False)
class RemoteRuntimeResult:
    receipt: rse.SecurityReceipt
    evidence: RemoteOperationEvidence | None = None
    events: tuple = ()
    divergences: tuple = ()
    boundary_status: str = 'OK'
    completeness: cet.TraceCompleteness = cet.TraceCompleteness.PARTIAL


@dataclass(frozen=True, repr=False)
class _Outcome:
    state: rse.ExecutionState
    evidence: RemoteOperationEvidence
    events: tuple = ()


def _evidence(p, reason, **values):
    return RemoteOperationEvidence(p.digest(), _digest(_endpoint(p.target, p.query).encode()), reason,
        _digest(p.request_identity.encode()) if p.request_identity else None, **values)


def _event(a, context, now, evidence, completed=False):
    return cet.CriticalEvent(uuid.uuid4().hex, cet.ACTION_EVENTS[a.action_class], context,
        cet.ObservationSource.ADAPTER_OBSERVED, now, a.target, a.data_classification, a.capability,
        cet.EventStatus.COMPLETED if completed else cet.EventStatus.ATTEMPTED,
        (sc.artifact_digest(evidence),))


class _HeaderBudget:
    """Bound framing, including trailers, and update deadline before each read.

    read1 avoids buffered read(n) waiting across arbitrarily many slow receives.
    Bytewise readline only covers the bounded 64 KiB protocol framing budget.
    """
    def __init__(self, source, sock, deadline):
        self.source, self.remaining, self.sock, self.deadline = source, MAX_HEADERS, sock, deadline

    def __getattr__(self, name):
        return getattr(self.source, name)

    def _deadline(self):
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            _require(remaining > 0, 'REMOTE_TIMEOUT')
            self.sock.settimeout(remaining)

    def readline(self, limit=-1):
        count = min(self.remaining + 1, limit) if limit >= 0 else self.remaining + 1
        parts = bytearray()
        while len(parts) < count:
            self._deadline()
            part = self.source.read(1)
            if not part:
                break
            parts.extend(part); self.remaining -= 1
            _require(self.remaining >= 0, 'REMOTE_RESPONSE_INVALID')
            if part == b'\n':
                break
        return bytes(parts)

    def read1(self, size=-1):
        self._deadline()
        return self.source.read1(size)

    def read(self, size=-1):
        _require(0 <= size <= MAX_BODY + MAX_HEADERS, 'REMOTE_RESPONSE_LIMIT')
        result = bytearray()
        while len(result) < size:
            part = self.read1(min(65536, size - len(result)))
            if not part:
                break
            result.extend(part)
        return bytes(result)


class _Response(http.client.HTTPResponse):
    def __init__(self, sock, *args, deadline=None, **kwargs):
        super().__init__(sock, *args, **kwargs)
        self.fp = _HeaderBudget(self.fp, sock, deadline)


class _ObservedResponseFailure(Exception):
    def __init__(self, status):
        super().__init__('REMOTE_RESPONSE_INVALID')
        self.status = status


class HTTPSRemoteTransport:
    """Direct verified HTTPS; no redirects, proxy, netrc, env or credential lookup.

    Optional authentication headers are supplied only by trusted host code.
    DNS resolution remains the host resolver's responsibility. Socket operations
    and body reads use the finite deadline; this is not a network sandbox.
    """
    tls_verified = True
    follows_redirects = False

    def __init__(self, *, credential_headers=()):
        _require(type(credential_headers) is tuple and all(type(h) is tuple and len(h) == 2
            and h[0].lower() in ('authorization', 'cookie') and _text(h[1], MAX_HEADERS) for h in credential_headers),
            'INVALID_REMOTE_CONFIG')
        _require(sum(len(k) + len(v) + 4 for k, v in credential_headers) <= MAX_HEADERS, 'INVALID_REMOTE_CONFIG')
        self._credentials = tuple(credential_headers)

    def request(self, method, url, headers, body, *, timeout, response_limit):
        _, target, query = _url(url)
        p = urlsplit(target)
        outgoing = (*headers, *self._credentials, ('Connection', 'close'))
        # Include generated Host and Content-Length fields with conservative
        # framing overhead, not only model-visible nonsecret headers.
        _require(sum(len(k.encode()) + len(v.encode()) + 4 for k, v in outgoing)
            + len(p.netloc.encode()) + 128 <= MAX_HEADERS, 'INVALID_REMOTE_CONFIG')
        context = ssl.create_default_context()
        _require(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname, 'INVALID_REMOTE_CONFIG')
        connection = http.client.HTTPSConnection(p.hostname, p.port, timeout=timeout, context=context)
        deadline = time.monotonic() + timeout
        response = None
        def make_response(*args, **kwargs):
            nonlocal response
            response = _Response(*args, deadline=deadline, **kwargs)
            return response
        connection.response_class = make_response
        try:
            connection.request(method, p.path + ('?' + query if query else ''), body=body,
                headers=dict(outgoing))
            response = connection.getresponse()
            # Reject transfer encodings that this minimal client cannot interpret.
            encoding = response.getheader('Transfer-Encoding')
            _require(encoding is None or encoding.lower() == 'chunked', 'REMOTE_RESPONSE_INVALID')
            response_headers = tuple(response.getheaders())
            pieces = []; remaining = response_limit + 1
            while remaining:
                duration = deadline - time.monotonic()
                _require(duration > 0, 'REMOTE_TIMEOUT')
                piece = response.read1(min(65536, remaining))
                if not piece:
                    break
                pieces.append(piece); remaining -= len(piece)
            data = b''.join(pieces)
            _require(len(data) <= response_limit and response.length in (None, 0), 'REMOTE_RESPONSE_LIMIT')
            return response.status, response_headers, data
        except Exception:
            if response is not None and type(response.status) is int and 100 <= response.status <= 599:
                raise _ObservedResponseFailure(response.status) from None
            raise ValueError('REMOTE_TRANSPORT_UNCERTAIN') from None
        finally:
            connection.close()


_PR_CLEANUP = 2.0
_PR_STARTUP = 2.0
_PR_INPUT = 2 * 1024 * 1024
_PR_OUTPUT = 12 * 1024 * 1024
_PR_METADATA = 64 * 1024


def _pr_frame(value, limit):
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')
    _require(0 < len(data) <= limit, 'PR_IPC_INVALID')
    return struct.pack('!I', len(data)) + data


def _pr_decode(data):
    def pairs(items):
        result = {}
        for k, v in items:
            _require(k not in result, 'PR_IPC_INVALID')
            result[k] = v
        return result
    value = json.loads(data, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('PR_IPC_INVALID')))
    _require(type(value) is dict and type(value.get('version')) is int
        and value['version'] == 1, 'PR_IPC_INVALID')
    return value


def _pr_headers(headers):
    _require(type(headers) in (tuple, list) and len(headers) <= 256, 'PR_IPC_INVALID')
    _require(all(type(v) in (tuple, list) and len(v) == 2
        and all(type(x) is str for x in v) for v in headers), 'PR_IPC_INVALID')
    _require(sum(len(k.encode('utf-8')) + len(v.encode('utf-8')) + 4 for k, v in headers)
        <= MAX_HEADERS, 'PR_IPC_INVALID')
    _require(all(k and not any(c in k+v for c in '\r\n\0') for k, v in headers), 'PR_IPC_INVALID')
    return tuple((k, v) for k, v in headers)


@dataclass(frozen=True, repr=False)
class _PRBudget:
    started: float
    end: float
    operation_end: float
    now: float
    action: object
    policies: tuple
    authorization: object

    @classmethod
    def create(cls, action, payload, policies, authorization, now, *, phase_deadline=None):
        start = time.monotonic()
        duration = min(payload.timeout, 30.0)
        _require(duration > _PR_CLEANUP, 'PR_BUDGET_EXHAUSTED')
        end = start+duration
        if phase_deadline is not None:
            _require(type(phase_deadline) in (int,float) and math.isfinite(phase_deadline), 'PR_BUDGET_EXHAUSTED')
            end = min(end,phase_deadline)
        _require(end-start > _PR_CLEANUP, 'PR_BUDGET_EXHAUSTED')
        return cls(start, end, end-_PR_CLEANUP,
                   now, action, tuple(policies), authorization)

    def check(self):
        current = time.monotonic()
        _require(current < self.operation_end, 'PR_DEADLINE')
        decision = rse.evaluate_policy(self.action, self.policies, self.authorization,
                                      self.now + current-self.started)
        _require(decision.disposition == 'ALLOW', 'PR_AUTHORITY_EXPIRED')
        return self.operation_end-current


def _pr_spawn_worker():
    directory = os.path.dirname(os.path.realpath(__file__))
    code = 'import sys;sys.path.insert(0,sys.argv[1]);import remote_runtime_binding as m;m._pr_worker_main()'
    return subprocess.Popen([os.path.realpath(sys.executable), '-I', '-B', '-S', '-c', code, directory],
        cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        close_fds=True, start_new_session=True, env={'PATH':'/usr/bin:/bin', 'LANG':'C'})


@dataclass(frozen=True)
class _PRCleanupRecord:
    """Finite facts only; quiescent describes the owner, not all descendants."""
    status: str = 'PENDING'
    stage: str = 'NOT_STARTED'
    errno: int | None = None
    identity: tuple | None = None
    reaped: bool = False
    group: str = 'UNKNOWN'
    pipes_closed: bool = False
    quiescent: bool = False

    def __post_init__(self):
        _require(self.status in ('PENDING','UNKNOWN','CONFIRMED')
            and self.stage in ('NOT_STARTED','IDENTITY','TERM','KILL','WAIT','PIPES','COMPLETE','INVALID','DIRECT_FINALIZATION')
            and (self.errno is None or type(self.errno) is int and 0 <= self.errno <= 65535)
            and (self.identity is None or type(self.identity) is tuple and len(self.identity) == 3
                 and all(type(v) is int and 0 < v <= 2147483647 for v in self.identity))
            and all(type(v) is bool for v in (self.reaped,self.pipes_closed,self.quiescent))
            and self.group in ('UNKNOWN','ABSENT_OBSERVED','CONFIRMED'), 'PR_CLEANUP_RECORD_INVALID')


@dataclass(frozen=True)
class _PRDirectFinalizationRecord:
    """Direct-handle facts only. Never group proof or execution authority."""
    outcome: str = 'INVALID'
    identity: tuple | None = None
    returncode: int | None = None
    reaped: bool = False
    pipes_closed: bool = False
    quiescent: bool = False
    within_budget: bool = False
    policy_allowed: bool = False
    errno: int | None = None

    def __post_init__(self):
        _require(type(self.outcome) is str and self.outcome in (
            'COMPLETE','WAIT_TIMEOUT','WAIT_ERROR','BUDGET_EXPIRED','POLICY_DENIED',
            'NONZERO_EXIT','PIPE_ERROR','IDENTITY_MISSING','INVALID')
            and (self.identity is None or type(self.identity) is tuple and len(self.identity)==3
                 and all(type(v) is int and 0<v<=2147483647 for v in self.identity)
                 and len(set(self.identity))==1)
            and (self.returncode is None or type(self.returncode) is int)
            and all(type(v) is bool for v in (self.reaped,self.pipes_closed,self.quiescent,
                                             self.within_budget,self.policy_allowed))
            and (self.errno is None or type(self.errno) is int and 0<self.errno<=65535),
            'PR_DIRECT_RECORD_INVALID')
        _require(not self.reaped or type(self.returncode) is int, 'PR_DIRECT_RECORD_INVALID')
        _require(self.outcome!='COMPLETE' or (self.identity is not None and self.returncode==0
            and self.reaped and self.pipes_closed and self.quiescent and self.within_budget
            and self.policy_allowed and self.errno is None), 'PR_DIRECT_RECORD_INVALID')


def _pr_cleanup_confirmed(record):
    """Consistency check, not a source of group proof or execution authority.

    No current production cleanup path supplies CONFIRMED group evidence.
    """
    return (type(record) is _PRCleanupRecord and record.status == 'CONFIRMED'
        and record.stage == 'COMPLETE' and record.errno is None
        and record.identity is not None and len(set(record.identity)) == 1
        and record.reaped and record.group == 'CONFIRMED'
        and record.pipes_closed and record.quiescent)


_PR_ABORT_FAILURES = ('INVALID','IDENTITY_MISSING','BUDGET_EXPIRED','POLICY_DENIED',
    'TERM_UNCONFIRMED','ESCALATION_OR_IDENTITY_UNQUALIFIED','WAIT_TIMEOUT','WAIT_ERROR',
    'PIPE_ERROR','EXIT_UNQUALIFIED','OWNER_NOT_QUIESCENT')


def _pr_abort_outcome(failures):
    ordered = tuple(v for v in _PR_ABORT_FAILURES if v in failures)
    return (ordered[0] if ordered else 'ABORT_OBSERVED'), ordered


@dataclass(frozen=True, repr=False)
class _PRDirectAbortRecord:
    """Private owned-handle observation; never group proof or effect authority."""
    version: int
    outcome: str
    identity: tuple | None
    term_attempts: int
    term_successes: int
    kill_attempts: int
    wait_calls: int
    identity_before_term: bool
    post_term_identity: str
    identity_errno: int | None
    returncode: int | None
    reaped: bool
    pipes_closed: bool
    owner_quiescent: bool
    within_budget: bool
    policy_allowed: bool
    failures: tuple
    error_stage: str | None
    error_errno: int | None

    def __post_init__(self):
        valid = 'PR_ABORT_RECORD_INVALID'
        _require(type(self.version) is int and self.version == 1
            and type(self.outcome) is str and self.outcome in ('ABORT_OBSERVED',)+_PR_ABORT_FAILURES
            and (self.identity is None or type(self.identity) is tuple and len(self.identity)==3
                and all(type(v) is int and 0<v<=2147483647 for v in self.identity)
                and len(set(self.identity))==1)
            and all(type(v) is int and v in (0,1) for v in
                (self.term_attempts,self.term_successes,self.kill_attempts,self.wait_calls))
            and all(type(v) is bool for v in (self.identity_before_term,self.reaped,self.pipes_closed,
                self.owner_quiescent,self.within_budget,self.policy_allowed))
            and type(self.post_term_identity) is str and self.post_term_identity in
                ('NOT_CHECKED','ESRCH','MATCH','MISMATCH','OTHER_ERROR','INVALID')
            and all(v is None or type(v) is int and 0<v<=65535 for v in (self.identity_errno,self.error_errno))
            and (self.returncode is None or type(self.returncode) is int and -2147483648<=self.returncode<=2147483647)
            and type(self.failures) is tuple and all(type(v) is str and v in _PR_ABORT_FAILURES for v in self.failures)
            and (self.error_stage is None or type(self.error_stage) is str and self.error_stage in
                ('IDENTITY','TERM','KILL','WAIT','PIPES','POLICY','INTERNAL')), valid)
        _require((self.outcome,self.failures)==_pr_abort_outcome(self.failures)
            and self.term_successes<=self.term_attempts
            and (not self.identity_before_term or self.identity is not None)
            and (not self.term_successes or self.identity_before_term)
            and (self.post_term_identity=='NOT_CHECKED' or self.term_successes==1)
            and (not self.reaped or self.returncode is not None)
            and (self.error_errno is None or self.error_stage is not None), valid)
        if self.post_term_identity=='ESRCH':
            _require(self.identity_errno==errno.ESRCH, valid)
        elif self.post_term_identity=='OTHER_ERROR':
            _require(self.identity_errno is not None and self.identity_errno!=errno.ESRCH, valid)
        else:
            _require(self.identity_errno is None, valid)
        if self.outcome=='ABORT_OBSERVED':
            _require(self.identity is not None and self.identity_before_term and self.term_attempts==1
                and self.term_successes==1 and self.kill_attempts==0 and self.wait_calls==1
                and self.post_term_identity=='ESRCH' and self.returncode==-int(signal.SIGTERM)
                and self.reaped and self.pipes_closed and self.owner_quiescent and self.within_budget
                and self.policy_allowed and self.error_stage is None and self.error_errno is None, valid)


def _pr_invalid_abort():
    return _PRDirectAbortRecord(1,'INVALID',None,0,0,0,0,False,'NOT_CHECKED',None,None,
        False,False,False,False,False,('INVALID',),None,None)


_PR_UNSEALED_FAILURES = ('INVALID','PROTOCOL_UNQUALIFIED','IDENTITY_UNQUALIFIED',
    'SIGNAL_OBSERVED','WAIT_TIMEOUT','WAIT_ERROR','EXIT_UNQUALIFIED','PIPE_ERROR',
    'OWNER_NOT_QUIESCENT','BUDGET_EXPIRED','POLICY_DENIED')


def _pr_unsealed_outcome(failures):
    ordered = tuple(v for v in _PR_UNSEALED_FAILURES if v in failures)
    return (ordered[0] if ordered else 'EXIT_OBSERVED'), ordered


@dataclass(frozen=True, repr=False)
class _PRIdentityQueryFacts:
    """Finite query prefix only; never an alternate identity or authority."""
    version: int
    pgid_state: str
    sid_state: str
    error_source: str | None
    error_errno: int | None

    def __post_init__(self):
        states=('NOT_CALLED','ERROR','MATCH','MISMATCH','INVALID')
        returned=('MATCH','MISMATCH','INVALID')
        valid='PR_IDENTITY_QUERY_FACTS_INVALID'
        _require(type(self.version) is int and self.version==1
            and all(type(v) is str and v in states for v in (self.pgid_state,self.sid_state))
            and (self.error_source is None or type(self.error_source) is str
                 and self.error_source in ('GETPGID','GETSID','GETPGRP'))
            and (self.error_errno is None or type(self.error_errno) is int and 0<self.error_errno<=65535),valid)
        if self.error_source=='GETPGID':
            _require(self.pgid_state=='ERROR' and self.sid_state=='NOT_CALLED',valid)
        elif self.error_source=='GETSID':
            _require(self.pgid_state in returned and self.sid_state=='ERROR',valid)
        elif self.error_source=='GETPGRP':
            _require(self.pgid_state in returned and self.sid_state in returned,valid)
        else:
            _require(self.error_errno is None and
                ((self.pgid_state==self.sid_state=='NOT_CALLED') or
                 (self.pgid_state in returned and self.sid_state in returned)),valid)


def _pr_unsealed_identity_eligible(facts):
    return (type(facts) is _PRIdentityQueryFacts and facts.error_errno==errno.ESRCH
        and ((facts.pgid_state=='ERROR' and facts.sid_state=='NOT_CALLED' and facts.error_source=='GETPGID')
             or (facts.pgid_state=='MATCH' and facts.sid_state=='ERROR' and facts.error_source=='GETSID')))


@dataclass(frozen=True, repr=False)
class _PRUnsealedExitRecord:
    """Private direct-handle observation, never effect or group authority."""
    version: int = 2
    outcome: str = 'INVALID'
    identity: tuple | None = None
    protocol_unsealed: bool = False
    go_sent: bool = False
    result_seen: bool = False
    ack_started: bool = False
    stdout_eof: bool = False
    stderr_eof: bool = False
    initial_cache_none: bool = False
    first_identity_kind: str = 'NOT_OBSERVED'
    first_identity_errno: int | None = None
    identity_observations: int = 0
    term_attempts: int = 0
    kill_attempts: int = 0
    wait_calls: int = 0
    wait_returncode: int | None = None
    cached_returncode: int | None = None
    reaped: bool = False
    pipes_closed: bool = False
    owner_quiescent: bool = False
    within_budget: bool = False
    policy_allowed: bool = False
    failures: tuple = ('INVALID',)
    error_stage: str | None = None
    error_errno: int | None = None
    identity_query_facts: _PRIdentityQueryFacts | None = None

    def __post_init__(self):
        valid = 'PR_UNSEALED_RECORD_INVALID'
        _require(type(self.version) is int and self.version==2
            and type(self.outcome) is str and self.outcome in ('EXIT_OBSERVED',)+_PR_UNSEALED_FAILURES
            and (self.identity is None or type(self.identity) is tuple and len(self.identity)==3
                and all(type(v) is int and 0<v<=2147483647 for v in self.identity)
                and len(set(self.identity))==1)
            and all(type(v) is bool for v in (self.protocol_unsealed,self.go_sent,self.result_seen,
                self.ack_started,self.stdout_eof,self.stderr_eof,self.initial_cache_none,self.reaped,
                self.pipes_closed,self.owner_quiescent,self.within_budget,self.policy_allowed))
            and type(self.first_identity_kind) is str and self.first_identity_kind in
                ('NOT_OBSERVED','LOOKUP_ERROR','MATCH','MISMATCH','MISSING','INVALID')
            and type(self.identity_observations) is int and 0<=self.identity_observations<=2
            and all(type(v) is int and v in (0,1) for v in
                (self.term_attempts,self.kill_attempts,self.wait_calls))
            and all(v is None or type(v) is int and -2147483648<=v<=2147483647
                for v in (self.wait_returncode,self.cached_returncode))
            and all(v is None or type(v) is int and 0<v<=65535
                for v in (self.first_identity_errno,self.error_errno))
            and type(self.failures) is tuple and all(type(v) is str and v in _PR_UNSEALED_FAILURES for v in self.failures)
            and (self.error_stage is None or type(self.error_stage) is str and self.error_stage in
                ('PROVENANCE','IDENTITY','WAIT','PIPES','POLICY','INTERNAL')), valid)
        _require((self.identity_query_facts is None or type(self.identity_query_facts) is _PRIdentityQueryFacts)
            and (self.identity_observations!=0 or self.identity_query_facts is None)
            and (self.outcome,self.failures)==_pr_unsealed_outcome(self.failures)
            and (self.first_identity_errno is None or self.first_identity_kind=='LOOKUP_ERROR')
            and ((self.first_identity_kind=='NOT_OBSERVED') == (self.identity_observations==0))
            and (self.error_errno is None or self.error_stage is not None)
            and (self.wait_returncode is None or self.wait_calls==1)
            and (not self.reaped or self.wait_calls==1 and self.wait_returncode is not None
                 and self.wait_returncode==self.cached_returncode), valid)
        if self.outcome=='EXIT_OBSERVED':
            _require(self.identity is not None and self.protocol_unsealed and self.go_sent
                and not self.result_seen and not self.ack_started and self.stdout_eof and self.stderr_eof
                and self.initial_cache_none and self.first_identity_kind=='LOOKUP_ERROR'
                and self.first_identity_errno==errno.ESRCH and self.identity_observations==1
                and _pr_unsealed_identity_eligible(self.identity_query_facts)
                and self.term_attempts==self.kill_attempts==0 and self.wait_calls==1
                and self.wait_returncode==self.cached_returncode==0 and self.reaped
                and self.pipes_closed and self.owner_quiescent and self.within_budget and self.policy_allowed
                and self.error_stage is None and self.error_errno is None, valid)


_PR_REJECTED_FAILURES = ('PROTOCOL_UNQUALIFIED','IDENTITY_UNQUALIFIED','SIGNAL_OBSERVED',
    'WAIT_UNQUALIFIED','PIPE_ERROR','OWNER_UNQUALIFIED','BUDGET_EXPIRED','POLICY_DENIED','BINDING_INVALID')


def _pr_rejection_valid(frame, nonce, limit):
    return (type(frame) is dict and set(frame)=={'version','kind','rejection_version',
        'rejection_nonce','reason','response_limit'} and type(frame['version']) is int
        and frame['version']==1 and frame['kind']=='rejected'
        and type(frame['rejection_version']) is int and frame['rejection_version']==1
        and type(frame['rejection_nonce']) is str and frame['rejection_nonce']==nonce
        and re.fullmatch('[0-9a-f]{32}',frame['rejection_nonce']) is not None
        and frame['reason']=='RESPONSE_BODY_LIMIT' and type(frame['response_limit']) is int
        and type(limit) is int and 0<limit<=MAX_BODY and frame['response_limit']==limit)


@dataclass(frozen=True, repr=False)
class _PRRejectedResponseExitRecord:
    """Trusted-worker report plus owned exit; NOT remote/group/retry authority."""
    version: int = 1
    outcome: str = 'UNKNOWN'
    reason: str = 'RESPONSE_BODY_LIMIT'
    response_limit: int = 1
    rejection_nonce: str = '0'*32
    identity: tuple | None = None
    go_sent: bool = False
    rejection_seen: bool = False
    result_seen: bool = False
    ack_started: bool = False
    stdout_eof: bool = False
    stderr_eof: bool = False
    initial_cache_none: bool = False
    first_identity_kind: str = 'NOT_OBSERVED'
    first_identity_errno: int | None = None
    identity_query_facts: _PRIdentityQueryFacts | None = None
    identity_observations: int = 0
    term_attempts: int = 0
    kill_attempts: int = 0
    wait_calls: int = 0
    wait_returncode: int | None = None
    cached_returncode: int | None = None
    reaped: bool = False
    pipes_closed: bool = False
    owner_quiescent: bool = False
    within_budget: bool = False
    policy_allowed: bool = False
    failures: tuple = ('BINDING_INVALID',)

    def __post_init__(self):
        valid='PR_REJECTED_RECORD_INVALID'
        _require(type(self.version) is int and self.version==1
            and type(self.outcome) is str and self.outcome in ('UNKNOWN','REJECTION_EXIT_OBSERVED')
            and type(self.reason) is str and self.reason=='RESPONSE_BODY_LIMIT'
            and type(self.response_limit) is int and 0<self.response_limit<=MAX_BODY
            and type(self.rejection_nonce) is str and re.fullmatch('[0-9a-f]{32}',self.rejection_nonce)
            and (self.identity is None or type(self.identity) is tuple and len(self.identity)==3
                and all(type(v) is int and 0<v<=2147483647 for v in self.identity)
                and len(set(self.identity))==1)
            and all(type(v) is bool for v in (self.go_sent,self.rejection_seen,self.result_seen,
                self.ack_started,self.stdout_eof,self.stderr_eof,self.initial_cache_none,self.reaped,
                self.pipes_closed,self.owner_quiescent,self.within_budget,self.policy_allowed))
            and type(self.first_identity_kind) is str and self.first_identity_kind in
                ('NOT_OBSERVED','LOOKUP_ERROR','MATCH','MISMATCH','MISSING','INVALID')
            and (self.first_identity_errno is None or type(self.first_identity_errno) is int
                and 0<self.first_identity_errno<=65535 and self.first_identity_kind=='LOOKUP_ERROR')
            and (self.identity_query_facts is None or type(self.identity_query_facts) is _PRIdentityQueryFacts)
            and type(self.identity_observations) is int and 0<=self.identity_observations<=2
            and ((self.first_identity_kind=='NOT_OBSERVED')==(self.identity_observations==0))
            and (self.identity_observations!=0 or self.identity_query_facts is None)
            and all(type(v) is int and v in (0,1) for v in (self.term_attempts,self.kill_attempts,self.wait_calls))
            and all(v is None or type(v) is int and -2147483648<=v<=2147483647
                for v in (self.wait_returncode,self.cached_returncode))
            and (self.wait_returncode is None or self.wait_calls==1)
            and (not self.reaped or self.wait_calls==1 and self.wait_returncode is not None
                and self.wait_returncode==self.cached_returncode)
            and type(self.failures) is tuple
            and self.failures==tuple(v for v in _PR_REJECTED_FAILURES if v in self.failures)
            and (self.outcome=='REJECTION_EXIT_OBSERVED')==(not self.failures),valid)
        if self.outcome=='REJECTION_EXIT_OBSERVED':
            _require(self.identity is not None and self.go_sent and self.rejection_seen
                and not self.result_seen and not self.ack_started and self.stdout_eof and self.stderr_eof
                and self.initial_cache_none and self.first_identity_kind=='LOOKUP_ERROR'
                and self.first_identity_errno==errno.ESRCH and self.identity_observations==1
                and _pr_unsealed_identity_eligible(self.identity_query_facts)
                and self.term_attempts==self.kill_attempts==0 and self.wait_calls==1
                and self.wait_returncode==self.cached_returncode==1 and self.reaped
                and self.pipes_closed and self.owner_quiescent and self.within_budget and self.policy_allowed,valid)


def _pr_unsealed_snapshot_matches(snapshot, process, budget):
    return (type(snapshot) is tuple and len(snapshot)==8 and snapshot[0] is process
        and snapshot[1] is budget and all(type(v) is bool for v in snapshot[2:7])
        and type(snapshot[7]) is str and snapshot[7] in ('PR_IPC_TRUNCATED','OTHER'))


def _pr_identity_details(process):
    # Cached None is not identity evidence. Never poll (which may reap) here.
    if process.returncode is not None:
        return (None, 'MISSING', None), None
    pid = process.pid
    if type(pid) is not int or not 0 < pid <= 2147483647:
        return (None, 'INVALID', None), None
    pgid_done=sid_done=False
    pgid=sid=None
    source=None
    number=None
    try:
        source='GETPGID'; pgid=os.getpgid(pid); pgid_done=True
        source='GETSID'; sid=os.getsid(pid); sid_done=True
        source=None
        identity = (pid, pgid, sid)
        legacy=(None,'MISMATCH',None)
        if identity == (pid,pid,pid):
            source='GETPGRP'
            if pid != os.getpgrp(): legacy=(identity,'MATCH',None)
        source=None
    except OSError as error:
        number = error.errno
        number=number if type(number) is int and 0<number<=65535 else None
        legacy=(None,'LOOKUP_ERROR',number)
    # Only after the unchanged query/comparison sequence: no prefix short circuit.
    def returned(value):
        if type(value) is not int or not 0<value<=2147483647: return 'INVALID'
        return 'MATCH' if value==pid else 'MISMATCH'
    try:
        facts=_PRIdentityQueryFacts(1,
            returned(pgid) if pgid_done else 'ERROR' if source=='GETPGID' else 'NOT_CALLED',
            returned(sid) if sid_done else 'ERROR' if source=='GETSID' else 'NOT_CALLED',
            source,number)
    except Exception:
        facts=None  # Metadata cannot alter legacy error handling or stop cleanup.
    return legacy,facts


def _pr_identity_observation(process):
    return _pr_identity_details(process)[0]


def _pr_identity(process):
    return _pr_identity_observation(process)[0]


class _PRLaunch:
    """One locked handoff and cleanup claimant, never a takeover/retry service."""
    def __init__(self, *, request_budget=None, selected_handle_only=False):
        _require(request_budget is None or type(request_budget) is _PRBudget, 'PR_BINDING_BUDGET_REQUIRED')
        _require(type(selected_handle_only) is bool and
            (not selected_handle_only or type(request_budget) is _PRBudget), 'PR_BINDING_BUDGET_REQUIRED')
        self._selected_handle_only = selected_handle_only
        if request_budget is not None:
            _require(all(type(v) in (int,float) and math.isfinite(v) for v in
                (request_budget.started,request_budget.operation_end,request_budget.end,request_budget.now))
                and request_budget.started <= request_budget.operation_end < request_budget.end,
                'PR_BINDING_BUDGET_REQUIRED')
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.launcher_done = threading.Event()
        self.cleanup_done = threading.Event()
        self.cancelled = False
        self.process = None
        self.identity = None
        self.owner = 'launcher'
        self.phase = 'LAUNCH_PENDING'
        self.claimant = None
        self.record = _PRCleanupRecord()
        self._protocol_budget = None
        self._direct_finalization = None
        self._request_budget = request_budget
        self._original_request_budget = request_budget
        self._direct_abort = None
        self._abort_context = None
        self._unsealed_protocol = None
        self._unsealed_exit = None
        self._unsealed_context = None
        self._rejection_binding = None
        self._rejected_protocol = None
        self._rejected_exit = None
        self._rejected_context = None

    def finish_direct_abort(self, claimant, legacy, record, *, unsealed_record=None, rejected_record=None):
        """One paired publication, backed by this claimant's local observations."""
        with self.lock:
            _require(claimant is self.claimant and self.phase=='CLEANUP_PENDING'
                and self.owner=='parent' and self._direct_abort is None, 'PR_CLEANUP_OWNER_INVALID')
            context = self._abort_context
            valid = (context is not None and context[0] is claimant and context[1] is self.process
                and context[2] == self.identity and context[3] is self._request_budget
                and context[3] is self._original_request_budget
                and type(context[3]) is _PRBudget and context[4] is record and context[5] is legacy
                and self._protocol_budget is None and self._direct_finalization is None
                and type(record) is _PRDirectAbortRecord and type(legacy) is _PRCleanupRecord
                and record.identity == legacy.identity == self.identity
                and record.pipes_closed == legacy.pipes_closed
                and record.owner_quiescent == legacy.quiescent)
            if valid and record.outcome=='ABORT_OBSERVED':
                valid = (legacy.status=='UNKNOWN' and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN'
                    and legacy.reaped and record.reaped and self.process is not None
                    and record.identity == (self.process.pid,)*3
                    and type(self.process.returncode) is int and record.returncode == self.process.returncode)
            if valid and time.monotonic()>=context[3].end:
                outcome, failures = _pr_abort_outcome(record.failures+('BUDGET_EXPIRED',))
                record = replace(record,outcome=outcome,failures=failures,within_budget=False)
                self._abort_context = (*context[:4],record,legacy)
            self._direct_abort = record if valid else _pr_invalid_abort()
            self.record = legacy if type(legacy) is _PRCleanupRecord and legacy.status=='UNKNOWN' else _PRCleanupRecord('UNKNOWN','INVALID')
            if unsealed_record is not None:
                uc = self._unsealed_context
                uv = (valid and type(uc) is tuple and len(uc)==9 and uc[0] is claimant
                    and uc[1] is self.process and uc[2] is self.identity
                    and uc[3] is self._original_request_budget and uc[3] is self._request_budget
                    and uc[4] is self._unsealed_protocol and uc[5] is legacy
                    and uc[6] is context[4] and uc[8] is unsealed_record
                    and type(unsealed_record) is _PRUnsealedExitRecord
                    and uc[7] is unsealed_record.identity_query_facts
                    and unsealed_record.identity==self.identity
                    and unsealed_record.pipes_closed==legacy.pipes_closed
                    and unsealed_record.owner_quiescent==legacy.quiescent)
                if uv and unsealed_record.outcome=='EXIT_OBSERVED':
                    uv = (record.outcome!='ABORT_OBSERVED' and legacy.status=='UNKNOWN'
                        and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN' and legacy.reaped
                        and _pr_unsealed_snapshot_matches(uc[4],self.process,uc[3])
                        and uc[4][2:]==(True,False,False,True,True,'PR_IPC_TRUNCATED')
                        and _pr_unsealed_identity_eligible(uc[7])
                        and self.process is not None and type(self.process.returncode) is int
                        and self.process.returncode==0 and self.identity==(self.process.pid,)*3)
                if uv and not time.monotonic()<uc[3].end:
                    outcome, reasons = _pr_unsealed_outcome(unsealed_record.failures+('BUDGET_EXPIRED',))
                    unsealed_record=replace(unsealed_record,outcome=outcome,failures=reasons,within_budget=False)
                self._unsealed_exit=unsealed_record if uv else _PRUnsealedExitRecord()
                self._unsealed_context=(*uc[:6],self._direct_abort,uc[7],self._unsealed_exit) if uv else None
            if rejected_record is not None:
                rc=self._rejected_context
                rv=(valid and type(rc) is tuple and len(rc)==9 and rc[0] is claimant
                    and rc[1] is self.process and rc[2] is self.identity
                    and rc[3] is self._request_budget and rc[3] is self._original_request_budget
                    and rc[4] is self._rejected_protocol and rc[5] is legacy
                    and rc[6] is context[4] and rc[8] is rejected_record
                    and type(rejected_record) is _PRRejectedResponseExitRecord
                    and rc[7] is rejected_record.identity_query_facts
                    and rejected_record.identity==self.identity
                    and rejected_record.pipes_closed==legacy.pipes_closed
                    and rejected_record.owner_quiescent==legacy.quiescent)
                if rv and rejected_record.outcome=='REJECTION_EXIT_OBSERVED':
                    rv=(self._rejection_protocol_valid(rc[4]) and legacy.status=='UNKNOWN'
                        and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN' and legacy.reaped
                        and type(self.process.returncode) is int and self.process.returncode==1
                        and self.identity==(self.process.pid,)*3 and _pr_unsealed_identity_eligible(rc[7]))
                if rv and not time.monotonic()<rc[3].end:
                    reasons=tuple(v for v in _PR_REJECTED_FAILURES
                                  if v in rejected_record.failures or v=='BUDGET_EXPIRED')
                    rejected_record=replace(rejected_record,outcome='UNKNOWN',failures=reasons,within_budget=False)
                self._rejected_exit=rejected_record if rv else _PRRejectedResponseExitRecord()
                self._rejected_context=(*rc[:6],self._direct_abort,rc[7],self._rejected_exit) if rv else None
            self.phase = 'CLEANUP_UNKNOWN'
            self.cleanup_done.set()
            return self.record

    @property
    def direct_child_abort_completion(self):
        """Point-in-time diagnostic. No queries, wait, signals or authority."""
        with self.lock:
            record, legacy, budget, process = self._direct_abort, self.record, self._request_budget, self.process
            context = self._abort_context
            valid = (type(record) is _PRDirectAbortRecord and record.outcome=='ABORT_OBSERVED'
                and type(legacy) is _PRCleanupRecord and context is not None
                and context[0] is self.claimant and self.claimant is not None
                and context[1] is process and context[2]==self.identity and context[3] is budget
                and context[4] is record and context[5] is legacy and type(budget) is _PRBudget
                and budget is self._original_request_budget
                and self.owner=='parent' and self.phase=='CLEANUP_UNKNOWN'
                and self._protocol_budget is None and self._direct_finalization is None
                and self.launcher_done.is_set() and self.cleanup_done.is_set()
                and legacy.status=='UNKNOWN' and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN'
                and legacy.reaped and legacy.pipes_closed and legacy.quiescent
                and record.identity==legacy.identity==self.identity
                and process is not None and record.identity==(process.pid,)*3
                and type(process.returncode) is int and process.returncode==record.returncode)
            if not valid: return 'UNKNOWN'
        try:
            current=time.monotonic()
            if current>=budget.end: return 'UNKNOWN'
            decision=rse.evaluate_policy(budget.action,budget.policies,budget.authorization,
                                         budget.now+current-budget.started)
            if decision.disposition!='ALLOW': return 'UNKNOWN'
            with self.lock:
                if (self._direct_abort is record and self.record is legacy and self._abort_context is context
                    and self._request_budget is budget and self._original_request_budget is budget and self.process is process
                    and self.claimant is context[0] and self.owner=='parent' and self.phase=='CLEANUP_UNKNOWN'
                    and self._protocol_budget is None and self._direct_finalization is None
                    and self.launcher_done.is_set() and self.cleanup_done.is_set()
                    and self.identity==record.identity and type(process.returncode) is int
                    and process.returncode==record.returncode and time.monotonic()<budget.end):
                    return 'DIRECT_CHILD_ABORT_COMPLETION'
        except Exception:
            pass
        return 'UNKNOWN'

    def note_unsealed_protocol(self, process, budget, *, go_sent, result_seen,
                               ack_started, stdout_eof, stderr_eof, error_code):
        """Wrapper-local progress only; does not seal or grant authority."""
        snapshot=(process,budget,go_sent,result_seen,ack_started,stdout_eof,stderr_eof,error_code)
        _require(_pr_unsealed_snapshot_matches(snapshot,process,budget), 'PR_UNSEALED_PROTOCOL_INVALID')
        with self.lock:
            _require(self.phase=='PARENT_CLAIMED' and self.owner=='parent' and self.claimant is None
                and self.process is process and process is not None and type(budget) is _PRBudget
                and budget is self._request_budget and budget is self._original_request_budget
                and self._protocol_budget is None and self._unsealed_protocol is None,
                'PR_UNSEALED_PROTOCOL_INVALID')
            self._unsealed_protocol=snapshot

    def _unsealed_bound(self, context):
        """Called only under lock; no observations beyond cached fields."""
        if not (type(context) is tuple and len(context)==9): return False
        token,process,identity,budget,snapshot,legacy,abort,facts,record=context
        return (self._unsealed_context is context and token is self.claimant and token is not None
            and process is self.process and identity is self.identity
            and budget is self._request_budget and budget is self._original_request_budget
            and type(budget) is _PRBudget and snapshot is self._unsealed_protocol
            and legacy is self.record and abort is self._direct_abort and record is self._unsealed_exit
            and type(record) is _PRUnsealedExitRecord and record.outcome=='EXIT_OBSERVED'
            and record.identity_query_facts is facts and _pr_unsealed_identity_eligible(facts)
            and type(abort) is _PRDirectAbortRecord and abort.outcome!='ABORT_OBSERVED'
            and type(legacy) is _PRCleanupRecord and legacy.status=='UNKNOWN'
            and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN'
            and legacy.reaped and legacy.pipes_closed and legacy.quiescent
            and record.identity==legacy.identity==abort.identity==identity
            and self.owner=='parent' and self.phase=='CLEANUP_UNKNOWN'
            and self.launcher_done.is_set() and self.cleanup_done.is_set()
            and self._protocol_budget is None and self._direct_finalization is None
            and _pr_unsealed_snapshot_matches(snapshot,process,budget)
            and snapshot[2:]==(True,False,False,True,True,'PR_IPC_TRUNCATED')
            and process is not None and identity==(process.pid,)*3
            and type(process.returncode) is int and process.returncode==0)

    @property
    def unsealed_direct_child_exit_observation(self):
        """Point-in-time direct exit only; quarantine and uncertainty persist."""
        with self.lock:
            context=self._unsealed_context
            if not self._unsealed_bound(context): return 'UNKNOWN'
            budget=context[3]
        try:
            current=time.monotonic()
            if not math.isfinite(current) or not current<budget.end: return 'UNKNOWN'
            decision=rse.evaluate_policy(budget.action,budget.policies,budget.authorization,
                                         budget.now+current-budget.started)
            if decision.disposition!='ALLOW': return 'UNKNOWN'
            with self.lock:
                if self._unsealed_bound(context) and time.monotonic()<budget.end:
                    return 'UNSEALED_DIRECT_CHILD_EXIT_OBSERVED'
        except Exception:
            pass
        return 'UNKNOWN'

    def _rejection_protocol_valid(self, snapshot):
        """Caller holds lock. Compare original objects, never reconstruct provenance."""
        binding=self._rejection_binding
        return (type(binding) is tuple and len(binding)==4 and binding[0] is self.process
            and binding[1] is self._request_budget and binding[1] is self._original_request_budget
            and type(snapshot) is tuple and len(snapshot)==8 and snapshot[0] is binding
            and all(type(v) is bool for v in snapshot[2:])
            and snapshot[2:]==(True,False,False,True,True,True)
            and _pr_rejection_valid(snapshot[1],binding[2],binding[3]))

    def _rejected_bound(self, context):
        if not (type(context) is tuple and len(context)==9): return False
        token,process,identity,budget,snapshot,legacy,abort,facts,record=context
        return (context is self._rejected_context and token is self.claimant and token is not None
            and process is self.process and identity is self.identity
            and budget is self._request_budget and budget is self._original_request_budget
            and type(budget) is _PRBudget and snapshot is self._rejected_protocol
            and legacy is self.record and abort is self._direct_abort and record is self._rejected_exit
            and type(record) is _PRRejectedResponseExitRecord and record.outcome=='REJECTION_EXIT_OBSERVED'
            and record.identity_query_facts is facts and _pr_unsealed_identity_eligible(facts)
            and self._rejection_protocol_valid(snapshot)
            and (record.rejection_nonce,record.response_limit)==self._rejection_binding[2:]
            and type(legacy) is _PRCleanupRecord and legacy.status=='UNKNOWN'
            and legacy.stage=='IDENTITY' and legacy.group=='UNKNOWN'
            and legacy.reaped and legacy.pipes_closed and legacy.quiescent
            and type(abort) is _PRDirectAbortRecord and abort.outcome!='ABORT_OBSERVED'
            and record.identity==legacy.identity==abort.identity==identity
            and self.owner=='parent' and self.phase=='CLEANUP_UNKNOWN'
            and self.launcher_done.is_set() and self.cleanup_done.is_set()
            and self._protocol_budget is None and self._direct_finalization is None
            and process is not None and identity==(process.pid,)*3
            and type(process.returncode) is int and process.returncode==1)

    @property
    def rejected_response_direct_child_exit_observation(self):
        with self.lock:
            context=self._rejected_context
            if not self._rejected_bound(context): return 'UNKNOWN'
            budget=context[3]
        try:
            current=time.monotonic()
            if not math.isfinite(current) or not current<budget.end: return 'UNKNOWN'
            decision=rse.evaluate_policy(budget.action,budget.policies,budget.authorization,
                                         budget.now+current-budget.started)
            if decision.disposition!='ALLOW': return 'UNKNOWN'
            with self.lock:
                if self._rejected_bound(context) and time.monotonic()<budget.end:
                    return 'REJECTED_RESPONSE_DIRECT_CHILD_EXIT_OBSERVED'
        except Exception:
            pass
        return 'UNKNOWN'

    def note_protocol_complete(self, budget):
        """Trusted wrapper bookkeeping only; never a cleanup/authority grant."""
        _require(type(budget) is _PRBudget, 'PR_PROTOCOL_COMPLETION_INVALID')
        budget.check()
        with self.lock:
            _require(self.phase == 'PARENT_CLAIMED' and self.owner == 'parent'
                and self.claimant is None and self._protocol_budget is None,
                'PR_PROTOCOL_COMPLETION_INVALID')
            self._protocol_budget = budget

    @property
    def direct_worker_completion(self):
        """Experimental direct-handle diagnostic, NOT group extinction.

        This does not clear cleaned/quarantine or establish a trusted runtime
        closure. No result consumer may use it as execution/retry authority.
        """
        with self.lock:
            budget, record, process = self._protocol_budget, self.record, self.process
            direct = self._direct_finalization
            stage_ok = type(record) is _PRCleanupRecord and record.stage == 'COMPLETE' and direct is None
            if type(record) is _PRCleanupRecord and record.stage == 'DIRECT_FINALIZATION':
                stage_ok = (type(direct) is _PRDirectFinalizationRecord and direct.outcome == 'COMPLETE'
                    and self.phase == 'CLEANUP_UNKNOWN' and record.status == 'UNKNOWN'
                    and record.group == 'UNKNOWN' and direct.identity == record.identity == self.identity
                    and direct.reaped == record.reaped and direct.pipes_closed == record.pipes_closed
                    and direct.quiescent == record.quiescent and direct.errno == record.errno
                    and direct.returncode == 0)
            if not (type(budget) is _PRBudget and type(record) is _PRCleanupRecord
                    and self.owner == 'parent' and self.claimant is not None
                    and self.phase in ('CLEANUP_UNKNOWN','CLEANUP_CONFIRMED')
                    and self.launcher_done.is_set() and self.cleanup_done.is_set()
                    and record.status != 'PENDING' and stage_ok
                    and record.errno is None and record.identity is not None
                    and process is not None and record.identity == (process.pid,)*3
                    and record.reaped and record.pipes_closed and record.quiescent
                    and type(process.returncode) is int and process.returncode == 0):
                return 'UNKNOWN'
        try:
            current = time.monotonic()
            decision = rse.evaluate_policy(budget.action, budget.policies, budget.authorization,
                                          budget.now+current-budget.started)
            if current < budget.end and decision.disposition == 'ALLOW':
                return 'DIRECT_WORKER_COMPLETION'
        except Exception:
            pass
        return 'UNKNOWN'

    def publish(self, process):
        identity = _pr_identity(process)
        with self.lock:
            _require(self.phase == 'LAUNCH_PENDING' and self.process is None, 'PR_HANDOFF_INVALID')
            self.process, self.identity = process, identity
            if self.cancelled:
                self.phase = 'LAUNCHER_HELD'
            else:
                self.phase, self.owner = 'PUBLISHED_PARENT', 'parent'

    def claim_parent(self):
        with self.lock:
            self.cancelled = True
            if self.phase == 'PUBLISHED_PARENT' and self.owner == 'parent':
                self.phase = 'PARENT_CLAIMED'
                return self.process
            return None

    def begin_cleanup(self, owner):
        with self.lock:
            if (owner != self.owner or self.claimant is not None
                    or (self.phase, owner) not in (('LAUNCHER_HELD','launcher'),('PARENT_CLAIMED','parent'))):
                return None
            self.claimant = object()
            self.phase = 'CLEANUP_PENDING'
            self.record = _PRCleanupRecord(identity=self.identity)
            return self.claimant, self.process, self.identity

    def finish_cleanup(self, claimant, record):
        with self.lock:
            _require(claimant is self.claimant and self.phase == 'CLEANUP_PENDING', 'PR_CLEANUP_OWNER_INVALID')
            if type(record) is not _PRCleanupRecord or record.status == 'PENDING':
                record = _PRCleanupRecord('UNKNOWN','INVALID')
            self.record = record
            self.phase = 'CLEANUP_CONFIRMED' if _pr_cleanup_confirmed(record) else 'CLEANUP_UNKNOWN'
            self.cleanup_done.set()
            return self.record

    def snapshot(self):
        with self.lock:
            return self.phase, self.owner, self.record

    def finish_direct_finalization(self, claimant, record):
        """Publish paired facts once, under the existing sole-owner lock."""
        with self.lock:
            _require(claimant is self.claimant and self.phase == 'CLEANUP_PENDING'
                     and self.owner == 'parent' and type(self._protocol_budget) is _PRBudget
                     and self._direct_finalization is None, 'PR_CLEANUP_OWNER_INVALID')
            valid = (type(record) is _PRDirectFinalizationRecord and self.process is not None
                and record.identity == self.identity and record.quiescent
                and (record.identity is None or record.identity == (self.process.pid,)*3)
                and (not record.reaped or type(self.process.returncode) is int
                     and record.returncode == self.process.returncode))
            if valid:
                paired = _PRCleanupRecord('UNKNOWN','DIRECT_FINALIZATION',record.errno,
                    record.identity,record.reaped,'UNKNOWN',record.pipes_closed,record.quiescent)
                self._direct_finalization = record
            else:
                paired = _PRCleanupRecord('UNKNOWN','INVALID')
                self._direct_finalization = _PRDirectFinalizationRecord()
            self.record = paired
            self.phase = 'CLEANUP_UNKNOWN'
            self.cleanup_done.set()
            return paired

    @property
    def cleaned(self):
        with self.lock:
            return self.phase == 'CLEANUP_CONFIRMED' and _pr_cleanup_confirmed(self.record)


def _pr_finalize_direct(state, token, process, identity, budget, deadline):
    """No numeric lookup, signal, retry or budget reset, even on failure."""
    invalid = type(deadline) not in (int,float) or deadline != budget.end
    missing = identity is None
    wait_failure = None; pipe_failure = False; number = None
    reaped = False; code = None; pipes_closed = True
    def remember(error):
        nonlocal number
        value = getattr(error,'errno',None)
        if number is None and isinstance(error,OSError) and type(value) is int and 0<value<=65535:
            number = value
    try:
        if process is None:
            invalid = True
        else:
            remaining = budget.end-time.monotonic()
            if process.returncode is None and remaining > 0:
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired as error:
                    wait_failure = 'WAIT_TIMEOUT'; remember(error)
                except Exception as error:
                    wait_failure = 'WAIT_ERROR'; remember(error)
            raw = process.returncode
            code = raw if type(raw) is int else None
            reaped = type(raw) is int
            if (raw is not None and type(raw) is not int) or (remaining > 0 and not reaped and wait_failure is None):
                invalid = True
    except Exception as error:
        invalid = True; remember(error)
    finally:
        for name in ('stdin','stdout','stderr'):
            try: getattr(process,name).close()
            except Exception as error:
                pipes_closed = False; pipe_failure = True; remember(error)
    current = time.monotonic()
    within_budget = current < budget.end
    try:
        decision = rse.evaluate_policy(budget.action,budget.policies,budget.authorization,
                                       budget.now+current-budget.started)
        allowed = decision.disposition == 'ALLOW'
    except Exception:
        allowed = False
    # Policy evaluation itself may consume time; it cannot extend completion.
    within_budget = within_budget and time.monotonic() < budget.end
    outcome = ('INVALID' if invalid else 'IDENTITY_MISSING' if missing else
        'BUDGET_EXPIRED' if not within_budget else wait_failure if wait_failure else
        'PIPE_ERROR' if pipe_failure else 'NONZERO_EXIT' if code != 0 else
        'POLICY_DENIED' if not allowed else 'COMPLETE')
    record = _PRDirectFinalizationRecord(outcome,identity,code,reaped,pipes_closed,True,
                                         within_budget,allowed,number)
    return state.finish_direct_finalization(token,record)


def _pr_cleanup_selected_handle(state, token, process, identity, owner, deadline):
    """Selected cooperative cleanup only; Popen is not a kernel identity capability.

    Never query/signal a numeric identity or promote exceptional completion.
    A TERM grace wait and optional KILL wait share the original deadline.
    """
    with state.lock:
        budget = state._original_request_budget
        valid = (type(budget) is _PRBudget and state._request_budget is budget
            and state.process is process and process is not None and state.claimant is token
            and state.owner == owner and state.phase == 'CLEANUP_PENDING'
            and type(deadline) in (int,float) and deadline == budget.end
            and (state._protocol_budget is None or state._protocol_budget is budget))
        sealed = valid and owner == 'parent' and state._protocol_budget is budget
    if not valid:
        return state.finish_cleanup(token, _PRCleanupRecord('UNKNOWN','INVALID'))
    if sealed:
        return _pr_finalize_direct(state,token,process,identity,budget,deadline)
    stage = 'COMPLETE'; number = None; pipes_closed = True; reaped = False
    interruption = None; at = 'TERM'
    def fail(where, error=None):
        nonlocal stage, number, interruption
        if stage == 'COMPLETE':
            stage = where
            value = getattr(error,'errno',None)
            number = value if type(value) is int and 0 <= value <= 65535 else None
        if error is not None and not isinstance(error,Exception) and interruption is None:
            interruption = error
    try:
        if process.returncode is not None:
            reaped = type(process.returncode) is int
            if not reaped: fail('INVALID')
        elif time.monotonic() >= budget.end:
            fail('WAIT')
        else:
            process.terminate()
            at = 'WAIT'
            remaining = budget.end-time.monotonic()
            if remaining <= 0:
                fail('WAIT')
            else:
                try:
                    code = process.wait(timeout=min(.25,remaining))
                except subprocess.TimeoutExpired:
                    remaining = budget.end-time.monotonic()
                    if remaining <= 0 or process.returncode is not None:
                        fail('WAIT')
                    else:
                        at = 'KILL'; process.kill(); at = 'WAIT'
                        remaining = budget.end-time.monotonic()
                        if remaining <= 0:
                            fail('WAIT')
                        else:
                            code = process.wait(timeout=remaining)
                if stage == 'COMPLETE':
                    reaped = type(code) is int and type(process.returncode) is int and code == process.returncode
                    if not reaped: fail('WAIT')
    except BaseException as error:
        fail(at,error)
    finally:
        for name in ('stdin','stdout','stderr'):
            try: getattr(process,name).close()
            except BaseException as error:
                pipes_closed = False; fail('PIPES',error)
    if time.monotonic() >= budget.end: fail('WAIT')
    record = state.finish_cleanup(token, _PRCleanupRecord('UNKNOWN',stage,number,
        identity,reaped,'UNKNOWN',pipes_closed,True))
    if interruption is not None: raise interruption
    return record


def _pr_cleanup(state, owner, deadline):
    """Only the claimant may signal/wait/close. No group probe after reap.

    Numeric identity checks have a race window; they are not kernel identity
    capabilities. Without an approved group-proof predicate, remain UNKNOWN.
    """
    claim = state.begin_cleanup(owner)
    if claim is None:
        return state.snapshot()[2]
    token, process, identity = claim
    if state._selected_handle_only:
        return _pr_cleanup_selected_handle(state,token,process,identity,owner,deadline)
    with state.lock:
        budget = state._protocol_budget if owner == 'parent' else None
    if type(budget) is _PRBudget:
        return _pr_finalize_direct(state,token,process,identity,budget,deadline)
    with state.lock:
        abort_budget = state._request_budget if owner=='parent' else None
        unsealed_snapshot = state._unsealed_protocol
    observe = type(abort_budget) is _PRBudget
    initial_cache_none = process.returncode is None
    first_kind = 'NOT_OBSERVED'; first_errno = None; identity_observations = 0
    first_query_facts = None
    exit_error_stage = exit_error_errno = None
    def remember_exit(at, error=None, number=None):
        nonlocal exit_error_stage, exit_error_errno
        if exit_error_stage is None:
            exit_error_stage=at
            value=number if error is None else getattr(error,'errno',None)
            exit_error_errno=value if type(value) is int and 0<value<=65535 else None
    failures = []
    term_attempts = term_successes = kill_attempts = wait_calls = 0
    before_term = False; post_identity = 'NOT_CHECKED'; identity_errno = None
    waited = False; code = None; wait_value = None
    error_stage = error_errno = None
    def remember(at, error):
        nonlocal error_stage, error_errno
        remember_exit(at if at in ('IDENTITY','WAIT','PIPES','POLICY','INTERNAL') else 'INTERNAL',error)
        if error_stage is None:
            error_stage = at
            value = getattr(error,'errno',None)
            error_errno = value if type(value) is int and 0<value<=65535 else None
    if observe:
        finite = type(deadline) in (int,float) and math.isfinite(deadline)
        if not finite or deadline != abort_budget.end: failures.append('INVALID')
        deadline = min(deadline,abort_budget.end) if finite else abort_budget.end
    stage = 'COMPLETE'; number = None; reaped = False; pipes_closed = True
    group = 'UNKNOWN'
    def failure(at, error=None):
        nonlocal stage, number
        if stage == 'COMPLETE':
            stage = at
            value = getattr(error,'errno',None)
            number = value if type(value) is int and 0 <= value <= 65535 else None
    try:
        if process.returncode is not None:
            reaped = True
            failure('IDENTITY')
        else:
            for sig, at in ((signal.SIGTERM,'TERM'),(signal.SIGKILL,'KILL')):
                observed, kind, identity_error = (None,'MISSING',None)
                if identity is not None:
                    (observed, kind, identity_error), query_facts = _pr_identity_details(process)
                    identity_observations += 1
                    if identity_observations==1:
                        first_kind,first_errno=kind,identity_error
                        first_query_facts=query_facts
                    if kind=='LOOKUP_ERROR' and identity_error!=errno.ESRCH:
                        remember_exit('IDENTITY',number=identity_error)
                if (kind=='LOOKUP_ERROR' and error_stage is None
                    and not (term_successes and identity_error==errno.ESRCH)):
                    error_stage, error_errno = 'IDENTITY', identity_error
                if observe and term_successes:
                    post_identity = ('ESRCH' if kind=='LOOKUP_ERROR' and identity_error==errno.ESRCH else
                        'OTHER_ERROR' if kind=='LOOKUP_ERROR' and identity_error is not None else
                        kind if kind in ('MATCH','MISMATCH') else 'INVALID')
                    identity_errno = identity_error if post_identity in ('ESRCH','OTHER_ERROR') else None
                if identity is None or observed != identity:
                    failure('IDENTITY'); break
                if time.monotonic() >= deadline:
                    failure(at); break
                try:
                    if sig==signal.SIGTERM:
                        before_term = True; term_attempts += 1
                    else:
                        kill_attempts += 1
                    os.killpg(process.pid, sig)
                    if sig==signal.SIGTERM: term_successes += 1
                except OSError as error:
                    remember(at,error)
                    if isinstance(error,ProcessLookupError): group = 'ABSENT_OBSERVED'
                    failure(at,error); break  # No second signal or alternate mechanism.
                if sig == signal.SIGTERM:
                    time.sleep(min(.25,max(0.0,deadline-time.monotonic())))
            remaining = deadline-time.monotonic()
            if remaining > 0:
                try:
                    wait_calls += 1
                    wait_value = process.wait(timeout=remaining)
                    waited = True
                    reaped = process.returncode is not None
                    if not reaped: failure('WAIT')
                except Exception as error:
                    remember('WAIT',error)
                    failures.append('WAIT_TIMEOUT' if isinstance(error,subprocess.TimeoutExpired) else 'WAIT_ERROR')
                    failure('WAIT',error)
            else:
                failure('WAIT')
    except Exception as error:
        remember('INTERNAL',error); failures.append('INVALID')
        failure('IDENTITY',error)
    finally:
        for stream in (process.stdin,process.stdout,process.stderr):
            try: stream.close()
            except Exception as error:
                remember('PIPES',error); failures.append('PIPE_ERROR')
                pipes_closed = False; failure('PIPES',error)
    record = _PRCleanupRecord('UNKNOWN',stage,number,identity,reaped,group,pipes_closed,True)
    if observe:
        raw = process.returncode
        code = raw if type(raw) is int and -2147483648<=raw<=2147483647 else None
        owned_reaped = waited and type(wait_value) is int and code is not None and wait_value==code
        if identity is None: failures.append('IDENTITY_MISSING')
        if term_attempts!=1 or term_successes!=1 or not before_term: failures.append('TERM_UNCONFIRMED')
        if kill_attempts or post_identity!='ESRCH': failures.append('ESCALATION_OR_IDENTITY_UNQUALIFIED')
        if not owned_reaped or code!=-int(signal.SIGTERM): failures.append('EXIT_UNQUALIFIED')
        current=time.monotonic()
        within=current<abort_budget.end
        try:
            allowed=rse.evaluate_policy(abort_budget.action,abort_budget.policies,abort_budget.authorization,
                abort_budget.now+current-abort_budget.started).disposition=='ALLOW'
        except Exception as error:
            allowed=False; remember('POLICY',error)
        within = within and time.monotonic()<abort_budget.end
        if not within: failures.append('BUDGET_EXPIRED')
        if not allowed: failures.append('POLICY_DENIED')
        outcome, reasons = _pr_abort_outcome(failures)
        abort = _PRDirectAbortRecord(1,outcome,identity,term_attempts,term_successes,kill_attempts,
            wait_calls,before_term,post_identity,identity_errno,code,owned_reaped,pipes_closed,
            True,within,allowed,reasons,error_stage,error_errno)
        # Independent diagnostic, derived solely from observations already made.
        snapshot_ok=_pr_unsealed_snapshot_matches(unsealed_snapshot,process,abort_budget)
        flags=unsealed_snapshot[2:7] if snapshot_ok else (False,False,False,False,False)
        exit_failures=[v for v in failures if v in _PR_UNSEALED_FAILURES and v!='EXIT_UNQUALIFIED']
        if not snapshot_ok or unsealed_snapshot[2:]!=(True,False,False,True,True,'PR_IPC_TRUNCATED'):
            exit_failures.append('PROTOCOL_UNQUALIFIED')
        if (identity is None or identity_observations!=1 or first_kind!='LOOKUP_ERROR'
            or first_errno!=errno.ESRCH or not _pr_unsealed_identity_eligible(first_query_facts)):
            exit_failures.append('IDENTITY_UNQUALIFIED')
        if term_attempts or kill_attempts: exit_failures.append('SIGNAL_OBSERVED')
        if not initial_cache_none or not owned_reaped or code!=0:
            exit_failures.append('EXIT_UNQUALIFIED')
        if exit_error_stage is not None and not exit_failures: exit_failures.append('INVALID')
        exit_outcome,exit_reasons=_pr_unsealed_outcome(exit_failures)
        wait_code=wait_value if type(wait_value) is int and -2147483648<=wait_value<=2147483647 else None
        unsealed=_PRUnsealedExitRecord(2,exit_outcome,identity,True,*flags,initial_cache_none,
            first_kind,first_errno,identity_observations,term_attempts,kill_attempts,wait_calls,
            wait_code,code,owned_reaped,pipes_closed,True,within,allowed,exit_reasons,
            exit_error_stage,exit_error_errno,first_query_facts)
        with state.lock:
            rejected_snapshot=state._rejected_protocol
            rejection_ok=state._rejection_protocol_valid(rejected_snapshot)
            rejection_binding=state._rejection_binding
        rejection_failures=[]
        if not rejection_ok: rejection_failures.append('PROTOCOL_UNQUALIFIED')
        if (identity is None or identity_observations!=1 or first_kind!='LOOKUP_ERROR'
            or first_errno!=errno.ESRCH or not _pr_unsealed_identity_eligible(first_query_facts)):
            rejection_failures.append('IDENTITY_UNQUALIFIED')
        if term_attempts or kill_attempts: rejection_failures.append('SIGNAL_OBSERVED')
        if not initial_cache_none or not owned_reaped or wait_calls!=1 or code!=1:
            rejection_failures.append('WAIT_UNQUALIFIED')
        if not pipes_closed: rejection_failures.append('PIPE_ERROR')
        if not within: rejection_failures.append('BUDGET_EXPIRED')
        if not allowed: rejection_failures.append('POLICY_DENIED')
        if 'INVALID' in failures or exit_error_stage=='INTERNAL': rejection_failures.append('BINDING_INVALID')
        rejection_flags=rejected_snapshot[2:7] if rejection_ok else (False,False,False,False,False)
        rejected=_PRRejectedResponseExitRecord(
            outcome='UNKNOWN' if rejection_failures else 'REJECTION_EXIT_OBSERVED',
            response_limit=rejection_binding[3] if rejection_ok else 1,
            rejection_nonce=rejection_binding[2] if rejection_ok else '0'*32,
            identity=identity,go_sent=rejection_flags[0],rejection_seen=rejection_ok,
            result_seen=rejection_flags[1],ack_started=rejection_flags[2],
            stdout_eof=rejection_flags[3],stderr_eof=rejection_flags[4],
            initial_cache_none=initial_cache_none,first_identity_kind=first_kind,
            first_identity_errno=first_errno,identity_query_facts=first_query_facts,
            identity_observations=identity_observations,term_attempts=term_attempts,
            kill_attempts=kill_attempts,wait_calls=wait_calls,wait_returncode=wait_code,
            cached_returncode=code,reaped=owned_reaped,pipes_closed=pipes_closed,
            owner_quiescent=True,within_budget=within,policy_allowed=allowed,
            failures=tuple(v for v in _PR_REJECTED_FAILURES if v in rejection_failures))
        with state.lock:
            _require(state.claimant is token and state.phase=='CLEANUP_PENDING'
                and state.process is process and state._request_budget is abort_budget,
                'PR_CLEANUP_OWNER_INVALID')
            state._abort_context=(token,process,identity,abort_budget,abort,record)
            state._unsealed_context=(token,process,identity,abort_budget,unsealed_snapshot,record,abort,first_query_facts,unsealed)
            state._rejected_context=(token,process,identity,abort_budget,rejected_snapshot,record,abort,first_query_facts,rejected)
        return state.finish_direct_abort(token,record,abort,unsealed_record=unsealed,rejected_record=rejected)
    return state.finish_cleanup(token,record)


def _pr_launch(state):
    try:
        state.publish(_pr_spawn_worker())
        state.ready.set()
        # Publication irrevocably reserves the handle for parent, even on error.
        if state.snapshot()[:2] == ('LAUNCHER_HELD','launcher'):
            _pr_cleanup(state,'launcher',state._original_request_budget.end
                if state._selected_handle_only else time.monotonic()+_PR_CLEANUP)
    except Exception:
        if state.snapshot()[:2] == ('LAUNCHER_HELD','launcher'):
            _pr_cleanup(state,'launcher',state._original_request_budget.end
                if state._selected_handle_only else time.monotonic()+_PR_CLEANUP)
    finally:
        state.launcher_done.set()
        try: state.ready.set()
        except Exception: pass  # Notification failure never authorizes takeover.


def _pr_qualification_url(q):
    _require(type(q) is dict and set(q)=={'repository','head','base','kind','number'}, 'PR_QUALIFICATION_ROUTE')
    _require(q['repository']=='Q20396/20396-acceptance-sandbox', 'PR_QUALIFICATION_ROUTE')
    for side in ('head','base'):
        ref=q[side]
        _require(type(ref) is str and 0<len(ref)<=200
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',ref)
            and '..' not in ref and '//' not in ref and not ref.endswith(('/','.')), 'PR_QUALIFICATION_ROUTE')
    root='https://api.github.com/repos/'+q['repository']
    if q['kind']=='pull':
        _require(type(q['number']) is int and 0<q['number']<=2147483647, 'PR_QUALIFICATION_ROUTE')
        return root+'/pulls/'+str(q['number'])
    _require(q['number'] is None, 'PR_QUALIFICATION_ROUTE')
    if q['kind']=='repo':return root
    if q['kind'] in ('head','base'):return root+'/branches/'+quote(q[q['kind']],safe='')
    if q['kind']=='list':
        return root+'/pulls?state=all&per_page=100&head='+quote('Q20396:'+q['head'],safe='')+'&base='+quote(q['base'],safe='')
    raise ValueError('PR_QUALIFICATION_ROUTE')


def _pr_check_qualification_route(method,url,body,q):
    _require(method=='GET' and body==b'' and url==_pr_qualification_url(q), 'PR_QUALIFICATION_ROUTE')


class _PRQualificationLimits:
    """One prepaid host phase; never a global ledger or execution authority."""
    def __init__(self,commitments,*,mode,expires_at,issued_at):
        _require(mode in ('create','recover') and type(commitments) is dict, 'PR_QUALIFICATION_LIMIT')
        self.commitments=dict(commitments);self.mode=mode
        self.end=time.monotonic()+60;self.expires_at=expires_at;self.issued_at=issued_at
        self.gets=self.posts=self.reserved_bytes=0;self.number=None
        self.observations=[]

    def check(self):
        _require(time.monotonic()<self.end and self.issued_at<=time.time()<self.expires_at,
            'PR_QUALIFICATION_EXPIRED')

    def charge(self,method,limit):
        self.check()
        _require(type(limit) is int and 0<limit<=262144 and self.reserved_bytes+limit<=1048576,
            'PR_QUALIFICATION_LIMIT')
        if method=='POST':
            _require(self.mode=='create' and self.posts==0, 'PR_QUALIFICATION_LIMIT');self.posts+=1
        else:
            _require(method=='GET' and self.gets<(8 if self.mode=='create' else 2), 'PR_QUALIFICATION_LIMIT');self.gets+=1
        self.reserved_bytes+=limit  # Irrevocable worst-case reservation, including failures.

    def observe(self,payload,method,status,headers,data):
        self.check()
        _require(type(status) is int and status in (200,201) and type(data) is bytes
            and not any(k.lower() in ('link','location') for k,v in headers), 'PR_QUALIFICATION_RESPONSE')
        value=json.loads(data)
        objects=value if type(value) is list else [value]
        _require(len(objects)<100, 'PR_QUALIFICATION_RESPONSE')
        for obj in objects:
            if type(obj) is not dict or 'number' not in obj:continue
            if not PullRequestCreateAdapter(transport=_PRObservationTransport(),
                    allowed_origins=('https://api.github.com',))._matches(payload,obj):continue
            m=self.commitments
            _require(all(type(obj[side]['repo'].get('id')) is int and obj[side]['repo']['id']==m['repository_id']
                and obj[side].get('sha')==m[side+'_oid'] for side in ('head','base')), 'PR_QUALIFICATION_RESPONSE')
            _require(self.number in (None,obj['number']), 'PR_QUALIFICATION_RESPONSE')
            self.number=obj['number']
        _require(len(self.observations)<9, 'PR_QUALIFICATION_LIMIT')
        self.observations.append(dict(method=method,http_status=status,response_sha256=_digest(data)))


class _PRObservationTransport:
    """No I/O: used only to reuse exact PR response matching."""
    tls_verified=True
    follows_redirects=False
    def request(self,*args,**kwargs):raise ValueError('OBSERVATION_ONLY')


class PRCreateBoundedHTTPS:
    """Explicit PR-only supervision, not live-execution authority or a sandbox.

    Possible sends and uncertain cleanup stay UNKNOWN. A dead parent cannot
    guarantee worker extinction. Credentials are explicit transient memory only.
    """
    tls_verified = True
    follows_redirects = False

    def __init__(self, *, credential_headers=(), qualification_limits=None, selected_direct=False):
        validator = HTTPSRemoteTransport(credential_headers=credential_headers)
        self._credentials = validator._credentials
        self._lock = threading.Lock()
        self._unresolved = None
        _require(qualification_limits is None or type(qualification_limits) is _PRQualificationLimits,
            'PR_QUALIFICATION_LIMIT')
        self._qualification=qualification_limits
        _require(type(selected_direct) is bool and (not selected_direct or qualification_limits is not None),
            'PR_SELECTED_SCOPE_REQUIRED')
        self._selected_direct=selected_direct
        self._selected_history=[]  # Closed direct handles only; group quarantine is retained.

    def _selected_bound(self,entry,payload):
        if not self._selected_direct or self._qualification is None:return False
        state,process,budget,direct,record,digest=entry
        with state.lock:
            return (type(state) is _PRLaunch and type(budget) is _PRBudget
                and type(direct) is _PRDirectFinalizationRecord and direct.outcome=='COMPLETE'
                and type(record) is _PRCleanupRecord and record.stage=='DIRECT_FINALIZATION'
                and record.status=='UNKNOWN' and record.group=='UNKNOWN'
                and state._protocol_budget is state._request_budget is state._original_request_budget is budget
                and state.process is process and state._direct_finalization is direct and state.record is record
                and state.owner=='parent' and state.claimant is not None and state.phase=='CLEANUP_UNKNOWN'
                and state.launcher_done.is_set() and state.cleanup_done.is_set()
                and record.identity==direct.identity==state.identity==(process.pid,)*3
                and record.reaped and direct.reaped and record.pipes_closed and direct.pipes_closed
                and record.quiescent and direct.quiescent and direct.within_budget and direct.policy_allowed
                and record.errno is None and direct.errno is None
                and type(process.returncode) is int and process.returncode==direct.returncode==0
                and digest==payload.digest())

    def _selected_snapshot(self,state,budget,process,payload):
        _require(self._selected_direct and type(self._qualification) is _PRQualificationLimits,
            'PR_SELECTED_SCOPE_REQUIRED')
        m=self._qualification.commitments
        _require(m['repository']=='Q20396/20396-acceptance-sandbox'
            and all(getattr(payload,k)==m[k] for k in ('repository','head','base'))
            and payload.target==_url('https://api.github.com/repos/Q20396/20396-acceptance-sandbox/pulls')[1],
            'PR_SELECTED_SCOPE_REQUIRED')
        _require(len(self._selected_history)<(9 if self._qualification.mode=='create' else 2),
            'PR_SELECTED_HISTORY_FULL')
        entry=(state,process,budget,state._direct_finalization,state.record,payload.digest())
        _require(self._selected_bound(entry,payload), 'PR_SELECTED_TERMINAL_UNKNOWN')
        # This current acceptance is under the original deadline/authority.
        # Historical facts alone never authorize another effect or retry.
        self._qualification.check()
        current=time.monotonic()
        decision=rse.evaluate_policy(budget.action,budget.policies,budget.authorization,
            budget.now+current-budget.started)
        _require(current<budget.end and decision.disposition=='ALLOW' and time.monotonic()<budget.end,
            'PR_SELECTED_TERMINAL_UNKNOWN')
        return entry

    def _selected_prior(self,state,payload):
        try:
            return any(entry[0] is state and self._selected_bound(entry,payload) for entry in self._selected_history)
        except Exception:return False

    def _selected_summary(self):
        value='UNKNOWN'
        if self._selected_direct and self._unresolved is None and not self._selected_history:
            value='NO_WORKER_LAUNCHED'
        elif self._selected_direct and self._selected_history:
            last=self._selected_history[-1]
            # Summary is finite terminal facts, not group proof or permission.
            class DigestOnly:
                def digest(self):return last[5]
            if last[0] is self._unresolved and all(self._selected_bound(e,DigestOnly()) for e in self._selected_history):
                value='SELECTED_DIRECT_WORKER_COMPLETE'
        return dict(direct_completion=value,group_cleanup='UNKNOWN',descendants='UNKNOWN')

    def _admit_request(self,budget,payload,method,url,body,timeout,response_limit,qualification=None):
        _require(type(budget) is _PRBudget and os.name=='posix', 'PR_BOUNDARY_UNAVAILABLE')
        budget.check()
        if qualification is None:
            query='state=all&per_page=100&head='+quote(payload.repository.split('/')[0]+':'+payload.head,safe='')+'&base='+quote(payload.base,safe='')
            _require((method=='POST' and url==payload.target) or
                (method=='GET' and url==payload.target+'?'+query and body==b''), 'PR_TARGET_MISMATCH')
        else:
            _require(self._qualification is not None, 'PR_QUALIFICATION_LIMIT')
            _pr_check_qualification_route(method,url,body,qualification)
            _require(all(qualification[k]==getattr(payload,k) for k in ('repository','head','base')),
                'PR_QUALIFICATION_ROUTE')
            if qualification['kind']=='pull':
                _require(qualification['number']==self._qualification.number, 'PR_QUALIFICATION_ROUTE')
        _require(timeout==payload.timeout and response_limit==payload.response_limit, 'PR_LIMIT_MISMATCH')
        if self._qualification is not None:
            m=self._qualification.commitments
            _require(payload.target==_url('https://api.github.com/repos/Q20396/20396-acceptance-sandbox/pulls')[1]
                and all(getattr(payload,k)==m[k] for k in ('repository','head','base')), 'PR_QUALIFICATION_ROUTE')
            _require(budget.end<=self._qualification.end
                and budget.operation_end<=self._qualification.end-_PR_CLEANUP, 'PR_QUALIFICATION_LIMIT')
            self._qualification.charge(method,response_limit)
            budget.check()

    def _observe_qualification(self,payload,method,status,headers,data):
        if self._qualification is not None:self._qualification.observe(payload,method,status,headers,data)

    def qualification_get(self,action,payload,kind,*,policy_stack,authorization,now,number=None):
        _require(self._qualification is not None and action.action_class==rse.ActionClass.PR_CREATE,
            'PR_QUALIFICATION_LIMIT')
        payload.validate_for(action)
        q=dict(repository=payload.repository,head=payload.head,base=payload.base,kind=kind,number=number)
        url=_pr_qualification_url(q)
        budget=_PRBudget.create(action,payload,policy_stack,authorization,now,
            phase_deadline=self._qualification.end)
        return self._request(budget,payload,'GET',url,
            (('accept','application/vnd.github+json'),('user-agent','20396-remote-runtime-binding')),b'',
            timeout=payload.timeout,response_limit=payload.response_limit,qualification=q)

    def request(self, *args, **kwargs):
        raise ValueError('PR_BINDING_BUDGET_REQUIRED')

    @property
    def direct_worker_completion(self):
        """Observe the quarantined handle; never remove its quarantine."""
        with self._lock:
            return (self._unresolved.direct_worker_completion
                    if type(self._unresolved) is _PRLaunch else 'UNKNOWN')

    @property
    def direct_child_abort_completion(self):
        with self._lock:
            return (self._unresolved.direct_child_abort_completion
                    if type(self._unresolved) is _PRLaunch else 'UNKNOWN')

    @property
    def unsealed_direct_child_exit_observation(self):
        with self._lock:
            return (self._unresolved.unsealed_direct_child_exit_observation
                    if type(self._unresolved) is _PRLaunch else 'UNKNOWN')

    @property
    def rejected_response_direct_child_exit_observation(self):
        with self._lock:
            return (self._unresolved.rejected_response_direct_child_exit_observation
                    if type(self._unresolved) is _PRLaunch else 'UNKNOWN')

    def _request(self, budget, payload, method, url, headers, body, *, timeout, response_limit, qualification=None):
        self._admit_request(budget,payload,method,url,body,timeout,response_limit,qualification)
        process = None; launch = None; result = None; clean = False
        selector = None
        go_sent=False; result_seen=False; ack_started=False; eof=set(); protocol_error='OTHER'
        rejected_frame=None
        interruption = None
        _require(self._lock.acquire(blocking=False), 'PR_TRANSPORT_BUSY')
        try:
            prior = self._unresolved
            _require(prior is None or prior.cleaned or self._selected_prior(prior,payload), 'PR_CLEANUP_UNKNOWN')
            budget.check()
            launch = _PRLaunch(request_budget=budget,selected_handle_only=self._selected_direct)
            # Pin the only launch association before scheduling can begin.
            # Admission/construction failure must leave prior untouched.
            self._unresolved = launch
            startup_end = min(budget.operation_end, time.monotonic()+_PR_STARTUP)
            threading.Thread(target=_pr_launch, args=(launch,), daemon=True).start()
            launch.ready.wait(max(0.0, startup_end-time.monotonic()))
            process = launch.claim_parent()
            _require(process is not None, 'PR_STARTUP_UNCONFIRMED')
            # Public correlation metadata, not a credential or cryptographic authentication.
            nonce=secrets.token_hex(16)
            with launch.lock:
                launch._rejection_binding=(process,budget,nonce,response_limit)
            selector = selectors.DefaultSelector()
            for pipe in (process.stdin, process.stdout, process.stderr): os.set_blocking(pipe.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ, 'out')
            selector.register(process.stderr, selectors.EVENT_READ, 'err')
            pending = b''; buffer = bytearray(); stage = 'ready'; outgoing_kind = None
            totals = {'out':0, 'err':0}
            while len(eof) < 2:
                budget.check()
                deadline = min(budget.operation_end, startup_end) if stage == 'ready' else budget.operation_end
                remaining = deadline-time.monotonic()
                _require(remaining > 0, 'PR_DEADLINE')
                for key, _ in selector.select(remaining):
                    budget.check()
                    if key.data == 'in':
                        if outgoing_kind=='ack': ack_started=True
                        count = os.write(key.fd, pending[:65536]); pending = pending[count:]
                        if not pending:
                            selector.unregister(process.stdin)
                            if outgoing_kind == 'go': go_sent = True
                        continue
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj); eof.add(key.data); continue
                    totals[key.data] += len(chunk)
                    _require(totals[key.data] <= (4096 if key.data == 'err' else _PR_OUTPUT+2*_PR_METADATA+12), 'PR_IPC_OVERFLOW')
                    if key.data == 'err':
                        _require(False, 'PR_WORKER_STDERR')  # Never copy raw stderr to logs/errors.
                    buffer.extend(chunk)
                    while len(buffer) >= 4:
                        length = struct.unpack('!I', buffer[:4])[0]
                        limit = _PR_OUTPUT if stage == 'result' else _PR_METADATA
                        _require(0 < length <= limit, 'PR_IPC_OVERFLOW')
                        if len(buffer) < length+4: break
                        message = _pr_decode(bytes(buffer[4:4+length])); del buffer[:4+length]
                        if message.get('kind')=='result': result_seen=True
                        _require(not pending, 'PR_IPC_ORDER')
                        if stage == 'ready':
                            _require(message == {'version':1,'kind':'ready'}, 'PR_IPC_ORDER')
                            request = dict(version=1,kind='request',method=method,url=url,
                                headers=list(_pr_headers(headers)), credentials=list(self._credentials),
                                body=base64.b64encode(body).decode('ascii'),
                                response_limit=response_limit, remaining=budget.check(),
                                rejection_version=1,rejection_nonce=nonce)
                            if qualification is not None:request['qualification']=qualification
                            pending = _pr_frame(request, _PR_INPUT); outgoing_kind='request'; stage='armed'
                        elif stage == 'armed':
                            _require(message == {'version':1,'kind':'armed'}, 'PR_IPC_ORDER')
                            budget.check()
                            pending = _pr_frame({'version':1,'kind':'go'}, _PR_METADATA)
                            outgoing_kind='go'; stage='result'
                        elif stage == 'result':
                            if message.get('kind')=='rejected':
                                _require(go_sent and length<=512
                                    and _pr_rejection_valid(message,nonce,response_limit),'PR_IPC_ORDER')
                                rejected_frame=message; stage='rejected'
                                continue  # No result or ACK, only terminal EOF is admissible.
                            _require(go_sent and message.get('kind') == 'result', 'PR_IPC_ORDER')
                            result = message; stage='done'
                            pending = _pr_frame({'version':1,'kind':'ack'}, _PR_METADATA); outgoing_kind='ack'
                        else:
                            raise ValueError('PR_IPC_ORDER')
                        selector.register(process.stdin, selectors.EVENT_WRITE, 'in')
            if stage=='rejected':
                _require(not buffer and not pending and go_sent and not result_seen
                    and not ack_started and rejected_frame is not None,'PR_IPC_ORDER')
                budget.check()
                with launch.lock:
                    _require(launch.phase=='PARENT_CLAIMED' and launch.claimant is None
                        and launch._rejected_protocol is None,'PR_IPC_ORDER')
                    launch._rejected_protocol=(launch._rejection_binding,rejected_frame,
                        go_sent,result_seen,ack_started,'out' in eof,'err' in eof,True)
                # Deliberately unsealed. Legacy uncertainty and quarantine remain.
                raise ValueError('PR_RESPONSE_REJECTED')
            _require(stage == 'done' and not buffer and not pending, 'PR_IPC_TRUNCATED')
            budget.check()
            # Validate the response envelope before noting protocol completion.
            # This observation does not authorize result acceptance below.
            _require(set(result) == {'version','kind','status','headers','body','complete'}
                and type(result['status']) is int and 100 <= result['status'] <= 599
                and type(result['complete']) is bool and type(result['body']) is str,
                'PR_IPC_INVALID')
            _pr_headers(result['headers'])
            _require(len(base64.b64decode(result['body'], validate=True)) <= response_limit,
                     'PR_IPC_INVALID')
            _require(result['complete'] or (result['body'] == '' and result['headers'] == []),
                     'PR_IPC_INVALID')
            launch.note_protocol_complete(budget)
        except Exception as error:
            if type(error) is ValueError and error.args==('PR_IPC_TRUNCATED',):
                protocol_error='PR_IPC_TRUNCATED'
            result = None
        except BaseException as error:
            interruption = error
        finally:
            try:
                try:
                    if selector is not None: selector.close()
                except BaseException as error:
                    result = None
                    if not isinstance(error, Exception) and interruption is None:
                        interruption = error
                # Only the process claimed by this call is eligible. Never
                # clean prior, take launcher ownership, or retry finalization.
                try:
                    if process is not None:
                        if launch._protocol_budget is None:
                            try:
                                launch.note_unsealed_protocol(process,budget,go_sent=go_sent,result_seen=result_seen,
                                    ack_started=ack_started,stdout_eof='out' in eof,stderr_eof='err' in eof,
                                    error_code=protocol_error)
                            except BaseException as error:
                                result = None
                                if not isinstance(error, Exception) and interruption is None:
                                    interruption = error
                                # Missing provenance cannot suppress this owner's cleanup.
                        _pr_cleanup(launch,'parent',budget.end)
                        clean = launch.cleaned
                except BaseException as error:
                    clean = False; result = None
                    if not isinstance(error, Exception) and interruption is None:
                        interruption = error
            finally:
                self._lock.release()
        if interruption is not None:
            raise interruption
        selected=None
        if not clean and result is not None and self._selected_direct:
            try:
                selected=self._selected_snapshot(launch,budget,process,payload)
                self._selected_history.append(selected)
            except Exception:
                selected=None
        _require((clean or selected is not None) and result is not None, 'PR_TRANSPORT_UNCERTAIN')
        # Cleanup consumed its reserve; authority still cannot be stale at acceptance.
        decision = rse.evaluate_policy(budget.action, budget.policies, budget.authorization,
                                      budget.now+time.monotonic()-budget.started)
        _require(time.monotonic() < budget.end and decision.disposition == 'ALLOW', 'PR_TRANSPORT_UNCERTAIN')
        _require(set(result) == {'version','kind','status','headers','body','complete'}, 'PR_IPC_INVALID')
        status = result['status']
        _require(type(status) is int and 100 <= status <= 599 and type(result['complete']) is bool, 'PR_IPC_INVALID')
        if not result['complete']:
            _require(result['body'] == '' and result['headers'] == [], 'PR_IPC_INVALID')
            raise _ObservedResponseFailure(status)
        returned = _pr_headers(result['headers'])
        _require(type(result['body']) is str, 'PR_IPC_INVALID')
        data = base64.b64decode(result['body'], validate=True)
        _require(len(data) <= response_limit, 'PR_IPC_INVALID')
        self._observe_qualification(payload,method,status,returned,data)
        return status, returned, data


class _PRBoundCall:
    tls_verified = True
    follows_redirects = False

    def __init__(self, transport, budget, payload):
        self.transport, self.budget, self.payload = transport, budget, payload

    def request(self, *args, **kwargs):
        return self.transport._request(self.budget, self.payload, *args, **kwargs)


def _pr_selected(adapter, payload, budget):
    if type(adapter) is PullRequestCreateAdapter and type(adapter.transport) is PRCreateBoundedHTTPS:
        _require(type(budget) is _PRBudget, 'PR_BINDING_BUDGET_REQUIRED')
        return PullRequestCreateAdapter(transport=_PRBoundCall(adapter.transport, budget, payload),
                                       allowed_origins=tuple(adapter.origins))
    return adapter


class _PRResponseBodyRejected(Exception):
    """Local control flow only, never exception text on the wire."""


def _pr_worker_main():
    """Fixed stdlib child. Never called on import. No effect before one GO."""
    selector = selectors.DefaultSelector()
    for fd in (0, 1): os.set_blocking(fd, False)
    anchor = time.monotonic(); deadline = anchor+_PR_STARTUP
    def transfer(data=None, limit=_PR_METADATA):
        buffer = bytearray(); output = data; want = None
        fd = 0 if data is None else 1
        selector.register(fd, selectors.EVENT_READ if data is None else selectors.EVENT_WRITE)
        try:
            while True:
                remaining = deadline-time.monotonic()
                _require(remaining > 0, 'PR_DEADLINE')
                if not selector.select(remaining): raise ValueError('PR_DEADLINE')
                if data is not None:
                    count = os.write(fd, output[:65536]); output=output[count:]
                    if not output: return
                else:
                    chunk = os.read(fd, min(65536, (4 if want is None else want+4)-len(buffer)))
                    _require(bool(chunk), 'PR_IPC_TRUNCATED'); buffer.extend(chunk)
                    if want is None and len(buffer) == 4:
                        want = struct.unpack('!I', buffer)[0]
                        _require(0 < want <= limit, 'PR_IPC_OVERFLOW')
                    if want is not None and len(buffer) == want+4: return _pr_decode(buffer[4:])
        finally:
            selector.unregister(fd)
    try:
        transfer(_pr_frame(dict(version=1,kind='ready'), _PR_METADATA))
        request = transfer(limit=_PR_INPUT)
        legacy_keys={'version','kind','method','url','headers','credentials','body','response_limit','remaining'}
        qualification=request.get('qualification')
        keys=set(request)-({'qualification'} if 'qualification' in request else set())
        extension=keys==legacy_keys|{'rejection_version','rejection_nonce'}
        _require((keys==legacy_keys or extension)
            and request['kind'] == 'request', 'PR_IPC_INVALID')
        if extension:
            _require(type(request['rejection_version']) is int and request['rejection_version']==1
                and type(request['rejection_nonce']) is str
                and re.fullmatch('[0-9a-f]{32}',request['rejection_nonce']), 'PR_IPC_INVALID')
        duration = request['remaining']
        _require(type(duration) in (int,float) and math.isfinite(duration) and 0 < duration <= 30, 'PR_IPC_INVALID')
        deadline = anchor+duration  # conservative READY anchor, never a parent clock epoch
        method, url = request['method'], request['url']
        origin, _, query = _url(url)
        parsed = urlsplit(url)
        if 'qualification' in request:
            _pr_check_qualification_route(method,url,b'',qualification)
        else:
            _require(method in ('POST','GET') and re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pulls',parsed.path)
                and (method != 'POST' or not query), 'PR_IPC_INVALID')
        headers = _pr_headers(request['headers']); credentials = _pr_headers(request['credentials'])
        _require(('user-agent','20396-remote-runtime-binding') in headers
            and all(k in ('accept','content-type','user-agent') for k,v in headers), 'PR_IPC_INVALID')
        body = base64.b64decode(request['body'], validate=True)
        limit = request['response_limit']
        _require(type(limit) is int and 0 < limit <= MAX_BODY and len(body) <= MAX_BODY
            and (method != 'GET' or not body), 'PR_IPC_INVALID')
        transport = HTTPSRemoteTransport(credential_headers=credentials)
        transfer(_pr_frame(dict(version=1,kind='armed'), _PR_METADATA))
        _require(transfer() == {'version':1,'kind':'go'}, 'PR_IPC_ORDER')
        remaining = deadline-time.monotonic()
        _require(remaining > 0, 'PR_DEADLINE')
        try:
            status, returned, data = transport.request(method,url,headers,body,timeout=remaining,response_limit=limit)
            returned = _pr_headers(returned)
            _require(type(status) is int and 100 <= status <= 599 and type(data) is bytes, 'PR_IPC_INVALID')
            if len(data)>limit:
                _require(extension,'PR_IPC_INVALID')
                transfer(_pr_frame(dict(version=1,kind='rejected',rejection_version=1,
                    rejection_nonce=request['rejection_nonce'],reason='RESPONSE_BODY_LIMIT',response_limit=limit),512))
                raise _PRResponseBodyRejected()
            result = dict(version=1,kind='result',status=status,headers=list(returned),
                          body=base64.b64encode(data).decode('ascii'),complete=True)
        except _ObservedResponseFailure as error:
            result = dict(version=1,kind='result',status=error.status,headers=[],body='',complete=False)
        transfer(_pr_frame(result, _PR_OUTPUT))
        _require(transfer() == {'version':1,'kind':'ack'}, 'PR_IPC_ORDER')
    except _PRResponseBodyRejected:
        os._exit(1)
    except BaseException:
        # No raw exceptions, stderr, frames or credentials leave this boundary.
        os._exit(1)
    finally:
        selector.close()


class NetworkRequestAdapter:
    def __init__(self, *, transport, allowed_origins):
        _require(type(allowed_origins) is tuple and 0 < len(allowed_origins) <= 64, 'INVALID_REMOTE_CONFIG')
        self.origins = frozenset(_url(o)[0] for o in allowed_origins)
        _require(all(_url(o)[1] == _url(o)[0] + '/' and not _url(o)[2] for o in allowed_origins), 'INVALID_REMOTE_CONFIG')
        self.transport = transport
        self._configuration()

    def _configuration(self):
        _require(getattr(self.transport, 'tls_verified', None) is True
            and getattr(self.transport, 'follows_redirects', None) is False
            and callable(getattr(self.transport, 'request', None)), 'INVALID_REMOTE_CONFIG')

    def execute(self, action):
        raise ValueError('REMOTE_BINDING_REQUIRED')

    def _preflight(self, target):
        self._configuration()
        _require(_url(target)[0] in self.origins, 'REMOTE_DESTINATION_DENIED')

    def _request(self, p, method, url, headers=(), body=b'', *, observe=None):
        # Per-invocation digest/status updates happen at the observed boundary,
        # before callers parse. Later parser failures cannot erase these facts.
        observe = observe or (lambda **values: None)
        self._preflight(url)
        observe(request_attempted=True)
        try:
            status, response_headers, data = self.transport.request(method, url, headers, body,
                timeout=p.timeout, response_limit=p.response_limit)
        except _ObservedResponseFailure as error:
            observe(response_observed=True, status_code=error.status, response_body_complete=False)
            raise
        _require(type(status) is int and 100 <= status <= 599, 'REMOTE_RESPONSE_INVALID')
        observe(response_observed=True, status_code=status, response_body_complete=False)
        try:
            _require(type(data) is bytes
            and len(data) <= p.response_limit and type(response_headers) is tuple
            and all(type(h) is tuple and len(h) == 2 and _text(h[0], MAX_HEADERS)
                and _text(h[1], MAX_HEADERS, empty=True) for h in response_headers)
            and sum(len(k.encode()) + len(v.encode()) + 4 for k, v in response_headers) <= MAX_HEADERS,
                'REMOTE_RESPONSE_INVALID')
        except Exception:
            raise _ObservedResponseFailure(status) from None
        observe(response_body_complete=True, response_digest=_digest(data))
        return status, response_headers, data

    def _run(self, a, p, context, now):
        attempted = False; observed = {}
        try:
            _require(a.action_class == rse.ActionClass.NETWORK_REQUEST, 'NOT_BOUND')
            self._preflight(p.target)
            headers = p.headers + ((('idempotency-key', p.request_identity),) if p.request_identity else ())
            attempted = True
            status, _, data = self._request(p, p.method, _endpoint(p.target, p.query), headers, p.body,
                observe=observed.update)
            state = (rse.ExecutionState.KNOWN_SUCCESS if 200 <= status < 300 else
                rse.ExecutionState.KNOWN_FAILURE if p.method in ('GET', 'HEAD') else rse.ExecutionState.UNKNOWN_OUTCOME)
            evidence = _evidence(p, 'RESPONSE_OBSERVED', **observed)
            return _Outcome(state, evidence, (_event(a, context, now, evidence, state == rse.ExecutionState.KNOWN_SUCCESS),))
        except Exception:
            state = rse.ExecutionState.UNKNOWN_OUTCOME if attempted and p.method not in ('GET', 'HEAD') else rse.ExecutionState.KNOWN_FAILURE
            evidence = _evidence(p, 'REMOTE_UNCERTAIN' if attempted else 'REMOTE_REJECTED', **observed)
            return _Outcome(state, evidence, (_event(a, context, now, evidence),) if attempted else ())

    def _readback(self, a, p, *, observe=None):
        if p.readback_target is None:
            return 'STILL_UNKNOWN', None
        status, _, data = self._request(p, 'GET', _endpoint(p.readback_target, p.readback_query), p.headers, observe=observe)
        digest = _digest(data)
        return ('RECONCILED_SUCCESS' if status == 200 and digest == p.expected_readback_digest else 'STILL_UNKNOWN'), digest


def _packets(data):
    """Strict v0 pkt-lines only, including flush; no sideband/protocol fallback."""
    _require(type(data) is bytes and len(data) <= MAX_BODY, 'GIT_PROTOCOL_INVALID')
    result = []; offset = 0
    while offset < len(data):
        size_bytes = data[offset:offset + 4]
        _require(len(size_bytes) == 4 and re.fullmatch(b'[0-9a-fA-F]{4}', size_bytes), 'GIT_PROTOCOL_INVALID')
        size = int(size_bytes, 16)
        if size == 0:
            result.append(None); offset += 4; continue
        _require(4 < size <= 65520 and offset + size <= len(data), 'GIT_PROTOCOL_INVALID')
        result.append(data[offset + 4:offset + size]); offset += size
        _require(len(result) <= 16384, 'GIT_PROTOCOL_INVALID')
    return result


def _packet(data):
    _require(len(data) + 4 <= 65520, 'GIT_PROTOCOL_INVALID')
    return ('%04x' % (len(data) + 4)).encode() + data


class GitPushAdapter(NetworkRequestAdapter):
    """Exact existing SHA-1 branch update using minimal HTTPS smart Git v0.

    No Git network helper is invoked. Local Git only validates/generates objects.
    No fetch, branch creation, SHA-256, sideband, remote hook bypass or fallback.
    """
    def __init__(self, *, workspace_root, git_executable, transport, allowed_origins):
        super().__init__(transport=transport, allowed_origins=allowed_origins)
        self.local = local.LocalGitAdapter(workspace_root=workspace_root, git_executable=git_executable)

    def _ancestry(self):
        # Reject override state, not just overrides relevant to today's graph.
        # Inspect metadata only: malformed/comment-only grafts are also unsafe.
        reason = 'GIT_ANCESTRY_OVERRIDE_PRESENT'
        try:
            with local._directory(self.local.root + '/.git/info') as fd:
                grafts = local._regular(fd, 'grafts', missing=True)
                _require(grafts is None or grafts.st_size == 0, reason)
        except FileNotFoundError:
            pass
        try:
            with local._directory(self.local.root + '/.git/refs/replace') as fd:
                _require(not os.listdir(fd), reason)
        except FileNotFoundError:
            pass
        # Includes packed refs; the directory check above also catches malformed
        # loose entries which Git may omit from its enumeration.
        _require(not self.local._read_git(('for-each-ref', '--format=%(refname)', 'refs/replace/')), reason)

    def _repository(self, p):
        _require(p.repository == self.local.root, 'GIT_REPOSITORY_MISMATCH')
        _require(self.local._validate() == 40, 'GIT_OBJECT_FORMAT_UNSUPPORTED')
        self._ancestry()
        raw = self.local._read_git(('config', '--local', '--no-includes', '--null', '--list'))
        values = {}
        for row in raw.decode().split('\0'):
            if not row:
                continue
            key, _, value = row.partition('\n')
            lower_key = key.lower()
            _require(not lower_key.startswith(('http.', 'https.', 'url.', 'protocol.', 'push.'))
                and not (lower_key.startswith('remote.') and lower_key.endswith(('.pushurl', '.receivepack', '.uploadpack', '.proxy', '.vcs'))),
                'UNSAFE_GIT_CONFIG')
            values.setdefault(key, []).append(value)
        urls = values.get('remote.' + p.remote_name + '.url', [])
        _require(len(urls) == 1 and _url(urls[0])[1] == p.target and not _url(urls[0])[2], 'GIT_REMOTE_BINDING_MISMATCH')
        oid = self.local._read_git(('rev-parse', '--verify', p.local_ref + '^{commit}')).decode().strip()
        _require(oid == p.expected_local_oid, 'LOCAL_REF_CHANGED')

    def _remote(self, p, *, observe=None):
        observe = observe or (lambda **values: None)
        status, headers, data = self._request(p, 'GET', p.target.rstrip('/') + '/info/refs?service=git-receive-pack',
            (('accept', 'application/x-git-receive-pack-advertisement'),), observe=observe)
        _require(status == 200 and ('content-type', 'application/x-git-receive-pack-advertisement') in
            tuple((k.lower(), v.lower()) for k, v in headers), 'GIT_PROTOCOL_INVALID')
        observe(response_parse_status='PARSE_FAILED')
        packets = _packets(data)
        _require(len(packets) >= 4 and packets[:2] == [b'# service=git-receive-pack\n', None]
            and packets[-1] is None and all(x is not None for x in packets[2:-1]), 'GIT_PROTOCOL_INVALID')
        refs = {}
        for index, row in enumerate(packets[2:-1]):
            row = row.rstrip(b'\n')
            if index == 0:
                row, sep, caps = row.partition(b'\0')
                _require(sep and b'report-status' in caps.split(), 'GIT_PROTOCOL_INVALID')
            _require(b'\0' not in row, 'GIT_PROTOCOL_INVALID')
            oid, sep, ref = row.partition(b' ')
            _require(sep and local._git_oid(oid.decode('ascii'), 40) and ref not in refs, 'GIT_PROTOCOL_INVALID')
            refs[ref] = oid.decode('ascii')
        observe(response_parse_status='PARSED')
        _require(p.remote_ref.encode() in refs, 'REMOTE_REF_CHANGED')
        return refs[p.remote_ref.encode()]

    def _run(self, a, p, context, now):
        attempted = False; observed = {}
        try:
            _require(a.action_class == rse.ActionClass.GIT_PUSH, 'NOT_BOUND')
            self._preflight(p.target); self._repository(p)
            _require(self._remote(p) == p.expected_remote_oid, 'REMOTE_REF_CHANGED')
            self._ancestry()
            code, _, _, trunc, expired = self.local._call(('merge-base', '--is-ancestor', p.expected_remote_oid, p.expected_local_oid))
            _require(code == 0 and not expired and not any(trunc), 'NON_FAST_FORWARD')
            self._ancestry()
            # Generate a self-contained exact reachability difference, never --all.
            with tempfile.TemporaryFile() as revisions:
                revisions.write((p.expected_local_oid + '\n^' + p.expected_remote_oid + '\n').encode()); revisions.seek(0)
                code, pack, _, trunc, expired = self.local._call(('pack-objects', '--stdout', '--revs', '--no-reuse-delta'),
                    stdin_file=revisions)
            _require(code == 0 and not expired and not any(trunc) and pack.startswith(b'PACK'), 'GIT_PACK_REJECTED')
            command = (p.expected_remote_oid + ' ' + p.expected_local_oid + ' ' + p.remote_ref).encode() + b'\0report-status\n'
            body = _packet(command) + b'0000' + pack
            _require(len(body) <= MAX_BODY, 'GIT_PACK_REJECTED')
            # Re-read mutable local inputs immediately before the sole mutation.
            self._repository(p)
            _require(self._remote(p) == p.expected_remote_oid, 'REMOTE_REF_CHANGED')
            self._ancestry()
            attempted = True
            status, _, data = self._request(p, 'POST', p.target.rstrip('/') + '/git-receive-pack',
                (('content-type', 'application/x-git-receive-pack-request'),
                 ('accept', 'application/x-git-receive-pack-result')), body, observe=observed.update)
            _require(status == 200, 'GIT_UNCERTAIN')
            observed['response_parse_status'] = 'PARSE_FAILED'
            _require(_packets(data) == [b'unpack ok\n', b'ok ' + p.remote_ref.encode() + b'\n', None], 'GIT_UNCERTAIN')
            observed['response_parse_status'] = 'PARSED'
            _require(self._remote(p) == p.expected_local_oid, 'GIT_UNCERTAIN')
            evidence = _evidence(p, 'COMPLETED', resource_digest=_digest(p.expected_local_oid.encode()), **observed)
            return _Outcome(rse.ExecutionState.KNOWN_SUCCESS, evidence, (_event(a, context, now, evidence, True),))
        except Exception as error:
            reason = 'GIT_UNCERTAIN' if attempted else 'GIT_REJECTED'
            if not attempted and type(error) is ValueError and str(error) in (
                'GIT_REPOSITORY_MISMATCH', 'LOCAL_REF_CHANGED', 'REMOTE_REF_CHANGED', 'GIT_REMOTE_BINDING_MISMATCH',
                'NON_FAST_FORWARD', 'UNSAFE_GIT_CONFIG', 'GIT_PACK_REJECTED', 'GIT_OBJECT_FORMAT_UNSUPPORTED',
                'GIT_ANCESTRY_OVERRIDE_PRESENT'):
                reason = str(error)
            evidence = _evidence(p, reason, **observed)
            return _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME if attempted else rse.ExecutionState.KNOWN_FAILURE,
                evidence, (_event(a, context, now, evidence),) if attempted else ())

    def _readback(self, a, p, *, observe=None):
        # Reconciliation reads the prebound URL; local refs may legitimately drift.
        oid = self._remote(p, observe=observe)
        state = 'RECONCILED_SUCCESS' if oid == p.expected_local_oid else (
            'RECONCILED_NOT_APPLIED' if oid == p.expected_remote_oid else 'CONFLICT')
        if observe:
            observe(resource_digest=_digest(oid.encode()))
        return state, _digest(oid.encode())


class PullRequestCreateAdapter(NetworkRequestAdapter):
    """GitHub-compatible create and one-page readback, no PR update/merge API."""
    def _body(self, p):
        marker = '\n\n<!-- 20396-request:' + p.request_identity + ' -->'
        return p.body.decode('utf-8') + marker

    def _matches(self, p, result):
        try:
            return (type(result) is dict and type(result['id']) is int and result['id'] > 0
                and type(result['number']) is int and result['number'] > 0
                and result['base']['repo']['full_name'] == p.repository
                and result['head']['repo']['full_name'] == p.repository
                and result['head']['ref'] == p.head and result['base']['ref'] == p.base
                and result['head']['label'] == p.repository.split('/')[0] + ':' + p.head
                and result['title'] == p.title and result['body'] == self._body(p)
                and result['draft'] is p.draft)
        except (KeyError, TypeError):
            return False

    def _run(self, a, p, context, now):
        attempted = False; observed = {}
        try:
            _require(a.action_class == rse.ActionClass.PR_CREATE, 'NOT_BOUND')
            self._preflight(p.target)
            body = json.dumps(dict(head=p.head, base=p.base, title=p.title, body=self._body(p), draft=p.draft),
                ensure_ascii=False, separators=(',', ':')).encode()
            _require(len(body) <= MAX_BODY)
            attempted = True
            status, _, data = self._request(p, 'POST', p.target,
                (('content-type', 'application/json'), ('accept', 'application/vnd.github+json'),
                 ('user-agent', '20396-remote-runtime-binding')), body, observe=observed.update)
            observed['response_parse_status'] = 'PARSE_FAILED'
            result = json.loads(data)
            _require(type(result) is dict, 'PR_UNCERTAIN')
            observed['response_parse_status'] = 'PARSED'
            _require(status == 201 and self._matches(p, result), 'PR_UNCERTAIN')
            evidence = _evidence(p, 'COMPLETED', resource_digest=sc.artifact_digest((result['id'], result['number'])), **observed)
            return _Outcome(rse.ExecutionState.KNOWN_SUCCESS, evidence, (_event(a, context, now, evidence, True),))
        except Exception:
            evidence = _evidence(p, 'PR_UNCERTAIN' if attempted else 'PR_REJECTED', **observed)
            return _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME if attempted else rse.ExecutionState.KNOWN_FAILURE,
                evidence, (_event(a, context, now, evidence),) if attempted else ())

    def _readback(self, a, p, *, observe=None):
        observe = observe or (lambda **values: None)
        query = 'state=all&per_page=100&head=' + quote(p.repository.split('/')[0] + ':' + p.head, safe='') + '&base=' + quote(p.base, safe='')
        status, headers, data = self._request(p, 'GET', p.target + '?' + query,
            (('accept', 'application/vnd.github+json'), ('user-agent', '20396-remote-runtime-binding')), observe=observe)
        observe(response_parse_status='PARSE_FAILED')
        results = json.loads(data)
        _require(type(results) is list, 'PR_READBACK_INCOMPLETE')
        observe(response_parse_status='PARSED')
        # Pagination could hide a duplicate. One bounded page, no automatic retry.
        _require(status == 200 and len(results) < 100
            and not any(k.lower() == 'link' for k, v in headers), 'PR_READBACK_INCOMPLETE')
        matches = [v for v in results if self._matches(p, v)]
        marker = '<!-- 20396-request:' + p.request_identity + ' -->'
        plausible = [v for v in results if type(v) is dict and type(v.get('body')) is str and marker in v['body']]
        return ('RECONCILED_SUCCESS' if len(matches) == 1 and len(plausible) == 1 else 'STILL_UNKNOWN'), _digest(data)


class _Invocation:
    def __init__(self, adapter, payload, context, now, budget=None):
        self.adapter, self.payload, self.context, self.now = adapter, payload, context, now
        self.budget = budget
        self.outcome = None

    def execute(self, action):
        adapter = _pr_selected(self.adapter, self.payload, self.budget)
        self.outcome = adapter._run(action, self.payload, self.context, self.now)
        if self.budget is not None:
            current = self.budget.now + time.monotonic()-self.budget.started
            if rse.evaluate_policy(action, self.budget.policies, self.budget.authorization, current).disposition != 'ALLOW':
                self.outcome = _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME,
                    replace(self.outcome.evidence, reason='PR_UNCERTAIN'), ())
        _require(type(self.outcome) is _Outcome, 'INVALID_REMOTE_RESULT')
        return rse.ExecutionResult(self.outcome.state, (sc.artifact_digest(self.outcome.evidence),))


class RemoteRuntimeBinding:
    """Approved digest snapshot is trusted controller input created pre-authorization.

    Never populate the snapshot from the payload being executed. Replacing the
    journal loses retry protection. The host also owns brokers/transports/actors.
    """
    def __init__(self, capability_broker, journal, chain, actor, *, approved_payload_digests):
        _require(type(approved_payload_digests) is dict and len(approved_payload_digests) <= 1024
            and all(_text(k, 1024) and sc._hash(v) for k, v in approved_payload_digests.items()), 'INVALID_APPROVED_PAYLOADS')
        self.approved_payload_digests = MappingProxyType(dict(approved_payload_digests))
        self.broker, self.journal, self.chain, self.actor = capability_broker, journal, chain, actor

    def _bound(self, action, payload):
        _require(type(payload) is RemoteRuntimePayload and type(action) is rse.ActionRequest)
        _require(action.action_class in BOUND_ACTIONS, 'NOT_BOUND')
        payload.validate_for(action)
        _require(self.approved_payload_digests.get(action.action_id) == payload.digest(), 'PAYLOAD_DIGEST_MISMATCH')
        _require(rse._valid_action(action))
        return replace(action, expected_effect='remote-payload:' + payload.digest() + ':' + _digest(action.expected_effect.encode()))

    def _authority(self, action, context, now):
        cet._match_action(action, context)
        _require(self.chain._installation_id == context.installation_id and self.chain.verify().valid
            and sc.authorize_management_change(self.actor, sc.ManagementAction.RSE_RECEIPT_RECORD,
                installation_id=context.installation_id, project_id=context.project_id, task_id=context.task_id,
                now=now).disposition == 'ALLOW', 'SECURITY_BOUNDARY_FAILURE')

    def _denied(self, action, error):
        reason = str(error) if type(error) is ValueError and str(error) in (
            'NOT_BOUND', 'PAYLOAD_DIGEST_MISMATCH', 'SECURITY_BOUNDARY_FAILURE') else 'MALFORMED_REMOTE_PAYLOAD'
        return RemoteRuntimeResult(rse._receipt(action, rse.PolicyDecision('DENY', reason)), boundary_status=reason)

    def _adapter(self, action):
        adapter = self.broker.get(action.capability)
        expected = {rse.ActionClass.NETWORK_REQUEST: NetworkRequestAdapter,
            rse.ActionClass.GIT_PUSH: GitPushAdapter, rse.ActionClass.PR_CREATE: PullRequestCreateAdapter}[action.action_class]
        _require(type(adapter) is expected, 'NOT_BOUND')
        return adapter

    def _record(self, action, context, now, receipt, events):
        divergences = []
        declaration = cet.declared_from_action(action, context)
        for event in events:
            _require(type(event) is cet.CriticalEvent and event.context == context)
            divergences.extend(cet.compare_effects(declaration,
                cet.ObservedEffects(context, **cet._event_effect(event))).divergences)
        sc.record_receipt(self.chain, self.actor, receipt, event_id=uuid.uuid4().hex, now=now,
            project_id=context.project_id, task_id=context.task_id)
        for event in events:
            cet.record_critical_event(self.chain, self.actor, event, now=now)
        for divergence in divergences:
            cet.record_trace_divergence(self.chain, self.actor, divergence, now=now)
        return tuple(divergences)

    def execute(self, action, payload, *, policy_stack, authorization, context, now):
        budget = None
        try:
            bound = self._bound(action, payload)
            self._authority(action, context, now)
            if action.action_class == rse.ActionClass.PR_CREATE and self.broker.has(action.capability):
                selected = self._adapter(action)
                if type(selected.transport) is PRCreateBoundedHTTPS:
                    budget = _PRBudget.create(bound, payload, policy_stack, authorization, now,
                        phase_deadline=(selected.transport._qualification.end
                            if selected.transport._qualification is not None else None))
        except Exception as error:
            return self._denied(action, error)
        invocation = None
        try:
            transaction = rse.action_transaction(self.journal, action.action_id)
        except Exception:
            return self._denied(action, ValueError('SECURITY_BOUNDARY_FAILURE'))
        with transaction:
            broker = rse.CapabilityBroker()
            if self.broker.has(action.capability):
                try:
                    adapter = self._adapter(action)
                except Exception:
                    return self._denied(action, ValueError('NOT_BOUND'))
                invocation = _Invocation(adapter, payload, context, now, budget)
                broker.register(action.capability, invocation)
            receipt = rse.evaluate_and_execute(bound, policy_stack, authorization, broker, self.journal, now, action_scoped=True)
            out = invocation.outcome if invocation else None
            events = out.events if out else ()
            try:
                divergences = self._record(action, context, now, receipt, events)
            except Exception:
                if out:
                    rse._append(self.journal, bound, rse.JournalState.RECONCILIATION_REQUIRED)
                receipt = replace(receipt, execution_state='UNKNOWN_OUTCOME', reconciliation_state='RECONCILIATION_REQUIRED',
                    final_disposition='REQUIRE_RECONCILIATION')
                return RemoteRuntimeResult(receipt, out.evidence if out else None, events, boundary_status='SECURITY_BOUNDARY_FAILURE')
            return RemoteRuntimeResult(receipt, out.evidence if out else None, events, divergences)

    def reconcile(self, action, payload, *, policy_stack, authorization, context, now):
        budget = None
        try:
            bound = self._bound(action, payload); self._authority(action, context, now)
            decision = rse.evaluate_policy(bound, policy_stack, authorization, now)
            if decision.disposition != 'ALLOW':
                return RemoteRuntimeResult(rse._receipt(action, decision))
            adapter = self._adapter(action)
            if type(adapter) is PullRequestCreateAdapter and type(adapter.transport) is PRCreateBoundedHTTPS:
                budget = _PRBudget.create(bound, payload, policy_stack, authorization, now,
                    phase_deadline=(adapter.transport._qualification.end
                        if adapter.transport._qualification is not None else None))
                adapter = _pr_selected(adapter, payload, budget)
        except Exception as error:
            return self._denied(action, error)
        evidence = None
        def read(_):
            nonlocal evidence
            state = 'STILL_UNKNOWN'
            evidence = _evidence(payload, 'READBACK_OBSERVED')
            def observe(**values):
                nonlocal evidence
                evidence = replace(evidence, **values)
            try:
                state, _ = adapter._readback(action, payload, observe=observe)
                if budget is not None:
                    current = now + time.monotonic()-budget.started
                    if rse.evaluate_policy(bound, policy_stack, authorization, current).disposition != 'ALLOW':
                        state = 'STILL_UNKNOWN'
            except Exception:
                pass
            evidence = replace(evidence, reconciliation=state)
            return {'RECONCILED_SUCCESS': rse.ReconciliationOutcome.EFFECT_APPLIED,
                'RECONCILED_NOT_APPLIED': rse.ReconciliationOutcome.EFFECT_NOT_APPLIED}.get(state, rse.ReconciliationOutcome.STILL_UNKNOWN)
        try:
            transaction = rse.action_transaction(self.journal, action.action_id)
        except Exception:
            return self._denied(action, ValueError('SECURITY_BOUNDARY_FAILURE'))
        with transaction:
            receipt = rse.reconcile(bound, self.journal, read)
            try:
                if evidence:
                    receipt = replace(receipt, evidence_refs=receipt.evidence_refs + (sc.artifact_digest(evidence),))
                self._record(action, context, now, receipt, ())
            except Exception:
                rse._append(self.journal, bound, rse.JournalState.RECONCILIATION_REQUIRED)
                return RemoteRuntimeResult(replace(receipt, execution_state='UNKNOWN_OUTCOME',
                    reconciliation_state='RECONCILIATION_REQUIRED', final_disposition='REQUIRE_RECONCILIATION'),
                    evidence, boundary_status='SECURITY_BOUNDARY_FAILURE')
            return RemoteRuntimeResult(receipt, evidence)
