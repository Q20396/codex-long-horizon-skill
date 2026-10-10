"""H7: native delivery is separate from portable negative-path doubles."""
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
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NATIVE = sys.platform == 'darwin' and hasattr(select, 'kqueue')


class Event:
    def __init__(self, ident, filter=1, flags=0, fflags=8):
        self.ident, self.filter, self.flags, self.fflags = ident, filter, flags, fflags


class Queue:
    def __init__(self):
        self.events, self.closed, self.closes = [], False, 0
        self.error = self.close_error = None

    def control(self, changes, count, timeout):
        if self.error:
            raise self.error
        if changes:
            event = changes[0]
            assert (event.filter, event.fflags, event.flags, count, timeout) == (1, 8, 7, 0, 0)
            return []
        assert count == 1 and 0 <= timeout <= 30
        return [self.events.pop(0)] if self.events else []

    def close(self):
        self.closes += 1
        if self.close_error:
            raise self.close_error
        self.closed = True


class ModuleCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('host_observer_macos_exit', 'host_observer', 'critical_execution_trace',
                     'runtime_safety_envelope', 'security_authority_chain')
        cls.saved_modules = {n: sys.modules.get(n) for n in cls.names}
        sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / '.agents/skills/long-horizon-engineering/scripts')]
        cls.m = importlib.import_module('host_observer_macos_exit') if (ROOT / 'scripts/host_observer_macos_exit.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for n, value in cls.saved_modules.items():
            if value is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = value

    def setUp(self):
        self.assertIsNotNone(self.m, 'H7 baseline lacks registered-PID PROCESS_EXIT collector')


class PortableExitTests(ModuleCase):
    def backend(self):
        q = Queue()
        api = SimpleNamespace(kqueue=lambda: q, kevent=Event, KQ_FILTER_PROC=1,
                              KQ_EV_ADD=1, KQ_EV_ENABLE=2, KQ_EV_ONESHOT=4,
                              KQ_EV_ERROR=16, KQ_NOTE_EXIT=8)
        self.enter_patch = patch.object(self.m, 'select', api)
        self.enter_patch.start(); self.addCleanup(self.enter_patch.stop)
        p = patch.object(self.m.sys, 'platform', 'darwin')
        p.start(); self.addCleanup(p.stop)
        return q

    def test_one_native_typed_match_only_consumes_once(self):
        # Catch accepting wrong source/PID, replay or advancing on mismatch.
        q = self.backend(); o = self.m.MacOSExitObserver('session')
        self.addCleanup(o.close); o.register(123, 'ref:action')
        for e in (Event(124), Event(123, filter=2), Event(123, fflags=4)):
            q.events.append(e); self.assertIsNone(o.wait_for_exit(0))
        q.events.append(Event(123)); r = o.wait_for_exit(0)
        self.assertEqual((r.event_class, r.coverage, r.sequence, r.target_ref,
                          r.action_id_ref, r.effect_digest),
                         ('PROCESS_EXIT', 'PARTIAL', 1, 'ref:pid-123', 'ref:action', None))
        self.assertEqual((r.observer_id, r.provenance_ref),
                         ('macos-kqueue-proc-exit', 'ref:macos-kqueue-evfilt-proc-note-exit'))
        q.events.append(Event(123)); self.assertIsNone(o.wait_for_exit(0))
        with self.assertRaises(ValueError): o.register(123)

    def test_validation_and_registration_budget(self):
        q = self.backend()
        for s in ('', True, None, 'x' * 129, 'bad\n'):
            with self.assertRaises(ValueError): self.m.MacOSExitObserver(s)
        for pid in (True, 0, -1, 2**31, '1', 1.5):
            o = self.m.MacOSExitObserver('s')
            with self.assertRaises(ValueError): o.register(pid)
            self.assertTrue(q.closed)
        o = self.m.MacOSExitObserver('s')
        for pid in range(1, 129): o.register(pid)
        with self.assertRaises(ValueError): o.register(129)
        o = self.m.MacOSExitObserver('s')
        with self.assertRaises(ValueError): o.register(123, 'raw secret')
        for timeout in (True, -1, 31, 10**1000, float('nan'), float('inf'), '1'):
            o = self.m.MacOSExitObserver('s')
            with self.assertRaises(ValueError): o.wait_for_exit(timeout)

    def test_errors_are_sanitized_and_fail_closed(self):
        q = self.backend()
        for e in (object(), Event(123, flags=16)):
            o = self.m.MacOSExitObserver('s'); o.register(123); q.events.append(e)
            with self.assertRaises((ValueError, RuntimeError)): o.wait_for_exit(0)
            with self.assertRaises(ValueError): o.wait_for_exit(0)
        for registration in (True, False):
            o = self.m.MacOSExitObserver('s')
            q.error = OSError('SENSITIVE_NATIVE_ERROR')
            with self.assertRaises(RuntimeError) as caught:
                o.register(123) if registration else o.wait_for_exit(0)
            self.assertNotIn('SENSITIVE', str(caught.exception))
            self.assertTrue(q.closed); q.error = None

    def test_close_uncertainty_is_not_retried(self):
        q = self.backend(); o = self.m.MacOSExitObserver('s')
        q.close_error = OSError('SENSITIVE_CLOSE')
        with self.assertRaisesRegex(RuntimeError, 'RESOURCE_STATE_UNKNOWN'): o.close()
        o.close(); self.assertEqual(q.closes, 1)
        with self.assertRaises(ValueError): o.register(123)

    def test_platform_guard_and_import_inactive(self):
        with patch.object(self.m.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(RuntimeError, 'NATIVE_HOST_OBSERVATION_UNAVAILABLE'):
                self.m.MacOSExitObserver('s')
        with patch('builtins.open', side_effect=AssertionError('file read')), \
             patch('threading.Thread.start', side_effect=AssertionError('thread')):
            importlib.reload(self.m)

    def test_native_open_error_is_sanitized(self):
        self.backend()
        with patch.object(self.m.select, 'kqueue', side_effect=OSError('SENSITIVE')):
            with self.assertRaisesRegex(RuntimeError, '^NATIVE_OBSERVER_OPEN_FAILED$'):
                self.m.MacOSExitObserver('s')

    def test_real_ingestor_replay_unknown_and_write_failure(self):
        q = self.backend(); o = self.m.MacOSExitObserver('s'); self.addCleanup(o.close)
        h = importlib.import_module('host_observer'); c = h.cet
        trace = c.CriticalTrace('trace', 'install')
        chain = c.sc.InMemorySecurityChain('chain', 'install')
        actor = c.sc.SecurityAuthority('actor', c.sc.AuthorityRole.RUNTIME, 'install')
        ing = h.HostObservationIngestor('macos-kqueue-proc-exit',
            'ref:macos-kqueue-evfilt-proc-note-exit', trace=trace, chain=chain, actor=actor)
        o.register(123); q.events.append(Event(123)); r = o.wait_for_exit(0)
        self.assertTrue(ing.ingest(r).accepted)
        self.assertEqual(ing.ingest(r).reason, 'IDEMPOTENT_DUPLICATE')
        self.assertEqual(len(trace.events()), 1)
        o.register(124); q.events.append(Event(124)); r2 = o.wait_for_exit(0)
        with patch.object(chain, 'append', side_effect=OSError('write failure')):
            self.assertFalse(ing.ingest(r2).accepted)
        self.assertFalse(ing.ingest(r2).accepted)
        self.assertEqual(len(trace.events()), 1)

    def test_sequence_trace_failure_and_no_authority(self):
        q = self.backend(); o = self.m.MacOSExitObserver('s'); self.addCleanup(o.close)
        h = importlib.import_module('host_observer'); c = h.cet
        trace = c.CriticalTrace('trace', 'install')
        context = c.TraceContext('trace', 'install', 'project', 'task', 'run', 'action', None, 'trusted', None, 'runtime')
        ing = h.HostObservationIngestor('macos-kqueue-proc-exit',
            'ref:macos-kqueue-evfilt-proc-note-exit', trace=trace, known_actions={'ref:action': context})
        o.register(123, 'ref:action'); q.events.append(Event(123)); r = o.wait_for_exit(0)
        self.assertTrue(ing.ingest(r).accepted)
        self.assertEqual(ing.ingest(replace(r, observation_id='replay')).reason, 'OBSERVATION_SEQUENCE_INVALID')
        gap = replace(r, observation_id='gap', sequence=3)
        self.assertEqual(ing.ingest(gap).reason, 'SEQUENCE_GAP')
        with patch.object(trace, 'append', side_effect=ValueError('trace unavailable')):
            self.assertFalse(ing.ingest(replace(r, observation_id='lost', sequence=4)).accepted)
        self.assertFalse(ing.ingest(replace(r, observation_id='later', sequence=5)).accepted)
        action = c.rse.ActionRequest('action', 'run', 'task', c.rse.ActionClass.EXECUTE_PROCESS,
            'ref:program', 'trusted', 'runtime', c.rse.DataClass.PUBLIC, None, 'process.execute', 'test')
        receipt = replace(c.rse._receipt(action, c.rse.PolicyDecision('REQUIRE_AUTHORIZATION',
            'NO_AUTHORIZATION')), execution_state='UNKNOWN_OUTCOME', reconciliation_state='STILL_UNKNOWN')
        self.assertEqual(c.correlate_rse(action, receipt, trace.events()[0], attempt_linked=True).execution_state,
                         'UNKNOWN_OUTCOME')
        self.assertFalse(c.rse.CapabilityBroker().has('process.execute'))
        self.assertIsNone(trace.events()[0].exit_code)
        self.assertIsNone(trace.events()[0].capability)


@contextmanager
def child():
    """Only this test's child; bounded wait and kill/reap even after assertion failure."""
    r, w = os.pipe()
    try: pid = os.fork()
    except BaseException:
        os.close(r); os.close(w); raise
    if pid == 0:
        os.close(w)
        ready = select.select([r], [], [], 3)[0]
        code = 0 if ready and os.read(r, 1) == b'x' else 2
        os.close(r); os._exit(code)
    os.close(r)
    try: yield pid, lambda: os.write(w, b'x')
    finally:
        os.close(w); deadline = time.monotonic() + 3; killed = False
        while True:
            found, status = os.waitpid(pid, os.WNOHANG)
            if found:
                if status != 0 or killed: raise AssertionError('controlled child failed')
                break
            if time.monotonic() >= deadline:
                if killed: raise AssertionError('child cleanup exceeded bound')
                os.kill(pid, signal.SIGKILL); killed = True; deadline = time.monotonic() + 3
            time.sleep(.01)


@unittest.skipUnless(NATIVE, 'NOT_RUN_PLATFORM_RESTRICTED: Darwin NOTE_EXIT required')
class NativeExitTests(ModuleCase):
    def test_native_registered_exit_ingestion_and_cleanup(self):
        h = importlib.import_module('host_observer'); c = h.cet
        o = self.m.MacOSExitObserver('native-exit'); self.addCleanup(o.close)
        fd = o._queue.fileno()
        trace = c.CriticalTrace('trace', 'install')
        chain = c.sc.InMemorySecurityChain('chain', 'install')
        actor = c.sc.SecurityAuthority('actor', c.sc.AuthorityRole.RUNTIME, 'install')
        context = c.TraceContext('trace', 'install', 'project', 'task', 'run', 'action', None, 'trusted', None, 'runtime')
        ing = h.HostObservationIngestor('macos-kqueue-proc-exit',
            'ref:macos-kqueue-evfilt-proc-note-exit', trace=trace, chain=chain, actor=actor,
            known_actions={'ref:action': context})
        for seq, ref, correlation in ((1, 'ref:action', 'CORRELATED'), (2, None, 'UNCORRELATED'),
                                       (3, 'ref:missing', 'UNRESOLVED_LINK')):
            with child() as (pid, release):
                o.register(pid, ref)
                self.assertIsNone(o.wait_for_exit(.01))
                release(); r = o.wait_for_exit(3)
                self.assertIsNotNone(r, 'native NOTE_EXIT not delivered')
                self.assertEqual((r.target_ref, r.sequence, r.session_id),
                                 ('ref:pid-' + str(pid), seq, 'native-exit'))
                out = ing.ingest(r)
                self.assertTrue(out.accepted); self.assertEqual(out.correlation_status, correlation)
                event = trace.events()[-1]
                self.assertEqual((event.source.value, event.event_type.value, event.exit_code, event.capability),
                                 ('HOST_OBSERVED', 'PROCESS_EXIT', None, None))
                self.assertIsNone(o.wait_for_exit(0))
                print('NATIVE_NOTE_EXIT registered_before_release=YES pid_match=YES session=native-exit sequence=%d coverage=PARTIAL correlation=%s chain=YES' % (seq, correlation))
        self.assertTrue(chain.verify().valid)
        self.assertNotIn('argv', json.dumps(asdict(r)))
        o.close(); o.close()
        with self.assertRaises(OSError): os.fstat(fd)
        with self.assertRaises(ValueError): o.wait_for_exit(0)

    def test_suppressed_native_exit_never_uses_reap_as_observation(self):
        native = select.kqueue
        class Suppress:
            def __init__(self): self.q = native()
            def control(self, changes, count, timeout):
                self.q.control(changes, count, timeout); return []
            def close(self): self.q.close()
        with patch.object(self.m.select, 'kqueue', Suppress):
            o = self.m.MacOSExitObserver('suppressed')
        self.addCleanup(o.close)
        with child() as (pid, release):
            o.register(pid); release()
            with patch.object(self.m, 'HostObservation', side_effect=AssertionError('fabricated')):
                self.assertIsNone(o.wait_for_exit(3))
