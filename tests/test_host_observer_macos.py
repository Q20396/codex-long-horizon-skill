"""One real macOS NOTE_EXEC path; doubles test rejection, never native PASS."""
from contextlib import contextmanager
from dataclasses import asdict, replace
import importlib
import json
import os
from pathlib import Path
import select
import signal
import sys
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'
NATIVE = sys.platform == 'darwin' and hasattr(select, 'kqueue')


@contextmanager
def controlled_child():
    """Child cannot exec until released; bounded cleanup reaps even on failure."""
    read_fd, write_fd = os.pipe()
    try:
        pid = os.fork()
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        raise
    if pid == 0:
        try:
            os.close(write_fd)
            if os.read(read_fd, 1) != b'x':
                os._exit(1)
            os.close(read_fd)
            os.execv(sys.executable, [sys.executable, '-c', 'raise SystemExit(0)'])
        except BaseException:
            os._exit(2)
    os.close(read_fd)
    try:
        yield pid, lambda: os.write(write_fd, b'x')
    finally:
        failed = sys.exc_info()[0] is not None
        os.close(write_fd)
        deadline = time.monotonic() + 3
        killed = False
        while True:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                if (status != 0 or killed) and not failed:
                    raise AssertionError('controlled child failed')
                break
            if time.monotonic() >= deadline:
                if killed:
                    raise AssertionError('controlled child could not be reaped within bound')
                os.kill(pid, signal.SIGKILL)
                killed = True
                deadline = time.monotonic() + 3
            time.sleep(0.01)


@unittest.skipUnless(NATIVE, 'NOT_RUN_PLATFORM_RESTRICTED: macOS kqueue required')
class MacOSExecObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('host_observer_macos', 'host_observer', 'critical_execution_trace',
                     'runtime_safety_envelope', 'security_authority_chain')
        cls.saved_modules = {name: sys.modules.get(name) for name in cls.names}
        sys.path.insert(0, str(SCRIPTS))
        cls.c = importlib.import_module('critical_execution_trace')
        cls.h = importlib.import_module('host_observer')
        cls.m = (importlib.import_module('host_observer_macos')
                 if (SCRIPTS / 'host_observer_macos.py').exists() else None)

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def observer(self, session='native-session'):
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        observer = self.m.MacOSExecObserver(session)
        self.addCleanup(observer.close)
        return observer

    def ingestor(self, **kwargs):
        return self.h.HostObservationIngestor('macos-kqueue-proc',
            'ref:macos-kqueue-evfilt-proc-note-exec', trace=self.trace, **kwargs)

    def setUp(self):
        self.trace = self.c.CriticalTrace('trace', 'install')

    def test_native_exec_enters_ingestor_cet_and_chain_with_explicit_only_links(self):
        # Break caught: replacing native NOTE_EXEC with parent-launch knowledge,
        # losing PID/session/sequence, fabricating coverage or granting authority.
        observer = self.observer()
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run',
                                      'action', None, 'trusted', None, 'runtime')
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
        ingestor = self.ingestor(known_actions={'ref:action': context}, chain=chain, actor=actor)
        rse = self.c.rse
        action = rse.ActionRequest('action', 'run', 'task', rse.ActionClass.EXECUTE_PROCESS,
            'ref:opaque-program', 'trusted', 'runtime', rse.DataClass.PUBLIC, None,
            'process.execute', 'native-test')
        receipt = replace(rse._receipt(action, rse.PolicyDecision('REQUIRE_AUTHORIZATION',
            'NO_AUTHORIZATION')), execution_state='UNKNOWN_OUTCOME', reconciliation_state='STILL_UNKNOWN')
        before = asdict(receipt)
        broker = rse.CapabilityBroker()
        for sequence, ref, correlation in ((1, 'ref:action', 'CORRELATED'),
                                           (2, None, 'UNCORRELATED'),
                                           (3, 'ref:unknown', 'UNRESOLVED_LINK')):
            with controlled_child() as (pid, release):
                with patch.object(os, 'environ', NoEnvironment()), \
                     patch('builtins.open', side_effect=AssertionError('metadata read')):
                    observer.register(pid, action_id_ref=ref)
                release()
                with patch.object(os, 'environ', NoEnvironment()), \
                     patch('builtins.open', side_effect=AssertionError('metadata read')):
                    observation = observer.wait_for_exec(3)
                self.assertIsNotNone(observation, 'real registered NOTE_EXEC was not observed')
                self.assertEqual((observation.event_class, observation.coverage,
                                  observation.session_id, observation.sequence, observation.target_ref),
                    ('PROCESS_EXEC', 'PARTIAL', 'native-session', sequence, 'ref:pid-' + str(pid)))
                self.assertEqual(observation.action_id_ref, ref)
                result = ingestor.ingest(observation)
                self.assertTrue(result.accepted)
                self.assertEqual(result.correlation_status, correlation)
                self.assertEqual(result.effective_coverage, 'PARTIAL')
                self.assertEqual(ingestor.ingest(observation).reason, 'IDEMPOTENT_DUPLICATE')
                replay = ingestor.ingest(replace(observation, observation_id='replay-' + str(sequence),
                                                sequence=sequence))
                self.assertEqual((replay.accepted, replay.reason),
                                 (False, 'OBSERVATION_SEQUENCE_INVALID'))
                bad = self.h.HostObservationIngestor('other', 'ref:wrong',
                    trace=self.c.CriticalTrace('trace', 'install')).ingest(observation)
                self.assertEqual((bad.accepted, bad.reason), (False, 'UNTRUSTED_OBSERVER'))
                event = self.trace.events()[-1]
                self.assertEqual((event.source.value, event.event_type.value, event.status.value),
                                 ('HOST_OBSERVED', 'PROCESS_EXEC', 'OBSERVED'))
                self.assertIsNone(event.capability)
                self.assertIsNone(event.exit_code)
                self.assertEqual(result.chain_ref, chain.records()[-1].record_hash)
                exported = json.dumps([asdict(observation), asdict(event),
                                       [asdict(record) for record in chain.records()]])
                for raw in (sys.executable, 'raise SystemExit(0)', 'SYNTHETIC_ENV_MARKER'):
                    self.assertNotIn(raw, exported)
                print('NATIVE_NOTE_EXEC: registered_pid=%d sequence=%d session=native-session '
                      'pid_match=YES session_match=YES coverage=PARTIAL correlation=%s '
                      'chain=YES' % (pid, sequence, correlation))
        self.assertEqual((len(self.trace.events()), len(chain.records())), (3, 3))
        self.assertTrue(chain.verify().valid)
        self.assertEqual(asdict(receipt), before)
        linked = self.c.correlate_rse(action, receipt, self.trace.events()[0], attempt_linked=True)
        self.assertEqual(linked.execution_state, 'UNKNOWN_OUTCOME')
        self.assertFalse(broker.has('process.execute'))
        observer.close()
        with self.assertRaises(ValueError):
            observer.wait_for_exec(0)

    def test_suppressed_native_delivery_cannot_fabricate_observation(self):
        # Break caught: construction from attempted exec without returned kevent.
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        native_factory = select.kqueue

        class SuppressedQueue:
            def __init__(self):
                self.native = native_factory()

            def control(self, changes, max_events, timeout):
                self.native.control(changes, max_events, timeout)
                return []

            def close(self):
                self.native.close()

        with patch.object(self.m.select, 'kqueue', SuppressedQueue):
            observer = self.observer()
        with controlled_child() as (pid, release):
            observer.register(pid)
            release()
            with patch.object(self.m, 'HostObservation', side_effect=AssertionError('fabricated')):
                self.assertIsNone(observer.wait_for_exec(3))

    def test_import_is_inactive(self):
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        with patch.object(select, 'kqueue', side_effect=AssertionError('kqueue on import')), \
             patch.object(os, 'fork', side_effect=AssertionError('process on import')), \
             patch('threading.Thread.start', side_effect=AssertionError('thread on import')), \
             patch('builtins.open', side_effect=AssertionError('write on import')), \
             patch.object(os, 'putenv', side_effect=AssertionError('environment mutation')), \
             patch.object(os, 'environ', NoEnvironment()):
            importlib.reload(self.m)

    def test_native_timeout_and_close_release_descriptor(self):
        observer = self.observer()
        queue = observer._queue
        descriptor = queue.fileno()
        with controlled_child() as (pid, release):
            observer.register(pid)
            with patch.object(self.m, 'HostObservation', side_effect=AssertionError('fabricated')):
                self.assertIsNone(observer.wait_for_exec(0.01))
            observer.close()
            self.assertTrue(queue.closed)
            with self.assertRaises(OSError):
                os.fstat(descriptor)
            with self.assertRaises(ValueError):
                observer.register(pid)
            release()

    def test_invalid_parameters_create_no_native_resource_or_close_existing_one(self):
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        for session in ('', 'bad\n', 'x' * 129, None, True):
            with patch.object(select, 'kqueue', side_effect=AssertionError('invalid session opened queue')):
                with self.assertRaises(ValueError):
                    self.m.MacOSExecObserver(session)
        for pid in (True, 0, -1, 1.5, '123', 2**31):
            observer = self.observer()
            queue = observer._queue
            with self.assertRaises(ValueError):
                observer.register(pid)
            self.assertTrue(queue.closed)
        for timeout in (True, -1, float('nan'), float('inf'), 31, '1'):
            observer = self.observer()
            queue = observer._queue
            with self.assertRaises(ValueError):
                observer.wait_for_exec(timeout)
            self.assertTrue(queue.closed)
        observer = self.observer()
        with self.assertRaises(ValueError):
            observer.register(os.getpid(), action_id_ref='raw command data')
        self.assertTrue(observer._queue.closed)

    def test_unavailable_platform_stops_without_creating_queue(self):
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        with patch.object(self.m.sys, 'platform', 'linux'), \
             patch.object(select, 'kqueue', side_effect=AssertionError('fallback')):
            with self.assertRaisesRegex(RuntimeError, 'NATIVE_HOST_OBSERVATION_UNAVAILABLE'):
                self.m.MacOSExecObserver('session')

    def test_duplicate_registration_and_wait_errors_close(self):
        observer = self.observer()
        observer.register(os.getpid())
        with self.assertRaises(ValueError):
            observer.register(os.getpid(), action_id_ref='ref:changed')
        self.assertTrue(observer._queue.closed)
        for event, error, kind in ((None, OSError('wait unavailable'), OSError),
                                    (None, KeyboardInterrupt(), KeyboardInterrupt),
                                    (object(), None, ValueError)):
            queue = TestQueue(event)
            with patch.object(select, 'kqueue', return_value=queue):
                observer = self.observer()
            observer.register(os.getpid())
            queue.error = error
            with self.assertRaises(kind):
                observer.wait_for_exec(0)
            self.assertTrue(queue.closed)

    def test_pid_filter_and_flag_mismatch_emit_nothing_and_errors_close(self):
        # Doubles are required only to deliver native impossible/unrelated inputs.
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        pid = os.getpid()
        events = [select.kevent(pid + 1, filter=select.KQ_FILTER_PROC, fflags=select.KQ_NOTE_EXEC),
                  select.kevent(pid, filter=select.KQ_FILTER_READ, fflags=select.KQ_NOTE_EXEC),
                  select.kevent(pid, filter=select.KQ_FILTER_PROC, fflags=select.KQ_NOTE_EXIT)]
        for event in events:
            queue = TestQueue(event)
            with patch.object(select, 'kqueue', return_value=queue):
                observer = self.observer()
            observer.register(pid)
            with patch.object(self.m, 'HostObservation', side_effect=AssertionError('fabricated')):
                self.assertIsNone(observer.wait_for_exec(0))
        queue = TestQueue(select.kevent(pid, filter=select.KQ_FILTER_PROC,
                         flags=select.KQ_EV_ERROR, fflags=select.KQ_NOTE_EXEC, data=3))
        with patch.object(select, 'kqueue', return_value=queue):
            observer = self.observer()
        observer.register(pid)
        with self.assertRaises(OSError):
            observer.wait_for_exec(0)
        self.assertTrue(queue.closed)

    def test_registration_bounds_and_native_errors_close(self):
        self.assertIsNotNone(self.m, 'Phase 3A has no native NOTE_EXEC backend')
        queue = TestQueue(None)
        with patch.object(select, 'kqueue', return_value=queue):
            observer = self.observer()
        for pid in range(1, 129):
            observer.register(pid)
        with self.assertRaises(ValueError):
            observer.register(129)
        self.assertTrue(queue.closed)
        for error in (OSError('registration unavailable'), KeyboardInterrupt()):
            queue = TestQueue(None, error)
            with patch.object(select, 'kqueue', return_value=queue):
                observer = self.observer()
            with self.assertRaises(type(error)):
                observer.register(os.getpid())
            self.assertTrue(queue.closed)


class TestQueue:
    """Negative-path double, not a native observation evidence source."""
    def __init__(self, event, error=None):
        self.event, self.error, self.closed = event, error, False

    def control(self, changes, max_events, timeout):
        if self.error is not None:
            raise self.error
        return [] if changes or self.event is None else [self.event]

    def close(self):
        self.closed = True


class NoEnvironment:
    """Fail on environment inspection; inherited child environment needs no read."""
    def __getattribute__(self, name):
        raise AssertionError('environment inspection')

    def __getitem__(self, name):
        raise AssertionError('environment inspection')


class ProcessExecSourceTests(unittest.TestCase):
    def test_process_exec_is_host_only_and_does_not_change_adapter_start_semantics(self):
        saved = sys.path[:]
        sys.path.insert(0, str(SCRIPTS))
        try:
            c = importlib.import_module('critical_execution_trace')
            h = importlib.import_module('host_observer')
            self.assertIn('PROCESS_EXEC', {kind.value for kind in c.CriticalEventType},
                          'host PROCESS_EXEC semantic is missing')
            context = c.TraceContext('trace', 'install', None, None, None, 'action',
                                      None, 'trusted', None, 'runtime')
            observation = h.HostObservation('20396-host-observation/v1', 'observer',
                'ref:provenance', 'session', 'one', 1, 1, 'PROCESS_EXEC', None,
                'ref:pid-123', None, 'PARTIAL')
            trace = c.CriticalTrace('trace', 'install')
            result = h.HostObservationIngestor('observer', 'ref:provenance', trace=trace).ingest(observation)
            self.assertTrue(result.accepted)
            for source in c.ObservationSource:
                with self.subTest(source=source.value):
                    with self.assertRaises(ValueError):
                        c.CriticalEvent('forged', c.CriticalEventType.PROCESS_EXEC, context,
                            source, 1, 'ref:program', c.rse.DataClass.PUBLIC)
            self.assertEqual(c.ACTION_EVENTS[c.rse.ActionClass.EXECUTE_PROCESS].value, 'PROCESS_START')
        finally:
            sys.path[:] = saved
