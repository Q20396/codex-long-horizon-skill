"""Inactive fixed GitHub anchor experiment; no import I/O or account discovery.

Trusted host inputs and cooperative local storage only. Publication never changes
RSE/action state. Provider receipt, actual GET, retention and freshness are separate.
"""
from dataclasses import dataclass, asdict
import base64
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit

import checkpoint_crypto as crypto
import signed_checkpoints as checkpoints
from runtime_safety_envelope import CrossProcessOwner

ORIGIN = 'https://api.github.com'
API_VERSION = '2026-03-10'
MAX_RESPONSE = 32768
MAX_CAPSULE = 16384
MAX_FILES = 256
MAX_DEPTH = 8
HEADERS = (('accept', 'application/vnd.github+json'), ('content-type', 'application/json'),
           ('x-github-api-version', API_VERSION))


class AnchorFailure(ValueError):
    """Only bounded public diagnostic codes escape; no response/credential text."""
    pass


def _require(condition, reason='BINDING_MISMATCH'):
    if not condition:
        raise AnchorFailure(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _parse(data, limit):
    _require(type(data) is bytes and 0 < len(data) <= limit, 'RESPONSE_LIMIT')
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'RESPONSE_INVALID')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(AnchorFailure('RESPONSE_INVALID')))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AnchorFailure('RESPONSE_INVALID') from None


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _oid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{40}', value) is not None and value != '0' * 40


def _component(value):
    return (type(value) is str and re.fullmatch('[A-Za-z0-9_-][A-Za-z0-9_.-]{0,63}', value) is not None
            and '..' not in value and not value.endswith(('.', '.lock')))


def _path(value):
    return (type(value) is str and 1 <= len(value) <= 512
            and 1 <= len(value.split('/')) <= MAX_DEPTH - 1
            and all(_component(part) for part in value.split('/')))


def _blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def _tree_entry(value):
    """Bound Git siblings without applying our stricter target-path subset."""
    if type(value) is not dict:
        return False
    name, kind, mode = value.get('path'), value.get('type'), value.get('mode')
    try:
        return (type(name) is str and 0 < len(name.encode('utf-8')) <= 256
            and name not in ('.', '..') and '/' not in name and '\0' not in name
            and type(kind) is str and type(mode) is str
            and mode in {'tree': ('040000',), 'blob': ('100644', '100755', '120000'),
                         'commit': ('160000',)}.get(kind, ()) and _oid(value.get('sha')))
    except UnicodeError:
        return False


def _request_shape(request):
    _require(type(request) is AnchorRequest and _component(request.request_id)
        and type(request.checkpoint_bytes) is bytes and 0 < len(request.checkpoint_bytes) <= checkpoints.MAX_ARTIFACT_BYTES
        and checkpoints._opaque(request.chain_id) and checkpoints._opaque(request.installation_id)
        and checkpoints._hash(request.checkpoint_hash) and checkpoints._sequence(request.sequence)
        and checkpoints._opaque(request.key_id) and type(request.policy_reference) is str
        and re.fullmatch(r'[A-Za-z0-9_.-]{1,256}:[0-9a-f]{64}', request.policy_reference) is not None)


@dataclass(frozen=True, repr=False)
class GitHubTarget:
    origin: str
    repository_id: int
    repository: str
    branch: str
    prefix: str

    def __post_init__(self):
        _require(self.origin == ORIGIN and type(self.repository_id) is int
            and 0 < self.repository_id <= 2**53 and type(self.repository) is str
            and len(self.repository.split('/')) == 2 and all(_component(p) for p in self.repository.split('/'))
            and _path(self.branch) and _path(self.prefix), 'CONFIGURATION_INVALID')


@dataclass(frozen=True, repr=False)
class AnchorRequest:
    request_id: str
    checkpoint_bytes: bytes
    chain_id: str
    installation_id: str
    checkpoint_hash: str
    sequence: int
    key_id: str
    policy_reference: str


@dataclass(frozen=True)
class AnchorResult:
    reason: str
    send_state: str = 'NOT_SENT_THIS_INVOCATION'
    publication: str = 'OUTCOME_UNKNOWN'
    readback: str = 'NOT_OBSERVED'
    independent_retention: str = 'NOT_VALIDATED'
    freshness: str = 'UNKNOWN'
    version: str = 'UNKNOWN'
    blob: str = 'UNKNOWN'
    transport_evidence: str = 'UNKNOWN'


class GitHubHTTPS:
    """Real verified HTTPS in a bounded child, including host DNS wall time.

    No redirects, retries, proxy/netrc/env auth discovery. Host supplies optional
    Authorization explicitly; it goes only through a private pipe to the worker.
    Killing a timeout worker cannot prove absence of an already sent request.
    """
    evidence_kind = 'REAL_HTTPS_IO'

    def __init__(self, *, authorization=None):
        _require(authorization is None or (type(authorization) is str and 0 < len(authorization) <= 4096
            and all(32 <= ord(c) < 127 for c in authorization)), 'CONFIGURATION_INVALID')
        self._authorization = authorization

    def request(self, method, url, headers, body, *, timeout, response_limit):
        _require(method in ('GET', 'PUT') and urlsplit(url).scheme == 'https'
            and urlsplit(url).netloc == 'api.github.com' and len(url) <= 2048
            and type(body) is bytes and len(body) <= MAX_CAPSULE
            and type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 30
            and type(response_limit) is int and 0 < response_limit <= MAX_RESPONSE, 'CONFIGURATION_INVALID')
        root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        paths = [os.path.join(root, 'scripts'), os.path.join(root, '.agents/skills/long-horizon-engineering/scripts')]
        code = 'import sys; sys.path[:0]=' + repr(paths) + '; import checkpoint_anchor; checkpoint_anchor._https_worker()'
        data = _json(dict(method=method, url=url, headers=headers, body=base64.b64encode(body).decode(),
                          authorization=self._authorization, timeout=timeout, response_limit=response_limit))
        process, selector = None, None
        output, errors, sent = bytearray(), bytearray(), 0
        completed = False
        deadline = time.monotonic() + timeout
        try:
            process = subprocess.Popen([sys.executable, '-I', '-B', '-c', code], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                close_fds=True, start_new_session=True)
            selector = selectors.DefaultSelector()
            for stream, event, target in ((process.stdin, selectors.EVENT_WRITE, None),
                    (process.stdout, selectors.EVENT_READ, output), (process.stderr, selectors.EVENT_READ, errors)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, target)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                _require(remaining > 0, 'TRANSPORT_TIMEOUT')
                for key, _ in selector.select(remaining):
                    stream, target = key.fileobj, key.data
                    if target is None:
                        sent += os.write(stream.fileno(), data[sent:])
                        if sent == len(data):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 4096)
                        if not chunk:
                            selector.unregister(stream)
                        else:
                            _require(len(output) + len(errors) + len(chunk) <= 65536, 'RESPONSE_LIMIT')
                            target.extend(chunk)
            _require(process.wait(timeout=max(.001, deadline - time.monotonic())) == 0, 'TRANSPORT_UNAVAILABLE')
            result = _parse(bytes(output), 65536)
            _require(set(result) == {'status', 'body'}, 'RESPONSE_INVALID')
            response = base64.b64decode(result['body'], validate=True)
            completed = True
            return result['status'], (), response
        except AnchorFailure:
            raise
        except Exception:
            raise AnchorFailure('TRANSPORT_UNAVAILABLE') from None
        finally:
            cleanup_ok = True
            if process is not None:
                if not completed or process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        cleanup_ok = False
                try:
                    process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    cleanup_ok = False
                for stream in (process.stdin, process.stdout, process.stderr):
                    try:
                        stream.close()
                    except OSError:
                        cleanup_ok = False
            if selector is not None:
                try:
                    selector.close()
                except OSError:
                    cleanup_ok = False
            if not cleanup_ok:
                raise AnchorFailure('CLEANUP_UNKNOWN') from None


def _https_worker():
    """Private worker entry; diagnostic output excludes credentials and responses."""
    try:
        import remote_runtime_binding as remote
        value = _parse(sys.stdin.buffer.read(32769), 32768)
        credentials = () if value['authorization'] is None else (('authorization', value['authorization']),)
        transport = remote.HTTPSRemoteTransport(credential_headers=credentials)
        status, _, data = transport.request(value['method'], value['url'], tuple(tuple(h) for h in value['headers']),
            base64.b64decode(value['body'], validate=True), timeout=value['timeout'], response_limit=value['response_limit'])
        sys.stdout.buffer.write(_json(dict(status=status, body=base64.b64encode(data).decode())))
    except Exception:
        sys.exit(1)


class GitHubAnchor:
    """One create admission, immutable capsule and one immutable version evidence.

    All state files are immediate owner-directory children. No global dedupe after
    deletion/rollback of storage; no independent retention or RSE reconciliation.
    """
    def __init__(self, target, directory, *, verifier, write_transport, read_transport, timeout=5):
        _require(type(target) is GitHubTarget and type(directory) is str and os.path.isabs(directory)
            and os.path.realpath(directory) == directory and type(verifier) is crypto.OpenSSHCheckpointVerifier
            and type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 30,
            'CONFIGURATION_INVALID')
        for transport in (write_transport, read_transport):
            _require(callable(getattr(transport, 'request', None)) and getattr(transport, 'evidence_kind', None)
                in ('REAL_HTTPS_IO', 'SYNTHETIC_SERVICE') and (transport.evidence_kind != 'REAL_HTTPS_IO'
                    or type(transport) is GitHubHTTPS), 'CONFIGURATION_INVALID')
        self.target, self.directory, self.verifier = target, directory, verifier
        self.write_transport, self.read_transport, self.timeout = write_transport, read_transport, float(timeout)

    def _material(self, request):
        _request_shape(request)
        values = asdict(request)
        values['checkpoint_bytes'] = base64.b64encode(request.checkpoint_bytes).decode()
        return dict(schema='20396-anchor-capsule/v1', target=asdict(self.target), request=values)

    def _verify(self, request):
        try:
            data = request.checkpoint_bytes
            cp = checkpoints.checkpoint_from_json(data.decode('utf-8'))
            _require(checkpoints.checkpoint_to_json(cp).encode() == data and _digest(data) == request.checkpoint_hash
                and cp.sequence == request.sequence and type(request.sequence) is int and cp.key_id == request.key_id
                and self.verifier.policy is not None and self.verifier.policy.reference == request.policy_reference)
            checked = checkpoints.verify_checkpoint(cp, self.verifier, expected_chain_id=request.chain_id,
                expected_installation_id=request.installation_id, expected_hash=request.checkpoint_hash)
            _require(checked.valid)
            return cp
        except Exception:
            raise AnchorFailure('BINDING_MISMATCH') from None

    def _filename(self, request):
        return _digest(request.request_id.encode())

    def _read_file(self, owner, name):
        path = os.path.join(self.directory, name)
        owner.require_path(path)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=owner._dir_fd)
        try:
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and not info.st_mode & 0o077 and 0 < info.st_size <= MAX_CAPSULE, 'PERSISTENCE_INVALID')
            identity = (info.st_dev, info.st_ino)
            owner.bind(path)
            _require(owner._bindings[path] == identity, 'PERSISTENCE_INVALID')
            data = bytearray()
            while len(data) <= MAX_CAPSULE:
                chunk = os.read(fd, min(4096, MAX_CAPSULE + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            _require(len(data) == info.st_size and len(data) <= MAX_CAPSULE, 'PERSISTENCE_INVALID')
            owner.check()
            _require((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == identity, 'PERSISTENCE_INVALID')
            parsed = _parse(bytes(data), MAX_CAPSULE)
            _require(_json(parsed) == bytes(data), 'PERSISTENCE_INVALID')
            return parsed, _digest(bytes(data))
        except Exception:
            raise AnchorFailure('PERSISTENCE_INVALID') from None
        finally:
            os.close(fd)

    def _persist(self, owner, name, value):
        data = _json(value)
        _require(len(data) <= MAX_CAPSULE, 'PERSISTENCE_INVALID')
        path = os.path.join(self.directory, name)
        owner.require_path(path)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=owner._dir_fd)
        try:
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and not info.st_mode & 0o077, 'PERSISTENCE_INVALID')
            owner.bind(path)
            _require(owner._bindings[path] == (info.st_dev, info.st_ino), 'PERSISTENCE_INVALID')
            offset = 0
            while offset < len(data):
                count = os.write(fd, data[offset:])
                _require(count > 0, 'PERSISTENCE_INVALID')
                offset += count
            os.fsync(fd)
            owner.check()
        finally:
            os.close(fd)
        owner.check()
        os.fsync(owner._dir_fd)
        actual, digest = self._read_file(owner, name)
        _require(actual == value and digest == _digest(data), 'PERSISTENCE_INVALID')
        return digest

    def _scan(self, owner):
        records, observations = {}, {}
        with os.scandir(self.directory) as entries:
            for count, item in enumerate(entries, 1):
                _require(count <= MAX_FILES + 1, 'PERSISTENCE_LIMIT')
                if item.name == '.h2-owner':
                    continue
                _require(re.fullmatch('[0-9a-f]{64}\\.(capsule|observation)', item.name) is not None,
                         'PERSISTENCE_INVALID')
                value, digest = self._read_file(owner, item.name)
                stem, kind = item.name.split('.')
                if kind == 'capsule':
                    try:
                        _require(set(value) == {'schema', 'target', 'request'} and value['schema'] == '20396-anchor-capsule/v1')
                        target = GitHubTarget(**value['target'])
                        request_values = dict(value['request'])
                        request_values['checkpoint_bytes'] = base64.b64decode(request_values['checkpoint_bytes'], validate=True)
                        request = AnchorRequest(**request_values)
                        _request_shape(request)
                        _require(_component(request.request_id) and self._filename(request) == stem
                            and self._material_for(target, request) == value
                            and _digest(request.checkpoint_bytes) == request.checkpoint_hash)
                        cp = checkpoints.checkpoint_from_json(request.checkpoint_bytes.decode())
                        _require(checkpoints.checkpoint_to_json(cp).encode() == request.checkpoint_bytes
                            and cp.chain_id_ref == checkpoints._ref(request.chain_id)
                            and cp.installation_ref == checkpoints._ref(request.installation_id)
                            and cp.sequence == request.sequence and cp.key_id == request.key_id)
                    except Exception:
                        raise AnchorFailure('PERSISTENCE_INVALID') from None
                    records[stem] = (value, digest)
                else:
                    observations[stem] = value
        for stem, observed in observations.items():
            _require(stem in records, 'PERSISTENCE_INVALID')
            capsule, digest = records[stem]
            _require(type(observed) is dict and set(observed) == {'schema', 'capsule_digest', 'request_id',
                'checkpoint_hash', 'target', 'commit', 'blob', 'evidence'}
                and observed['schema'] == '20396-anchor-observation/v1'
                and observed['capsule_digest'] == digest and observed['request_id'] == capsule['request']['request_id']
                and observed['checkpoint_hash'] == capsule['request']['checkpoint_hash']
                and observed['target'] == capsule['target'] and _oid(observed['commit']) and _oid(observed['blob'])
                and observed['blob'] == _blob(base64.b64decode(capsule['request']['checkpoint_bytes']))
                and observed['evidence'] in ('PROVIDER_RECEIPT', 'ACTUAL_GET'), 'PERSISTENCE_INVALID')
        return records, observations

    @staticmethod
    def _material_for(target, request):
        values = asdict(request)
        values['checkpoint_bytes'] = base64.b64encode(request.checkpoint_bytes).decode()
        return dict(schema='20396-anchor-capsule/v1', target=asdict(target), request=values)

    def _observe(self, owner, request, capsule_digest, commit, blob, evidence, existing):
        _require(_oid(commit) and blob == _blob(request.checkpoint_bytes))
        if existing is not None:
            _require(existing['commit'] == commit and existing['blob'] == blob)
            return existing
        value = dict(schema='20396-anchor-observation/v1', capsule_digest=capsule_digest,
            request_id=request.request_id, checkpoint_hash=request.checkpoint_hash, target=asdict(self.target),
            commit=commit, blob=blob, evidence=evidence)
        self._persist(owner, self._filename(request) + '.observation', value)
        return value

    def _call(self, transport, method, suffix, body=b''):
        try:
            status, headers, data = transport.request(method, ORIGIN + '/repos/' + self.target.repository + suffix,
                HEADERS, body, timeout=self.timeout, response_limit=MAX_RESPONSE)
        except AnchorFailure:
            raise
        except Exception:
            raise AnchorFailure('TRANSPORT_UNAVAILABLE') from None
        _require(type(status) is int and 100 <= status <= 599 and type(headers) is tuple
            and len(headers) <= 128 and all(type(h) is tuple and len(h) == 2
            and all(type(v) is str and len(v) <= 8192 for v in h) for h in headers)
            and sum(len(k) + len(v) for k, v in headers) <= 65536, 'RESPONSE_INVALID')
        _require(type(data) is bytes and len(data) <= MAX_RESPONSE, 'RESPONSE_LIMIT')
        if status not in ((201,) if method == 'PUT' else (200,)):
            raise AnchorFailure('NOT_OBSERVED' if status == 404 else 'HTTP_' + str(status))
        value = _parse(data, MAX_RESPONSE)
        _require(type(value) is dict, 'RESPONSE_INVALID')
        return value

    def _repository(self, transport):
        value = self._call(transport, 'GET', '')
        _require(type(value.get('id')) is int and value['id'] == self.target.repository_id
            and value.get('full_name') == self.target.repository)

    def _version_bytes(self, request):
        transport = self.read_transport
        self._repository(transport)
        ref = self._call(transport, 'GET', '/git/ref/heads/' + self.target.branch)
        _require(ref.get('ref') == 'refs/heads/' + self.target.branch and type(ref.get('object')) is dict
            and ref['object'].get('type') == 'commit' and _oid(ref['object'].get('sha')))
        commit = ref['object']['sha']
        value = self._call(transport, 'GET', '/git/commits/' + commit)
        _require(value.get('sha') == commit and type(value.get('tree')) is dict and _oid(value['tree'].get('sha')))
        tree = value['tree']['sha']
        parts = (self.target.prefix + '/' + request.request_id + '.json').split('/')
        for index, part in enumerate(parts):
            value = self._call(transport, 'GET', '/git/trees/' + tree)
            _require(value.get('sha') == tree and value.get('truncated') is False
                and type(value.get('tree')) is list and len(value['tree']) <= 256, 'RESPONSE_INVALID')
            entries = value['tree']
            _require(all(_tree_entry(e) for e in entries)
                and len({e['path'] for e in entries}) == len(entries), 'RESPONSE_INVALID')
            entry = next((e for e in entries if e['path'] == part), None)
            _require(entry is not None, 'NOT_OBSERVED')
            if index == len(parts) - 1:
                _require(entry.get('type') == 'blob' and entry.get('mode') in ('100644', '100755'))
                blob = entry['sha']
            else:
                _require(entry.get('type') == 'tree' and entry.get('mode') == '040000')
                tree = entry['sha']
        value = self._call(transport, 'GET', '/git/blobs/' + blob)
        _require(value.get('sha') == blob and value.get('encoding') == 'base64'
            and type(value.get('size')) is int and 0 < value['size'] <= checkpoints.MAX_ARTIFACT_BYTES
            and type(value.get('content')) is str)
        try:
            # GitHub may wrap base64 with LF. No other non-base64 octets accepted.
            data = base64.b64decode(value['content'].replace('\n', ''), validate=True)
        except Exception:
            raise AnchorFailure('BINDING_MISMATCH') from None
        _require(len(data) == value['size'] and _blob(data) == blob and data == request.checkpoint_bytes)
        return commit, blob

    def _result(self, reason, observation=None, *, sent=False, readback=False, freshness='UNKNOWN'):
        return AnchorResult(reason, 'CREATE_ATTEMPTED' if sent else 'NOT_SENT_THIS_INVOCATION',
            'PUBLICATION_CONFIRMED_BY_PROVIDER' if observation and observation['evidence'] == 'PROVIDER_RECEIPT'
            else 'OUTCOME_UNKNOWN', 'READBACK_OBSERVED' if readback else 'NOT_OBSERVED',
            freshness=freshness, version=observation['commit'] if observation else 'UNKNOWN',
            blob=observation['blob'] if observation else 'UNKNOWN',
            transport_evidence=self.read_transport.evidence_kind if readback else self.write_transport.evidence_kind)

    def _read(self, owner, request, digest, observation, **freshness_inputs):
        self._verify(request)
        commit, blob = self._version_bytes(request)
        observation = self._observe(owner, request, digest, commit, blob, 'ACTUAL_GET', observation)
        owner.check()
        return self._result('VALID', observation, readback=True, freshness=self._freshness(request, **freshness_inputs))

    def _freshness(self, request, *, expected_head=None, trusted_clock=None, max_age=None):
        cp = checkpoints.checkpoint_from_json(request.checkpoint_bytes.decode())
        supplied = False
        if expected_head is not None:
            _require(type(expected_head) is tuple and len(expected_head) == 2
                and type(expected_head[0]) is int and expected_head[0] >= 1 and checkpoints._hash(expected_head[1]),
                'FRESHNESS_INPUT_INVALID')
            supplied = True
            if (cp.sequence, cp.chain_head_hash) != expected_head:
                return 'STALE'
        if trusted_clock is not None or max_age is not None:
            _require(checkpoints._time(trusted_clock) and type(max_age) in (int, float)
                and math.isfinite(max_age) and max_age >= 0, 'FRESHNESS_INPUT_INVALID')
            supplied = True
            if not 0 <= trusted_clock - cp.created_at <= max_age:
                return 'STALE'
        return 'FRESH_RELATIVE_TO_TRUSTED_INPUTS' if supplied else 'UNKNOWN'

    def _operation(self, request, publish, **freshness_inputs):
        owner, sent, observation = None, False, None
        try:
            material = self._material(request)
            info = os.lstat(self.directory)
            _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
                     'PERSISTENCE_INVALID')
            owner = CrossProcessOwner(self.directory)
            with owner.operation():
                records, observations = self._scan(owner)
                stem = self._filename(request)
                if stem in records:
                    capsule, digest = records[stem]
                    _require(capsule == material, 'CONFLICT')
                    observation = observations.get(stem)
                    return self._read(owner, request, digest, observation, **freshness_inputs)
                _require(publish, 'CAPSULE_MISSING')
                for capsule, _ in records.values():
                    _require(not (capsule['target'] == material['target']
                        and capsule['request']['checkpoint_hash'] == request.checkpoint_hash), 'DUPLICATE_CHECKPOINT_TARGET')
                self._verify(request)
                digest = self._persist(owner, stem + '.capsule', material)
                owner.check()
                # Even repository preflight GET follows complete capsule durability.
                self._repository(self.write_transport)
                owner.check()
                path = self.target.prefix + '/' + request.request_id + '.json'
                body = _json(dict(message='20396 checkpoint anchor ' + request.request_id,
                                  content=base64.b64encode(request.checkpoint_bytes).decode(), branch=self.target.branch))
                sent = True
                value = self._call(self.write_transport, 'PUT', '/contents/' + path, body)
                _require(type(value.get('content')) is dict and value['content'].get('path') == path
                    and value['content'].get('sha') == _blob(request.checkpoint_bytes)
                    and type(value.get('commit')) is dict and _oid(value['commit'].get('sha')))
                observation = dict(evidence='PROVIDER_RECEIPT', commit=value['commit']['sha'], blob=value['content']['sha'])
                observation = self._observe(owner, request, digest, value['commit']['sha'], value['content']['sha'],
                                            'PROVIDER_RECEIPT', None)
                return self._result('VALID', observation, sent=True)
        except AnchorFailure as error:
            return self._result(str(error), observation, sent=sent)
        except ValueError as error:
            reason = str(error) if str(error) in ('OWNERSHIP_CONTENDED', 'OWNERSHIP_PLATFORM_UNSUPPORTED',
                'OWNERSHIP_STORAGE_UNSUPPORTED', 'OWNERSHIP_IDENTITY_INVALID',
                'OWNERSHIP_ACQUISITION_FAILED') else 'PERSISTENCE_INVALID'
            return self._result(reason, observation, sent=sent)
        except Exception:
            return self._result('PERSISTENCE_INVALID', observation, sent=sent)
        finally:
            if owner is not None:
                owner.close()

    def publish(self, request):
        """Explicit host authorization only; existing capsule always GET-only."""
        return self._operation(request, True)

    def read(self, request, *, expected_head=None, trusted_clock=None, max_age=None):
        """GET-only recovery; capsule absence never establishes historic absence."""
        return self._operation(request, False, expected_head=expected_head, trusted_clock=trusted_clock, max_age=max_age)
