"""H3 contracts: real synthetic files; low-level faults only where unavoidable."""
from dataclasses import replace
import importlib
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
DIGEST_A = '559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd'
DIGEST_B = 'df7e70e5021544f4834bbee64a9e3789febc4be81470df629cad6ddb03320a5c'


class IndependentTargetRealityTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        # Missing capability is an assertion RED, not an accidental import error.
        self.assertIsNotNone(importlib.util.find_spec('independent_target_reality'),
                             'independent local artifact collector missing')
        self.m = importlib.import_module('independent_target_reality')
        self.tmp = tempfile.TemporaryDirectory(prefix='h3-collector-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def request(self, target='artifact', **changes):
        values = dict(root=self.root, target=target, expected_size=1,
                      expected_digest=DIGEST_A, attempt_ref='ref:attempt-1',
                      scope_ref='ref:one-local-file', max_bytes=32)
        values.update(changes)
        return self.m.bind_request(**values)

    def observe(self, request=None):
        return self.m.collect(request or self.request())

    def test_actual_bytes_match_without_authorship_or_retry_authority(self):
        # Break: return expectation rather than bytes, or conflate match with cause.
        (self.root / 'artifact').write_bytes(b'A')
        request = self.request()
        result = self.observe(request)
        self.assertEqual((result.status, result.observed_size, result.observed_digest,
                          result.expectation_match, result.process_authorship),
                         ('OBSERVED', 1, DIGEST_A, 'MATCH', 'NOT_PROVEN'))
        self.assertEqual(result.expected_digest, DIGEST_A)
        self.assertTrue(self.m.matches_request(request, result))
        self.assertIsNotNone(result.file_identity)
        self.assertFalse(result.retry_authorized)

    def test_actual_mismatch_retains_independent_digest(self):
        # Break: use expected digest as actual or map mismatch to NOT_APPLIED.
        (self.root / 'artifact').write_bytes(b'B')
        result = self.observe()
        self.assertEqual((result.status, result.observed_digest, result.expected_digest,
                          result.expectation_match), ('OBSERVED', DIGEST_B, DIGEST_A, 'MISMATCH'))
        self.assertEqual(result.process_authorship, 'NOT_PROVEN')
        self.assertFalse(result.retry_authorized)

    def test_missing_file_is_unknown(self):
        # Break: interpret absence as failure/not applied or synthesize digest.
        result = self.observe()
        self.assertEqual((result.status, result.expectation_match, result.observed_digest),
                         ('UNKNOWN', 'UNKNOWN', None))
        self.assertFalse(result.retry_authorized)

    def test_nested_regular_file_and_exact_read_limit(self):
        # Break: stop at bound without testing EOF, or refuse bounded nesting.
        (self.root / 'dir').mkdir()
        (self.root / 'dir/file').write_bytes(b'A')
        self.assertEqual(self.observe(self.request('dir/file', max_bytes=1)).status, 'OBSERVED')
        (self.root / 'dir/file').write_bytes(b'AB')
        result = self.observe(self.request('dir/file', max_bytes=1))
        self.assertEqual((result.status, result.reason, result.observed_digest),
                         ('UNKNOWN', 'READ_LIMIT_EXCEEDED', None))

    def test_path_escape_and_noncanonical_targets_rejected(self):
        # Break: normalize traversal into an admitted path or accept absolute input.
        for target in ('../outside', '/outside', 'a/../artifact', './artifact',
                       'a//file', 'a/', '', 'a\x00b', '\ud800'):
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, '^INVALID_OBSERVATION_REQUEST$'):
                    self.request(target)

    def test_final_and_parent_symlink_do_not_read_outside(self):
        # Break: follow a target or parent symlink after a path-only check.
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'file').write_bytes(b'SYNTHETIC_PRIVATE_CONTENT')
        (self.root / 'final').symlink_to(outside / 'file')
        (self.root / 'parent').symlink_to(outside, target_is_directory=True)
        for target in ('final', 'parent/file'):
            result = self.observe(self.request(target))
            self.assertEqual(result.status, 'UNKNOWN')
            self.assertIsNone(result.observed_digest)
            self.assertNotIn('SYNTHETIC_PRIVATE_CONTENT', repr(result))

    def test_root_symlink_nonprivate_and_replaced_root_rejected(self):
        # Break: follow root symlink, admit shared root, or silently reopen new root.
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, '^ROOT_BOUNDARY_UNAVAILABLE$'):
            self.request(root=alias)
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, '^ROOT_BOUNDARY_UNAVAILABLE$'):
            self.request()
        self.root.chmod(0o700)
        request = self.request()
        moved = self.root.with_name(self.root.name + '-old')
        self.root.rename(moved)
        self.addCleanup(lambda: moved.rename(self.root))
        self.root.mkdir(mode=0o700)
        self.addCleanup(self.root.rmdir)
        self.assertEqual(self.observe(request).status, 'UNKNOWN')

    def test_fifo_socket_directory_and_device_are_not_read(self):
        # Break: block opening FIFO or read a device/nonregular descriptor.
        os.mkfifo(self.root / 'fifo')
        endpoint = socket.socket(socket.AF_UNIX)
        self.addCleanup(endpoint.close)
        endpoint.bind(str(self.root / 'socket'))
        (self.root / 'directory').mkdir()
        for target in ('fifo', 'socket', 'directory'):
            request = self.request(target)
            with patch.object(self.m.os, 'read', side_effect=AssertionError('special file read')):
                self.assertEqual(self.observe(request).status, 'UNKNOWN')
        # Creating a device requires privileged mknod; substitute only its stat.
        (self.root / 'artifact').write_bytes(b'A')
        original = os.fstat
        def device(fd):
            value = original(fd)
            if stat.S_ISREG(value.st_mode):
                fields = list(value)
                fields[0] = stat.S_IFCHR | 0o600
                return os.stat_result(fields)
            return value
        request = self.request()
        with patch.object(self.m.os, 'fstat', side_effect=device), \
                patch.object(self.m.os, 'read', side_effect=AssertionError('device read')):
            self.assertEqual(self.observe(request).status, 'UNKNOWN')

    def test_denied_open_and_read_errors_are_sanitized_unknown(self):
        # Break: propagate exception path/content, or allow failed read to match.
        (self.root / 'artifact').write_bytes(b'A')
        request = self.request()
        original = os.open
        def denied(path, *args, **kwargs):
            if path == 'artifact':
                raise PermissionError(str(self.root) + ' SYNTHETIC_PRIVATE_CONTENT')
            return original(path, *args, **kwargs)
        for operation, fault in (('open', denied), ('read', PermissionError(str(self.root)))):
            with patch.object(self.m.os, operation, side_effect=fault):
                result = self.observe(request)
            self.assertEqual(result.status, 'UNKNOWN')
            self.assertNotIn(str(self.root), repr(result))
            self.assertNotIn('SYNTHETIC_PRIVATE_CONTENT', repr(result))

    def test_same_descriptor_mutation_is_unknown(self):
        # Break: hash while ignoring post-read metadata on the opened descriptor.
        path = self.root / 'artifact'
        path.write_bytes(b'A')
        request = self.request()
        original = os.read
        changed = False
        def mutate(fd, size):
            nonlocal changed
            value = original(fd, size)
            if not changed:
                changed = True
                path.write_bytes(b'BB')
            return value
        with patch.object(self.m.os, 'read', side_effect=mutate):
            result = self.observe(request)
        self.assertEqual((result.status, result.observed_digest), ('UNKNOWN', None))

    def test_final_and_parent_path_replacement_is_unknown(self):
        # Break: validate opened fd but ignore replacement at the requested path.
        for parent in (False, True):
            with self.subTest(parent=parent):
                directory = self.root / ('parent' if parent else 'flat')
                directory.mkdir()
                path = directory / 'artifact'
                path.write_bytes(b'A')
                request = self.request(directory.name + '/artifact')
                original = os.read
                changed = False
                def replace_path(fd, size):
                    nonlocal changed
                    value = original(fd, size)
                    if not changed:
                        changed = True
                        if parent:
                            directory.rename(self.root / 'old-parent')
                            directory.mkdir()
                        else:
                            path.unlink()
                        path.write_bytes(b'A')
                    return value
                with patch.object(self.m.os, 'read', side_effect=replace_path):
                    self.assertEqual(self.observe(request).status, 'UNKNOWN')

    def test_binding_consumer_rejects_wrong_root_target_attempt_and_old_result(self):
        # Break: reuse previous-request observation as current evidence.
        (self.root / 'artifact').write_bytes(b'A')
        request = self.request()
        result = self.observe(request)
        self.assertTrue(self.m.matches_request(request, result))
        for changes in ({'root_ref': '0' * 64}, {'root_identity': (0, 0)},
                        {'target_ref': '0' * 64}, {'attempt_ref': 'ref:other'},
                        {'request_ref': 'ref:old'}, {'scope_ref': 'ref:other'},
                        {'expected_digest': DIGEST_B}, {'max_bytes': 1}):
            with self.subTest(changes=changes):
                self.assertFalse(self.m.matches_request(request, replace(result, **changes)))
        self.assertFalse(self.m.matches_request(self.request(), result))
        # A modified raw target must not retain the old target label and make
        # matching bytes from another file appear bound to this request.
        (self.root / 'other').write_bytes(b'A')
        self.assertFalse(self.m.matches_request(replace(request, target='other'), result))
        with self.assertRaisesRegex(ValueError, '^INVALID_OBSERVATION_REQUEST$'):
            self.observe(replace(request, target='other'))
        with self.assertRaisesRegex(ValueError, '^INVALID_OBSERVATION_REQUEST$'):
            self.observe(replace(request, root_ref='0' * 64))
        # Stateless correlation is not a global replay defense or authentication.
        self.assertTrue(self.m.matches_request(request, result))

    def test_finite_actual_read_when_initial_stat_understates_size(self):
        # Break: read to unlimited EOF or rely exclusively on initial st_size.
        (self.root / 'artifact').write_bytes(b'B' * 256)
        request = self.request(max_bytes=2)
        original_stat, original_read = os.fstat, os.read
        consumed = []
        def understated(fd):
            value = original_stat(fd)
            if stat.S_ISREG(value.st_mode):
                fields = list(value)
                fields[6] = 1
                return os.stat_result(fields)
            return value
        def bounded(fd, size):
            value = original_read(fd, size)
            consumed.append(len(value))
            return value
        with patch.object(self.m.os, 'fstat', side_effect=understated), \
                patch.object(self.m.os, 'read', side_effect=bounded):
            result = self.observe(request)
        self.assertEqual(result.status, 'UNKNOWN')
        self.assertLessEqual(sum(consumed), 3)

    def test_descriptors_close_after_success_and_read_exception(self):
        # Break: leak root, intermediate, or file fds through either exit path.
        (self.root / 'dir').mkdir()
        (self.root / 'dir/file').write_bytes(b'A')
        request = self.request('dir/file')
        original = os.open
        for fail in (False, True):
            handles = []
            def opened(*args, **kwargs):
                fd = original(*args, **kwargs)
                handles.append(fd)
                return fd
            with patch.object(self.m.os, 'open', side_effect=opened):
                if fail:
                    with patch.object(self.m.os, 'read', side_effect=OSError('synthetic')):
                        self.assertEqual(self.observe(request).status, 'UNKNOWN')
                else:
                    self.assertEqual(self.observe(request).status, 'OBSERVED')
            for fd in handles:
                with self.assertRaises(OSError):
                    os.fstat(fd)
        # A close error must not abandon the remaining descriptors or expose
        # host error text. The substitute closes the real fd before reporting
        # uncertainty; cleanup of an OS-failed close itself cannot be guaranteed.
        handles = []
        original_close = os.close
        uncertain = True
        def cleanup(fd):
            try:
                original_close(fd)
            except OSError:
                pass
        def uncertain_close(fd):
            nonlocal uncertain
            original_close(fd)
            if uncertain:
                uncertain = False
                raise OSError(str(self.root) + ' synthetic cleanup uncertainty')
        def opened_for_cleanup(*args, **kwargs):
            fd = original(*args, **kwargs)
            handles.append(fd)
            self.addCleanup(cleanup, fd)
            return fd
        with patch.object(self.m.os, 'open', side_effect=opened_for_cleanup), \
                patch.object(self.m.os, 'close', side_effect=uncertain_close):
            result = self.observe(request)
        self.assertEqual(result.status, 'UNKNOWN')
        self.assertNotIn(str(self.root), repr(result))
        for fd in handles:
            with self.assertRaises(OSError):
                os.fstat(fd)
        handles, uncertain = [], True
        with patch.object(self.m.os, 'open', side_effect=opened_for_cleanup), \
                patch.object(self.m.os, 'close', side_effect=uncertain_close):
            with self.assertRaisesRegex(ValueError, '^ROOT_BOUNDARY_UNAVAILABLE$'):
                self.request('dir/file')
        for fd in handles:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_unsupported_primitives_fail_closed(self):
        # Break: fallback to ordinary path open when secure primitive unavailable.
        (self.root / 'artifact').write_bytes(b'A')
        request = self.request()
        with patch.object(self.m.os, 'O_NOFOLLOW', 0):
            result = self.observe(request)
        self.assertEqual((result.status, result.reason, result.observed_digest),
                         ('UNSUPPORTED', 'REQUIRED_PRIMITIVES_UNAVAILABLE', None))

    def test_collector_only_reads_and_export_omits_paths_and_contents(self):
        # Break: write/reconcile/spawn on collect or leak raw data/path in exports.
        path = self.root / 'artifact'
        path.write_bytes(b'SYNTHETIC_PRIVATE_CONTENT')
        request = self.request(expected_size=25)
        before = (path.read_bytes(), path.stat().st_mtime_ns, tuple(self.root.iterdir()))
        with patch.object(self.m.os, 'write', side_effect=AssertionError('collector write')), \
                patch.object(subprocess, 'Popen', side_effect=AssertionError('collector process')):
            result = self.observe(request)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns, tuple(self.root.iterdir())), before)
        self.assertNotIn(str(self.root), repr(result) + repr(request))
        self.assertNotIn('SYNTHETIC_PRIVATE_CONTENT', repr(result) + repr(request))

    def test_invalid_limit_and_expectation_are_rejected(self):
        # Break: allow infinite/unbounded reads or malformed trusted expectations.
        for changes in ({'max_bytes': 0}, {'max_bytes': True}, {'max_bytes': 2**64},
                        {'expected_size': -1}, {'expected_digest': 'not-a-digest'},
                        {'attempt_ref': str(self.root)}, {'scope_ref': ''}):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, '^INVALID_OBSERVATION_REQUEST$'):
                    self.request(**changes)

    def test_import_is_inactive(self):
        # Break: collect or launch resources at module import.
        code = '''
import sys, os, pathlib, subprocess, threading, dataclasses, hashlib, uuid
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs): raise AssertionError('active import')
os.open = os.read = os.write = forbidden
pathlib.Path.open = forbidden
subprocess.Popen = threading.Thread.start = forbidden
import independent_target_reality
print('INACTIVE')
'''
        out = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(SCRIPTS)],
                             capture_output=True, timeout=5)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, b'INACTIVE'))


if __name__ == '__main__':
    unittest.main()
