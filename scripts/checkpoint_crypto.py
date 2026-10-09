"""Inactive, repository-only Ed25519/OpenSSH checkpoint adapter.

Trusted callers configure the backend, key handle and immutable public policy.
Import performs no key/policy discovery, subprocess, signing or file writes.
This is not production enrollment, custody, authorization or hostile-host isolation.
"""
from dataclasses import dataclass
from contextlib import contextmanager
import base64
import hashlib
import json
import math
import os
import re
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time

import signed_checkpoints as checkpoints

NAMESPACE = '20396-security-checkpoint/v1'
POLICY_SCHEMA = '20396-checkpoint-trust-policy/v1'
MAX_MESSAGE_BYTES = 8192
MAX_POLICY_BYTES = 32768
MAX_POLICY_KEYS = 32


class PolicyError(ValueError):
    def __init__(self):
        super().__init__('POLICY_INVALID')


class BackendFailure(RuntimeError):
    """Bounded public reason only; never backend stderr or a sensitive key path."""
    def __init__(self, reason):
        if reason not in ('BACKEND_UNAVAILABLE', 'BACKEND_UNSUPPORTED', 'BACKEND_TIMEOUT',
                          'BACKEND_OUTPUT_LIMIT', 'BACKEND_FAILED', 'CLEANUP_UNKNOWN',
                          'SIGNING_KEY_UNAVAILABLE'):
            reason = 'BACKEND_FAILED'
        super().__init__(reason)
        self.reason = reason


def _opaque(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,256}', value) is not None


def _absolute(value):
    return (type(value) is str and 0 < len(value) <= 4096 and os.path.isabs(value)
            and '\x00' not in value and all(p not in ('.', '..') for p in value.split('/')))


def _message(value):
    if type(value) is not bytes or not 0 < len(value) <= MAX_MESSAGE_BYTES:
        raise ValueError('MESSAGE_INVALID')


class _Reader:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def take(self, count):
        if count < 0 or self.offset + count > len(self.data):
            raise ValueError('SIGNATURE_ENCODING_INVALID')
        start = self.offset
        self.offset += count
        return self.data[start:self.offset]

    def uint32(self):
        return struct.unpack('>I', self.take(4))[0]

    def string(self):
        return self.take(self.uint32())

    def end(self):
        if self.offset != len(self.data):
            raise ValueError('SIGNATURE_ENCODING_INVALID')


def _public_blob(blob):
    reader = _Reader(blob)
    if reader.string() != b'ssh-ed25519' or len(reader.string()) != 32:
        raise ValueError('PUBLIC_KEY_INVALID')
    reader.end()
    return blob


def _public_key(text):
    if type(text) is not str or len(text) > 256:
        raise ValueError('PUBLIC_KEY_INVALID')
    parts = text.split(' ')
    if len(parts) != 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('PUBLIC_KEY_INVALID')
    blob = base64.b64decode(parts[1], validate=True)
    if base64.b64encode(blob).decode('ascii') != parts[1]:
        raise ValueError('PUBLIC_KEY_INVALID')
    return _public_blob(blob)


def _signature(data):
    """Strict raw SSHSIG v1, Ed25519, empty reserved field and SHA512 only."""
    if type(data) is not bytes or not 0 < len(data) <= checkpoints.MAX_SIGNATURE_BYTES:
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    reader = _Reader(data)
    if reader.take(6) != b'SSHSIG' or reader.uint32() != 1:
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    public = _public_blob(reader.string())
    if (reader.string() != NAMESPACE.encode('ascii') or reader.string() != b''
            or reader.string() != b'sha512'):
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    signature = _Reader(reader.string())
    if signature.string() != b'ssh-ed25519' or len(signature.string()) != 64:
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    signature.end()
    reader.end()
    return public


def _armor(data):
    encoded = base64.b64encode(data)
    return (b'-----BEGIN SSH SIGNATURE-----\n'
            + b'\n'.join(encoded[i:i + 70] for i in range(0, len(encoded), 70))
            + b'\n-----END SSH SIGNATURE-----\n')


def _unarmor(data):
    lines = data.splitlines()
    if (len(lines) < 3 or lines[0] != b'-----BEGIN SSH SIGNATURE-----'
            or lines[-1] != b'-----END SSH SIGNATURE-----'
            or not data.endswith(b'\n') or b'\r' in data):
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    raw = base64.b64decode(b''.join(lines[1:-1]), validate=True)
    if _armor(raw) != data:
        raise ValueError('SIGNATURE_ENCODING_INVALID')
    _signature(raw)
    return raw


@dataclass(frozen=True, repr=False)
class PolicyKey:
    key_id: str
    principal: str
    public_key: str
    fingerprint: str
    purpose: str
    status: str

    def __post_init__(self):
        try:
            blob = _public_key(self.public_key)
            fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode('ascii').rstrip('=')
            if (not _opaque(self.key_id) or not _opaque(self.principal)
                    or type(self.fingerprint) is not str or self.fingerprint != fingerprint
                    or type(self.purpose) is not str or self.purpose != NAMESPACE
                    or type(self.status) is not str or self.status not in ('ACTIVE', 'REVOKED')):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise PolicyError() from None


@dataclass(frozen=True, repr=False)
class TrustPolicy:
    schema_version: str
    policy_version: str
    keys: tuple

    def __post_init__(self):
        if (type(self.schema_version) is not str or self.schema_version != POLICY_SCHEMA
                or not _opaque(self.policy_version) or type(self.keys) is not tuple
                or not 0 <= len(self.keys) <= MAX_POLICY_KEYS
                or any(type(key) is not PolicyKey for key in self.keys)):
            raise PolicyError()
        for field in ('key_id', 'principal', 'public_key'):
            if len({getattr(key, field) for key in self.keys}) != len(self.keys):
                raise PolicyError()

    @property
    def reference(self):
        values = dict(schema_version=self.schema_version, policy_version=self.policy_version,
                      keys=[vars(key) for key in self.keys])
        material = json.dumps(values, sort_keys=True, separators=(',', ':')).encode('ascii')
        return self.policy_version + ':' + hashlib.sha256(material).hexdigest()


def load_policy(text):
    """Parse explicit public JSON bytes/text only; no default path or file discovery."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PolicyError()
            result[key] = value
        return result

    try:
        if type(text) is bytes:
            if len(text) > MAX_POLICY_BYTES:
                raise PolicyError()
            text = text.decode('utf-8')
        if type(text) is not str or len(text.encode('utf-8')) > MAX_POLICY_BYTES:
            raise PolicyError()
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(PolicyError()))
        if (type(value) is not dict or set(value) != {'schema_version', 'policy_version', 'keys'}
                or type(value['keys']) is not list or len(value['keys']) > MAX_POLICY_KEYS):
            raise PolicyError()
        keys = []
        for key in value['keys']:
            if type(key) is not dict or set(key) != {'key_id', 'principal', 'public_key',
                                                   'fingerprint', 'purpose', 'status'}:
                raise PolicyError()
            keys.append(PolicyKey(**key))
        return TrustPolicy(value['schema_version'], value['policy_version'], tuple(keys))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise PolicyError() from None


@contextmanager
def _workspace():
    directory = None
    try:
        directory = tempfile.mkdtemp(prefix='checkpoint-crypto-')
        os.chmod(directory, 0o700)
        yield directory
    except OSError:
        raise BackendFailure('BACKEND_FAILED') from None
    finally:
        if directory is not None:
            try:
                shutil.rmtree(directory)
                if os.path.lexists(directory):
                    raise OSError()
            except OSError:
                raise BackendFailure('CLEANUP_UNKNOWN') from None


def _write(directory, name, data):
    path = os.path.join(directory, name)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        stream = os.fdopen(descriptor, 'wb')
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            raise BackendFailure('CLEANUP_UNKNOWN') from None
        raise
    try:
        stream.write(data)
    finally:
        try:
            stream.close()
        except OSError:
            raise BackendFailure('CLEANUP_UNKNOWN') from None
    return path


class OpenSSHBackend:
    """Explicit trusted local executable; no PATH search, inherited agent or shell.

    POSIX Darwin/Linux only. Limits include combined stdout/stderr while produced,
    not an unbounded communicate() followed by a size check. Backend failure is
    not mathematical invalidity. The operator must protect executable/key ancestry.
    """
    def __init__(self, executable, *, timeout=5.0, max_output_bytes=8192):
        if (not _absolute(executable) or type(timeout) not in (int, float)
                or not math.isfinite(timeout) or not 0 < timeout <= 30
                or type(max_output_bytes) is not int or not 512 <= max_output_bytes <= 65536):
            raise ValueError('BACKEND_CONFIGURATION_INVALID')
        self.executable = executable
        self.timeout = float(timeout)
        self.max_output_bytes = max_output_bytes

    def _run(self, args, data):
        _message(data)
        if os.name != 'posix' or sys.platform not in ('darwin', 'linux'):
            raise BackendFailure('BACKEND_UNSUPPORTED')
        try:
            info = os.lstat(self.executable)
            if not stat.S_ISREG(info.st_mode) or not os.access(self.executable, os.X_OK):
                raise OSError()
        except OSError:
            raise BackendFailure('BACKEND_UNAVAILABLE') from None
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'SSH_ASKPASS_REQUIRE': 'never'}
        process, selector = None, None
        output, errors, sent = bytearray(), bytearray(), 0
        deadline = time.monotonic() + self.timeout
        cleanup_ok = True
        completed = False
        try:
            process = subprocess.Popen([self.executable] + args, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=False,
                close_fds=True, start_new_session=True)
            selector = selectors.DefaultSelector()
            for stream, mode, target in ((process.stdin, selectors.EVENT_WRITE, None),
                                        (process.stdout, selectors.EVENT_READ, output),
                                        (process.stderr, selectors.EVENT_READ, errors)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, mode, target)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BackendFailure('BACKEND_TIMEOUT')
                for key, _ in selector.select(remaining):
                    stream, target = key.fileobj, key.data
                    if target is None:
                        try:
                            sent += os.write(stream.fileno(), data[sent:])
                        except BrokenPipeError:
                            sent = len(data)
                        if sent == len(data):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 4096)
                        if not chunk:
                            selector.unregister(stream)
                        else:
                            if len(output) + len(errors) + len(chunk) > self.max_output_bytes:
                                raise BackendFailure('BACKEND_OUTPUT_LIMIT')
                            target.extend(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BackendFailure('BACKEND_TIMEOUT')
            code = process.wait(timeout=remaining)
            completed = code == 0
            return code, bytes(output), bytes(errors)
        except subprocess.TimeoutExpired:
            raise BackendFailure('BACKEND_TIMEOUT') from None
        except (OSError, ValueError):
            raise BackendFailure('BACKEND_FAILED') from None
        finally:
            if process is not None:
                # A leader can exit while descendants still hold our pipe ends.
                # Kill the original session group on failure even after leader exit.
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
                raise BackendFailure('CLEANUP_UNKNOWN') from None


class OpenSSHCheckpointSigner:
    def __init__(self, backend, key_id, signing_key_path):
        if type(backend) is not OpenSSHBackend or not _opaque(key_id) or not _absolute(signing_key_path):
            raise ValueError('SIGNER_CONFIGURATION_INVALID')
        self.backend, self.key_id, self._key_path = backend, key_id, signing_key_path

    def sign(self, message_bytes):
        _message(message_bytes)
        try:
            info = os.lstat(self._key_path)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or not 0 < info.st_size <= 16384):
                raise OSError()
        except OSError:
            raise BackendFailure('SIGNING_KEY_UNAVAILABLE') from None
        # Inspect the explicitly provided handle before any signing, rather than
        # signing an unsupported RSA/ECDSA key then merely rejecting its output.
        code, public_output, _ = self.backend._run(['-y', '-P', '', '-f', self._key_path], message_bytes)
        try:
            if code != 0:
                raise ValueError()
            line = public_output.decode('ascii').rstrip('\n')
            if '\n' in line or '\r' in line:
                raise ValueError()
            # ssh-keygen -y may preserve the key's public comment. Comments have
            # no trust meaning; the public-policy format remains comment-free.
            public = _public_key(' '.join(line.split(' ', 2)[:2]))
        except (ValueError, UnicodeError):
            raise BackendFailure('SIGNING_KEY_UNAVAILABLE') from None
        code, output, _ = self.backend._run(['-Y', 'sign', '-f', self._key_path,
                                            '-n', NAMESPACE, '-O', 'hashalg=sha512'], message_bytes)
        if code != 0:
            raise BackendFailure('BACKEND_FAILED')
        try:
            raw = _unarmor(output)
            if _signature(raw) != public:
                raise ValueError()
        except (ValueError, TypeError):
            raise BackendFailure('BACKEND_FAILED') from None
        return checkpoints.SignatureEnvelope(checkpoints.SignatureAlgorithm.ED25519, self.key_id, raw)


@dataclass(frozen=True)
class SignatureAssessment:
    cryptographic_validity: str
    signer_trust: str
    reason: str
    policy_reference: str = None


class OpenSSHCheckpointVerifier:
    def __init__(self, backend, policy):
        if type(backend) is not OpenSSHBackend or (policy is not None and type(policy) is not TrustPolicy):
            raise ValueError('VERIFIER_CONFIGURATION_INVALID')
        self.backend, self.policy = backend, policy

    def assess(self, message_bytes, envelope):
        reference = self.policy.reference if self.policy is not None else None
        trust = 'UNKNOWN' if self.policy is None else 'UNTRUSTED'
        try:
            _message(message_bytes)
            if type(envelope) is not checkpoints.SignatureEnvelope:
                raise ValueError()
            # Revalidate typed but possibly caller-mutated envelopes.
            envelope = checkpoints.SignatureEnvelope(envelope.algorithm, envelope.key_id, envelope.signature)
            if envelope.algorithm != checkpoints.SignatureAlgorithm.ED25519:
                return SignatureAssessment('NOT_ASSESSED', trust, 'ALGORITHM_UNSUPPORTED', reference)
            public = _signature(envelope.signature)
        except (ValueError, TypeError, AttributeError):
            return SignatureAssessment('INVALID', trust, 'SIGNATURE_ENCODING_INVALID', reference)
        key = next((key for key in self.policy.keys if key.key_id == envelope.key_id), None) if self.policy else None
        if key is not None and key.status == 'ACTIVE' and _public_key(key.public_key) == public:
            trust = 'TRUSTED'
        try:
            with _workspace() as directory:
                signature = _write(directory, 'signature', _armor(envelope.signature))
                # This command checks mathematics using the SSHSIG-carried key;
                # it never writes that key into the independently supplied policy.
                code, _, errors = self.backend._run(['-Y', 'check-novalidate', '-n', NAMESPACE,
                                                     '-s', signature], message_bytes)
                if code != 0:
                    if errors.strip() == b'Signature verification failed: incorrect signature':
                        assessment = SignatureAssessment('INVALID', trust, 'SIGNATURE_INVALID', reference)
                    else:
                        assessment = SignatureAssessment('UNKNOWN', trust, 'BACKEND_FAILED', reference)
                elif trust != 'TRUSTED':
                    assessment = SignatureAssessment('VALID', trust, 'KEY_NOT_TRUSTED' if self.policy else 'POLICY_UNAVAILABLE', reference)
                else:
                    allowed = _write(directory, 'allowed-signers', (key.principal + ' namespaces="'
                        + NAMESPACE + '" ' + key.public_key + '\n').encode('ascii'))
                    code, _, _ = self.backend._run(['-Y', 'verify', '-f', allowed, '-I', key.principal,
                                                   '-n', NAMESPACE, '-s', signature], message_bytes)
                    assessment = SignatureAssessment('VALID' if code == 0 else 'UNKNOWN',
                        trust if code == 0 else 'UNKNOWN', 'VALID' if code == 0 else 'BACKEND_FAILED', reference)
            return assessment
        except BackendFailure as failure:
            return SignatureAssessment('UNKNOWN', 'UNKNOWN', failure.reason, reference)

    def verify(self, message_bytes, envelope):
        assessment = self.assess(message_bytes, envelope)
        accepted = assessment.cryptographic_validity == 'VALID' and assessment.signer_trust == 'TRUSTED'
        reason = 'VALID' if accepted else ('KEY_NOT_TRUSTED' if assessment.signer_trust == 'UNTRUSTED'
                                         else assessment.reason)
        return checkpoints.SignatureVerification(accepted, reason,
            envelope.algorithm if type(envelope) is checkpoints.SignatureEnvelope else None,
            envelope.key_id if type(envelope) is checkpoints.SignatureEnvelope else None)
