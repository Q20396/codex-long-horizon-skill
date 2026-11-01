"""Opt-in count-bytes task: owned wc process, one explicitly authorized input.

Imports are inert. No arbitrary command, file-content capture or automatic trust.
"""
import argparse
import ctypes
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time

_SPEC = importlib.util.spec_from_file_location('_owned_primitives', Path(__file__).with_name('linux_owned_file_observer.py'))
B = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(B)
Rejected, need = B.Rejected, B.require
MAX_INPUT = 65536
MAX_REPORT = 32768
MAX_READS = 32
MAX_RUNTIME = 8
MAX_RUNTIME_BYTES = 32 * 1024 * 1024
SOURCE = 'LINUX_COUNT_BYTES_TASK_V1'
STATUS = 'PASS_SELECTED_COUNT_BYTES_TASK_WITH_LIMITS'
# -l forces actual sequential processing instead of wc -c's size-only fast path.
# Only the second numeric column (bytes) becomes customer output.
ARGV = ['/usr/bin/wc', '-l', '-c']
CHILD = r'''
import ctypes, os, signal, sys
c = ctypes.CDLL(None, use_errno=True)
if c.prctl(1, signal.SIGKILL, 0, 0, 0) != 0: os._exit(18)
if os.getppid() != int(sys.argv[1]): os._exit(19)
if c.ptrace(0, 0, None, None) != 0: os._exit(20)
os.kill(os.getpid(), signal.SIGSTOP)
os.execve('/usr/bin/wc', ['/usr/bin/wc','-l','-c'], {'PATH':'/usr/bin:/bin','LC_ALL':'C'})
'''


def identity(s):
    return {'device': s.st_dev, 'inode': s.st_ino}


def unchanged(a, b):
    return all(getattr(a, k) == getattr(b, k) for k in
               ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def checked_leaf(directory, leaf):
    need(type(leaf) is str and leaf not in ('', '.', '..') and '/' not in leaf
         and '\\' not in leaf and '\x00' not in leaf and len(leaf.encode()) <= 255, 'INPUT_LEAF')
    p = Path(directory)
    need(p.is_absolute() and '..' not in p.parts, 'INPUT_DIRECTORY')
    return p, leaf


def close_preserving(fd, primary=None):
    try:
        os.close(fd)
    except BaseException as exc:
        target = primary if primary is not None else exc
        target.cleanup_unknown = True
        target.additional_close_kinds = getattr(target, 'additional_close_kinds', []) + [type(exc).__name__]
        if primary is None:
            raise


@contextmanager
def owned_fd(fd):
    primary = None
    try:
        yield fd
    except BaseException as exc:
        primary = exc
        raise
    finally:
        close_preserving(fd, primary)


def open_input(directory, leaf):
    p, leaf = checked_leaf(directory, leaf)
    B.safe_parent(p)
    fd = None
    try:
        with owned_fd(os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)) as dfd:
            ds = os.fstat(dfd)
            need(ds.st_uid == os.getuid(), 'DIRECTORY_OWNER')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
            s = os.fstat(fd)
            need(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
                 and 0 <= s.st_size <= MAX_INPUT, 'INPUT_TYPE_SIZE_OWNER')
            need(not s.st_mode & 0o022, 'INPUT_PERMISSIONS')
    except BaseException as exc:
        if fd is not None:
            close_preserving(fd, exc)
        raise
    return fd, s, p / leaf


class RuntimeRows(dict):
    absent = frozenset()


def load_runtime(path, forbidden_object):
    # Explicit manifest only. Never infer an allowlist from observed opens.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with owned_fd(fd):
        a = os.fstat(fd)
        need(identity(a) != forbidden_object, 'INPUT_MANIFEST_OVERLAP')
        need(stat.S_ISREG(a.st_mode) and 0 < a.st_size <= 8192, 'RUNTIME_MANIFEST_SIZE')
        raw = os.read(fd, a.st_size + 1)
        need(len(raw) == a.st_size and unchanged(a, os.fstat(fd)), 'RUNTIME_MANIFEST_CHANGED')
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'RUNTIME_DUPLICATE')
            out[k] = v
        return out
    obj = json.loads(raw, object_pairs_hook=pairs)
    need(type(obj) is dict and type(obj.get('version')) is int and obj['version'] == 1
         and obj.get('executable') == ARGV[0], 'RUNTIME_MANIFEST')
    rows = obj.get('objects')
    need(type(rows) is list and 1 <= len(rows) <= MAX_RUNTIME, 'RUNTIME_OBJECT_CAP')
    out, total = RuntimeRows(), 0
    for x in rows:
        need(type(x) is dict, 'RUNTIME_OBJECT')
        for k in ('path', 'resolved_path'):
            p = x.get(k)
            need(type(p) is str and len(p.encode()) <= 4096 and p.startswith('/')
                 and '..' not in p.split('/'), 'RUNTIME_PATH')
        need(x['path'] not in out and re.fullmatch('[0-9a-f]{64}', x.get('sha256', '')) is not None,
             'RUNTIME_PIN')
        need(all(type(x.get(k)) is int and x[k] >= 0 for k in ('device','inode','size')), 'RUNTIME_IDENTITY')
        total += x['size']; need(total <= MAX_RUNTIME_BYTES, 'RUNTIME_BYTE_CAP')
        out[x['path']] = x
    absent = obj.get('absent_paths', [])
    need(type(absent) is list and len(absent) <= 8, 'ABSENT_CAP')
    need(all(type(p) is str and len(p.encode()) <= 4096 and p.startswith('/')
             and '..' not in p.split('/') and p not in out for p in absent), 'ABSENT_PATH')
    out.absent = frozenset(absent)
    out.manifest_sha256 = hashlib.sha256(raw).hexdigest()
    need(ARGV[0] in out, 'EXECUTABLE_PIN_MISSING')
    return out


def verify_runtime(rows, deadline, forbidden_object):
    for path in rows.absent:
        need(time.monotonic() < deadline and not os.path.lexists(path), 'ABSENT_RUNTIME_CHANGED')
    for path, x in rows.items():
        need(time.monotonic() < deadline, 'PREPARATION_DEADLINE')
        need(os.path.realpath(path) == x['resolved_path']
             and os.path.realpath(x['resolved_path']) == x['resolved_path'], 'RUNTIME_ALIAS_CHANGED')
        fd = os.open(x['resolved_path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with owned_fd(fd):
            a = os.fstat(fd)
            need(identity(a) != forbidden_object, 'INPUT_RUNTIME_OVERLAP')
            need(stat.S_ISREG(a.st_mode) and not a.st_mode & 0o022 and a.st_uid in (0,os.getuid())
                 and identity(a) == {k:x[k] for k in ('device','inode')} and a.st_size == x['size'], 'RUNTIME_OBJECT_CHANGED')
            x['_stat'] = a
            digest = hashlib.sha256(); remaining = x['size']
            while remaining:
                need(time.monotonic() < deadline, 'PREPARATION_DEADLINE')
                chunk = os.read(fd, min(65536, remaining))
                need(bool(chunk), 'RUNTIME_SHORT_READ'); digest.update(chunk); remaining -= len(chunk)
            need(digest.hexdigest() == x['sha256'] and unchanged(a, os.fstat(fd)), 'RUNTIME_HASH_CHANGED')


class TaskNative(B.Native):
    def __init__(self, handle, ident, ns, input_path, input_obj, runtime, deadline):
        super().__init__(handle, ident, ns, str(input_path), deadline)
        self.input_obj, self.runtime = input_obj, runtime

    def fd_object(self, fd, domain, row=None):
        need(time.monotonic() < self.deadline, 'OBSERVATION_DEADLINE')
        name = '/proc/%d/fd/%d' % (self.handle.pid, fd)
        expected = self.fixture if domain == 'data' else row['resolved_path']
        need(os.readlink(name) == expected, 'FD_PATH_CHANGED')
        s = os.stat(name)
        want = self.input_obj if domain == 'data' else {k:row[k] for k in ('device','inode')}
        need(stat.S_ISREG(s.st_mode) and identity(s) == want, 'FD_OBJECT_CHANGED')
        if domain == 'runtime':
            need(unchanged(row['_stat'], s), 'RUNTIME_CONTENT_CHANGED')
            need(os.path.realpath(row['path']) == row['resolved_path']
                 and identity(os.stat(row['path'])) == want, 'RUNTIME_ALIAS_CHANGED')
        return want

    def executable(self, row):
        need(time.monotonic() < self.deadline, 'OBSERVATION_DEADLINE')
        p = '/proc/%d/exe' % self.handle.pid
        need(os.readlink(p) == row['resolved_path']
             and identity(os.stat(p)) == {k:row[k] for k in ('device','inode')}, 'EXEC_IDENTITY_CHANGED')
        # Kernel-loaded interpreter is not an open syscall: verify its maps here.
        with open('/proc/%d/maps' % self.handle.pid, 'rb') as f:
            raw = f.read(16385)
        need(len(raw) <= 16384, 'EXEC_MAPS_CAP')
        approved = {x['resolved_path']:x for x in self.runtime.values()}
        for line in raw.decode('utf-8','strict').splitlines():
            parts = line.split(None,5)
            need(len(parts) >= 5, 'EXEC_MAPS_SHAPE')
            if len(parts) == 6 and not parts[5].startswith('['):
                path = parts[5];need(path in approved, 'UNAPPROVED_EXEC_MAPPING')
                x = approved[path];major,minor = (int(v,16) for v in parts[3].split(':'))
                need(os.makedev(major,minor) == x['device'] and int(parts[4]) == x['inode']
                     and unchanged(x['_stat'],os.stat(path)), 'EXEC_MAPPING_CHANGED')


# Only metadata/anonymous memory/process setup syscalls not accessing file data.
# All unknown syscall numbers are rejected, never silently ignored.
SAFE = {10,11,12,13,14,15,24,39,60,63,102,104,107,108,110,131,158,186,
        202,218,228,231,234,273,302,318,334}
FILE_META = {5,6,262}  # fstat, lstat, newfstatat: handled, never content proof.


class TaskEvidence:
    def __init__(self, ident, path, obj, size, runtime):
        self.ident, self.path, self.obj, self.size, self.runtime = ident, str(path), obj, size, runtime
        self.pending = None; self.events = []; self.seq = 0
        self.fds = {0:('data', None)}; self.exec_seen = False; self.exec_event = False
        self.read_bytes = 0; self.reads = 0; self.eof = False; self.closed = False
        self.alignment = False; self.seen_entry = False
        self.rejection = None

    def emit(self, op, phase, domain, stamp, **kw):
        need(len(self.events) < 96, 'EVENT_CAP')
        need(all(type(v) is int and v > 0 for v in stamp) and (not self.events or stamp[0] >= self.events[-1]['observed_monotonic_ns']), 'EVENT_TIME')
        self.events.append(dict(self.ident, syscall_seq=self.seq, operation=op, phase=phase,
            domain=domain, path=self.path if domain == 'data' else 'APPROVED_RUNTIME_OBJECT',
            observed_monotonic_ns=stamp[0], observed_wall_ns=stamp[1], **kw))

    def entry(self, nr, args, stamp, read_path, fd_object):
        need(self.pending is None, 'MISSING_SYSCALL_EXIT'); self.seen_entry = True; self.seq += 1
        op, domain, extra = None, None, {}
        if nr == 59:
            need(not self.exec_seen and read_path(args[0]) == ARGV[0], 'EXEC_SCOPE')
            self.exec_seen=True;op,domain='exec','runtime'
        elif nr in (2,257):
            address, flags = (args[0],args[1]) if nr==2 else (args[1],args[2])
            name=read_path(address);need(name in self.runtime or name in getattr(self.runtime,'absent',()), 'UNAPPROVED_RUNTIME_PATH')
            need(flags & ~(os.O_CLOEXEC | os.O_NOFOLLOW) == os.O_RDONLY, 'RUNTIME_NOT_READ_ONLY')
            op,domain='open','runtime';extra={'row':self.runtime.get(name), 'expected_absent':name in getattr(self.runtime,'absent',())}
        elif nr == 21:  # Only explicit absence checks, not arbitrary access scans.
            name=read_path(args[0]);need(name in getattr(self.runtime,'absent',()) and args[1] in (0,4), 'UNAPPROVED_ACCESS_PATH')
            op,domain='access','runtime';extra={'expected_absent':True}
        elif nr == 221:
            need(args[0] in self.fds, 'UNTRACKED_ADVICE_FD');fd_object(args[0],*self.fds[args[0]])
        elif nr in (0,1,3,8):
            fd=args[0]
            if fd in self.fds:
                domain,row=self.fds[fd];fd_object(fd,domain,row)
                op={0:'read',1:'write',3:'close',8:'seek'}[nr]
                need(not (domain=='data' and op in ('write','seek')), 'DATA_MUTATION_OR_SEEK')
                need(op!='write', 'RUNTIME_MUTATION')
                extra={'fd':fd,'row':row}
                if op=='read':extra['requested_bytes']=args[2]
            else:
                need(fd in (1,2) and nr in (1,3), 'UNTRACKED_FD')
                if nr==1:need(args[2] <= 128, 'TASK_OUTPUT_CAP')
        elif nr == 9:
            # mmap protection and FD domain: data-mmap always unsupported.
            need(not args[2] & 2 or args[3] & 2, 'SHARED_WRITABLE_MAPPING')
            if not args[3] & 0x20:
                fd=args[4];need(fd in self.fds and self.fds[fd][0]=='runtime', 'UNTRACKED_OR_DATA_MAPPING')
                fd_object(fd,*self.fds[fd])
        elif nr in FILE_META:
            if nr==5:
                fd=args[0];need(fd in self.fds or fd in (1,2), 'UNTRACKED_META_FD')
                if fd in self.fds:fd_object(fd,*self.fds[fd])
            else:
                name=read_path(args[0] if nr==6 else args[1])
                need(name=='' and nr==262 and (args[0] in self.fds or args[0] in (1,2)) and args[3] == 0x1000,
                     'UNAPPROVED_METADATA_PATH')
                if args[0] in self.fds:fd_object(args[0],*self.fds[args[0]])
        else:
            if nr not in SAFE:
                # Number/ABI only. Unknown semantics cannot classify raw arguments as FDs.
                self.rejection = {'reason':'UNSUPPORTED_SYSCALL',
                    'syscall_nr':nr if type(nr) is int and 0 <= nr < 2**32 else None,
                    'abi':'LINUX_X86_64', 'phase':'ENTRY', 'fd_domain':'UNKNOWN'}
                raise Rejected('UNSUPPORTED_SYSCALL')
        self.pending={'nr':nr,'operation':op,'domain':domain,'extra':extra}
        if op:self.emit(op,'ATTEMPT',domain,stamp,**{k:v for k,v in extra.items() if k!='row'})

    def exec_stop(self, verify):
        need(self.pending is not None and self.pending['nr']==59 and not self.exec_event, 'EXEC_EVENT_UNPAIRED')
        verify(self.runtime[ARGV[0]]);self.exec_event=True

    def exit(self, retval, error, stamp, fd_object):
        need(type(error) is int and error in (0,1) and bool(error)==(-4095<=retval<0), 'SYSCALL_RESULT')
        if self.pending is None:
            need(not self.seen_entry and not self.alignment, 'MISSING_SYSCALL_ENTRY');self.alignment=True;return
        p=self.pending;self.pending=None;op,domain=p['operation'],p['domain'];extra=p['extra']
        if not op:return
        if extra.get('expected_absent'):
            need(error == 1 and retval == -2, 'ABSENT_RUNTIME_CHANGED')
            self.emit(op,'RESULT',domain,stamp,retval=retval,success=False,confirmed_positive_bytes=False)
            return
        need(not error, 'TASK_SYSCALL_FAILED')
        out={k:v for k,v in extra.items() if k!='row'}
        if op=='exec':need(retval==0 and self.exec_event, 'EXEC_NOT_CONFIRMED')
        if op=='open':
            need(retval>=3 and retval not in self.fds, 'RUNTIME_FD_COLLISION')
            fd_object(retval,'runtime',extra['row']);self.fds[retval]=('runtime',extra['row']);out['fd']=retval
        if op=='read':
            need(0<=retval<=extra['requested_bytes'], 'READ_RESULT')
            if domain=='data':
                need(self.exec_event and not self.eof, 'READ_PHASE')
                self.reads+=1;need(self.reads<=MAX_READS, 'READ_CAP')
                self.read_bytes+=retval;need(self.read_bytes<=self.size, 'READ_EXCEEDS_INPUT')
                self.eof=retval==0
        if op=='close':
            need(retval==0, 'CLOSE_RESULT');del self.fds[extra['fd']]
            if domain=='data':self.closed=True
        self.emit(op,'RESULT',domain,stamp,retval=retval,success=True,
                  confirmed_positive_bytes=op=='read' and retval>0,**out)

    def qualify(self, returncode, output):
        need(returncode==0 and self.exec_event and self.eof and self.closed
             and not self.fds, 'INCOMPLETE_TASK_OR_FDS')
        need(self.pending is None or self.pending['nr'] in (60,231), 'INCOMPLETE_SYSCALL')
        need(len(output)<=128 and re.fullmatch(rb'[ \t]*[0-9]+[ \t]+([0-9]+)\n',output) is not None,
             'TASK_OUTPUT_FORMAT')
        count=int(output.split()[1]);need(count==self.read_bytes==self.size, 'COUNT_READ_MISMATCH')
        return count


def run_task(directory, leaf, runtime_file, permit, project=None):
    need(permit=='NEW_COUNT_BYTES_TASK_GRANTED', 'NO_TASK_AUTHORITY')
    checked_leaf(directory,leaf)
    need(sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info>=(3,11)
         and os.geteuid()!=0 and hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'), 'LINUX_RUNTIME_REQUIRED')
    need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL, 'SIGCHLD_DEFAULT_REQUIRED')
    start=time.monotonic();deadline=start+30
    runtime=None
    project=Path(project) if project else Path(__file__).resolve().parents[1]
    B.safe_parent(project/'examples')
    root=Path(tempfile.mkdtemp(prefix='count-bytes-',dir=project/'examples'))
    result={'source':SOURCE,'schema_version':1,'task':'count-bytes','status':'NOT_PASS',
        'input_path':str(Path(directory)/leaf),'events':[],'contents_collected':False,
        'time_semantics':'OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME',
        'scope':'ONE_INPUT_DIRECT_CHILD_NO_DESCENDANTS','cleanup':{},'write_tail':'UNKNOWN_NOT_HARD_DEADLINE','all_descendants_or_all_files':False}
    handle=pidfd=fd=trace=None;original=None
    try:
        fd,before,path=open_input(directory,leaf)
        runtime=load_runtime(runtime_file,identity(before))
        result['runtime_manifest_sha256']=runtime.manifest_sha256
        need(all(identity(before) != {k:x[k] for k in ('device','inode')} for x in runtime.values()), 'INPUT_RUNTIME_OVERLAP')
        verify_runtime(runtime,deadline-5,identity(before))
        need(time.monotonic()<deadline-5, 'PRELAUNCH_DEADLINE')
        handle=subprocess.Popen([sys.executable,'-I','-S','-B','-c',CHILD,str(os.getpid())],
            stdin=fd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,close_fds=True,
            cwd=root,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        os.set_blocking(handle.stdout.fileno(),False)
        pidfd=os.pidfd_open(handle.pid,0);ident=B.owned_identity(handle.pid)
        ns=os.readlink('/proc/self/ns/mnt');stop=min(deadline-5,time.monotonic()+8)
        native=TaskNative(handle,ident,ns,path,identity(before),runtime,stop)
        s=native.wait(stop);need(os.WIFSTOPPED(s) and os.WSTOPSIG(s)==signal.SIGSTOP,'INITIAL_STOP')
        native.identity_check();native.fd_object(0,'data')
        native.ptrace(B.SETOPTIONS,0,B.OPTIONS | 0x10)  # TRACEEXEC, never follow children.
        trace=TaskEvidence(ident,path,identity(before),before.st_size,runtime)
        result.update(identity=ident,file_identity=identity(before),input_size=before.st_size,mount_namespace=ns)
        while handle.returncode is None:
            native.ptrace(B.SYSCALL);s=native.wait(stop)
            if handle.returncode is not None:break
            need(os.WIFSTOPPED(s),'UNEXPECTED_WAIT')
            native.identity_check()
            if s>>16==4:
                trace.exec_stop(native.executable);continue
            need(os.WSTOPSIG(s)==signal.SIGTRAP|0x80,'UNEXPECTED_SIGNAL')
            info=B.SyscallInfo();n=native.ptrace(B.GETINFO,ctypes.sizeof(info),ctypes.addressof(info))
            need(n>=24 and info.arch==B.AUDIT_ARCH_X86_64,'SYSCALL_ABI')
            stamp=(time.monotonic_ns(),time.time_ns())
            if info.op==1:
                need(n>=80,'ENTRY_TRUNCATED');trace.entry(info.data.entry.nr,list(info.data.entry.args),stamp,native.path,native.fd_object)
            elif info.op==2:
                need(n>=33,'EXIT_TRUNCATED');trace.exit(info.data.exit.rval,info.data.exit.is_error,stamp,native.fd_object)
            else:raise Rejected('UNKNOWN_STOP')
        need(unchanged(before,os.fstat(fd)) and identity(os.lstat(path))==identity(before),'INPUT_CHANGED')
        output=os.read(handle.stdout.fileno(),129)
        result['task_reported_bytes']=trace.qualify(handle.returncode,output)
        result['observed_read_bytes']=trace.read_bytes;result['status']=STATUS
    except BaseException as exc:
        result['reason']=str(exc) if isinstance(exc,Rejected) else type(exc).__name__
        if getattr(exc,'cleanup_unknown',False):
            result['preparation_cleanup']='CLOSE_UNKNOWN'
            result['additional_close_kinds']=exc.additional_close_kinds
        if not isinstance(exc,Exception):original=(exc,exc.__traceback__)
    finally:
        result['cleanup'],interrupts=B.cleanup(handle,pidfd,fd,deadline)
        if 'fixture_fd' in result['cleanup']:result['cleanup']['input_fd']=result['cleanup'].pop('fixture_fd')
        if original is None and interrupts:original=interrupts[0]
        if handle is not None and handle.stdout is not None:
            try:handle.stdout.close();result['cleanup']['stdout']='CLOSED'
            except BaseException as exc:
                result['cleanup']['stdout']='CLOSE_UNKNOWN'
                if original is None and not isinstance(exc,Exception):original=(exc,exc.__traceback__)
    if trace is not None:
        result['events']=trace.events;result['observed_read_bytes']=trace.read_bytes
        result['exec_identity_verified']=trace.exec_event
        result['rejection']=trace.rejection
    if any(x in ('UNKNOWN','CLOSE_UNKNOWN') for x in result['cleanup'].values()):
        result['status']='NOT_PASS';result.setdefault('reason','CLEANUP_UNKNOWN')
    try:
        result['elapsed_before_write']=time.monotonic()-start
        if result['elapsed_before_write']>30:result['status']='NOT_PASS';result.setdefault('reason','TOTAL_DEADLINE')
        payload=(json.dumps(result,ensure_ascii=True,indent=2)+'\n').encode();need(len(payload)<=MAX_REPORT,'REPORT_CAP')
        with (root/'result.json').open('xb') as f:need(f.write(payload)==len(payload),'REPORT_SHORT_WRITE')
    except BaseException:
        if original:raise original[0].with_traceback(original[1])
        raise
    if original:raise original[0].with_traceback(original[1])
    return result,root/'result.json'


def main(argv=None):
    p=argparse.ArgumentParser(description='默认禁用：统计明确授权文件字节数，观察唯一自有wc任务。')
    p.add_argument('--task',choices=['count-bytes'],required=True);p.add_argument('--directory',required=True)
    p.add_argument('--input',required=True);p.add_argument('--runtime-manifest',required=True);p.add_argument('--run-once')
    a=p.parse_args(argv)
    try:
        r,path=run_task(a.directory,a.input,a.runtime_manifest,a.run_once)
        print(json.dumps({'status':r['status'],'report':str(path)},ensure_ascii=True));return 0 if r['status']==STATUS else 1
    except (Rejected,OSError,ValueError,TypeError,KeyError):
        print('任务未启动或未完成：前置或报告无效；保持UNKNOWN。',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
