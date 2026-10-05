"""Bounded experimental remote effects through RSE; trusted host transports only.

No network, discovery, registration or credentials on import. The journal is
same-process only. An allowlisted host is not proof of public IP space, DNS
integrity or server trust. Credentials never belong in RemoteRuntimePayload.
"""
from __future__ import annotations
from dataclasses import dataclass, fields, replace
import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import ssl
import tempfile
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
                (('content-type', 'application/json'), ('accept', 'application/vnd.github+json')), body, observe=observed.update)
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
        status, headers, data = self._request(p, 'GET', p.target + '?' + query, (('accept', 'application/vnd.github+json'),), observe=observe)
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
    def __init__(self, adapter, payload, context, now):
        self.adapter, self.payload, self.context, self.now = adapter, payload, context, now
        self.outcome = None

    def execute(self, action):
        self.outcome = self.adapter._run(action, self.payload, self.context, self.now)
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
        try:
            bound = self._bound(action, payload)
            self._authority(action, context, now)
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
                invocation = _Invocation(adapter, payload, context, now)
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
        try:
            bound = self._bound(action, payload); self._authority(action, context, now)
            decision = rse.evaluate_policy(bound, policy_stack, authorization, now)
            if decision.disposition != 'ALLOW':
                return RemoteRuntimeResult(rse._receipt(action, decision))
            adapter = self._adapter(action)
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
