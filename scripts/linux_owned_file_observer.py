"""Opt-in Linux x86-64 owned-child syscall metadata observer; import is inert.

No arbitrary command/PID, read/write buffer copying, privileged fallback or daemon.
Stop timestamps are observer observations, not atomic kernel access timestamps.
"""
import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 16384
MAX_EVENTS = 32
MAX_PATH = 4096
TOTAL_SECONDS = 30
OBSERVATION_SECONDS = 8
CLEANUP_RESERVE = 5
AUDIT_ARCH_X86_64 = 0xC000003E
TRACEME, PEEKDATA, SYSCALL, SETOPTIONS, GETINFO = 0, 2, 24, 0x4200, 0x420E
OPTIONS = 1 | (1 << 20)  # TRACESYSGOOD | EXITKILL; never follow arbitrary tasks.
FILE_CALLS = {0: 'read', 1: 'write', 2: 'open', 3: 'close', 257: 'openat'}
UNSUPPORTED = {17, 18, 19, 20, 32, 33, 40, 56, 57, 58, 59, 72, 76, 77, 80, 81,
               155, 161, 165, 166, 272, 275, 276, 278, 292, 295, 296,
               308, 310, 311, 322, 326, 327, 328, 425, 426, 427, 435, 436, 437}

# Imports and interpreter startup happen before TRACEME. Only this fixed helper
# is ever launched. It opens the two absolute names supplied by its parent.
CHILD = r'''
import ctypes, errno, os, signal, sys
libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.restype = ctypes.c_long
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0: os._exit(18)
if os.getppid() != int(sys.argv[3]): os._exit(19)
if libc.ptrace(0, 0, None, None) != 0: os._exit(20)
os.kill(os.getpid(), signal.SIGSTOP)
try:
    fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
    if len(os.read(fd, 1)) != 1: os._exit(21)
    os.close(fd)
    fd = os.open(sys.argv[1], os.O_WRONLY | os.O_NOFOLLOW)
    if os.write(fd, b'X') != 1: os._exit(22)
    os.close(fd)
    try:
        os.open(sys.argv[2], os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        if exc.errno != errno.ENOENT: os._exit(23)
    else: os._exit(24)
except BaseException: os._exit(25)
os._exit(0)
'''


class Rejected(Exception):
    """Fixed codes only; never persist free-form syscall/path exceptions."""


class EntryInfo(ctypes.Structure):
    _fields_ = [('nr', ctypes.c_uint64), ('args', ctypes.c_uint64 * 6)]


class ExitInfo(ctypes.Structure):
    _fields_ = [('rval', ctypes.c_int64), ('is_error', ctypes.c_uint8)]


class InfoData(ctypes.Union):
    _fields_ = [('entry', EntryInfo), ('exit', ExitInfo), ('space', ctypes.c_byte * 64)]


class SyscallInfo(ctypes.Structure):
    _fields_ = [('op', ctypes.c_uint8), ('pad', ctypes.c_uint8 * 3),
                ('arch', ctypes.c_uint32), ('ip', ctypes.c_uint64),
                ('sp', ctypes.c_uint64), ('data', InfoData)]


def require(ok, code):
    if not ok:
        raise Rejected(code)


def proc_start_ticks(raw):
    try:
        return int(raw.rsplit(') ', 1)[1].split()[19])
    except (ValueError, IndexError):
        raise Rejected('PROCESS_IDENTITY_PARSE') from None


def owned_identity(pid):
    # Exact owned PID only. No process listing or arbitrary executable paths.
    start = proc_start_ticks(Path('/proc/%d/stat' % pid).read_text())
    require(start > 0, 'PROCESS_IDENTITY_PARSE')
    return {'pid': pid, 'start_ticks': start}


class Evidence:
    """Pure finite correlator. Native reads are injected, never simulated as live."""
    def __init__(self, identity, fixture, missing, file_identity):
        self.identity = identity
        self.fixture, self.missing = fixture, missing
        self.file_identity = file_identity
        self.pending = None
        self.fds = {}
        self.generation = 0
        self.events = []
        self.seen_entry = False
        self.initial_unpaired_exit = False
        self.seq = 0

    def emit(self, operation, phase, path, stamp, **fields):
        require(len(self.events) < MAX_EVENTS, 'EVENT_CAP')
        mono, wall = stamp
        require(type(mono) is int and type(wall) is int and mono > 0 and wall > 0,
                'TIME_IDENTITY')
        self.events.append(dict(self.identity, syscall_seq=self.seq,
            operation=operation, phase=phase, path=path,
            observed_monotonic_ns=mono, observed_wall_ns=wall, **fields))

    def entry(self, nr, args, stamp, read_path, fd_identity):
        require(self.pending is None, 'MISSING_SYSCALL_EXIT')
        self.seen_entry = True
        require(nr not in UNSUPPORTED, 'UNSUPPORTED_OPERATION')
        if nr == 9:  # No file-backed mmap proof, including zero syscall read count.
            require(args[3] & 0x20, 'UNSUPPORTED_FILE_MAPPING')
        self.seq += 1
        operation = FILE_CALLS.get(nr)
        scoped = None
        if operation in ('open', 'openat'):
            address, flags = ((args[0], args[1]) if nr == 2 else (args[1], args[2]))
            path = read_path(address)
            require(path in (self.fixture, self.missing), 'OUT_OF_SCOPE_OR_RELATIVE_PATH')
            require(flags & os.O_NOFOLLOW, 'NOFOLLOW_REQUIRED')
            scoped = {'operation': 'open', 'path': path, 'flags': flags}
        elif operation in ('read', 'write', 'close') and args[0] in self.fds:
            fd = args[0]
            meta = fd_identity(fd)
            require(meta == self.file_identity, 'FD_OBJECT_CHANGED')
            scoped = {'operation': operation, 'path': self.fds[fd]['path'],
                      'fd': fd, 'generation': self.fds[fd]['generation']}
            if operation != 'close':
                scoped['requested_bytes'] = args[2]
        elif operation in ('read', 'write', 'close') and args[0] > 2:
            raise Rejected('UNTRACKED_FILE_DESCRIPTOR')
        self.pending = {'nr': nr, 'scoped': scoped}
        if scoped:
            self.emit(scoped['operation'], 'ATTEMPT', scoped['path'], stamp,
                      **{k: v for k, v in scoped.items() if k not in ('operation', 'path')})

    def exit(self, retval, is_error, stamp, fd_identity):
        require(is_error in (0, 1), 'SYSCALL_RESULT_SHAPE')
        if self.pending is None:
            require(not self.seen_entry and not self.initial_unpaired_exit,
                    'MISSING_SYSCALL_ENTRY')
            self.initial_unpaired_exit = True
            return  # Startup SIGSTOP's return, before any claimed paired access.
        scoped = self.pending['scoped']
        self.pending = None
        require(bool(is_error) == (-4095 <= retval < 0), 'SYSCALL_RESULT_SHAPE')
        if not scoped:
            return
        operation, path = scoped['operation'], scoped['path']
        extra = {k: v for k, v in scoped.items() if k not in ('operation', 'path')}
        success = not is_error
        if operation == 'open' and success:
            require(path == self.fixture and retval >= 0, 'UNEXPECTED_OPEN_SUCCESS')
            require(fd_identity(retval) == self.file_identity, 'OPEN_OBJECT_CHANGED')
            require(retval not in self.fds, 'FD_REUSE_WITHOUT_CLOSE')
            self.generation += 1
            self.fds[retval] = {'path': path, 'generation': self.generation}
            extra.update(fd=retval, generation=self.generation,
                         file_identity=self.file_identity)
        if operation in ('read', 'write') and success:
            require(0 <= retval <= scoped['requested_bytes'], 'BYTE_COUNT_SHAPE')
        if operation == 'close' and success:
            require(retval == 0, 'CLOSE_RESULT_SHAPE')
            del self.fds[scoped['fd']]
        self.emit(operation, 'RESULT', path, stamp, retval=retval,
                  errno=(-retval if is_error else None), success=success,
                  confirmed_positive_bytes=(success and operation in ('read', 'write') and retval > 0),
                  **extra)

    def qualify(self, child_returncode):
        require(child_returncode == 0 and not self.fds, 'CHILD_EXIT_OR_OPEN_FDS')
        require(self.pending is None or self.pending['scoped'] is None,
                'INCOMPLETE_SCOPED_SYSCALL')
        expected = ['open', 'read', 'close', 'open', 'write', 'close', 'open']
        require([x['operation'] for x in self.events[::2]] == expected
                and len(self.events) == 14, 'SCOPED_MATRIX_INCOMPLETE')
        for a, b in zip(self.events[::2], self.events[1::2]):
            require(a['phase'] == 'ATTEMPT' and b['phase'] == 'RESULT'
                    and a['syscall_seq'] == b['syscall_seq']
                    and a['operation'] == b['operation'] and a['path'] == b['path']
                    and a['observed_monotonic_ns'] <= b['observed_monotonic_ns'],
                    'PAIRING_OR_TIME')
        results = self.events[1::2]
        require(all(x['success'] for x in results[:-1]), 'POSITIVE_CASE_FAILED')
        require(all(x['retval'] == 1 for x in (results[1], results[4])), 'READ_WRITE_NOT_CONFIRMED')
        require(results[-1]['path'] == self.missing and results[-1]['errno'] == errno.ENOENT,
                'NEGATIVE_CASE_NOT_CONFIRMED')


class Native:
    def __init__(self, handle, identity, mount_ns, fixture, deadline):
        self.handle, self.identity, self.mount_ns = handle, identity, mount_ns
        self.fixture, self.deadline = fixture, deadline
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.ptrace.restype = ctypes.c_long

    def ptrace(self, request, addr=0, data=0):
        require(time.monotonic() < self.deadline, 'OBSERVATION_DEADLINE')
        ctypes.set_errno(0)
        value = self.libc.ptrace(ctypes.c_uint(request), ctypes.c_uint(self.handle.pid),
                                 ctypes.c_void_p(addr), ctypes.c_void_p(data))
        if value == -1 and ctypes.get_errno():
            raise Rejected('PTRACE_ERRNO_%d' % ctypes.get_errno())
        return value

    def identity_check(self):
        require(time.monotonic() < self.deadline, 'OBSERVATION_DEADLINE')
        require(owned_identity(self.handle.pid) == self.identity, 'PROCESS_IDENTITY_CHANGED')
        require(os.readlink('/proc/%d/ns/mnt' % self.handle.pid) == self.mount_ns,
                'MOUNT_NAMESPACE_CHANGED')
        fields = Path('/proc/%d/status' % self.handle.pid).read_text().splitlines()
        threads = [line.split(':', 1)[1].strip() for line in fields if line.startswith('Threads:')]
        require(threads == ['1'], 'UNSUPPORTED_CONCURRENCY')

    def path(self, address):
        value = bytearray()
        for offset in range(0, MAX_PATH, ctypes.sizeof(ctypes.c_long)):
            word = self.ptrace(PEEKDATA, address + offset)
            data = (word & ((1 << 64) - 1)).to_bytes(8, 'little')
            if 0 in data:
                value.extend(data[:data.index(0)])
                try:
                    return value.decode('utf-8', 'strict')
                except UnicodeError:
                    raise Rejected('PATH_ENCODING_UNKNOWN') from None
            value.extend(data)
        raise Rejected('PATH_LIMIT_UNKNOWN')

    def fd_identity(self, fd):
        require(time.monotonic() < self.deadline, 'OBSERVATION_DEADLINE')
        name = '/proc/%d/fd/%d' % (self.handle.pid, fd)
        require(os.readlink(name) == self.fixture, 'FD_RESOLVED_PATH_UNKNOWN')
        info = os.stat(name)
        require(stat.S_ISREG(info.st_mode), 'FD_NOT_REGULAR')
        return {'device': info.st_dev, 'inode': info.st_ino}

    def wait(self, deadline):
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self.handle.pid, os.WNOHANG)
            if pid:
                require(pid == self.handle.pid, 'WAITER_IDENTITY')
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    self.handle.returncode = os.waitstatus_to_exitcode(status)
                return status
            time.sleep(0.002)
        raise Rejected('OBSERVATION_DEADLINE')


def safe_parent(path):
    for p in reversed((path,) + tuple(path.parents)):
        s = os.lstat(p)
        require(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode)
                and s.st_uid in (0, os.getuid()) and not s.st_mode & 0o022,
                'UNSAFE_OUTPUT_ANCESTRY')


def cleanup(handle, pidfd, fixture_fd, deadline):
    result = {}
    interrupts = []
    if handle is not None:
        try:
            if handle.returncode is None:
                require(time.monotonic() < deadline, 'CLEANUP_DEADLINE')
                # Original Popen child is unreaped, sole waiter; no arbitrary PID/PGID.
                if pidfd is not None:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                else:
                    handle.kill()
                result['kill'] = True
            else:
                result['kill'] = False
            result['returncode'] = handle.wait(timeout=max(0, min(2, deadline-time.monotonic())))
        except BaseException as exc:
            result['child_state'] = 'UNKNOWN'
            result['error_kind'] = type(exc).__name__
            if not isinstance(exc, Exception):
                interrupts.append((exc, exc.__traceback__))
    for name, fd in (('pidfd', pidfd), ('fixture_fd', fixture_fd)):
        if fd is not None:
            try:
                os.close(fd)
                result[name] = 'CLOSED'
            except BaseException as exc:
                result[name] = 'CLOSE_UNKNOWN'
                if not isinstance(exc, Exception):
                    interrupts.append((exc, exc.__traceback__))
    return result, interrupts


def save_result(result, root, started, saved_interrupt=None):
    """Final write errors must not replace a previously received interrupt."""
    try:
        result['elapsed_before_write'] = time.monotonic()-started
        if result['elapsed_before_write'] > TOTAL_SECONDS:
            result['status'] = 'NOT_PASS'
            result.setdefault('reason', 'TOTAL_SOFTWARE_DEADLINE')
        result['write_tail'] = 'UNKNOWN_NOT_HARD_DEADLINE'
        payload = (json.dumps(result, ensure_ascii=True, indent=2)+'\n').encode()
        require(len(payload) <= MAX_BYTES, 'REPORT_CAP')
        with (root/'result.json').open('xb') as f:
            require(f.write(payload) == len(payload), 'REPORT_SHORT_WRITE')
    except BaseException:
        if saved_interrupt:
            exc, tb = saved_interrupt
            raise exc.with_traceback(tb)
        raise
    if saved_interrupt:
        exc, tb = saved_interrupt
        raise exc.with_traceback(tb)
    return result, root/'result.json'


def run_owned(project, authorization_id=None):
    require(authorization_id is not None and authorization_id == 'NEW_SINGLE_RUN_GRANTED',
            'NO_NATIVE_AUTHORITY')
    require(sys.platform == 'linux' and platform.machine() == 'x86_64'
            and ctypes.sizeof(ctypes.c_long) == 8, 'LINUX_X86_64_REQUIRED')
    require(os.geteuid() != 0 and hasattr(os, 'pidfd_open')
            and hasattr(signal, 'pidfd_send_signal'), 'UNPRIVILEGED_PIDFD_RUNTIME_REQUIRED')
    require(sys.version_info >= (3, 11), 'PYTHON_311_REQUIRED')
    require(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, 'SIGCHLD_DEFAULT_REQUIRED')
    try:
        kernel = tuple(int(x) for x in platform.release().split('.')[:2])
    except ValueError:
        raise Rejected('KERNEL_VERSION_UNKNOWN') from None
    require(len(kernel) == 2 and kernel >= (5, 3), 'KERNEL_53_REQUIRED')
    started = time.monotonic()
    deadline = started + TOTAL_SECONDS
    project = Path(project).absolute()
    safe_parent(project)
    base = project / 'examples'
    require(base.is_dir(), 'PROJECT_EXAMPLES_REQUIRED')
    safe_parent(base)
    root = Path(tempfile.mkdtemp(prefix='linux-owned-', dir=base))
    fixture, missing = root/'synthetic.txt', root/'absent.txt'
    handle = pidfd = fixture_fd = trace = None
    saved_interrupt = None
    result = {'status': 'NOT_PASS', 'source': 'LINUX_PTRACE_OWNED_DIRECT_CHILD',
              'scope': 'SINGLE_THREAD_TWO_ABSOLUTE_SYNTHETIC_LEAVES',
              'time_semantics': 'OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME',
              'path_semantics': 'ABSOLUTE_ENTRY_ARGUMENT_AND_STOPPED_PROC_FD_PATH_DEV_INODE',
              'all_descendants_or_all_files': False, 'contents_collected': False,
              'events': [], 'test_root': str(root), 'child_created': False,
              'tracing_started': False}
    result['environment'] = {'kernel': platform.release(), 'machine': platform.machine(),
                             'python': list(sys.version_info[:3]), 'uid': os.geteuid()}
    try:
        fixture_fd = os.open(fixture, os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        require(os.write(fixture_fd, b'A') == 1, 'FIXTURE_SHORT_WRITE')
        initial = os.fstat(fixture_fd)
        file_identity = {'device': initial.st_dev, 'inode': initial.st_ino}
        require(time.monotonic() < deadline-CLEANUP_RESERVE, 'PRELAUNCH_DEADLINE')
        handle = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', CHILD,
                                   str(fixture), str(missing), str(os.getpid())],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, close_fds=True,
                                  env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, cwd=root)
        result['child_created'] = True
        pidfd = os.pidfd_open(handle.pid, 0)
        identity = owned_identity(handle.pid)
        mount_ns = os.readlink('/proc/self/ns/mnt')
        observe_deadline = min(started+TOTAL_SECONDS-CLEANUP_RESERVE,
                               time.monotonic()+OBSERVATION_SECONDS)
        native = Native(handle, identity, mount_ns, str(fixture), observe_deadline)
        status = native.wait(observe_deadline)
        require(os.WIFSTOPPED(status) and os.WSTOPSIG(status) == signal.SIGSTOP,
                'INITIAL_TRACEME_STOP_MISSING')
        native.identity_check()
        native.ptrace(SETOPTIONS, 0, OPTIONS)
        result['tracing_started'] = True
        trace = Evidence(identity, str(fixture), str(missing), file_identity)
        result.update(identity=identity, mount_namespace=mount_ns,
                      file_identity=file_identity, fixture=str(fixture), missing=str(missing))
        while handle.returncode is None:
            require(time.monotonic() < observe_deadline, 'OBSERVATION_DEADLINE')
            native.ptrace(SYSCALL)
            status = native.wait(observe_deadline)
            if handle.returncode is not None:
                break
            require(os.WIFSTOPPED(status) and os.WSTOPSIG(status) == (signal.SIGTRAP|0x80),
                    'UNEXPECTED_SIGNAL_STOP')
            native.identity_check()
            info = SyscallInfo()
            size = native.ptrace(GETINFO, ctypes.sizeof(info), ctypes.addressof(info))
            require(size >= 24 and info.arch == AUDIT_ARCH_X86_64, 'SYSCALL_INFO_ABI')
            stamp = (time.monotonic_ns(), time.time_ns())
            if info.op == 1:
                require(size >= 80, 'SYSCALL_ENTRY_TRUNCATED')
                trace.entry(info.data.entry.nr, list(info.data.entry.args), stamp,
                            native.path, native.fd_identity)
            elif info.op == 2:
                require(size >= 33, 'SYSCALL_EXIT_TRUNCATED')
                trace.exit(info.data.exit.rval, info.data.exit.is_error, stamp, native.fd_identity)
            else:
                raise Rejected('SYSCALL_INFO_UNKNOWN')
        after, leaf = os.fstat(fixture_fd), os.lstat(fixture)
        require(stat.S_ISREG(leaf.st_mode)
                and (after.st_dev, after.st_ino) == (initial.st_dev, initial.st_ino)
                and (leaf.st_dev, leaf.st_ino) == (initial.st_dev, initial.st_ino),
                'FINAL_FILE_IDENTITY')
        trace.qualify(handle.returncode)
        result['status'] = 'PASS_SELECTED_OWNED_SYSCALL_MATRIX_WITH_LIMITS'
    except BaseException as exc:
        result['reason'] = str(exc) if isinstance(exc, Rejected) else type(exc).__name__
        if not isinstance(exc, Exception):
            saved_interrupt = (exc, exc.__traceback__)
    finally:
        result['cleanup'], cleanup_interrupts = cleanup(handle, pidfd, fixture_fd, deadline)
        if saved_interrupt is None and cleanup_interrupts:
            saved_interrupt = cleanup_interrupts[0]
    if trace is not None:
        result['events'] = trace.events
        result['startup_alignment'] = ('ONE_PRE_SCOPE_UNPAIRED_EXIT_OBSERVED'
            if trace.initial_unpaired_exit else 'PAIRED_FROM_FIRST_SYSCALL_STOP')
    if any(x in ('UNKNOWN', 'CLOSE_UNKNOWN') for x in result['cleanup'].values()):
        result['status'] = 'NOT_PASS'
        result.setdefault('reason', 'CLEANUP_UNKNOWN')
    return save_result(result, root, started, saved_interrupt)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-owned-once', action='store_true')
    parser.add_argument('--authorization-id')
    args = parser.parse_args(argv)
    if not args.run_owned_once:
        parser.error('disabled: requires fresh scoped authorization and --run-owned-once')
    try:
        result, path = run_owned(Path(__file__).resolve().parents[1], args.authorization_id)
        print(json.dumps({'status': result['status'], 'reason': result.get('reason'),
                          'result_path': str(path)}))
        return 0 if result['status'].startswith('PASS_SELECTED') else 1
    except Rejected as exc:
        print(json.dumps({'status': 'NOT_PASS', 'reason': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
