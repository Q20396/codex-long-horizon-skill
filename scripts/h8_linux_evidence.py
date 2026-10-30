#!/usr/bin/env python3
"""H8 selected stop-boundary observer v1; preparation only until new authority.

Linux x86_64, CPython 3.15.1, standard-library ctypes. No import-time tracing.
Syscall requests/returns and subsequent stopped FD snapshots are distinct facts.
No atomic event-time snapshot, hostile-host protection, universal path coverage,
product-parent reap, or whole-host descendant claim is made.

ABI: Linux v6.8 include/uapi/linux/ptrace.h and x86 syscall_64.tbl.
Ptrace changes scheduling. The five future cases are instrumented evidence only.
"""
import base64
import ctypes as C
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time

TESTED = '214d7104dda1b27a5c9faf7c15ee06b7911176c8'
TREE = '730ac24f5719eaf5f100e4b3376e75c0718545f7'
BRANCH = 'h8-event-stop-repair-214d710-20261030-once'
VERSION = 'H8_EVENT_STOP_V4'
LIMIT = 16 * 1024 * 1024
LOG_LIMIT = 48 * 1024 * 1024
LOG_BYTES = 0
WALL = 0x40000000
TRACE_OPTIONS = 1 | 2 | 4 | 8 | 16 | 64 | 0x100000  # sysgood/fork/vfork/clone/exec/exit/exitkill
ARCH = 0xc000003e
CLONE_SHARED = 0x200 | 0x400 | 0x10000  # FS, FILES, THREAD
CLONE_VM, CLONE_VFORK = 0x100, 0x4000
# Only pathname argument positions are peeked; never argv/env/read/write buffers.
PATH_ARGS = {2: (0,), 4: (0,), 6: (0,), 21: (0,), 80: (0,), 82: (0, 1),
             83: (0,), 84: (0,), 85: (0,), 86: (0, 1), 87: (0,),
             88: (0, 1), 89: (0,), 90: (0,), 92: (0,), 94: (0,),
             137: (0,), 257: (1,), 258: (1,), 259: (1,), 260: (1,),
             262: (1,), 263: (1,), 264: (1, 3), 265: (1, 3),
             266: (0, 2), 267: (1,), 268: (1,), 269: (1,),
             280: (1,), 316: (1, 3), 332: (1,), 437: (1,), 439: (1,)}
DIR_ARGS = {257: (0,), 258: (0,), 259: (0,), 260: (0,), 262: (0,),
            263: (0,), 264: (0, 2), 265: (0, 2), 266: (1,), 267: (0,),
            268: (0,), 269: (0,), 280: (0,), 316: (0, 2), 332: (0,),
            437: (0,), 439: (0,)}
FD_ARGS = {0: (0,), 1: (0,), 3: (0,), 5: (0,), 8: (0,), 17: (0,),
           18: (0,), 19: (0,), 20: (0,), 32: (0,), 33: (0,), 72: (0,),
           73: (0,), 74: (0,), 75: (0,), 77: (0,), 78: (0,), 81: (0,),
           91: (0,), 93: (0,), 138: (0,), 217: (0,), 285: (0,), 292: (0,)}
OPEN_RESULT = {2, 85, 257, 437, 32, 33, 292}
# No namespace/mount/root changes, ptrace nesting, async io or fd injection.
FORBIDDEN = {101, 155, 161, 165, 166, 272, 298, 308, 310, 311,
             323, 425, 426, 427, 428, 429, 430, 431, 432, 433, 438, 440, 442}
METHODS = (
 'test_fork_child_cannot_use_owner_or_unlock_parent',
 'test_fork_during_construction_does_not_retain_hidden_lock',
 'test_exec_releases_owner_while_new_image_stays_alive',
 'test_parent_death_effect_child_does_not_hold_lock_or_clear_unknown',
)
# An explicitly synthetic mechanism probe. No credential, network or product effect.
PROBE = r'''
import os,sys,subprocess
from pathlib import Path
root=Path(sys.argv[1]); d=root/'relative'; d.mkdir()
fd=os.open(str(d),os.O_RDONLY|os.O_DIRECTORY)
f=os.open('synthetic',os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600,dir_fd=fd)
os.write(f,b'synthetic'); os.lseek(f,0,0); assert os.read(f,9)==b'synthetic'
os.close(f); os.close(fd)
child=os.fork()
if child==0:
 os.execv(sys.executable,[sys.executable,'-I','-S','-c',
  'import os,sys; assert sys.flags.isolated==1 and sys.flags.no_site==1 and sys.flags.ignore_environment==1; '
  'f=os.open(sys.argv[1],os.O_RDONLY); assert os.read(f,9)==b\"synthetic\"; os.fstat(f); os.close(f)',str(d/'synthetic')])
_,status=os.waitpid(child,0); assert os.waitstatus_to_exitcode(status)==0
subprocess.run(['/usr/bin/true'],check=True)
print('SYNTHETIC_MECHANISM_PROBE_OK',flush=True)
'''


def child_status_notice(signum, frame):
    # Wakeup FD is the notification; this handler never waits, kills or mutates tracees.
    pass


class Stop(Exception):
    """Sanitized fail-closed observation failure; no raw backend diagnostics."""


def emit(kind, **fields):
    global LOG_BYTES
    line = 'H8_JSON ' + json.dumps(dict(kind=kind, **fields), sort_keys=True)
    LOG_BYTES += len(line.encode()) + 1
    if LOG_BYTES > LOG_LIMIT:
        raise Stop('JOB_LOG_OUTPUT_LIMIT')
    print(line, flush=True)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=10).decode().strip()


def checkout(root):
    value = dict(sha=git(root, 'rev-parse', 'HEAD'), tree=git(root, 'rev-parse', 'HEAD^{tree}'),
                 status=git(root, 'status', '--porcelain'))
    if value != dict(sha=TESTED, tree=TREE, status=''):
        raise Stop('TESTED_CHECKOUT_MISMATCH')
    subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True, timeout=10)
    return value


def read_bound(path, bound=1024*1024):
    # Only explicitly named proc metadata; never arbitrary tracee file contents.
    with open(path, 'rb') as stream:
        data = stream.read(bound + 1)
    if len(data) > bound:
        raise Stop('PROC_METADATA_LIMIT')
    return data


def proc_identity(pid):
    text = read_bound('/proc/%d/stat' % pid, 8192).decode('ascii')
    fields = text[text.rindex(')')+2:].split()
    status = read_bound('/proc/%d/status' % pid, 65536).decode('ascii')
    tgid = int(re.search(r'^Tgid:\s+(\d+)$', status, re.M)[1])
    if tgid != pid:
        raise Stop('THREAD_DOMAIN_UNSUPPORTED')
    return dict(pid=pid, start_ticks=int(fields[19]),
                pidns=os.stat('/proc/%d/ns/pid' % pid).st_ino,
                mntns=os.stat('/proc/%d/ns/mnt' % pid).st_ino)


def mount_table(pid):
    return read_bound('/proc/%d/mountinfo' % pid)


def fs_record(pid, fd, expected_mounts):
    """FD object at this task's stop, not reconstructed pathname traversal."""
    before = mount_table(pid)
    if before != expected_mounts:
        raise Stop('MOUNT_DOMAIN_CHANGED')
    info_path = '/proc/%d/fdinfo/%d' % (pid, fd)
    link_path = '/proc/%d/fd/%d' % (pid, fd)
    try:
        info = read_bound(info_path, 65536).decode('ascii')
        st = os.stat(link_path)
        target = os.readlink(link_path)
        mid = int(re.search(r'^mnt_id:\s+(\d+)$', info, re.M)[1])
        ino = int(re.search(r'^ino:\s+(\d+)$', info, re.M)[1])
        if st.st_ino != ino:
            raise Stop('FD_IDENTITY_CHANGED')
        mounts = []
        for line in before.decode('ascii').splitlines():
            a, b = line.split(' - ', 1)
            left, right = a.split(), b.split()
            if int(left[0]) == mid:
                mounts.append(dict(mount_id=mid, device=left[2], mount_root=left[3],
                                   mountpoint=left[4], fstype=right[0]))
        # Pipes/sockets may have mount IDs absent from the task's mountinfo.
        if not mounts:
            return dict(fd=fd, object_kind='NON_PATH_OR_UNMAPPED_MOUNT',
                        target=target, inode=ino, device=st.st_dev, mount_id=mid,
                        filesystem='UNKNOWN')
        if len(mounts) != 1 or mounts[0]['device'] != '%d:%d' % (os.major(st.st_dev), os.minor(st.st_dev)):
            raise Stop('FD_MOUNT_IDENTITY_CONFLICT')
        after = read_bound(info_path, 65536).decode('ascii')
        if info != after or before != mount_table(pid):
            raise Stop('FD_OR_MOUNT_CHANGED_DURING_STOP_SNAPSHOT')
        return dict(fd=fd, target=target, inode=ino, st_dev=st.st_dev,
                    mountinfo_sha256=hashlib.sha256(before).hexdigest(),
                    boundary='FD_SNAPSHOT_WHILE_TASK_STOPPED', **mounts[0])
    except FileNotFoundError:
        return dict(fd=fd, object_kind='ABSENT_AT_STOP', filesystem='UNKNOWN')


class Channel:
    def __init__(self, path):
        self.stream = os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'wb')
        self.size = 0

    def write(self, raw):
        if self.size + len(raw) > LIMIT:
            raise Stop('CHANNEL_OUTPUT_LIMIT')
        self.stream.write(raw); self.stream.flush(); self.size += len(raw)

    def event(self, kind, **fields):
        self.write((json.dumps(dict(kind=kind, stop_observation_ns=time.monotonic_ns(), **fields), sort_keys=True)+'\n').encode())

    def close(self):
        self.stream.close()


class Observer:
    def __init__(self, events, console, domain, deadline, case_deadline, probe_target=None):
        self.events, self.console, self.domain = events, console, domain
        self.deadline, self.case_deadline = deadline, case_deadline
        self.probe_target = str(probe_target) if probe_target is not None else None
        self.probe = dict(object=None, creator=None, child=None, creator_ops=set(), child_ops=set(),
                          true_generation=None, terminal={})
        self.tasks, self.early_stops, self.handles = {}, {}, {}
        self.serial = 0
        self.libc = C.CDLL(None, use_errno=True)
        self.libc.ptrace.argtypes = [C.c_uint, C.c_int, C.c_void_p, C.c_void_p]
        self.libc.ptrace.restype = C.c_long
        self.mounts = mount_table(os.getpid())
        self.ns = (os.stat('/proc/self/ns/pid').st_ino, os.stat('/proc/self/ns/mnt').st_ino)
        self.root_pid = None
        self.root_exit = None
        self.births, self.exits, self.execs = 0, 0, 0
        self.relative_paths, self.fd_only = 0, 0
        self.exec_images = set()
        self.fd_bound, self.path_requests, self.fd_unknown = 0, 0, 0
        self.observer_error = None
        self.wake_r = self.wake_w = None
        self.old_wakeup = None
        self.old_sigchld = None
        self.sigchld_restore_needed = False
        self.wakeup_maybe_active = False
        self.wakeup_restore_unknown = False
        self.secondary_failures = []
        self.secondary_failure_count = 0
        self.secondary_log_incomplete = False
        self.wait_metrics = dict(waitpid_calls=0, empty_status_polls=0, readiness_waits=0,
                                 readiness_wait_seconds=0.0)

    def record_secondary(self, phase, exc):
        # Diagnostics must never replace a primary/restoration exception.
        try:
            self.secondary_failure_count += 1
            item = dict(phase=phase, type=type(exc).__name__)
            number = getattr(exc, 'errno', None)
            if type(number) is int: item['errno'] = number
            if len(self.secondary_failures) < 16:
                self.secondary_failures.append(item)
                try: self.events.event('SECONDARY_FAILURE', **item)
                except BaseException: self.secondary_log_incomplete = True
        except BaseException:
            self.secondary_log_incomplete = True

    def resource_summary(self):
        return dict(secondary_failure_count=self.secondary_failure_count,
                    secondary_failures=list(self.secondary_failures),
                    secondary_log_incomplete=self.secondary_log_incomplete,
                    wakeup_restore_unknown=self.wakeup_restore_unknown,
                    wake_pipe_retained=self.wake_r is not None or self.wake_w is not None)

    def open_wakeup(self):
        # One recovery owner: launch.finally handles even partially failed setup.
        self.old_sigchld = signal.getsignal(signal.SIGCHLD)
        if signal.SIGCHLD in signal.pthread_sigmask(signal.SIG_BLOCK, []):
            raise Stop('BLOCKED_SIGCHLD_UNSUPPORTED')
        if self.old_sigchld != signal.SIG_DFL:
            raise Stop('EXISTING_SIGCHLD_HANDLER_UNSUPPORTED')
        self.wake_r, self.wake_w = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        self.wakeup_maybe_active = True  # If the call raises, do not guess FD state.
        self.old_wakeup = signal.set_wakeup_fd(self.wake_w, warn_on_full_buffer=False)
        if self.old_wakeup != -1:
            raise Stop('EXISTING_WAKEUP_FD_UNSUPPORTED')
        self.sigchld_restore_needed = True  # Also restore if handler installation raises.
        signal.signal(signal.SIGCHLD, child_status_notice)

    def close_wakeup(self):
        # Each restoration is attempted once. Preserve the first actual exception.
        first = None
        if self.wakeup_maybe_active:
            if self.old_wakeup is None:
                self.wakeup_restore_unknown = True
                exc = Stop('WAKEUP_RESTORE_TARGET_UNKNOWN')
                first = (exc, exc.__traceback__)
                self.record_secondary('restore_wakeup_target_unknown', exc)
            else:
                saved = self.old_wakeup
                self.old_wakeup = None  # No retry after an ambiguous restoration failure.
                try:
                    signal.set_wakeup_fd(saved)
                    self.wakeup_maybe_active = False
                    self.wakeup_restore_unknown = False
                except BaseException as exc:
                    self.wakeup_restore_unknown = True
                    first = (exc, exc.__traceback__)
                    self.record_secondary('restore_wakeup_fd', exc)
        if self.sigchld_restore_needed:
            self.sigchld_restore_needed = False
            try: signal.signal(signal.SIGCHLD, self.old_sigchld)
            except BaseException as exc:
                if first is None: first = (exc, exc.__traceback__)
                self.record_secondary('restore_sigchld_handler', exc)
        # If wakeup restoration is uncertain, keep BOTH pipe ends valid. A signal
        # may still write this FD; closing/reusing it or closing only the reader is unsafe.
        if not self.wakeup_maybe_active and not self.wakeup_restore_unknown:
            for name in ('wake_r', 'wake_w'):
                fd = getattr(self, name)
                if fd is not None:
                    setattr(self, name, None)  # Never retry close after identity becomes unknown.
                    try: os.close(fd)
                    except BaseException as exc:
                        if first is None: first = (exc, exc.__traceback__)
                        self.record_secondary('close_'+name, exc)
        if first is not None:
            raise first[0].with_traceback(first[1])

    def poll_status(self):
        # Sole status owner, including initial stop and failure cleanup.
        self.wait_metrics['waitpid_calls'] += 1
        value = os.waitpid(-1, os.WNOHANG | WALL)
        if value[0] == 0:
            self.wait_metrics['empty_status_polls'] += 1
        return value

    def wait_status(self, deadline, output_fd=None):
        """Kernel status first; SIGCHLD readiness only wakes, never supplies status.

        Drain/coalesced/full wake pipe is harmless: recheck waitpid after draining
        and before sleeping. A signal between recheck and select leaves FD readiness.
        No fixed per-stop sleep and no serial run-until-syscall-exit policy.
        """
        if time.monotonic() >= deadline:
            raise Stop('CASE_DEADLINE')
        value = self.poll_status()
        if value[0]: return value
        while True:
            if time.monotonic() >= deadline: raise Stop('CASE_DEADLINE')
            try: data = os.read(self.wake_r, 4096)
            except BlockingIOError: break
            if not data: raise Stop('WAKEUP_PIPE_CLOSED')
        # Status may have become pending while the notification pipe was drained.
        value = self.poll_status()
        if value[0]: return value
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise Stop('CASE_DEADLINE')
        watches = [self.wake_r] + ([] if output_fd is None else [output_fd])
        before = time.monotonic()
        self.wait_metrics['readiness_waits'] += 1
        select.select(watches, [], [], remaining)
        self.wait_metrics['readiness_wait_seconds'] += time.monotonic()-before
        return 0, 0  # Caller drains output, then checks kernel status again.

    def check_budget(self):
        if time.monotonic() >= self.deadline:
            raise Stop('CASE_DEADLINE')

    def ptrace(self, request, pid, addr=0, data=0):
        C.set_errno(0)
        value = self.libc.ptrace(request, pid, C.c_void_p(addr), C.c_void_p(data))
        error = C.get_errno()
        if value == -1 and error:
            raise Stop('PTRACE_FAILED_%d' % error)
        return value

    def stable(self, task):
        if proc_identity(task['pid']) != task['identity']:
            raise Stop('TASK_IDENTITY_CHANGED')
        if mount_table(task['pid']) != self.mounts:
            raise Stop('MOUNT_DOMAIN_CHANGED')

    def birth(self, pid, parent):
        if pid in self.tasks:
            raise Stop('DUPLICATE_LIVE_PID')
        self.serial += 1
        if pid not in self.handles:
            self.handles[pid] = os.pidfd_open(pid, 0)
        identity = proc_identity(pid)
        if (identity['pidns'], identity['mntns']) != self.ns:
            raise Stop('NAMESPACE_UNSUPPORTED')
        # pidfd is opened only for a known ptrace birth, never an enumerated PID.
        pidfd = self.handles[pid]
        task = dict(pid=pid, identity=identity, generation=self.serial, parent=parent,
                    pidfd=pidfd, pending=None, stopped=True, initial=True,
                    born_return=True, exec_return=False, image=0)
        self.tasks[pid] = task
        self.births += 1
        self.events.event('BIRTH', identity=identity, generation=self.serial, parent=parent)
        return task

    def peek_word(self, pid, address):
        return self.ptrace(2, pid, address) & ((1 << 64)-1)

    def path(self, pid, address):
        if not address:
            return dict(state='NULL_PATH')
        raw = bytearray()
        for offset in range(0, 4096, 8):
            self.check_budget()
            chunk = self.peek_word(pid, address + offset).to_bytes(8, 'little')
            raw.extend(chunk)
            if 0 in chunk:
                value = bytes(raw).split(b'\0', 1)[0]
                # Path bytes only, never an arbitrary user-data/argv/env buffer.
                return dict(state='PATH_BYTES_AT_ENTRY_STOP', path=os.fsdecode(value))
        raise Stop('PATH_UNTERMINATED_OR_LIMIT')

    def fd(self, task, fd):
        value = fs_record(task['pid'], fd, self.mounts)
        if 'fstype' in value:
            self.fd_bound += 1
        else:
            self.fd_unknown += 1
        return value

    @staticmethod
    def object_key(value):
        if not value or 'fstype' not in value:
            return None
        return (value['st_dev'], value['inode'], value['mount_id'], value['device'],
                value['fstype'], value['mountinfo_sha256'])

    def probe_return(self, task, pending, result, is_error, result_fd):
        """Require the fixed probe object, not interpreter-startup counters."""
        if self.probe_target is None or is_error or result < 0:
            return
        refs = pending.get('probe_refs')
        if refs is None:
            return
        paths, dirs, fds = refs
        key = self.object_key(result_fd)
        actor = (task['generation'], task['image'])
        if pending['nr'] == 257 and key and result_fd.get('target') == self.probe_target:
            if self.probe['object'] is None:
                # Exact relative openat + exact stopped directory descriptor + result FD.
                relative = len(paths) == 1 and paths[0].get('path') == 'synthetic'
                parent = str(Path(self.probe_target).parent)
                directory = len(dirs) == 1 and dirs[0].get('target') == parent and self.object_key(dirs[0])
                if not (relative and directory and task['parent'] is None):
                    raise Stop('PROBE_RELATIVE_OBJECT_CHAIN_MISSING')
                self.probe['object'] = key
                self.probe['creator'] = (actor, result)
                self.events.event('PROBE_RELATIVE_OPEN_BOUND', generation=actor[0], image=actor[1],
                                  dirfd=dirs[0], result_fd=result_fd)
            elif (key == self.probe['object'] and task['parent'] == self.probe['creator'][0][0]
                  and task['image'] >= 1 and task.get('executable') == os.path.realpath(sys.executable)
                  and len(paths) == 1 and paths[0].get('path') == self.probe_target):
                # The fixed fixture execs Python with -I/-S; that code asserts actual flags.
                if self.probe['child'] not in (None, (actor, result)):
                    raise Stop('PROBE_CHILD_BINDING_AMBIGUOUS')
                self.probe['child'] = (actor, result)
                self.events.event('PROBE_ISOLATED_CHILD_OPEN_BOUND', generation=actor[0], image=actor[1],
                                  result_fd=result_fd)
        expected = self.probe['object']
        if expected is None:
            return
        # Capture only successful FD operations on the exact creator/child FD and object.
        candidates = list(fds)
        flags_index = 3 if pending['nr'] == 262 else 2
        if (pending['nr'] in (262, 332) and pending['args'][flags_index] & 0x1000
                and len(paths) == 1 and paths[0].get('path') == ''):
            candidates += dirs  # fstat via *at(AT_EMPTY_PATH), still the exact bound FD.
        for role in ('creator', 'child'):
            binding = self.probe[role]
            if binding is None or actor != binding[0]:
                continue
            if not any(v.get('fd') == binding[1] and self.object_key(v) == expected for v in candidates):
                continue
            operation = {0:'read', 1:'write', 5:'fstat', 262:'fstat', 332:'fstat'}.get(pending['nr'])
            if operation and ((operation in ('read', 'write') and result == 9)
                              or (operation == 'fstat' and result == 0)):
                self.probe[role+'_ops'].add(operation)
                self.events.event('PROBE_FD_OPERATION_BOUND', role=role, operation=operation,
                                  generation=actor[0], image=actor[1], fd=binding[1],
                                  object_identity=expected, result=result)

    def probe_result(self):
        if self.probe_target is None:
            return None
        p = self.probe
        generations = [p['creator'][0][0] if p['creator'] else None,
                       p['child'][0][0] if p['child'] else None, p['true_generation']]
        complete = (p['object'] is not None and None not in generations and len(set(generations)) == 3
                    and {'read','write'} <= p['creator_ops'] and {'read','fstat'} <= p['child_ops']
                    and all(p['terminal'].get(g) == 0 for g in generations))
        return dict(complete=complete, object_identity=p['object'], creator=p['creator'], child=p['child'],
                    creator_ops=sorted(p['creator_ops']), child_ops=sorted(p['child_ops']),
                    nonpython_generation=p['true_generation'], terminal=p['terminal'],
                    claim='fixed synthetic object and observed descendant chain only; not product proof')

    def syscall_info(self, pid):
        buf = C.create_string_buffer(128)
        count = self.ptrace(0x420e, pid, 128, C.addressof(buf))
        raw = buf.raw
        op, arch = raw[0], struct.unpack_from('<I', raw, 4)[0]
        if arch != ARCH:
            raise Stop('SYSCALL_ARCH_UNSUPPORTED')
        if op == 1 and count >= 80:
            nr, *args = struct.unpack_from('<7Q', raw, 24)
            if nr & 0x40000000:
                raise Stop('X32_ABI_UNSUPPORTED')
            return op, nr, args
        if op == 2 and count >= 33:
            return op, struct.unpack_from('<q', raw, 24)[0], bool(raw[32])
        raise Stop('SYSCALL_INFO_UNAVAILABLE')

    def entry(self, task, nr, args):
        if task['pending'] is not None:
            raise Stop('UNPAIRED_SYSCALL_ENTRY')
        if nr in FORBIDDEN:
            raise Stop('UNSUPPORTED_OBSERVATION_DOMAIN_SYSCALL_%d' % nr)
        if nr in (56, 435):
            flags = args[0] if nr == 56 else self.peek_word(task['pid'], args[0])
            if flags & CLONE_SHARED:
                raise Stop('SHARED_FD_FS_OR_THREAD_UNSUPPORTED')
            if flags & CLONE_VM and not flags & CLONE_VFORK:
                raise Stop('CONCURRENT_SHARED_VM_UNSUPPORTED')
            allowed = 0xff | CLONE_VM | CLONE_VFORK | 0x200000 | 0x1000000 | 0x100000000
            if flags & ~allowed:
                raise Stop('CLONE_FLAGS_UNSUPPORTED')
        event = dict(nr=nr, args=args, captured=False)
        if nr in PATH_ARGS or nr in FD_ARGS or nr in OPEN_RESULT:
            self.stable(task)
            fields = dict(pid=task['pid'], generation=task['generation'], image=task['image'], nr=nr,
                          boundary='SYSCALL_ENTRY_STOP_NOT_ATOMIC_KERNEL_EVENT')
            if nr in PATH_ARGS:
                self.path_requests += 1
                fields['paths'] = [self.path(task['pid'], args[k]) for k in PATH_ARGS[nr]]
                self.relative_paths += sum(1 for p in fields['paths'] if p.get('path') and not p['path'].startswith('/'))
                fields['cwd_at_stop'] = os.readlink('/proc/%d/cwd' % task['pid'])
                fields['dirfds'] = []
                for k in DIR_ARGS.get(nr, ()):
                    fd = C.c_int(args[k] & 0xffffffff).value
                    fields['dirfds'].append(dict(at_fdcwd=True) if fd == -100 else self.fd(task, fd))
                fields['path_object_identity'] = 'UNKNOWN_UNTIL_RESULT_FD; pathname-only operations remain UNKNOWN'
            if nr in FD_ARGS:
                self.fd_only += 1
                fields['fds'] = [self.fd(task, C.c_int(args[k] & 0xffffffff).value) for k in FD_ARGS[nr]]
            self.stable(task)
            self.events.event('ENTRY', **fields)
            if self.probe_target is not None:
                event['probe_refs'] = (fields.get('paths', []), fields.get('dirfds', []), fields.get('fds', []))
            event['captured'] = True
        task['pending'] = event
        task['born_return'] = False

    def exit_syscall(self, task, result, is_error):
        pending = task['pending']
        if pending is None:
            if (task['born_return'] or task['exec_return']) and result == 0 and not is_error:
                task['born_return'] = task['exec_return'] = False
                return
            raise Stop('UNPAIRED_SYSCALL_EXIT')
        if pending['captured']:
            self.stable(task)
            record = dict(pid=task['pid'], generation=task['generation'], nr=pending['nr'],
                          result=result, is_error=is_error, boundary='SYSCALL_EXIT_STOP')
            if pending['nr'] in OPEN_RESULT and not is_error and result >= 0:
                record['result_fd_snapshot'] = self.fd(task, result)
                if record['result_fd_snapshot'].get('object_kind') == 'ABSENT_AT_STOP':
                    raise Stop('RETURNED_FD_MISSING_AT_STOP')
                record['claim'] = 'object at return stop; not atomic snapshot of entire syscall'
            self.stable(task)
            self.events.event('RETURN', **record)
            self.probe_return(task, pending, result, is_error, record.get('result_fd_snapshot'))
        task['pending'] = None

    def resume(self, task, sig=0):
        self.ptrace(24, task['pid'], 0, sig)
        task['stopped'] = False

    def stopped(self, pid, status):
        task = self.tasks.get(pid)
        if task is None:
            # Kernel may report the new child's stop before the parent's birth event.
            if not os.WIFSTOPPED(status) or os.WSTOPSIG(status) != signal.SIGSTOP or pid in self.early_stops:
                raise Stop('UNATTRIBUTED_WAIT_EVENT')
            self.early_stops[pid] = status
            return
        task['stopped'] = True
        sig, event = os.WSTOPSIG(status), status >> 16
        if task['initial'] and sig == signal.SIGSTOP and not event:
            task['initial'] = False
            self.ptrace(0x4200, pid, 0, TRACE_OPTIONS)
            self.resume(task); return
        task['initial'] = False
        if event in (1, 2, 3):
            child = C.c_ulonglong()
            self.ptrace(0x4201, pid, 0, C.addressof(child))
            new = self.birth(child.value, task['generation'])
            self.events.event('FORK_EVENT', parent_generation=task['generation'], child_generation=new['generation'], event=event)
            if child.value in self.early_stops:
                self.stopped(child.value, self.early_stops.pop(child.value))
            self.resume(task); return
        if event == 4:
            former = C.c_ulonglong()
            self.ptrace(0x4201, pid, 0, C.addressof(former))
            if former.value != pid:
                raise Stop('NONLEADER_EXEC_UNSUPPORTED')
            task['pending'] = None; task['exec_return'] = True; task['image'] += 1
            self.stable(task); self.execs += 1
            executable = os.readlink('/proc/%d/exe' % pid)
            if executable not in (os.path.realpath(sys.executable), os.path.realpath('/usr/bin/true')):
                raise Stop('UNEXPECTED_EXECUTABLE_IMAGE')
            self.exec_images.add(executable)
            task['executable'] = executable
            if (self.probe_target is not None and executable == os.path.realpath('/usr/bin/true')
                    and self.probe['creator'] is not None and task['parent'] == self.probe['creator'][0][0]):
                if self.probe['true_generation'] not in (None, task['generation']):
                    raise Stop('PROBE_NONPYTHON_BINDING_AMBIGUOUS')
                self.probe['true_generation'] = task['generation']
            self.events.event('EXEC_STOP', generation=task['generation'], image=task['image'],
                              executable=executable, identity=task['identity'])
            self.resume(task); return
        if event == 6:
            self.events.event('PRE_EXIT_STOP', generation=task['generation'], terminal=False)
            self.resume(task); return
        if event:
            raise Stop('UNSUPPORTED_PTRACE_EVENT')
        if sig == signal.SIGTRAP | 0x80:
            op, a, b = self.syscall_info(pid)
            if op == 1: self.entry(task, a, b)
            else: self.exit_syscall(task, a, b)
            self.resume(task); return
        if sig in (signal.SIGSTOP, signal.SIGTSTP, signal.SIGTTIN, signal.SIGTTOU):
            raise Stop('JOB_CONTROL_STOP_UNSUPPORTED')
        # Genuine signal-delivery stop: preserve the same signal, no invented signal.
        self.events.event('SIGNAL_DELIVERY', generation=task['generation'], signal=sig)
        self.resume(task, sig)

    def wait_event(self, pid, status):
        if os.WIFSTOPPED(status):
            self.stopped(pid, status); return
        if not (os.WIFEXITED(status) or os.WIFSIGNALED(status)) or pid not in self.tasks:
            raise Stop('UNKNOWN_TERMINAL_WAIT')
        task = self.tasks.pop(pid)
        code = os.waitstatus_to_exitcode(status)
        self.exits += 1
        if self.probe_target is not None:
            self.probe['terminal'][task['generation']] = code
        self.events.event('TERMINAL_WAIT', generation=task['generation'], identity=task['identity'],
                          exit_code=code, claim='tracer terminal wait; not product-parent reap')
        os.close(self.handles.pop(pid))
        if pid == self.root_pid: self.root_exit = code

    def cleanup(self):
        # Same absolute case cap and exact pidfds; no new PID/PGID authority.
        errors = []
        deadline = min(self.case_deadline, self.deadline + 2, time.monotonic() + 2)
        for handle in list(self.handles.values()):
            if time.monotonic() >= deadline:
                errors.append('CLEANUP_BUDGET_EXHAUSTED'); break
            try: signal.pidfd_send_signal(handle, signal.SIGKILL)
            except ProcessLookupError: pass
            except OSError: errors.append('PIDFD_SIGNAL_FAILED')
        while self.handles and time.monotonic() < deadline:
            try: pid, status = self.wait_status(deadline)
            except ChildProcessError:
                errors.append('CLEANUP_WAIT_OWNERSHIP_UNKNOWN'); break
            except Stop:
                errors.append('CLEANUP_BUDGET_EXHAUSTED'); break
            if not pid: continue
            if os.WIFSTOPPED(status):
                try: self.ptrace(7, pid, 0, signal.SIGKILL)
                except Stop: errors.append('FINAL_CONTINUE_FAILED')
            elif os.WIFEXITED(status) or os.WIFSIGNALED(status):
                task = self.tasks.pop(pid, None)
                handle = self.handles.pop(pid, None)
                if handle is not None: os.close(handle)
                try:
                    self.events.event('CLEANUP_TERMINAL_WAIT', pid=pid,
                                      generation=task['generation'] if task else None,
                                      identity=task['identity'] if task else None,
                                      exit_code=os.waitstatus_to_exitcode(status),
                                      case_result='NOT_PASS',
                                      claim='sole tracer cleanup wait; not a successful case or product-parent reap')
                except Stop:
                    errors.append('CLEANUP_TERMINAL_RECORD_INCOMPLETE')
            else:
                errors.append('UNEXPECTED_CLEANUP_WAIT')
        return dict(known_live_tasks=len(self.handles), early_unassociated_stops=len(self.early_stops),
                    errors=errors, wait_metrics=dict(self.wait_metrics),
                    claim='best effort exact-task termination; unobserved descendants UNKNOWN')

    def launch(self, argv, cwd, tmpdir):
        readfd = writefd = None
        primary = None
        cleanup_summary = None
        try:
            self.open_wakeup()
            readfd, writefd = os.pipe()
            os.set_blocking(readfd, False)
            child = os.fork()
            if child == 0:
                try:
                    # Do not pass the observer's SIGCHLD handler/wakeup pipe to tests.
                    signal.set_wakeup_fd(-1)
                    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                    os.close(self.wake_r); os.close(self.wake_w)
                    os.close(readfd)
                    os.dup2(writefd, 1); os.dup2(writefd, 2); os.close(writefd)
                    os.chdir(cwd)
                    env = {'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8',
                           'TMPDIR':str(tmpdir), 'PYTHONDONTWRITEBYTECODE':'1'}
                    self.ptrace(0, 0)
                    os.kill(os.getpid(), signal.SIGSTOP)
                    os.execve(argv[0], argv, env)
                except BaseException:
                    os._exit(125)
            owned_writefd = writefd; writefd = None
            os.close(owned_writefd)  # Do not retry if close raises with uncertain FD state.
            self.root_pid = child
            # Direct child cannot be PID-reused before this sole parent waiter reaps it.
            self.handles[child] = os.pidfd_open(child, 0)
            initial = None
            while initial is None:
                self.check_budget()
                pid, status = self.wait_status(self.deadline)
                if pid:
                    if pid != child: raise Stop('UNATTRIBUTED_INITIAL_WAIT')
                    initial = status
            if not os.WIFSTOPPED(initial) or os.WSTOPSIG(initial) != signal.SIGSTOP:
                raise Stop('INITIAL_TRACEME_STOP_FAILED')
            self.ptrace(0x4200, child, 0, TRACE_OPTIONS)
            self.birth(child, None)
            self.stopped(child, initial)
            eof = False
            while self.tasks or not eof:
                self.check_budget()
                while True:
                    self.check_budget()
                    try: chunk = os.read(readfd, 65536)
                    except BlockingIOError: break
                    if not chunk: eof = True; break
                    self.console.write(chunk)
                    self.check_budget()
                if self.tasks:
                    pid, status = self.wait_status(self.deadline, None if eof else readfd)
                    if pid: self.wait_event(pid, status)
                elif not eof:
                    # No known task left. Wait only for owned output EOF within same cap.
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0: raise Stop('CASE_DEADLINE')
                    select.select([readfd], [], [], remaining)
            if self.early_stops or self.births != self.exits or self.root_exit != 0:
                raise Stop('DESCENDANT_CLOSURE_OR_CASE_FAILED')
            return dict(root_exit=self.root_exit, births=self.births, terminal_waits=self.exits,
                        relative_path_requests=self.relative_paths, fd_only_requests=self.fd_only,
                        exec_images=sorted(self.exec_images), wait_metrics=dict(self.wait_metrics),
                        exec_stops=self.execs, fd_snapshots_bound=self.fd_bound,
                        fd_unmapped_or_absent=self.fd_unknown, pathname_requests=self.path_requests,
                        closure='OBSERVED_PTRACE_TASKS_ONLY', all_paths='NOT_PROVEN',
                        event_time_atomicity='NOT_CLAIMED', synthetic_probe=self.probe_result())
        except BaseException as exc:
            primary = exc
            try: cleanup_summary = self.cleanup()
            except BaseException as cleanup_error:
                self.record_secondary('cleanup', cleanup_error)
                cleanup_summary = dict(state='UNKNOWN', known_live_tasks=len(self.handles),
                                       claim='cleanup raised; no terminal closure inferred')
            raise  # Original exception object and traceback, not cleanup's exception.
        finally:
            first_restore = None
            for name, fd in (('console_read', readfd), ('console_write', writefd)):
                if fd is not None:
                    # This local ownership is surrendered before close: never retry it.
                    if name == 'console_read': readfd = None
                    else: writefd = None
                    try: os.close(fd)
                    except BaseException as restore_error:
                        if first_restore is None:
                            first_restore = (restore_error, restore_error.__traceback__)
                        self.record_secondary('close_'+name, restore_error)
            try: self.close_wakeup()
            except BaseException as restore_error:
                if first_restore is None:
                    first_restore = (restore_error, restore_error.__traceback__)
                self.record_secondary('restore_wakeup_resources', restore_error)
            if primary is not None:
                try:
                    self.events.event('ABORT', cleanup=cleanup_summary,
                                      primary_type=type(primary).__name__,
                                      restoration=self.resource_summary())
                except BaseException as log_error:
                    self.record_secondary('abort_record', log_error)
                # Never raise here: the original active exception remains authoritative.
            elif first_restore is not None:
                try: self.events.event('RESTORE_FAILURE', restoration=self.resource_summary())
                except BaseException as log_error:
                    self.record_secondary('restore_failure_record', log_error)
                # A successful action with failed restoration is NOT_PASS. Keep exact error.
                raise first_restore[0].with_traceback(first_restore[1])


def channel_blob(name, path):
    # Runtime output only; archive locally from complete job log after future run.
    raw = path.read_bytes()
    if len(raw) > LIMIT: raise Stop('CHANNEL_OUTPUT_LIMIT')
    for index, offset in enumerate(range(0, len(raw), 3072)):
        emit('BLOB', name=name, index=index, base64=base64.b64encode(raw[offset:offset+3072]).decode())
    emit('BLOB_END', name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(tested, control):
    start = time.monotonic()
    if sys.platform != 'linux' or platform.machine() != 'x86_64' or sys.version_info[:3] != (3, 15, 1):
        raise Stop('PLATFORM_RUNTIME_UNSUPPORTED')
    if os.geteuid() == 0:
        raise Stop('ROOT_EXECUTION_NOT_AUTHORIZED')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise Stop('PIDFD_UNAVAILABLE')
    if os.environ.get('H8_REPOSITORY_PRIVATE') != 'false':
        raise Stop('PUBLIC_REPOSITORY_REQUIRED')
    if os.environ.get('GITHUB_REF') != 'refs/heads/'+BRANCH or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise Stop('EXECUTION_REF_ATTEMPT_MISMATCH')
    if git(control, 'rev-parse', 'HEAD') != os.environ['GITHUB_SHA'] or git(control, 'status', '--porcelain'):
        raise Stop('CONTROL_IDENTITY_MISMATCH')
    if git(control, 'hash-object', '--', str(Path(__file__).resolve())) != git(control, 'rev-parse', 'HEAD:scripts/h8_linux_evidence.py'):
        raise Stop('COLLECTOR_BLOB_MISMATCH')
    pre = checkout(tested)
    private = Path(tempfile.mkdtemp(prefix='h8-stop-', dir=os.environ['RUNNER_TEMP']))
    os.chmod(private, 0o700)
    events_path, console_path = private/'events.jsonl', private/'console.log'
    events, console = Channel(events_path), Channel(console_path)
    emit('BEGIN', version=VERSION, control_sha=os.environ['GITHUB_SHA'], control_tree=git(control, 'rev-parse', 'HEAD^{tree}'),
         tested=pre, runtime=sys.version, arch=platform.machine(), image=os.environ.get('ImageVersion'),
         runner_image=os.environ.get('ImageOS'), run=os.environ.get('GITHUB_RUN_ID'),
         private=str(private), retention='NO_RECURSIVE_COLLECTOR_CLEANUP; runner lifetime only',
         assumptions='trusted cooperative host; no concurrent host-admin mount/fd/ptrace interference',
         interference='ptrace syscall stops change timing; not historical-suite noninterference',
         cleanup_effect='PTRACE_O_EXITKILL and exact known-task pidfd SIGKILL on failure; requires future explicit run authority',
         linux_abi='x86_64 AUDIT_ARCH_X86_64; PTRACE_GET_SYSCALL_INFO; incompatible ABI refused')
    outcomes, failure = [], None
    try:
        if time.monotonic()-start >= 120: raise Stop('PREPARATION_BUDGET')
        cases = [('SYNTHETIC_MECHANISM_PROBE', [sys.executable, '-B', '-c', PROBE, str(private/'probe')])]
        (private/'probe').mkdir(mode=0o700)
        for name in METHODS:
            cases.append((name, [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                '-p', 'test_cross_process_coordination.py', '-k', 'CrossProcessTests.'+name, '-v']))
        if time.monotonic()-start >= 120: raise Stop('PREPARATION_BUDGET')
        cases_start = time.monotonic()
        total_deadline = cases_start + 180
        for name, argv in cases:
            case_start = time.monotonic()
            case_deadline = min(case_start + 30, total_deadline)
            action_deadline = case_deadline - 2  # Cleanup reserve is inside the same absolute cap.
            def check_case():
                if time.monotonic() >= case_deadline or time.monotonic() >= total_deadline:
                    raise Stop('CASE_OR_CUMULATIVE_BUDGET')
            check_case()
            tmp = private/name; tmp.mkdir(mode=0o700)
            before = console.size
            events.event('CASE_BEGIN', name=name, argv=argv if name != 'SYNTHETIC_MECHANISM_PROBE' else ['python','-B','-c','FIXED_SYNTHETIC_PROBE'],
                         case_deadline=case_deadline, action_deadline=action_deadline,
                         total_deadline=total_deadline, synthetic=name=='SYNTHETIC_MECHANISM_PROBE')
            target = private/'probe'/'relative'/'synthetic' if name == 'SYNTHETIC_MECHANISM_PROBE' else None
            observer = Observer(events, console, private, action_deadline, case_deadline, target)
            check_case(); observer.check_budget()
            result = observer.launch(argv, str(tested), tmp)
            check_case()
            # Qualification, metadata reread and CASE_END consume the same case budget.
            console.stream.flush()
            case_log = console_path.read_bytes()[before:]
            check_case()
            if name != 'SYNTHETIC_MECHANISM_PROBE':
                if not re.search(rb'Ran 1 test in ', case_log) or not re.search(rb'\nOK\s*\n', case_log) or b'skipped' in case_log:
                    raise Stop('EXPECTED_ONE_UNSKIPPED_CASE_NOT_CONFIRMED')
            elif (b'SYNTHETIC_MECHANISM_PROBE_OK' not in case_log
                  or not result['synthetic_probe']['complete']):
                raise Stop('SYNTHETIC_PROBE_EXACT_CHAIN_NOT_CONFIRMED')
            check_case()
            events.event('CASE_END', name=name, result=result)
            check_case()
            outcomes.append(dict(name=name, **result))
            check_case()
        if time.monotonic() >= total_deadline:
            raise Stop('CUMULATIVE_CASE_BUDGET')
    except BaseException as exc:
        failure = str(exc) if isinstance(exc, Stop) else 'UNEXPECTED_'+type(exc).__name__
    finally:
        events.close(); console.close()
        # Separate 120-second log-emission reserve; a killed/truncated log is incomplete.
        signal.setitimer(signal.ITIMER_REAL, 120)
        channel_blob('events', events_path); channel_blob('console', console_path)
        signal.setitimer(signal.ITIMER_REAL, 0)
    post = checkout(tested)
    control_post = dict(sha=git(control,'rev-parse','HEAD'), tree=git(control,'rev-parse','HEAD^{tree}'), status=git(control,'status','--porcelain'))
    if control_post['sha'] != os.environ['GITHUB_SHA'] or control_post['status']:
        failure = failure or 'CONTROL_POST_MISMATCH'
    emit('END', failure=failure, outcomes=outcomes, post=post, control_post=control_post,
         elapsed=time.monotonic()-start, classification='SELECTED_STOP_BOUNDARY_OBSERVATION_ONLY' if not failure else 'NOT_PASS',
         all_paths='NOT_PROVEN; pathname-only operations and unmapped fd targets UNKNOWN',
         unsupported='threads/shared fd/fs/concurrent shared VM/namespaces/mount mutation/async io rejected',
         cleanup='known ptrace tasks only; no product-parent reap or hostile escape guarantee',
         H8_OVERALL='PARTIAL', old_permission='40975038926 CONSUMED; not reused')
    return 0 if failure is None and len(outcomes)==5 else 1


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--run':
        raise SystemExit('Explicit --run TESTED CONTROL only; requires separate execution authority')
    try:
        raise SystemExit(run(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()))
    except Stop as exc:
        emit('BLOCKED', reason=str(exc)); raise SystemExit(1)
