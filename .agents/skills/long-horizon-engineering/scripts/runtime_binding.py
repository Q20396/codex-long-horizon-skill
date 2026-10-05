"""Experimental trusted local effects; same-process lifecycle, never an OS sandbox.

Controllers own approved payload commitments, current RSE authority and journals.
Adapters are trusted Python code. Child-internal effects are not observed or
contained. No effects, discovery, registration or environment changes on import.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from types import MappingProxyType
import uuid

import runtime_safety_envelope as rse
import critical_execution_trace as cet
import security_authority_chain as sc

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
UNBORN_GIT_PARENT = 'UNBORN'
BOUND_ACTIONS = frozenset(rse.ActionClass[n] for n in (
    'READ_FILE', 'WRITE_FILE', 'CREATE_FILE', 'DELETE_FILE', 'MOVE_FILE',
    'EXECUTE_PROCESS', 'GIT_STAGE', 'GIT_COMMIT'))


def _require(condition, reason='MALFORMED_RUNTIME_PAYLOAD'):
    if not condition:
        raise ValueError(reason)


def _text(value, limit=4096):
    return type(value) is str and 0 < len(value.encode('utf-8')) <= limit and '\0' not in value


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _limit(value, maximum):
    _require(type(value) is int and 0 < value <= maximum, 'INVALID_RUNTIME_CONFIG')
    return value


def _duration(value, maximum=300):
    _require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum,
             'INVALID_TIMEOUT')
    return value


def _git_path(value):
    return (_text(value) and not value.startswith(('/', '-'))
        and all(p not in ('', '.', '..', '.git') for p in value.split('/'))
        and not any(c in value for c in '*?[]\\:\n\r'))


def _git_oid(value, length=None):
    return (type(value) is str and len(value) in ((length,) if length else (40, 64))
            and re.fullmatch('[0-9a-f]+', value) is not None)


@dataclass(frozen=True, repr=False)
class RuntimePayload:
    action_id: str
    content_bytes: bytes | None = None
    argv: tuple | None = None
    cwd: str | None = None
    environment: tuple | None = None
    commit_message: str | None = None
    git_paths: tuple | None = None
    timeout: float | str = 'DEFAULT'
    expected_git_tree: str | None = None
    expected_git_parent: str | None = None

    def __post_init__(self):
        _require(_text(self.action_id, 1024))
        _require(self.content_bytes is None or (type(self.content_bytes) is bytes and len(self.content_bytes) <= MAX_FILE_BYTES))
        _require(self.argv is None or (type(self.argv) is tuple and 0 < len(self.argv) <= 128
            and all(_text(a) for a in self.argv) and sum(len(a.encode()) for a in self.argv) <= 32768))
        _require(self.cwd is None or _text(self.cwd))
        _require(self.environment is None or (type(self.environment) is tuple and len(self.environment) <= 64
            and all(type(p) is tuple and len(p) == 2 and _text(p[0], 128) and type(p[1]) is str
                    and len(p[1].encode()) <= 4096 and '\0' not in p[1] for p in self.environment)
            and len({p[0] for p in self.environment}) == len(self.environment)))
        _require(self.commit_message is None or _text(self.commit_message, 16384))
        _require(self.expected_git_tree is None or _git_oid(self.expected_git_tree))
        _require(self.expected_git_parent is None or self.expected_git_parent == UNBORN_GIT_PARENT
                 or _git_oid(self.expected_git_parent))
        _require(self.git_paths is None or (type(self.git_paths) is tuple and 0 < len(self.git_paths) <= 128
            and all(_git_path(p) for p in self.git_paths) and len(set(self.git_paths)) == len(self.git_paths)))
        if self.timeout != 'DEFAULT':
            _duration(self.timeout)

    def digest(self):
        values = dict(action_id=self.action_id, content_digest=None if self.content_bytes is None else _hash(self.content_bytes),
            content_size=None if self.content_bytes is None else len(self.content_bytes), argv=self.argv, cwd=self.cwd,
            environment=None if self.environment is None else sorted(self.environment),
            commit_message=self.commit_message, git_paths=self.git_paths, timeout=self.timeout,
            expected_git_tree=self.expected_git_tree, expected_git_parent=self.expected_git_parent)
        return _hash(json.dumps(values, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())

    def validate_for(self, action):
        _require(type(action) is rse.ActionRequest and self.action_id == action.action_id)
        names = ('content_bytes', 'argv', 'cwd', 'environment', 'commit_message', 'git_paths',
                 'expected_git_tree', 'expected_git_parent')
        permitted = {
            rse.ActionClass.WRITE_FILE: {'content_bytes'}, rse.ActionClass.CREATE_FILE: {'content_bytes'},
            rse.ActionClass.EXECUTE_PROCESS: {'argv', 'cwd', 'environment'},
            rse.ActionClass.GIT_STAGE: {'git_paths'}, rse.ActionClass.GIT_COMMIT:
                {'commit_message', 'expected_git_tree', 'expected_git_parent'},
        }.get(action.action_class, set())
        _require(all(getattr(self, name) is None for name in names if name not in permitted))
        required = permitted - {'cwd', 'environment'}
        _require(all(getattr(self, name) is not None for name in required))
        _require(action.action_class == rse.ActionClass.EXECUTE_PROCESS or self.timeout == 'DEFAULT')


@dataclass(frozen=True, repr=False)
class RuntimeOperationEvidence:
    payload_digest: str
    reason: str
    content_digest: str | None = None
    byte_count: int = 0
    exit_code: int | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    commit_sha: str | None = None
    before_digest: str | None = None
    tree_sha: str | None = None
    parent_sha: str | None = None


@dataclass(frozen=True, repr=False)
class RuntimeBindingResult:
    receipt: rse.SecurityReceipt
    evidence: RuntimeOperationEvidence | None = None
    events: tuple = ()
    divergences: tuple = ()
    content_bytes: bytes | None = None
    stdout: bytes = b''
    stderr: bytes = b''
    boundary_status: str = 'OK'
    completeness: cet.TraceCompleteness = cet.TraceCompleteness.PARTIAL


@dataclass(frozen=True, repr=False)
class _Outcome:
    state: rse.ExecutionState
    evidence: RuntimeOperationEvidence
    events: tuple = ()
    content_bytes: bytes | None = None
    stdout: bytes = b''
    stderr: bytes = b''


def _event(action, context, now, kind=None, exit_code=None):
    kind = kind or cet.ACTION_EVENTS[action.action_class]
    return cet.CriticalEvent(uuid.uuid4().hex, kind, context, cet.ObservationSource.ADAPTER_OBSERVED,
        now, action.target, action.data_classification, capability=action.capability,
        status=cet.EventStatus.COMPLETED, exit_code=exit_code,
        destination=action.destination if kind == cet.CriticalEventType.FILE_MOVE else None)


def _platform():
    _require(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY')
        and all(f in os.supports_dir_fd for f in (os.open, os.stat, os.unlink, os.link))
        and all(f in os.supports_follow_symlinks for f in (os.stat, os.link)), 'PLATFORM_UNSUPPORTED')


def _absolute(path):
    _require(_text(path) and path.startswith('/') and not path.startswith('//')
        and all(p not in ('.', '..') for p in path.split('/')) and '\\' not in path, 'UNSAFE_PATH')
    return str(PurePosixPath(path))


@contextmanager
def _directory(path):
    """Walk every component from / with no-follow directory opens."""
    _platform(); path = _absolute(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in PurePosixPath(path).parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        yield fd
    finally:
        os.close(fd)


def _contained(root, path):
    path = _absolute(path)
    _require(os.path.commonpath((root, path)) == root, 'PATH_OUT_OF_SCOPE')
    return path


@contextmanager
def _parent(root, path):
    path = _contained(root, path)
    _require(path != root, 'REGULAR_FILE_REQUIRED')
    with _directory(str(PurePosixPath(path).parent)) as fd:
        yield fd, PurePosixPath(path).name


def _regular(fd, name, *, missing=False):
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        if missing:
            return None
        raise
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_FILE_REQUIRED')
    return info


def _read(fd, name, maximum):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        info = os.fstat(handle)
        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_FILE_REQUIRED')
        _require(info.st_size <= maximum, 'TOO_LARGE')
        data = bytearray()
        while len(data) <= maximum:
            part = os.read(handle, min(65536, maximum + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        _require(len(data) <= maximum, 'TOO_LARGE')
        return bytes(data), info
    finally:
        os.close(handle)


class FilesystemAdapter:
    def __init__(self, *, workspace_root, max_read_bytes=MAX_FILE_BYTES, max_write_bytes=MAX_FILE_BYTES):
        self.root = _absolute(workspace_root)
        self.max_read_bytes = _limit(max_read_bytes, MAX_FILE_BYTES)
        self.max_write_bytes = _limit(max_write_bytes, MAX_FILE_BYTES)

    def execute(self, action):
        raise ValueError('RUNTIME_BINDING_REQUIRED')

    def run(self, action, payload, context, now):
        """Trusted low-level adapter boundary; public controllers use RuntimeBinding."""
        effect = False; events = (); data = None; digest = None; count = 0; before_digest = None
        try:
            _require(action.action_class in {rse.ActionClass[n] for n in
                ('READ_FILE', 'WRITE_FILE', 'CREATE_FILE', 'DELETE_FILE', 'MOVE_FILE')}, 'NOT_BOUND')
            with _parent(self.root, action.target) as (fd, name):
                kind = action.action_class
                if kind == rse.ActionClass.READ_FILE:
                    data, _ = _read(fd, name, self.max_read_bytes)
                    digest, count = _hash(data), len(data)
                elif kind in (rse.ActionClass.WRITE_FILE, rse.ActionClass.CREATE_FILE):
                    _require(len(payload.content_bytes) <= self.max_write_bytes, 'TOO_LARGE')
                    flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    if kind == rse.ActionClass.CREATE_FILE:
                        flags |= os.O_CREAT | os.O_EXCL
                    else:
                        previous, _ = _read(fd, name, self.max_read_bytes)
                        before_digest = _hash(previous)
                    digest, count = _hash(payload.content_bytes), len(payload.content_bytes)
                    handle = os.open(name, flags, 0o600, dir_fd=fd)
                    effect = kind == rse.ActionClass.CREATE_FILE
                    try:
                        info = os.fstat(handle)
                        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_FILE_REQUIRED')
                        effect = True
                        os.ftruncate(handle, 0)
                        view = memoryview(payload.content_bytes)
                        while view:
                            written = os.write(handle, view)
                            _require(written > 0, 'WRITE_FAILED')
                            view = view[written:]
                        events = (_event(action, context, now),)
                        os.fsync(handle)
                    finally:
                        os.close(handle)
                    os.fsync(fd)
                elif kind == rse.ActionClass.DELETE_FILE:
                    _regular(fd, name)
                    effect = True
                    os.unlink(name, dir_fd=fd)
                    events = (_event(action, context, now),)
                    os.fsync(fd)
                else:
                    source, info = _read(fd, name, self.max_read_bytes)
                    digest, count = _hash(source), len(source)
                    with _parent(self.root, action.destination) as (dest_fd, dest):
                        _require(_regular(dest_fd, dest, missing=True) is None, 'DESTINATION_EXISTS')
                        _require(_regular(fd, name).st_ino == info.st_ino, 'PATH_CHANGED')
                        # link is exclusive, unlike rename on POSIX. A failed unlink
                        # leaves a visible partial effect and therefore UNKNOWN.
                        effect = True
                        os.link(name, dest, src_dir_fd=fd, dst_dir_fd=dest_fd, follow_symlinks=False)
                        os.unlink(name, dir_fd=fd)
                        events = (_event(action, context, now),)
                        os.fsync(dest_fd); os.fsync(fd)
                if not events:
                    events = (_event(action, context, now),)
            return _Outcome(rse.ExecutionState.KNOWN_SUCCESS,
                RuntimeOperationEvidence(payload.digest(), 'COMPLETED', digest, count, before_digest=before_digest), events, data)
        except (OSError, ValueError) as error:
            reason = 'FILESYSTEM_BOUNDARY_UNCERTAIN' if effect else 'FILESYSTEM_REJECTED'
            if type(error) is ValueError and str(error) == 'PLATFORM_UNSUPPORTED':
                reason = 'PLATFORM_UNSUPPORTED'
            return _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME if effect else rse.ExecutionState.KNOWN_FAILURE,
                RuntimeOperationEvidence(payload.digest(), reason, digest, count, before_digest=before_digest), events)

    def reconcile(self, action, payload, evidence=None):
        try:
            with _parent(self.root, action.target) as (fd, name):
                info = _regular(fd, name, missing=True)
                if action.action_class == rse.ActionClass.DELETE_FILE:
                    return rse.ReconciliationOutcome.EFFECT_APPLIED if info is None else rse.ReconciliationOutcome.STILL_UNKNOWN
                if action.action_class in (rse.ActionClass.CREATE_FILE, rse.ActionClass.WRITE_FILE):
                    if info is None:
                        return (rse.ReconciliationOutcome.EFFECT_NOT_APPLIED if action.action_class == rse.ActionClass.CREATE_FILE
                            else rse.ReconciliationOutcome.STILL_UNKNOWN)
                    data, _ = _read(fd, name, self.max_read_bytes)
                    if _hash(data) == _hash(payload.content_bytes):
                        return rse.ReconciliationOutcome.EFFECT_APPLIED
                    if evidence and evidence.before_digest == _hash(data):
                        return rse.ReconciliationOutcome.EFFECT_NOT_APPLIED
                if action.action_class == rse.ActionClass.MOVE_FILE and info is None and evidence and evidence.content_digest:
                    with _parent(self.root, action.destination) as (dest_fd, dest):
                        data, _ = _read(dest_fd, dest, self.max_read_bytes)
                        if _hash(data) == evidence.content_digest:
                            return rse.ReconciliationOutcome.EFFECT_APPLIED
        except (OSError, ValueError):
            pass
        return rse.ReconciliationOutcome.STILL_UNKNOWN


_FORBIDDEN_EXECUTABLES = frozenset(('sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'csh', 'tcsh',
    'curl', 'wget', 'pip', 'pip3', 'npm', 'npx', 'brew', 'apt', 'apt-get', 'yum', 'dnf',
    'aws', 'gcloud', 'az', 'gh', 'launchctl', 'systemctl', 'git'))


def _pin(executable, *, git=False):
    executable = _absolute(executable)
    _require(PurePosixPath(executable).name not in (_FORBIDDEN_EXECUTABLES - ({'git'} if git else set())), 'EXECUTABLE_DENIED')
    info = os.stat(executable, follow_symlinks=False)
    _require(stat.S_ISREG(info.st_mode) and os.access(executable, os.X_OK), 'EXECUTABLE_DENIED')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _environment(base, keys, overrides):
    _require(type(base) is dict and len(base) <= 64, 'INVALID_RUNTIME_CONFIG')
    result = dict(base)
    for key, value in (overrides or ()):
        _require(key in keys, 'ENVIRONMENT_KEY_DENIED')
        result[key] = value
    _require(all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', k) and type(v) is str and '\0' not in v
                 and len(v.encode()) <= 4096 for k, v in result.items()), 'INVALID_ENVIRONMENT')
    return result


_LAUNCHER_CODE = '''import os, sys, json
fd, status = int(sys.argv[1]), int(sys.argv[2])
try:
    os.set_inheritable(status, False)
    os.fchdir(fd)
    os.close(fd)
    argv, expected = json.loads(sys.argv[3]), json.loads(sys.argv[4])
    environment = json.loads(sys.argv[5])
    st = os.stat(argv[0], follow_symlinks=False)
    if [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns] != expected:
        raise ValueError()
    os.write(status, b'R')
    os.execve(argv[0], argv, environment)
except BaseException:
    os.write(status, b'F')
    os._exit(125)
'''


class _LaunchUncertain(Exception):
    pass


def _launcher():
    executable = os.path.realpath(sys.executable)
    return executable, _pin(executable)


def _capture(argv, cwd, env, timeout, stdout_limit, stderr_limit, on_start=None, *, cwd_fd, launcher, target_pin,
             stdin_file=None):
    """Drain pipes continuously, retain bounded prefixes, and kill group on timeout."""
    _require(_pin(launcher[0]) == launcher[1], 'LAUNCHER_CHANGED')
    read_status, write_status = os.pipe()
    process = None
    failure = None
    proved_not_started = [False]
    try:
        process = subprocess.Popen((launcher[0], '-I', '-S', '-c', _LAUNCHER_CODE,
            str(cwd_fd), str(write_status), json.dumps(argv), json.dumps(target_pin), json.dumps(env)),
            cwd='/', env={}, shell=False, stdin=subprocess.DEVNULL if stdin_file is None else stdin_file,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
            pass_fds=(cwd_fd, write_status))
        closing, write_status = write_status, None
        os.close(closing)
        result = _capture_started(process, read_status, timeout, stdout_limit, stderr_limit,
                                  on_start, proved_not_started)
    except Exception as error:
        failure = error
    finally:
        # Cleanup failures must not overwrite post-launch uncertainty with a
        # clean rejection, and one failed cleanup must not skip other resources.
        for fd in (read_status, write_status):
            if fd is not None:
                try:
                    os.close(fd)
                except Exception as error:
                    failure = failure or error
        if process is not None:
            try:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        try:
                            process.kill()
                        except OSError:
                            pass
                    process.wait(timeout=1)
            except Exception as error:
                failure = failure or error
            finally:
                for stream in (process.stdout, process.stderr):
                    try:
                        stream.close()
                    except Exception as error:
                        failure = failure or error
    if failure is not None:
        if process is not None and not proved_not_started[0]:
            raise _LaunchUncertain() from None
        raise failure
    return result


def _capture_started(process, read_status, timeout, stdout_limit, stderr_limit, on_start,
                     proved_not_started):
    """Only the fixed helper F acknowledgement proves target exec did not occur."""
    output = [bytearray(), bytearray()]; truncated = [False, False]; timed_out = False
    deadline = time.monotonic() + timeout
    status = bytearray()
    with selectors.DefaultSelector() as ready:
        ready.register(read_status, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not ready.select(remaining):
                raise _LaunchUncertain()
            part = os.read(read_status, 8)
            status.extend(part)
            if status in (b'F', b'RF'):
                proved_not_started[0] = True
                raise ValueError('TARGET_NOT_STARTED')
            if not part:
                if status != b'R':
                    raise _LaunchUncertain()
                if process.poll() is not None and process.returncode < 0:
                    raise _LaunchUncertain()
                break
            if len(status) > 2:
                raise _LaunchUncertain()
    if on_start:
        on_start()
    with selectors.DefaultSelector() as selector:
        for i, stream in enumerate((process.stdout, process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, i)
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(min(remaining, 0.05)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                i = key.data; limit = (stdout_limit, stderr_limit)[i]
                available = limit - len(output[i])
                output[i].extend(chunk[:available])
                truncated[i] |= len(chunk) > available
    if timed_out:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=1)
    return process.returncode, bytes(output[0]), bytes(output[1]), tuple(truncated), timed_out


class ProcessAdapter:
    def __init__(self, *, workspace_root, allowed_executables, default_timeout=30, max_timeout=300,
                 max_stdout_bytes=MAX_OUTPUT_BYTES, max_stderr_bytes=MAX_OUTPUT_BYTES,
                 base_env=None, allowed_env_keys=()):
        self.root = _absolute(workspace_root)
        _require(type(allowed_executables) is tuple and 0 < len(allowed_executables) <= 32, 'INVALID_RUNTIME_CONFIG')
        self.executables = MappingProxyType({p: _pin(p) for p in allowed_executables})
        self.launcher = _launcher()
        self.max_timeout = _duration(max_timeout)
        self.default_timeout = _duration(default_timeout, max_timeout)
        self.stdout_limit = _limit(max_stdout_bytes, MAX_OUTPUT_BYTES)
        self.stderr_limit = _limit(max_stderr_bytes, MAX_OUTPUT_BYTES)
        self.base_env = MappingProxyType(_environment(base_env or {}, (), ()))
        self.allowed_env_keys = frozenset(allowed_env_keys)

    def execute(self, action):
        raise ValueError('RUNTIME_BINDING_REQUIRED')

    def run(self, action, payload, context, now):
        events = []
        try:
            _require(action.action_class == rse.ActionClass.EXECUTE_PROCESS, 'NOT_BOUND')
            executable = payload.argv[0]
            _require(action.target == executable and executable in self.executables
                and _pin(executable) == self.executables[executable], 'EXECUTABLE_DENIED')
            timeout = self.default_timeout if payload.timeout == 'DEFAULT' else _duration(payload.timeout, self.max_timeout)
            cwd = _contained(self.root, payload.cwd or self.root)
            env = _environment(dict(self.base_env), self.allowed_env_keys, payload.environment)
            with _directory(cwd) as cwd_fd:
                code, stdout, stderr, truncated, expired = _capture(payload.argv, cwd, env, timeout,
                    self.stdout_limit, self.stderr_limit,
                    lambda: events.append(_event(action, context, now)), cwd_fd=cwd_fd,
                    launcher=self.launcher, target_pin=self.executables[executable])
            if not expired:
                events.append(_event(action, context, now, cet.CriticalEventType.PROCESS_EXIT, code))
            state = rse.ExecutionState.UNKNOWN_OUTCOME if expired or code != 0 else rse.ExecutionState.KNOWN_SUCCESS
            return _Outcome(state, RuntimeOperationEvidence(payload.digest(), 'TIMEOUT' if expired else 'EXITED',
                exit_code=None if expired else code, stdout_truncated=truncated[0], stderr_truncated=truncated[1]),
                tuple(events), stdout=stdout, stderr=stderr)
        except (OSError, ValueError, subprocess.SubprocessError, _LaunchUncertain) as error:
            uncertain = bool(events) or isinstance(error, _LaunchUncertain)
            return _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME if uncertain else rse.ExecutionState.KNOWN_FAILURE,
                RuntimeOperationEvidence(payload.digest(), 'PROCESS_UNCERTAIN' if uncertain else 'PROCESS_REJECTED'), tuple(events))


class LocalGitAdapter:
    """Only exact stage and local commit; unsafe repository configuration rejected."""
    def __init__(self, *, workspace_root, git_executable, base_env=None):
        self.root = _absolute(workspace_root)
        self.git = git_executable; self.pin = _pin(git_executable, git=True)
        self.launcher = _launcher()
        allowed = {'GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL'}
        _require(not base_env or set(base_env) <= allowed, 'INVALID_ENVIRONMENT')
        self.env = MappingProxyType(_environment(base_env or {}, (), ()))

    def execute(self, action):
        raise ValueError('RUNTIME_BINDING_REQUIRED')

    def _call(self, args, *, stdin_file=None):
        env = dict(self.env)
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0',
            GIT_PAGER='', GIT_EDITOR='/usr/bin/false', GIT_SEQUENCE_EDITOR='/usr/bin/false',
            GIT_LITERAL_PATHSPECS='1', GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1',
            GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='', GIT_PROTOCOL_FROM_USER='0', LC_ALL='C')
        argv = (self.git, '--no-pager', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false',
            '-c', 'tag.gpgSign=false', '-c', 'credential.helper=', '-c', 'core.fsmonitor=false',
            '-c', 'core.untrackedCache=false', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
            '-c', 'core.pager=', '-c', 'core.editor=/usr/bin/false', '-c', 'protocol.allow=never', *args)
        with _directory(self.root) as cwd_fd:
            return _capture(argv, self.root, env, 30, MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES,
                cwd_fd=cwd_fd, launcher=self.launcher, target_pin=self.pin, stdin_file=stdin_file)

    def _validate(self):
        _require(_pin(self.git, git=True) == self.pin, 'EXECUTABLE_CHANGED')
        with _directory(self.root), _directory(self.root + '/.git') as fd:
            self._check_metadata(fd, [0])
        # Reject config includes and all external helper families. Git config
        # inspection does not execute values; --no-includes avoids reading extras.
        code, data, _, trunc, expired = self._call(('config', '--local', '--no-includes', '--null', '--list'))
        _require(code == 0 and not any(trunc) and not expired, 'UNSAFE_GIT_CONFIG')
        for row in data.decode('utf-8').split('\0'):
            key, _, value = row.partition('\n')
            key = key.lower()
            _require(not key.startswith(('include.', 'includeif.', 'filter.', 'diff.', 'credential.', 'alias.'))
                and not (key.startswith('remote.') and key.endswith(('.promisor', '.uploadpack', '.receivepack')))
                and key not in ('core.sshcommand', 'core.gitproxy', 'core.worktree')
                and (not key.startswith('extensions.') or
                     (key == 'extensions.objectformat' and value in ('sha1', 'sha256'))), 'UNSAFE_GIT_CONFIG')
        code, data, _, trunc, expired = self._call(('rev-parse', '--show-toplevel'))
        _require(code == 0 and data.decode().strip() == self.root and not any(trunc) and not expired, 'REPOSITORY_MISMATCH')
        object_format = self._read_git(('rev-parse', '--show-object-format')).decode().strip()
        _require(object_format in ('sha1', 'sha256'), 'UNSUPPORTED_GIT_OBJECT_FORMAT')
        return 40 if object_format == 'sha1' else 64

    def _read_git(self, args):
        code, data, _, trunc, expired = self._call(args)
        _require(code == 0 and not expired and not any(trunc), 'GIT_REJECTED')
        return data

    def _head(self, oid_length):
        code, data, _, trunc, expired = self._call(('rev-parse', '--verify', 'HEAD^{commit}'))
        _require(not expired and not any(trunc), 'GIT_REJECTED')
        if code == 0:
            head = data.decode().strip()
            _require(_git_oid(head, oid_length), 'GIT_REJECTED')
            return head
        # A failed rev-parse alone does not prove an unborn repository. Require
        # a symbolic branch whose reference is demonstrably absent.
        branch = self._read_git(('symbolic-ref', '--quiet', 'HEAD')).decode().strip()
        _require(branch.startswith('refs/heads/'), 'UNSUPPORTED_GIT_STATE')
        code, _, _, trunc, expired = self._call(('show-ref', '--verify', '--quiet', branch))
        _require(code == 1 and not expired and not any(trunc), 'UNSUPPORTED_GIT_STATE')
        return UNBORN_GIT_PARENT

    def _simple_commit_state(self):
        markers = {'MERGE_HEAD', 'MERGE_MSG', 'MERGE_MODE', 'AUTO_MERGE', 'SQUASH_MSG',
            'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'REBASE_HEAD', 'rebase-apply', 'rebase-merge',
            'sequencer', 'BISECT_START', 'BISECT_LOG', 'BISECT_NAMES', 'BISECT_EXPECTED_REV'}
        with _directory(self.root + '/.git') as fd:
            _require(not markers.intersection(os.listdir(fd)), 'UNSUPPORTED_GIT_STATE')
        _require(not self._read_git(('ls-files', '--unmerged', '-z')), 'UNSUPPORTED_GIT_STATE')

    def _commit_matches(self, head, payload, oid_length):
        _require(_git_oid(head, oid_length), 'GIT_REJECTED')
        data = self._read_git(('cat-file', 'commit', head))
        header, message = data.split(b'\n\n', 1)
        expected_message = payload.commit_message.encode()
        if not expected_message.endswith(b'\n'):
            expected_message += b'\n'
        parents = [row[7:].decode() for row in header.split(b'\n') if row.startswith(b'parent ')]
        trees = [row[5:].decode() for row in header.split(b'\n') if row.startswith(b'tree ')]
        expected_parents = [] if payload.expected_git_parent == UNBORN_GIT_PARENT else [payload.expected_git_parent]
        return trees == [payload.expected_git_tree] and parents == expected_parents and message == expected_message

    def _check_metadata(self, fd, budget, depth=0):
        _require(depth <= 16, 'UNSAFE_GIT_METADATA')
        for name in os.listdir(fd):
            budget[0] += 1
            _require(budget[0] <= 4096, 'UNSAFE_GIT_METADATA')
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            _require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'UNSAFE_GIT_METADATA')
            _require(not stat.S_ISREG(info.st_mode) or info.st_nlink == 1, 'UNSAFE_GIT_METADATA')
            _require(name not in ('alternates', 'commondir', 'gitdir'), 'UNSAFE_GIT_METADATA')
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    self._check_metadata(child, budget, depth + 1)
                finally:
                    os.close(child)

    def run(self, action, payload, context, now):
        attempted = False; events = (); commit_sha = None; tree_sha = None; parent_sha = None
        try:
            _require(action.action_class in (rse.ActionClass.GIT_STAGE, rse.ActionClass.GIT_COMMIT)
                and action.target == self.root, 'NOT_BOUND')
            oid_length = self._validate()
            if action.action_class == rse.ActionClass.GIT_STAGE:
                for path in payload.git_paths:
                    with _parent(self.root, self.root + '/' + path) as (fd, name):
                        _regular(fd, name)
                args = ('add', '--', *payload.git_paths)
            else:
                _require(_git_oid(payload.expected_git_tree, oid_length)
                    and (payload.expected_git_parent == UNBORN_GIT_PARENT
                         or _git_oid(payload.expected_git_parent, oid_length)), 'GIT_OBJECT_FORMAT_MISMATCH')
                self._simple_commit_state()
                parent_sha = self._head(oid_length)
                _require(parent_sha == payload.expected_git_parent, 'GIT_PARENT_BINDING_MISMATCH')
                parent_tree = None; has_staged = True
                if parent_sha != UNBORN_GIT_PARENT:
                    parent_tree = self._read_git(('rev-parse', '--verify', parent_sha + '^{tree}')).decode().strip()
                    _require(_git_oid(parent_tree, oid_length), 'GIT_REJECTED')
                else:
                    has_staged = bool(self._read_git(('ls-files', '--cached', '-z')))
                tree_sha = self._read_git(('write-tree',)).decode().strip()
                _require(_git_oid(tree_sha, oid_length), 'GIT_REJECTED')
                _require(tree_sha == payload.expected_git_tree, 'GIT_TREE_BINDING_MISMATCH')
                _require(has_staged and tree_sha != parent_tree, 'GIT_NOTHING_TO_COMMIT')
                args = ('commit', '--no-gpg-sign', '--no-verify', '--cleanup=verbatim', '-m', payload.commit_message)
            attempted = True
            code, stdout, stderr, trunc, expired = self._call(args)
            if code != 0 or expired:
                raise ValueError('GIT_UNCERTAIN')
            events = (_event(action, context, now),)
            if action.action_class == rse.ActionClass.GIT_COMMIT:
                commit_sha = self._head(oid_length)
                _require(self._commit_matches(commit_sha, payload, oid_length), 'GIT_COMMIT_RESULT_MISMATCH')
            return _Outcome(rse.ExecutionState.KNOWN_SUCCESS,
                RuntimeOperationEvidence(payload.digest(), 'COMPLETED', commit_sha=commit_sha,
                    tree_sha=tree_sha, parent_sha=parent_sha), events)
        except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, _LaunchUncertain) as error:
            # A precheck Git process may have started before its capture failed.
            # An empty adapter event list is not proof of no effects.
            attempted = attempted or isinstance(error, _LaunchUncertain)
            reason = 'GIT_UNCERTAIN' if attempted else 'GIT_REJECTED'
            if not attempted and type(error) is ValueError and str(error) in (
                    'GIT_PARENT_BINDING_MISMATCH', 'GIT_TREE_BINDING_MISMATCH', 'GIT_OBJECT_FORMAT_MISMATCH',
                    'UNSUPPORTED_GIT_STATE', 'UNSUPPORTED_GIT_OBJECT_FORMAT', 'GIT_NOTHING_TO_COMMIT'):
                reason = str(error)
            if attempted and type(error) is ValueError and str(error) == 'GIT_COMMIT_RESULT_MISMATCH':
                reason = str(error)
            return _Outcome(rse.ExecutionState.UNKNOWN_OUTCOME if attempted else rse.ExecutionState.KNOWN_FAILURE,
                RuntimeOperationEvidence(payload.digest(), reason,
                    tree_sha=tree_sha, parent_sha=parent_sha), events)

    def reconcile(self, action, payload, evidence=None):
        if action.action_class != rse.ActionClass.GIT_COMMIT or not evidence or not evidence.tree_sha:
            return rse.ReconciliationOutcome.STILL_UNKNOWN
        try:
            oid_length = self._validate()
            head = self._head(oid_length)
            if head == payload.expected_git_parent:
                return rse.ReconciliationOutcome.EFFECT_NOT_APPLIED
            if self._commit_matches(head, payload, oid_length):
                return rse.ReconciliationOutcome.EFFECT_APPLIED
        except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, _LaunchUncertain):
            pass
        return rse.ReconciliationOutcome.STILL_UNKNOWN


class _Invocation:
    def __init__(self, adapter, payload, context, now):
        self.adapter, self.payload, self.context, self.now = adapter, payload, context, now
        self.outcome = None

    def execute(self, action):
        self.outcome = self.adapter.run(action, self.payload, self.context, self.now)
        _require(type(self.outcome) is _Outcome, 'ADAPTER_RESULT_INVALID')
        return rse.ExecutionResult(self.outcome.state, (sc.artifact_digest(self.outcome.evidence),))


class RuntimeBinding:
    """One trusted controller with commitments established BEFORE authorization.

    Replacing the journal loses same-process retry protection. The frozen digest
    snapshot is trusted host input, never populated from a model execution call.
    """
    def __init__(self, capability_broker, journal, chain, actor, *, approved_payload_digests):
        _require(type(approved_payload_digests) is dict and len(approved_payload_digests) <= 1024
            and all(_text(k, 1024) and sc._hash(v) for k, v in approved_payload_digests.items()), 'INVALID_APPROVED_PAYLOADS')
        self.approved_payload_digests = MappingProxyType(dict(approved_payload_digests))
        self.broker, self.journal, self.chain, self.actor = capability_broker, journal, chain, actor
        self._evidence = {}

    def _bound(self, action, payload):
        _require(rse._valid_action(action))
        _require(type(payload) is RuntimePayload)
        payload.validate_for(action)
        _require(self.approved_payload_digests.get(action.action_id) == payload.digest(), 'PAYLOAD_DIGEST_MISMATCH')
        return replace(action, expected_effect='runtime-payload:' + payload.digest() + ':' + _hash(action.expected_effect.encode()))

    def execute(self, action, payload, *, policy_stack, authorization, context, now):
        invocation = None
        try:
            bound = self._bound(action, payload)
            _require(action.action_class in BOUND_ACTIONS, 'NOT_BOUND')
            cet._match_action(action, context)
            _require(self.chain._installation_id == context.installation_id and self.chain.verify().valid and sc.authorize_management_change(self.actor,
                sc.ManagementAction.RSE_RECEIPT_RECORD, installation_id=context.installation_id,
                project_id=context.project_id, task_id=context.task_id, now=now).disposition == 'ALLOW',
                'SECURITY_BOUNDARY_FAILURE')
        except (ValueError, TypeError, AttributeError) as error:
            # Fixed reason codes only: never expose payload text or host errors.
            reason = 'MALFORMED_RUNTIME_PAYLOAD'
            if type(error) is ValueError and str(error) == 'SECURITY_BOUNDARY_FAILURE':
                reason = 'SECURITY_BOUNDARY_FAILURE'
            if type(payload) is RuntimePayload and type(action) is rse.ActionRequest and payload.action_id == action.action_id:
                if self.approved_payload_digests.get(action.action_id) != payload.digest():
                    reason = 'PAYLOAD_DIGEST_MISMATCH'
                elif action.action_class not in BOUND_ACTIONS:
                    reason = 'NOT_BOUND'
            return RuntimeBindingResult(rse._receipt(action, rse.PolicyDecision('DENY', reason)), boundary_status=reason)
        with self.journal.transaction():
            broker = rse.CapabilityBroker()
            if self.broker.has(action.capability):
                invocation = _Invocation(self.broker.get(action.capability), payload, context, now)
                broker.register(action.capability, invocation)
            receipt = rse.evaluate_and_execute(bound, policy_stack, authorization, broker, self.journal, now)
            out = invocation.outcome if invocation else None
            events = out.events if out else ()
            if out:
                self._evidence[action.action_id] = out.evidence
            divergences = []
            try:
                declaration = cet.declared_from_action(action, context)
                for event in events:
                    _require(type(event) is cet.CriticalEvent and event.context == context, 'ADAPTER_EVENT_INVALID')
                    observed = cet.ObservedEffects(context, **cet._event_effect(event))
                    divergences.extend(cet.compare_effects(declaration, observed).divergences)
                sc.record_receipt(self.chain, self.actor, receipt, event_id=uuid.uuid4().hex, now=now,
                    project_id=context.project_id, task_id=context.task_id)
                for event in events:
                    cet.record_critical_event(self.chain, self.actor, event, now=now)
                for divergence in divergences:
                    cet.record_trace_divergence(self.chain, self.actor, divergence, now=now)
            except Exception:
                if out:
                    rse._append(self.journal, bound, rse.JournalState.RECONCILIATION_REQUIRED)
                receipt = replace(receipt, execution_state='UNKNOWN_OUTCOME',
                    reconciliation_state='RECONCILIATION_REQUIRED', final_disposition='REQUIRE_RECONCILIATION')
                return RuntimeBindingResult(receipt, out.evidence if out else None, events, tuple(divergences),
                    out.content_bytes if out else None, out.stdout if out else b'', out.stderr if out else b'',
                    boundary_status='SECURITY_BOUNDARY_FAILURE')
            return RuntimeBindingResult(receipt, out.evidence if out else None, events, tuple(divergences),
                out.content_bytes if out else None, out.stdout if out else b'', out.stderr if out else b'',
                'TRACE_DIVERGENCE' if divergences else 'OK')

    def reconcile(self, action, payload):
        bound = self._bound(action, payload)
        adapter = self.broker.get(action.capability)
        def inspect(_):
            if not callable(getattr(adapter, 'reconcile', None)):
                return rse.ReconciliationOutcome.STILL_UNKNOWN
            return adapter.reconcile(action, payload, self._evidence.get(action.action_id))
        return rse.reconcile(bound, self.journal, inspect)
