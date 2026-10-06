"""Session-scoped macOS registered-PID NOTE_EXEC evidence; no import effects.

One registration observes at most one exec. PID is a short-session reference,
not a durable identity. Trusted callers own correlation, ingestion and lifecycle.
"""
from __future__ import annotations

import math
import select
import sys
import time
from uuid import uuid4

from host_observer import HostObservation, MAX_OBSERVATIONS, SCHEMA, _identity, _ref

OBSERVER_ID = 'macos-kqueue-proc'
PROVENANCE_REF = 'ref:macos-kqueue-evfilt-proc-note-exec'
MAX_TIMEOUT = 30


class MacOSExecObserver:
    """Explicit create/register/wait/close, one trusted synchronous controller.

    wait_for_exec returns None (OBSERVATION_TIMEOUT) if the finite wait supplies
    no matching NOTE_EXEC. This establishes no negative-effect claim. No sensor starts
    until construction; no target is inspected, launched, authorized or reconciled.
    """

    def __init__(self, session_id):
        if not _identity(session_id):
            raise ValueError('INVALID_OBSERVER_INPUT')
        if sys.platform != 'darwin' or not all(hasattr(select, name) for name in
                ('kqueue', 'kevent', 'KQ_FILTER_PROC', 'KQ_NOTE_EXEC')):
            raise RuntimeError('NATIVE_HOST_OBSERVATION_UNAVAILABLE')
        self._session = session_id
        self._registered = {}
        self._registration_count = self._sequence = 0
        self._closed = False
        self._queue = select.kqueue()

    def register(self, pid, action_id_ref=None):
        """Register trusted PID before exec; optional linkage is explicit only."""
        try:
            if (self._closed or type(pid) is not int or not 1 <= pid < 2**31
                    or pid in self._registered or self._registration_count >= MAX_OBSERVATIONS
                    or (action_id_ref is not None and not _ref(action_id_ref))):
                raise ValueError('INVALID_OBSERVER_INPUT')
            event = select.kevent(pid, filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_ONESHOT,
                fflags=select.KQ_NOTE_EXEC)
            self._queue.control([event], 0, 0)
            self._registered[pid] = action_id_ref
            self._registration_count += 1
        except BaseException:
            self.close()
            raise

    def wait_for_exec(self, timeout):
        """Accept only a returned native process NOTE_EXEC for a registered PID."""
        try:
            if (self._closed or type(timeout) not in (int, float)
                    or not math.isfinite(timeout) or not 0 <= timeout <= MAX_TIMEOUT
                    or self._sequence >= MAX_OBSERVATIONS):
                raise ValueError('INVALID_OBSERVER_INPUT')
            events = self._queue.control(None, 1, timeout)
            if not events:
                return None
            event = events[0]
            if type(event) is not select.kevent:
                raise ValueError('INVALID_NATIVE_EVENT')
            if event.flags & select.KQ_EV_ERROR:
                raise OSError('NATIVE_OBSERVER_ERROR')
            if (event.ident not in self._registered or event.filter != select.KQ_FILTER_PROC
                    or not event.fflags & select.KQ_NOTE_EXEC):
                return None
            action_ref = self._registered.pop(event.ident)
            self._sequence += 1
            return HostObservation(SCHEMA, OBSERVER_ID, PROVENANCE_REF, self._session,
                uuid4().hex, self._sequence, time.time(), 'PROCESS_EXEC', action_ref,
                'ref:pid-' + str(event.ident), None, 'PARTIAL')
        except BaseException:
            self.close()
            raise

    def close(self):
        """Idempotently stop this instance and release its native descriptor."""
        if not self._closed:
            self._closed = True
            try:
                self._queue.close()
            finally:
                self._registered.clear()
