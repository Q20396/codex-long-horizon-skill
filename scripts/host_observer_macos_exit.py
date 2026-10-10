"""Explicit registered-PID Darwin NOTE_EXIT collector; repository experiment only.

Native delivery reports exit, not exit status, authorship or effect success.
The trusted caller owns PID selection, correlation and ingestion. No import effects.
"""
import math
import select
import sys
import time
from uuid import uuid4

from host_observer import HostObservation, MAX_OBSERVATIONS, SCHEMA, _identity, _ref

OBSERVER_ID = 'macos-kqueue-proc-exit'
PROVENANCE_REF = 'ref:macos-kqueue-evfilt-proc-note-exit'


class MacOSExitObserver:
    """One queue, synchronous trusted caller, finite waits, short-session PID refs."""

    def __init__(self, session_id):
        if not _identity(session_id):
            raise ValueError('INVALID_OBSERVER_INPUT')
        required = ('kqueue', 'kevent', 'KQ_FILTER_PROC', 'KQ_NOTE_EXIT',
                    'KQ_EV_ADD', 'KQ_EV_ENABLE', 'KQ_EV_ONESHOT', 'KQ_EV_ERROR')
        if sys.platform != 'darwin' or not all(hasattr(select, n) for n in required):
            raise RuntimeError('NATIVE_HOST_OBSERVATION_UNAVAILABLE')
        self._session = session_id
        self._registered, self._seen = {}, set()
        self._sequence = 0
        self._closed = False
        try:
            self._queue = select.kqueue()
        except Exception:
            raise RuntimeError('NATIVE_OBSERVER_OPEN_FAILED') from None

    def _check(self):
        if self._closed:
            raise ValueError('OBSERVER_CLOSED')

    def register(self, pid, action_id_ref=None):
        try:
            self._check()
            if (type(pid) is not int or not 1 <= pid < 2**31 or pid in self._seen
                    or len(self._seen) >= MAX_OBSERVATIONS
                    or (action_id_ref is not None and not _ref(action_id_ref))):
                raise ValueError('INVALID_OBSERVER_INPUT')
            try:
                event = select.kevent(pid, filter=select.KQ_FILTER_PROC,
                    flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_ONESHOT,
                    fflags=select.KQ_NOTE_EXIT)
                self._queue.control([event], 0, 0)
            except Exception:
                raise RuntimeError('NATIVE_OBSERVER_REGISTER_FAILED') from None
            self._registered[pid] = action_id_ref
            self._seen.add(pid)
        except BaseException:
            self.close()
            raise

    def wait_for_exit(self, timeout):
        """None means no matching evidence; never a negative-effect assertion."""
        try:
            self._check()
            if (type(timeout) not in (int, float) or not 0 <= timeout <= 30
                    or not math.isfinite(timeout)):
                raise ValueError('INVALID_OBSERVER_INPUT')
            try:
                events = self._queue.control(None, 1, timeout)
            except Exception:
                raise RuntimeError('NATIVE_OBSERVER_WAIT_FAILED') from None
            if not events:
                return None
            event = events[0]
            if type(event) is not select.kevent:
                raise ValueError('INVALID_NATIVE_EVENT')
            if event.flags & select.KQ_EV_ERROR:
                raise RuntimeError('NATIVE_OBSERVER_EVENT_FAILED')
            if (event.filter != select.KQ_FILTER_PROC or event.ident not in self._registered
                    or not event.fflags & select.KQ_NOTE_EXIT):
                return None
            ref = self._registered[event.ident]
            observation = HostObservation(SCHEMA, OBSERVER_ID, PROVENANCE_REF,
                self._session, uuid4().hex, self._sequence + 1, time.time(),
                'PROCESS_EXIT', ref, 'ref:pid-' + str(event.ident), None, 'PARTIAL')
            del self._registered[event.ident]
            self._sequence += 1
            return observation
        except BaseException:
            self.close()
            raise

    def close(self):
        """Latch closed before cleanup; never retry an ambiguously closed descriptor."""
        if not self._closed:
            self._closed = True
            self._registered.clear()
            try:
                self._queue.close()
            except Exception:
                raise RuntimeError('RESOURCE_STATE_UNKNOWN') from None
