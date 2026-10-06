"""Trusted host evidence ingestion. This module has no sensor or execution authority."""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from threading import Lock
from types import MappingProxyType

import critical_execution_trace as cet

SCHEMA = '20396-host-observation/v1'
MAX_OBSERVATIONS = 128
_CLASSES = frozenset(kind.value for kind in cet._HOST_EVENT_TYPES)
_COVERAGE = ('SCOPED_COMPLETE', 'PARTIAL', 'UNKNOWN')
_CORRELATION = ('CORRELATED', 'UNCORRELATED', 'UNRESOLVED_LINK')
_REASONS = ('ACCEPTED', 'IDEMPOTENT_DUPLICATE', 'UNTRUSTED_OBSERVER',
            'OBSERVATION_SEQUENCE_INVALID', 'SEQUENCE_GAP', 'OBSERVATION_ID_CONFLICT',
            'MALFORMED_OBSERVATION', 'UNRESOLVED_LINK')


def _require(condition):
    if not condition:
        raise ValueError('MALFORMED_OBSERVATION')


def _identity(value):
    return type(value) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}', value) is not None


def _ref(value):
    return (type(value) is str and (re.fullmatch('ref:[A-Za-z0-9_.-]{1,128}', value) is not None
                                  or (value.startswith('sha256:') and cet._digest(value[7:]))))


@dataclass(frozen=True, repr=False)
class HostObservation:
    schema_version: str
    observer_id: str
    provenance_ref: str
    session_id: str
    observation_id: str
    sequence: int
    observed_at: float
    event_class: str
    action_id_ref: str | None
    target_ref: str | None
    effect_digest: str | None
    coverage: str

    def __post_init__(self):
        _require(type(self.schema_version) is str and self.schema_version == SCHEMA)
        _require(all(_identity(getattr(self, field)) for field in
                     ('observer_id', 'session_id', 'observation_id')) and _ref(self.provenance_ref))
        _require(type(self.sequence) is int and 1 <= self.sequence <= 2**53)
        _require(cet._time(self.observed_at))
        _require(type(self.event_class) is str and self.event_class in _CLASSES)
        _require(type(self.coverage) is str and self.coverage in _COVERAGE)
        _require(all(value is None or _ref(value) for value in (self.action_id_ref, self.target_ref)))
        _require(self.effect_digest is None or cet._digest(self.effect_digest))


@dataclass(frozen=True)
class HostObservationResult:
    accepted: bool
    reason: str
    correlation_status: str
    effective_coverage: str
    cet_event_ref: str | None = None
    chain_ref: str | None = None

    def __post_init__(self):
        _require(type(self.accepted) is bool and type(self.reason) is str and self.reason in _REASONS)
        _require(type(self.correlation_status) is str and self.correlation_status in _CORRELATION)
        _require(type(self.effective_coverage) is str and self.effective_coverage in _COVERAGE)
        _require(all(value is None or cet._digest(value) for value in (self.cet_event_ref, self.chain_ref)))


class HostObservationIngestor:
    """One trusted controller, bounded same-process replay state, no persistence.

    The caller owns the trace/chain and supplies known action contexts explicitly.
    References must be opaque before entry; output commits them by digest. The
    private CET factory is API source separation, not an adversarial Python sandbox.
    """

    def __init__(self, trusted_observer_id, trusted_provenance_ref, *, trace,
                 known_actions=None, chain=None, actor=None):
        _require(_identity(trusted_observer_id) and _ref(trusted_provenance_ref))
        _require(type(trace) is cet.CriticalTrace)
        _require((chain is None) == (actor is None))
        known = {} if known_actions is None else known_actions
        _require(type(known) is dict and len(known) <= MAX_OBSERVATIONS)
        _require(all(_ref(key) and type(context) is cet.TraceContext
                     and context.trace_id == trace.trace_id
                     and context.installation_id == trace.installation_id
                     for key, context in known.items()))
        self._observer = trusted_observer_id
        self._provenance = trusted_provenance_ref
        self._trace, self._chain, self._actor = trace, chain, actor
        self._known = MappingProxyType(dict(known))
        self._accepted, self._sessions = {}, {}
        self._lock = Lock()
        self._closed = False

    def ingest(self, observation):
        with self._lock:
            reject = lambda reason: HostObservationResult(False, reason, 'UNCORRELATED', 'UNKNOWN')
            if type(observation) is not HostObservation:
                return reject('MALFORMED_OBSERVATION')
            try:
                observation.__post_init__()
            except ValueError:
                return reject('MALFORMED_OBSERVATION')
            if observation.observer_id != self._observer or observation.provenance_ref != self._provenance:
                return reject('UNTRUSTED_OBSERVER')
            digest = cet.sc.artifact_digest(observation)
            previous = self._accepted.get(observation.observation_id)
            if previous is not None:
                if previous[0] != digest:
                    return reject('OBSERVATION_ID_CONFLICT')
                result = previous[1]
                return HostObservationResult(False, 'IDEMPOTENT_DUPLICATE', result.correlation_status,
                    result.effective_coverage, result.cet_event_ref, result.chain_ref)
            if self._closed or len(self._accepted) >= MAX_OBSERVATIONS:
                return reject('MALFORMED_OBSERVATION')
            last, incomplete = self._sessions.get(observation.session_id, (None, False))
            if last is not None and observation.sequence <= last:
                return reject('OBSERVATION_SEQUENCE_INVALID')
            gap = last is not None and observation.sequence > last + 1
            incomplete = incomplete or gap
            coverage = 'PARTIAL' if incomplete else observation.coverage
            context = self._known.get(observation.action_id_ref)
            correlation = ('CORRELATED' if context is not None else
                           'UNCORRELATED' if observation.action_id_ref is None else 'UNRESOLVED_LINK')
            if context is None:
                context = cet.TraceContext(self._trace.trace_id, self._trace.installation_id,
                    None, None, None, 'host:' + cet.sc._ref(observation.observation_id),
                    None, 'host-observer', None, 'host-evidence')
            # Hash opaque refs before CET/chain output; never infer operation detail.
            evidence = tuple(label + '-sha256:' + cet.sc._ref(value) for label, value in (
                ('observer', observation.observer_id), ('provenance', observation.provenance_ref),
                ('session', observation.session_id), ('observation', observation.observation_id),
                ('action', observation.action_id_ref)) if value is not None)
            evidence += ('host-observation:' + digest, 'sequence:' + str(observation.sequence),
                         'coverage:' + coverage, 'correlation:' + correlation,
                         'sequence-gap:' + ('YES' if gap else 'NO'))
            if observation.effect_digest is not None:
                evidence += ('effect-sha256:' + observation.effect_digest,)
            event = cet._host_observed_event(event_id='host:' + digest,
                event_type=cet.CriticalEventType(observation.event_class), context=context,
                timestamp=observation.observed_at,
                target='sha256:' + cet.sc._ref(observation.target_ref or ('observation:' + digest)),
                data_classification=cet.rse.DataClass.UNKNOWN, evidence_refs=evidence)
            chain_ref = None
            try:
                cet._require(len(self._trace._events) < cet.MAX_EVENTS)
                self._trace._structure(self._trace._events + (event,))
                if self._chain is not None:
                    record = cet.record_critical_event(self._chain, self._actor, event,
                                                      now=time.time())
                    chain_ref = record.record_hash
                self._trace.append(event)
                reason = ('SEQUENCE_GAP' if gap else 'UNRESOLVED_LINK'
                          if correlation == 'UNRESOLVED_LINK' else 'ACCEPTED')
                result = HostObservationResult(True, reason, correlation, coverage,
                                               cet.sc.artifact_digest(event), chain_ref)
                self._accepted[observation.observation_id] = (digest, result)
                self._sessions[observation.session_id] = (observation.sequence, incomplete)
                return result
            except BaseException as error:
                # An optional store may have written before failing. Never retry
                # within this lifecycle or claim crash-safe atomic publication.
                self._closed = True
                if isinstance(error, (ValueError, OSError)):
                    return reject('MALFORMED_OBSERVATION')
                raise  # Preserve unexpected errors and interrupts after latching.
