# Host Observation — Phase 3A

`HOST_OBSERVED` is supported as a distinct evidence source. This experimental
foundation receives synthetic `HostObservation` values from explicitly trusted
host code. It starts no observer and performs no target effects. Importing the
module performs no filesystem, subprocess, socket, thread or environment effects.

| Boundary | Status |
| --- | --- |
| HOST_OBSERVED | SUPPORTED AS A DISTINCT EVIDENCE SOURCE |
| REAL HOST SENSOR | NOT_IMPLEMENTED |
| HOST ENFORCEMENT | NOT_IMPLEMENTED |
| KERNEL TRACE | NOT_IMPLEMENTED |
| HOST OBSERVED == TARGET REALITY | FALSE |
| HOST OBSERVED == KERNEL TRUTH | FALSE |
| NO HOST OBSERVATION == NO EFFECT | FALSE |
| CROSS-PROCESS DEDUPE | NOT_IMPLEMENTED |
| CRASH DURABILITY | NO |
| COVERAGE | SCOPED / EXPLICIT |

## Input and trust

The frozen scalar `HostObservation` uses schema `20396-host-observation/v1` and
contains observer/provenance, session/observation identity, sequence, bounded
timestamp, event class, optional action/target refs and effect digest, and coverage.
No arbitrary metadata, raw file contents, HTTP bodies, credentials, environment,
stdout/stderr or command payload is accepted. The caller must normalize sensitive
input into opaque refs or digests before construction; this module does not read
or sanitize raw host payloads.

Identity strings contain 1–128 ASCII letters, digits, underscores, dots or hyphens.
Refs are `ref:` plus such an opaque identity, or `sha256:` plus 64 lowercase hex
characters. Effect digests are 64 lowercase hex characters. Sequence is an exact
integer from 1 through 2**53 (bool is invalid); time is finite, nonnegative and at
most 2**53. Time supports ordering evidence, not global trusted time or causality.

Allowed classes are FILE_READ, FILE_WRITE, FILE_CREATE, FILE_DELETE, FILE_MOVE,
PROCESS_START, PROCESS_EXIT, NETWORK_REQUEST, GIT_EFFECT and REMOTE_EFFECT. These
are normalization categories, not implemented OS sensor capabilities. GIT_EFFECT
does not imply commit, stage, push, a ref mutation or success. REMOTE_EFFECT does
not imply HTTP method, PR creation, remote success or target-reality change.
Host FILE_MOVE keeps only an opaque target/effect commitment; it invents no source
or destination path. Existing adapter FILE_MOVE still requires both concrete paths.

## Ingestion and correlation

Construct `HostObservationIngestor(trusted_observer_id, trusted_provenance_ref,
trace=..., known_actions=..., chain=..., actor=...)` in trusted host code. Both
incoming observer and provenance must match. `known_actions` is an optional bounded
dict of opaque action refs to trusted existing CET `TraceContext` values; the
ingestor snapshots it. A known explicit ref returns CORRELATED; absent ref returns
UNCORRELATED; unknown ref returns UNRESOLVED_LINK and is still retained. Timestamp
proximity never supplies a relation. Uncorrelated events have their own hashed
observation identity as context, without an invented governed-action relation.

The only entrypoint is `ingest(observation)`. Accepted results contain reason,
correlation status, effective coverage and event/optional chain digests. Rejected
input emits no host event. Reasons are ACCEPTED, IDEMPOTENT_DUPLICATE,
UNTRUSTED_OBSERVER, OBSERVATION_SEQUENCE_INVALID, SEQUENCE_GAP,
OBSERVATION_ID_CONFLICT, MALFORMED_OBSERVATION and UNRESOLVED_LINK.

Public CET event construction and `ObservedEffects` reject HOST_OBSERVED. The
ingestor uses a private trusted CET construction path. Phase 2A/2B adapters and the
Phase 2C bridge retain ADAPTER_OBSERVED. Private Python internals are not a hostile
code sandbox: trusted code must prevent model/runtime code from obtaining this
ingestor or calling private constructors. Host ingestion creates no authorization,
capability, policy, Break Glass grant or reconciliation/lifecycle transition.

## Ordering, coverage and recovery

One lock protects duplicate checks, session order, emission and replay state.
Same observation ID and canonical digest returns IDEMPOTENT_DUPLICATE with original
refs and emits nothing; changed content returns OBSERVATION_ID_CONFLICT. Each
session must strictly increase; a new session can restart. Revisited sessions
retain their high-water mark, so changing session does not bypass replay checks.
The first supplied sequence is a baseline; no earlier continuity is inferred.

Coverage is SCOPED_COMPLETE, PARTIAL or UNKNOWN. SCOPED_COMPLETE means only the
observer's explicit scoped attestation, never complete host visibility. A jump
past last sequence + 1 is retained with SEQUENCE_GAP and effective PARTIAL coverage.
That session remains PARTIAL on subsequent contiguous observations and after a
session revisit. No gap object, backfill, automatic repair or negative-effect
proof is provided.

At most 128 accepted observations/sessions and 128 known action refs are retained,
subject to the existing trace's 128-event limit. Overflow fails closed using
MALFORMED_OBSERVATION; old replay evidence is never evicted. Use one ingestor and
one trusted controller for a trace/chain. Other writers must be serialized by
the caller; this lock does not coordinate separate ingestors or processes.

Emission failure latches ingestion closed with MALFORMED_OBSERVATION. An optional
chain may have written before failing; inspect existing evidence rather than
blindly retrying with a fresh ingestor/ID. There is no durable atomic transaction,
persistent session registry, crash recovery or cross-process deduplication.

## Evidence output and existing analysis

CET records the exact host category, OBSERVED status, UNKNOWN data classification,
hashed opaque target and hashed observer/provenance/session/observation/action refs,
observation/effect digests, sequence, effective coverage, correlation and immediate
gap flag. No capability, exit code, HTTP operation or move destination is invented.
These commitments allow a trusted operator retaining the original opaque refs to
identify the observer/session and audit sequence and coverage. Digests are neither
encryption nor anonymization; deterministic low-entropy refs can be guessed.

When chain and actor are explicitly configured together, ingestion reuses existing
`record_critical_event` authority validation and CRITICAL_TRACE_EVENT anchoring.
The existing `20396-security-chain/v1` schema and ledger are unchanged; sealed
records contain digests only. No chain is automatically created or persisted.

Legacy CET effect comparisons, risk detection and RSE correlation exclude host
evidence. The trace retains host events, but legacy `observed_event_count` counts
adapter/reconciliation observations only. Phase 4 cross-layer verdicts are not
implemented. No host observation does not change an action or prove no effect.

## Synthetic example

```python
import critical_execution_trace as cet
from host_observer import HostObservation, HostObservationIngestor

trace = cet.CriticalTrace('synthetic-trace', 'synthetic-installation')
ingestor = HostObservationIngestor('synthetic-observer', 'ref:synthetic-provenance',
                                 trace=trace)
observation = HostObservation('20396-host-observation/v1', 'synthetic-observer',
    'ref:synthetic-provenance', 'synthetic-session', 'synthetic-observation',
    1, 1, 'FILE_MOVE', None, 'ref:opaque-target', None, 'UNKNOWN')
result = ingestor.ingest(observation)
assert result.accepted and result.correlation_status == 'UNCORRELATED'
assert trace.events()[0].destination is None
```

Tests: `python3 -B -m unittest discover -s tests -p 'test_host_observer*.py' -v`.
No batch API, backend registry, daemon, telemetry framework or cross-layer verifier
is included. Phase 3B, enforcement and production hardening require separate work.
