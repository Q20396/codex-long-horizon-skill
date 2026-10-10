"""One-shot H8 evidence collector, not a runtime or production observer.

No child injection: forked/exec/isolated child storage is explicitly UNKNOWN.
Only successful tempfile creation and audited absolute open-attempt parents in
this process are observed. Relative dir_fd opens remain UNKNOWN. Original
arguments, results and exceptions are delegated unchanged.
No journal content, environment dump, network client or artifact upload.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

SHA = '2a5ced0f17232039fad09f8e0f077329c07a3530'
TREE = '318d4c846382c60ea13a41d3fc640bca73fb1d67'
LIMIT = 16 * 1024 * 1024  # each raw channel; encoded job output < 48 MiB


def line(kind, **fields):
    print('H8_JSON ' + json.dumps(dict(kind=kind, **fields), sort_keys=True), flush=True)


def mount_path(path):
    """Bind stat device to longest matching mountinfo entry; no file contents."""
    resolved = os.path.realpath(path)
    st = os.stat(resolved)
    mounts = []
    def unescape(s):
        return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), s)
    for row in Path('/proc/self/mountinfo').read_text().splitlines():
        left, right = row.split(' - ', 1)
        a, b = left.split(), right.split()
        target = unescape(a[4])
        if resolved == target or resolved.startswith(target.rstrip('/') + '/'):
            mounts.append((len(target), a, b, target))
    _, a, b, target = max(mounts)
    device = '%d:%d' % (os.major(st.st_dev), os.minor(st.st_dev))
    if device != a[2]:
        raise ValueError('mount device mismatch')
    return dict(resolved=resolved, st_dev=st.st_dev, device=device,
                mount_id=a[0], mountpoint=target, mount_root=unescape(a[3]),
                fstype=b[0], mount_options=a[5], super_options=b[2],
                source='/proc/self/mountinfo', local_attribute='NOT_INFERRED')


class Observer:
    def __init__(self, root, emit, describe=mount_path):
        self.root = os.path.realpath(root)
        self.emit, self.describe = emit, describe
        self.pid = os.getpid()
        self.thread = threading.get_ident()
        self.test_id = None
        self.errors = 0
        self.seen = set()

    def observe(self, kind, path, role=None):
        # Inherited hooks never instrument a child or acquire a parent lock.
        if os.getpid() != self.pid:
            return
        try:
            resolved = os.path.realpath(path)
            if not (resolved == self.root or resolved.startswith(self.root + os.sep)):
                return
            test = self.test_id if threading.get_ident() == self.thread else None
            key = (kind, resolved, test, role)
            if key in self.seen:
                return
            if len(self.seen) >= 12000:
                self.errors += 1
                return
            self.seen.add(key)
            self.emit(kind, pid=self.pid, test_id=test, role=role,
                      fs=self.describe(resolved))
        except Exception:
            # Observation failure never changes the tested operation.
            self.errors += 1

    def __enter__(self):
        self.old_temp = tempfile.mkdtemp
        self.active = True
        def mkdtemp(*args, **kwargs):
            result = self.old_temp(*args, **kwargs)
            self.observe('TEMP_CREATED', result)
            return result
        def audit(event, args):
            if self.active and os.getpid() == self.pid and event == 'open':
                try:
                    if isinstance(args[0], int):
                        return  # FD-only audit has no trustworthy pathname: UNKNOWN.
                    actual = os.fspath(args[0])
                    if not isinstance(actual, str) or not os.path.isabs(actual):
                        return  # No dir_fd in audit event: never guess its parent.
                    leaf = os.path.basename(actual)
                    role = 'owner' if leaf == '.h2-owner' else ('journal' if 'journal' in leaf else 'other')
                    # Parent exists at attempted open, not proof the open succeeds.
                    self.observe('OPEN_PARENT', os.path.dirname(actual), role)
                except Exception:
                    self.errors += 1
        # Audit hooks cannot be removed; deactivate on exit. Never replace os.open:
        # runtime_binding checks its identity in os.supports_dir_fd.
        sys.addaudithook(audit)
        tempfile.mkdtemp = mkdtemp
        return self

    def __exit__(self, *exc):
        self.active = False
        tempfile.mkdtemp = self.old_temp


def result_class(observer, emit):
    class Result(unittest.TextTestResult):
        def startTest(self, test):
            observer.test_id = test.id()
            super().startTest(test)

        def stopTest(self, test):
            super().stopTest(test)
            observer.test_id = None

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            emit('SKIP', test_id=test.id(), reason=reason)
    return Result


def suite(root, metadata):
    fd = os.open(metadata, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    write, fstat = os.write, os.fstat
    incomplete = [False]
    def emit(kind, **fields):
        raw = (json.dumps(dict(kind=kind, **fields), sort_keys=True) + '\n').encode()
        if fstat(fd).st_size + len(raw) > LIMIT:
            incomplete[0] = True
            return
        if write(fd, raw) != len(raw):
            incomplete[0] = True
    observer = Observer(root, emit)
    try:
        with observer:
            # Equivalent unittest CLI discovery and default ordering/result behavior.
            runner = unittest.TextTestRunner(verbosity=2, resultclass=result_class(observer, emit))
            program = unittest.main(module=None, argv=['unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'],
                                    testRunner=runner, exit=False)
        r = program.result
        emit('RESULT', tests=r.testsRun, failures=len(r.failures), errors=len(r.errors),
             skips=len(r.skipped), expected_failures=len(r.expectedFailures),
             unexpected_successes=len(r.unexpectedSuccesses), success=r.wasSuccessful(),
             observation_errors=observer.errors, metadata_incomplete=incomplete[0])
        return 0 if r.wasSuccessful() and not observer.errors and not incomplete[0] else 1
    finally:
        os.close(fd)


def self_test():
    # Real synthetic cases: compare default runner with observational subclass.
    with tempfile.TemporaryDirectory() as root:
        def describe(p):
            return dict(resolved=os.path.realpath(p), st_dev=os.stat(p).st_dev)
        class Cases(unittest.TestCase):
            def test_create_and_error(self):
                with tempfile.TemporaryDirectory(dir=root) as p:
                    fd = os.open(p + '/journal', os.O_CREAT | os.O_RDWR, 0o600)
                    with os.fdopen(fd, 'rb') as stream:
                        self.assertEqual(stream.read(), b'')
                with self.assertRaises(FileNotFoundError):
                    tempfile.mkdtemp(dir=root + '/absent')
            def test_skip(self):
                self.skipTest('synthetic noninterference skip')
            def test_child_is_not_injected(self):
                p = subprocess.run([sys.executable, '-I', '-S', '-c', 'import tempfile; print(tempfile.mkdtemp.__module__)'],
                                   capture_output=True, text=True, timeout=5)
                self.assertEqual((p.returncode, p.stdout.strip()), (0, 'tempfile'))
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        events = []
        emit = lambda kind, **kw: events.append(dict(kind=kind, **kw))
        obs = Observer(root, emit, describe)
        with obs:
            assert os.open in os.supports_dir_fd or sys.platform == 'win32'
            measured = unittest.TextTestRunner(stream=io.StringIO(), resultclass=result_class(obs, emit)).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        def identity(r):
            return r.testsRun, len(r.errors), len(r.failures), [(t.id(), s) for t, s in r.skipped]
        assert identity(baseline) == identity(measured)
        assert baseline.wasSuccessful() and measured.wasSuccessful()
        assert obs.errors == 0
        assert len([e for e in events if e['kind'] == 'SKIP']) == 1
        assert any(e['kind'] == 'TEMP_CREATED' for e in events)
        assert any(e['kind'] == 'OPEN_PARENT' for e in events)
        closed = [sys.executable, '-c', 'import os,time; os.close(1); os.close(2); time.sleep(5)']
        _, state = supervise(closed, root, dict(os.environ), budget=.2)
        assert state['timed_out'] and state['reap'] == 'REAPED'
        def broken_read(*args):
            raise OSError('synthetic read failure')
        _, state = supervise([sys.executable, '-c', 'print("ready",flush=True); import time; time.sleep(5)'],
                             root, dict(os.environ), budget=1, read_chunk=broken_read)
        assert state['supervisor_error'] == 'OSError' and state['reap'] == 'REAPED'
        line('NONINTERFERENCE_PASS', cases=3, skipped=1, scope='synthetic; not whole-suite equivalence')


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], timeout=10, text=True).strip()


def checkout_state(cwd):
    state = dict(sha=git(cwd, 'rev-parse', 'HEAD'), tree=git(cwd, 'rev-parse', 'HEAD^{tree}'),
                 status=git(cwd, 'status', '--porcelain'))
    subprocess.run(['git', '-C', str(cwd), 'diff', '--check'], check=True, timeout=10)
    if state != dict(sha=SHA, tree=TREE, status=''):
        raise ValueError('tested identity or clean-state mismatch')
    return state


def blob(name, raw):
    digest = hashlib.sha256(raw).hexdigest()
    for index, offset in enumerate(range(0, len(raw), 3072)):
        line('BLOB', name=name, index=index, base64=base64.b64encode(raw[offset:offset+3072]).decode())
    line('BLOB_END', name=name, bytes=len(raw), sha256=digest)


def supervise(args, cwd, env, budget=600, read_chunk=os.read):
    """Keep captured bytes and bounded failure status even after early pipe EOF."""
    output = bytearray()
    state = dict(exit_status=None, timed_out=False, output_overflow=False,
                 supervisor_error=None, reap='UNKNOWN', cleanup='NOT_STARTED')
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + budget
        while selector.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                state['timed_out'] = True
                break
            for key, _ in selector.select(min(.1, max(0, deadline-time.monotonic()))):
                chunk = read_chunk(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    available = LIMIT - len(output)
                    output.extend(chunk[:available])
                    if len(chunk) > available:
                        state['output_overflow'] = True
                        break
            if state['output_overflow']:
                break
    except Exception as exc:
        state['supervisor_error'] = type(exc).__name__
    finally:
        selector.close()
        if process is not None:
            failed = state['timed_out'] or state['output_overflow'] or state['supervisor_error']
            # Never signal a reaped leader's possibly reused process-group ID.
            if failed and process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    state['cleanup'] = 'owned group signalled; descendant reaping UNKNOWN'
                except ProcessLookupError:
                    state['cleanup'] = 'owned group absent'
                except OSError:
                    state['cleanup'] = 'UNKNOWN_SIGNAL_FAILED'
            else:
                state['cleanup'] = 'no signal; descendant state UNKNOWN'
            try:
                state['exit_status'] = process.wait(timeout=5)
                state['reap'] = 'REAPED'
            except subprocess.TimeoutExpired:
                state['reap'] = 'UNKNOWN'
            process.stdout.close()
    return bytes(output), state


def run(checkout, control):
    start = time.time()
    assert sys.version_info[:3] == (3, 14, 8) and platform.machine() == 'x86_64' and sys.platform == 'linux'
    assert os.environ.get('GITHUB_REF') == 'refs/heads/h8-linux-evidence-20261010-once'
    assert os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
    assert git(control, 'rev-parse', 'HEAD') == os.environ['GITHUB_SHA']
    pre = checkout_state(checkout)
    line('BEGIN', control_sha=git(control, 'rev-parse', 'HEAD'), control_tree=git(control, 'rev-parse', 'HEAD^{tree}'),
         tested=pre, runtime=sys.version, os=platform.system(), arch=platform.machine(),
         image=os.environ.get('ImageOS'), image_version=os.environ.get('ImageVersion'),
         run=os.environ.get('GITHUB_RUN_ID'), job=os.environ.get('GITHUB_JOB'), start=start)
    with tempfile.TemporaryDirectory(prefix='h8-evidence-', dir=os.environ['RUNNER_TEMP']) as private:
        root = Path(private) / 'tests'; root.mkdir(mode=0o700)
        for role, path in [('runner_root', '/'), ('checkout', checkout), ('test_root', root)]:
            line('FS_ROOT', role=role, **mount_path(path))
        metadata = Path(private) / 'metadata.jsonl'
        env = dict(os.environ, TMPDIR=str(root), PYTHONDONTWRITEBYTECODE='1')
        # Never pass explicitly named credential variables; no environment dump.
        for name in list(env):
            if any(word in name.upper() for word in ('TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL')):
                env.pop(name)
        args = [sys.executable, '-B', str(Path(__file__).resolve()), '--suite', str(root), str(metadata)]
        line('COMMAND', argv=['python3', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'],
             mode='equivalent unittest.main runner; extra metadata only', timeout_seconds=600,
             child_coverage='fork/exec/-I/-S and non-Python child paths UNKNOWN; no injection',
             path_coverage='TEMP_CREATED is successful creation; OPEN_PARENT is existing parent at absolute open ATTEMPT, not successful effect; relative dir_fd paths UNKNOWN')
        if time.time() - start > 120:
            raise TimeoutError('metadata budget exceeded')
        output, supervision = supervise(args, checkout, env)
        raw_meta = metadata.read_bytes() if metadata.exists() else b''
        blob('verbose_combined', bytes(output[:LIMIT]))
        blob('metadata', raw_meta[:LIMIT])
        parse_error = None
        try:
            records = [json.loads(s) for s in raw_meta.splitlines()]
        except (ValueError, UnicodeError):
            records = []
            parse_error = 'INVALID_METADATA'
        results = [r for r in records if r['kind'] == 'RESULT']
        skips = [r for r in records if r['kind'] == 'SKIP']
        complete = (not supervision['timed_out'] and not supervision['output_overflow']
                    and not supervision['supervisor_error'] and supervision['reap'] == 'REAPED'
                    and not parse_error and len(raw_meta) <= LIMIT and len(results) == 1
                    and len(skips) == results[0]['skips'] and not results[0]['metadata_incomplete']
                    and results[0]['observation_errors'] == 0)
        try:
            post = checkout_state(checkout)
        except Exception as exc:
            post = dict(error=type(exc).__name__)
            complete = False
        line('END', **supervision, parse_error=parse_error,
             evidence='COMPLETE_CHANNELS' if complete else 'EVIDENCE_INCOMPLETE', post=post,
             result=results, structured_skips=len(skips),
             remaining_test_entries=len(list(root.iterdir())), end=time.time(), elapsed=time.time()-start)
        return 0 if complete and supervision['exit_status'] == 0 else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif len(sys.argv) == 4 and sys.argv[1] == '--suite':
        sys.exit(suite(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) == 4 and sys.argv[1] == '--run':
        sys.exit(run(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()))
    else:
        raise SystemExit('invalid H8 collector invocation')
