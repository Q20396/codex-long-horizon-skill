# End-to-End Security Runtime — Experimental Architecture Closure

Phase 5 is a bounded integration test, not another runtime layer. Run from the
repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_end_to_end_security_runtime.py' -v
```

The native success test requires macOS kqueue NOTE_EXEC. A non-macOS skip is
`BETA: TARGET_VALIDATION_ENVIRONMENT_UNAVAILABLE`, never native PASS. A timeout on
a supported host fails once; no synthetic fallback or automatic scenario retry
exists. Local Linux formal validation remains a separate target-environment gate.

## One real controlled path

The untrusted `AgentActionProposal` requests the current resolved Python
executable with bounded argv/cwd/timeout. `AgentRuntimeBridge.prepare` produces
the action and payload commitments. A trusted test controller supplies the
policy, task authorization, capability adapter and preapproved payload digest.
`AgentRuntimeBridge.execute` calls the unchanged Phase 2A `RuntimeBinding`; RSE
authorizes the actual invocation. A proposal without authorization cannot run.

The real ProcessAdapter launches the controlled child. **TEST-ONLY
SYNCHRONIZATION** inside the test communicates a decimal PID and an empty release
file in one secure per-test temporary directory. PID publication is atomic.
The child waits before exec. The parent validates the PID, registers it with the
existing MacOSExecObserver, then releases it. Only the native NOTE_EXEC result
creates `PROCESS_EXEC` HostObservation; PID knowledge and release are not host
evidence. The existing HostObservationIngestor correlates the explicit action
reference, emits HOST_OBSERVED CET and appends its existing chain record.

PID readiness and NOTE_EXEC waits each have a 3-second bound, the child release
wait is 5 seconds, the success runtime deadline is 6 seconds and the result wait
is 8 seconds. On a parent failure before release, the child and runtime deadlines
still bound termination/reaping. The runtime owns the process group and cleanup;
the test creates no subprocess directly. Temporary files and observer descriptors
are cleaned up. The helper performs no network operation, uses no credentials,
and executes with the runtime's empty environment and `shell=False`.

## Distinct evidence and normalization

| Layer | Actual source and bounded interpretation |
| --- | --- |
| DECLARED | The bridge's DECLARED PROCESS_START event plus the prepared proposal's normalized parameters; untrusted intent |
| AUTHORIZED | Actual ALLOW receipt, exact preapproved payload commitment and governed action; not copied proposal authority |
| ADAPTER_OBSERVED | Actual RuntimeBinding PROCESS_START and PROCESS_EXIT events, retaining both classes |
| HOST_OBSERVED | Native NOTE_EXEC followed by real ingestion; registered PID executed a new program image; PARTIAL coverage |
| TARGET_REALITY | Existing RuntimeOperationEvidence `reason=EXITED`, `exit_code=0`, bound payload digest, and the successful completed runtime result; exclusively the bounded process wait/reap result |

The prepared material identity represents the checked process payload. Declaration,
authorization and adapter descriptors retain separate evidence digests. The native
PID does not identify the image or argv, so its comparable material identity stays
`None`; no fabricated adapter-to-PID/image mapping is introduced.

The reality fact is derived from the existing `_capture_started` wait/reap result,
not inferred from a generic KNOWN_SUCCESS string, PROCESS_START CET or NOTE_EXEC.
It shares RuntimeBinding provenance with adapter evidence: it is **not** a new
independent sensor, independent subsystem, or second execution. The Phase 5 v1.1
design expressly permits this existing narrow exit/result fact. `VERIFIED` here
attests only the controlled process's returned zero exit status after a completed
wait, with a matching payload commitment. It does not establish the executed
image identity, all side effects, complete host state or hostile-host truth.
No ProcessAdapter reconciler exists; uncertain process outcomes remain unknown.
Nothing in Phase 5 adds a reconciler or claims RECONCILED_SUCCESS.

## Exact unchanged verifier results

| Comparison | Semantic class | Result |
| --- | --- | --- |
| DECLARED → AUTHORIZED | PROCESS_START | MATCH |
| AUTHORIZED → ADAPTER_OBSERVED | PROCESS_START | MATCH |
| AUTHORIZED → ADAPTER_OBSERVED | PROCESS_EXIT | EXTRA |
| ADAPTER_OBSERVED → HOST_OBSERVED | PROCESS_START | NOT_OBSERVED |
| ADAPTER_OBSERVED → HOST_OBSERVED | PROCESS_EXIT | NOT_OBSERVED |
| ADAPTER_OBSERVED → HOST_OBSERVED | PROCESS_EXEC | UNKNOWN |
| HOST_OBSERVED → TARGET_REALITY | PROCESS_EXEC | UNKNOWN |
| HOST_OBSERVED → TARGET_REALITY | PROCESS_EXIT | UNKNOWN |

The existing action/declaration contract represents process execution as
PROCESS_START. The adapter additionally reports PROCESS_EXIT. Keeping that known
class visible produces EXTRA in that bounded source-set comparison; it is not an
unauthorized-execution or maliciousness verdict, and is not a second deliberately
constructed mismatch scenario. Phase 5 does not invent an authorized EXIT
descriptor to suppress this result. The native observer sees image replacement,
not process birth, exit, complete lifecycle, or the executable payload identity.
PARTIAL absence means NOT_OBSERVED, not MISSING. No observation is not no effect.
Removing the exit/result reality source leaves TARGET_REALITY_UNKNOWN, even when
both adapter and host observations exist. The Phase 4 F1 regression tests remain
the authority for incomplete-coverage ambiguous pairing.

## Existing chain and checkpoint

The success path naturally appends six existing records: the Phase 2A receipt,
adapter START and EXIT CET, bridge receipt, DECLARED CET, and HOST_OBSERVED CET.
The test verifies their actual artifact digests and sequence. There is no new
ledger or E2E_SUCCESS record. The runtime result evidence is an existing returned
object; its narrow exit fact is also represented in the existing EXIT CET. Phase
5 does not append the raw result object merely to make it checkpointed.

The verifier receives only bounded normalized refs and produces transient
findings. The test forbids effect/reconciliation calls, observer control, chain
writes and CET writes during verification and checks that policy, authorization,
journal, chain, trace and execution count stay unchanged. Findings are neither
persisted nor chained and cannot trigger retries.

After all six records exist, the existing Signed Checkpoint API binds their
sequence/head and canonical payload. The test reuses the existing **FakeSigner /
FakeVerifier test contract**, which is exact-message lookup, not cryptography.
Passing demonstrates checkpoint API/head binding and verification behavior under
that test contract; it does not demonstrate a trusted signing key, production
cryptographic security, host/kernel integrity, or correctness of unpersisted
findings. General signed checkpoints commit chain state under their documented
trust assumptions; they are not tamper-proof.

## One controlled mismatch and bounded negatives

Exactly one deliberately synthetic mismatch is labeled
`CONTROLLED_VERIFICATION_FIXTURE`. At VerificationInput only, complete scoped
authorized PROCESS_EXEC A is compared with synthetic adapter PROCESS_EXEC B;
the unchanged verifier returns DIVERGED. It does not claim real host observation,
real adapter execution or real target mutation. No process runs, authority or
reconciliation changes, finding is persisted, host observer starts, or retry
occurs because of it. Results retain the existing factual vocabulary.

The small negative set checks malformed PID rejection, a forced missing PID
timeout with one real execution and runtime cleanup, no host evidence when a
registered child has not execed, and missing authorization. Synthetic private
reason text is excluded from chain/CET/host/findings/checkpoint and handshake
outputs. Existing lower-layer suites retain their detailed failure matrices.

This is not a universal sandbox, production handshake capability, all-process
observer, enforcement system, distributed exactly-once runtime, hostile-code
containment proof, or hardening program. RuntimeBinding, Agent Runtime, CET,
HostObserver, CrossLayerVerifier, Security Chain and Signed Checkpoint production
contracts remain unchanged.
