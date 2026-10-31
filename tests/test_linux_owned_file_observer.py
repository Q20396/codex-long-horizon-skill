"""Pure syscall metadata fixtures and mocked cleanup; never start a monitor."""
import ctypes
import errno
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1]/'scripts/linux_owned_file_observer.py'
SPEC = importlib.util.spec_from_file_location('linux_owned', SOURCE)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ident = {'pid': 41, 'start_ticks': 101}
        self.file, self.missing = '/owned/synthetic.txt', '/owned/absent.txt'
        self.obj = {'device': 7, 'inode': 19}
        self.e = M.Evidence(self.ident, self.file, self.missing, self.obj)
        self.tick = 0

    def stamp(self):
        self.tick += 1
        return self.tick, self.tick + 1000

    def pair(self, nr, args, ret, path=None, error=0, obj=None):
        identity = lambda fd: self.obj if obj is None else obj
        self.e.entry(nr, args, self.stamp(), lambda addr: path, identity)
        self.e.exit(ret, error, self.stamp(), identity)

    def positive(self, read_ret=1, write_ret=1):
        nofollow = M.os.O_NOFOLLOW
        self.pair(257, [-100, 1, nofollow, 0, 0, 0], 3, self.file)
        self.pair(0, [3, 123456, 1, 0, 0, 0], read_ret)
        self.pair(3, [3, 0, 0, 0, 0, 0], 0)
        self.pair(2, [1, nofollow|M.os.O_WRONLY, 0, 0, 0, 0], 3, self.file)
        self.pair(1, [3, 987654, 1, 0, 0, 0], write_ret)
        self.pair(3, [3, 0, 0, 0, 0, 0], 0)
        self.pair(257, [-100, 1, nofollow, 0, 0, 0], -errno.ENOENT, self.missing, 1)

    def test_selected_complete_matrix_and_fd_reuse(self):
        self.positive()
        self.e.qualify(0)
        self.assertEqual(len(self.e.events), 14)
        self.assertEqual(self.e.events[1]['generation'], 1)
        self.assertEqual(self.e.events[7]['generation'], 2)
        self.assertTrue(self.e.events[3]['confirmed_positive_bytes'])
        self.assertTrue(self.e.events[9]['confirmed_positive_bytes'])
        self.assertEqual(self.e.events[-1]['errno'], errno.ENOENT)
        self.assertFalse(self.e.events[-1]['success'])
        self.assertNotIn('buffer', json.dumps(self.e.events))

    def test_zero_bytes_is_not_actual_read_or_write_confirmation(self):
        self.positive(read_ret=0)
        self.assertFalse(self.e.events[3]['confirmed_positive_bytes'])
        with self.assertRaisesRegex(M.Rejected, 'READ_WRITE_NOT_CONFIRMED'):
            self.e.qualify(0)

    def test_attempt_is_not_success(self):
        self.pair(2, [1, M.os.O_NOFOLLOW, 0, 0, 0, 0], -errno.EACCES, self.file, 1)
        self.assertEqual(self.e.events[0]['phase'], 'ATTEMPT')
        self.assertNotIn('success', self.e.events[0])
        self.assertFalse(self.e.events[1]['success'])
        self.assertEqual(self.e.events[1]['errno'], errno.EACCES)

    def test_relative_or_outside_path_rejected_without_persistence(self):
        for path in ('relative', '/UNAPPROVED', '/owned/../UNAPPROVED', ''):
            with self.assertRaisesRegex(M.Rejected, 'OUT_OF_SCOPE_OR_RELATIVE_PATH') as caught:
                self.e.entry(2, [1, M.os.O_NOFOLLOW, 0, 0, 0, 0], self.stamp(),
                             lambda addr: path, lambda fd: self.obj)
            self.assertNotIn('UNAPPROVED', str(caught.exception))
            self.assertEqual(self.e.events, [])

    def test_missing_nofollow_rejected(self):
        with self.assertRaisesRegex(M.Rejected, 'NOFOLLOW_REQUIRED'):
            self.e.entry(2, [1, 0, 0, 0, 0, 0], self.stamp(),
                         lambda addr: self.file, lambda fd: self.obj)

    def test_fd_identity_mismatch_does_not_claim_success(self):
        with self.assertRaisesRegex(M.Rejected, 'OPEN_OBJECT_CHANGED'):
            self.pair(2, [1, M.os.O_NOFOLLOW, 0, 0, 0, 0], 3, self.file,
                      obj={'device': 8, 'inode': 19})
        self.assertEqual(len(self.e.events), 1)
        self.assertEqual(self.e.events[0]['phase'], 'ATTEMPT')

    def test_unknown_fd_fails_and_stdout_not_misidentified(self):
        with self.assertRaisesRegex(M.Rejected, 'UNTRACKED_FILE_DESCRIPTOR'):
            self.e.entry(0, [7, 111, 1, 0, 0, 0], self.stamp(), None, None)
        self.pair(1, [1, 111, 1, 0, 0, 0], 1)
        self.assertEqual(self.e.events, [])

    def test_fd_object_checked_before_read(self):
        self.pair(2, [1, M.os.O_NOFOLLOW, 0, 0, 0, 0], 3, self.file)
        with self.assertRaisesRegex(M.Rejected, 'FD_OBJECT_CHANGED'):
            self.e.entry(0, [3, 111, 1, 0, 0, 0], self.stamp(), None,
                         lambda fd: {'device': 7, 'inode': 20})

    def test_missing_exit_or_entry_is_not_silently_accepted(self):
        self.e.entry(39, [0]*6, self.stamp(), None, None)
        with self.assertRaisesRegex(M.Rejected, 'MISSING_SYSCALL_EXIT'):
            self.e.entry(39, [0]*6, self.stamp(), None, None)
        self.e.exit(41, 0, self.stamp(), None)
        with self.assertRaisesRegex(M.Rejected, 'MISSING_SYSCALL_ENTRY'):
            self.e.exit(41, 0, self.stamp(), None)

    def test_one_startup_unpaired_exit_is_explicitly_limited(self):
        self.e.exit(0, 0, self.stamp(), None)
        self.assertTrue(self.e.initial_unpaired_exit)
        with self.assertRaisesRegex(M.Rejected, 'MISSING_SYSCALL_ENTRY'):
            self.e.exit(0, 0, self.stamp(), None)

    def test_clone_namespace_and_unsupported_io_stop_before_resume(self):
        for nr in (56, 57, 58, 59, 308, 435, 437, 19, 20, 32, 72):
            with self.assertRaisesRegex(M.Rejected, 'UNSUPPORTED_OPERATION'):
                self.e.entry(nr, [0]*6, self.stamp(), None, None)
        with self.assertRaisesRegex(M.Rejected, 'UNSUPPORTED_FILE_MAPPING'):
            self.e.entry(9, [0]*6, self.stamp(), None, None)

    def test_invalid_result_count_and_error_state_rejected(self):
        self.pair(2, [1, M.os.O_NOFOLLOW, 0, 0, 0, 0], 3, self.file)
        self.e.entry(0, [3, 111, 1, 0, 0, 0], self.stamp(), None, lambda fd: self.obj)
        with self.assertRaisesRegex(M.Rejected, 'BYTE_COUNT_SHAPE'):
            self.e.exit(2, 0, self.stamp(), lambda fd: self.obj)

    def test_matrix_incomplete_or_child_failed_stays_not_pass(self):
        with self.assertRaises(M.Rejected): self.e.qualify(0)
        self.positive()
        with self.assertRaisesRegex(M.Rejected, 'CHILD_EXIT_OR_OPEN_FDS'):
            self.e.qualify(1)

    def test_event_cap_does_not_trim_into_success(self):
        self.e.events = [{}] * M.MAX_EVENTS
        with self.assertRaisesRegex(M.Rejected, 'EVENT_CAP'):
            self.e.emit('open', 'ATTEMPT', self.file, self.stamp())

    def test_struct_layout_and_proc_start_parser(self):
        self.assertEqual(ctypes.sizeof(M.SyscallInfo), 88)
        self.assertEqual(M.SyscallInfo.data.offset, 24)
        raw = '41 (name with ) marker) ' + ' '.join(['S']+['0']*18+['101'])
        self.assertEqual(M.proc_start_ticks(raw), 101)
        with self.assertRaises(M.Rejected): M.proc_start_ticks('invalid')

    def test_import_and_default_auth_never_spawn_or_load_tracer(self):
        with patch.object(M.subprocess, 'Popen') as spawn, patch.object(M.ctypes, 'CDLL') as load:
            with self.assertRaisesRegex(M.Rejected, 'NO_NATIVE_AUTHORITY'):
                M.run_owned(Path('/UNUSED'))
            with patch.object(M.sys, 'platform', 'darwin'):
                with self.assertRaisesRegex(M.Rejected, 'LINUX_X86_64_REQUIRED'):
                    M.run_owned(Path('/UNUSED'), 'NEW_SINGLE_RUN_GRANTED')
            spawn.assert_not_called(); load.assert_not_called()

    def test_cleanup_uses_original_resources_and_one_signal(self):
        handle = Mock(returncode=None); handle.wait.return_value = -9
        with patch.object(M.time, 'monotonic', return_value=1), \
             patch.object(M.signal, 'pidfd_send_signal', create=True) as kill, \
             patch.object(M.os, 'close') as close:
            receipt, interrupts = M.cleanup(handle, 71, 72, 10)
        kill.assert_called_once_with(71, M.signal.SIGKILL)
        handle.kill.assert_not_called(); handle.wait.assert_called_once()
        self.assertEqual([x.args[0] for x in close.call_args_list], [71, 72])
        self.assertEqual(receipt['returncode'], -9)
        self.assertEqual(interrupts, [])

    def test_cleanup_deadline_does_not_send_late_signal(self):
        handle = Mock(returncode=None)
        with patch.object(M.time, 'monotonic', return_value=11), \
             patch.object(M.signal, 'pidfd_send_signal', create=True) as kill:
            receipt, interrupts = M.cleanup(handle, None, None, 10)
        handle.kill.assert_not_called(); handle.wait.assert_not_called()
        kill.assert_not_called()
        self.assertEqual(receipt['child_state'], 'UNKNOWN')

    def test_native_deadline_stops_before_ptrace_or_proc_reads(self):
        native = object.__new__(M.Native)
        native.deadline = 0
        native.libc = Mock()
        with patch.object(M.time, 'monotonic', return_value=1), \
             patch.object(M.os, 'readlink') as readlink:
            for call in (lambda: native.ptrace(M.SYSCALL), native.identity_check,
                         lambda: native.fd_identity(3)):
                with self.assertRaisesRegex(M.Rejected, 'OBSERVATION_DEADLINE'): call()
            native.libc.ptrace.assert_not_called()
            readlink.assert_not_called()

    def test_stopped_fd_path_must_be_exact_before_stat(self):
        native = object.__new__(M.Native)
        native.deadline = 10
        native.handle = Mock(pid=41)
        native.fixture = self.file
        with patch.object(M.time, 'monotonic', return_value=1), \
             patch.object(M.os, 'readlink', return_value='/UNAPPROVED'), \
             patch.object(M.os, 'stat') as stat:
            with self.assertRaisesRegex(M.Rejected, 'FD_RESOLVED_PATH_UNKNOWN') as caught:
                native.fd_identity(3)
            self.assertNotIn('UNAPPROVED', str(caught.exception))
            stat.assert_not_called()

    def test_cleanup_interrupt_keeps_fd_close_attempts(self):
        handle = Mock(returncode=0); handle.wait.side_effect = KeyboardInterrupt('synthetic')
        with patch.object(M.os, 'close') as close:
            receipt, interrupts = M.cleanup(handle, 71, 72, 10)
        self.assertEqual(close.call_count, 2)
        self.assertEqual(receipt['child_state'], 'UNKNOWN')
        self.assertIsInstance(interrupts[0][0], KeyboardInterrupt)

    def test_saved_interrupt_not_overwritten_by_report_failure(self):
        error = KeyboardInterrupt('original')
        with patch.object(M.time, 'monotonic', side_effect=RuntimeError('secondary')):
            with self.assertRaises(KeyboardInterrupt) as caught:
                M.save_result({'status': 'NOT_PASS'}, Path('/UNUSED'), 0, (error, None))
        self.assertIs(caught.exception, error)

    def test_synthetic_report_exclusive_and_bounded(self):
        with tempfile.TemporaryDirectory(prefix='owned-fixture-only-') as directory:
            result = {'status': 'NOT_PASS', 'events': []}
            with patch.object(M.time, 'monotonic', return_value=1):
                M.save_result(result, Path(directory), 0)
                with self.assertRaises(FileExistsError): M.save_result(result, Path(directory), 0)
            self.assertLess((Path(directory)/'result.json').stat().st_size, M.MAX_BYTES)
        with patch.object(M.time, 'monotonic', return_value=1):
            with self.assertRaisesRegex(M.Rejected, 'REPORT_CAP'):
                M.save_result({'status': 'NOT_PASS', 'data': 'x'*M.MAX_BYTES}, Path('/UNUSED'), 0)


if __name__ == '__main__':
    unittest.main()
