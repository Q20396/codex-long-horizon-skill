# Host Observation — Phase 3A / 3B

`HOST_OBSERVED` is supported as a distinct evidence source. This experimental
foundation receives bounded `HostObservation` values from explicitly trusted
host code, including the Phase 3B macOS backend below. The ingestor starts no
observer and performs no target effects. Importing either module creates no
observer, filesystem write, subprocess, socket, thread or environment mutation.

| Boundary | Status |
| --- | --- |
| HOST_OBSERVED | SUPPORTED AS A DISTINCT EVIDENCE SOURCE |
| REAL HOST SENSOR | EXPERIMENTAL MACOS REGISTERED-PID NOTE_EXEC ONLY |
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
PROCESS_START, PROCESS_EXEC, PROCESS_EXIT, NETWORK_REQUEST, GIT_EFFECT and REMOTE_EFFECT. These
are normalization categories, not general OS sensor capabilities. PROCESS_EXEC
means a registered process executed a new program image; it implies no fork,
new PID birth, application success or completed side effect. It is host-only;
existing EXECUTE_PROCESS adapters retain PROCESS_START/PROCESS_EXIT semantics. GIT_EFFECT
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

Any exceptional exit during publication or replay-state update latches ingestion
closed. ValueError/OSError return MALFORMED_OBSERVATION; unexpected exceptions and
interrupts propagate after latching and are not swallowed. An optional
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
Chain permission checks and recording use the trusted host's current wall clock,
not the observation's supporting timestamp. Event evidence keeps `observed_at`
unchanged. Expired current authority and observations later than the host's current
clock cannot anchor an event. This is not a tamper-resistant clock guarantee.

Legacy CET effect comparisons, risk detection and RSE correlation exclude host
evidence. Legacy risk ancestry and finding digests use only non-host events, so
host-only intermediary contexts cannot create a legacy causal path. The trace
retains host events, but legacy `observed_event_count` counts
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

## Experimental macOS registered-process exec slice

`host_observer_macos.MacOSExecObserver(session_id)` explicitly creates one native
macOS `select.kqueue` session. Trusted code supplies a unique bounded session ID
and owns the synchronous lifecycle:

```python
from host_observer_macos import MacOSExecObserver, OBSERVER_ID, PROVENANCE_REF

observer = MacOSExecObserver('unique-host-session')
try:
    observer.register(explicit_pid, action_id_ref=None)
    observation = observer.wait_for_exec(3)
    if observation is not None:
        result = trusted_ingestor.ingest(observation)
finally:
    observer.close()
```

Configure `trusted_ingestor` with `OBSERVER_ID` (`macos-kqueue-proc`) and
`PROVENANCE_REF` (`ref:macos-kqueue-evfilt-proc-note-exec`). An exact integer PID
from 1 through 2**31-1 is trusted caller input. A successful registration uses
EVFILT_PROC, NOTE_EXEC and EV_ONESHOT. It observes one exec, then requires another
explicit registration to observe a later exec. Re-registering a pending PID is
rejected rather than changing its correlation. At most 128 registrations and
observations are allowed across one instance; there is no eviction or persistent
session registry. One controller serializes calls; no background thread exists.

`wait_for_exec(timeout)` makes one bounded native wait, accepting finite int/float
timeouts from 0 through 30 seconds. Only a returned native kevent with matching
registered ident/PID, EVFILT_PROC and NOTE_EXEC creates a HostObservation. Error
events cannot create observations. No matching event returns `None`, the
OBSERVATION_TIMEOUT result, and establishes no negative-effect claim. Invalid inputs and
native errors propagate after closing the descriptor; timeout alone leaves the
session open. `close()` is idempotent and prevents further use.

The observation carries PROCESS_EXEC, PARTIAL coverage, the supplied session,
monotonic sequence starting at 1, fresh observation identity, native backend
provenance and `ref:pid-<registered PID>`. PID is a short-session reference, not a
durable global process identity or executable identity. A caller must register
the intended live process before exec and close the short session; this slice adds
no global PID-reuse protection. A supplied action ref is carried exactly; None
stays uncorrelated. Ingestion, sequence/dedupe rules, source isolation, hashed
evidence and authority/reconciliation boundaries remain the Phase 3A path.

No command line, executable metadata or environment is inspected or stored.
PROCESS_EXIT, fork/new-PID discovery, global process creation, filesystem/network
observation, enforcement, daemon, Endpoint Security, FSEvents, DTrace, polling
fallback and multi-platform framework are NOT_IMPLEMENTED. This is native host
observation from macOS kqueue NOTE_EXEC, not tamper-proof kernel truth.

Tests: `python3 -B -m unittest discover -s tests -p 'test_host_observer*.py' -v`.
The native test forks a harmless child blocked on a pipe, registers its PID,
then releases it to exec the current Python and exit. Native delivery must precede
normalization, ingestion, CET and chain assertions. Negative doubles never count
as native PASS. Child cleanup and wait are bounded. On non-macOS, native tests
report NOT_RUN_PLATFORM_RESTRICTED rather than PASS; unavailable native validation
is BETA only for an environment limitation, never a reproducible implementation
defect. Linux formal validation is a separate gate and proves no macOS event.
No batch API, backend registry, daemon, telemetry framework or cross-layer verifier
is included. Phase 4, enforcement and production hardening require separate work.
