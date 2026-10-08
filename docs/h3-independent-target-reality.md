# H3 — Independent local artifact observation

Authorized base: `13e536b923ff062b8cca746d735caeb78508c8d1`.
Selected slice: **INDEPENDENT LOCAL ARTIFACT OBSERVATION**.
Delivery: **REPOSITORY_ONLY_EXPERIMENTAL**. Independent review and exact-candidate
CI are separate gates; implementation and local checks do not authorize merge.
This collector lives in repository `scripts/`, outside the installed package.
No client installation, runtime activation, release, or H4–H9 work is included.

## Contract and trusted inputs

`scripts/independent_target_reality.py` provides `bind_request`, `collect`, and
`matches_request`. The trusted controller calls `bind_request` **before** the
governed action. It fixes a private, canonical absolute root, relative target,
expected byte size and SHA-256 digest, attempt reference, scope reference, and
finite byte limit. The root must belong to the local user and exclude
group/other permissions. The controller supplies a canonical root without
symlink components (on Darwin, `/private/tmp`, rather than `/tmp`). The collector
does not resolve a model-selected path into an approved one.

Prebinding opens and validates only the root ancestry, pins the root device/inode,
and assigns a fresh request reference. Root creation/change of directory mtime
does not itself invalidate a request: directory identity and permissions are
checked, while expected target creation remains possible. The controller retains
the request; a proposal cannot choose observation paths or grant independence.
Each request covers exactly one file, not a process tree or all effects.

After the action, the caller independently calls `collect(request)` and checks
`matches_request(current_trusted_request, observation)` before consuming evidence.
Both collector and helper first verify that root/target reference hashes still
describe the request's actual paths; modifying a raw target while keeping the
old label cannot substitute matching bytes from another file. The helper compares
root reference/device/inode, target reference, attempt,
scope, fresh request reference, expected size/digest, and limit. Substituting a
prior request's result, even with the same attempt label, fails this check.
Checking an attacker-supplied request against an attacker-supplied result would
not establish the trusted binding. This is no authentication framework, global
replay registry, persistent ledger, or same-request replay defense. The host,
collector implementation, and caller-supplied inputs remain trusted.

Requests suppress root/target paths in `repr`. Results contain hashed root/target
references and metadata, never raw contents or absolute paths. Callers must not
serialize the private request's raw `root`/`target` fields or supply sensitive
identifiers as reference labels. Errors use fixed codes, not host exception text.

## Observation, expectation, and causality

| Observation | Expectation | Meaning |
| --- | --- | --- |
| `OBSERVED` | `MATCH` | A bounded read of a regular file matched the separately stored expected size/digest. |
| `OBSERVED` | `MISMATCH` | Actual read was valid; actual size/digest remain available and differ from expectation. |
| `UNKNOWN` | `UNKNOWN` | Missing, denied, nonregular, oversized, changed/replaced, or ambiguous target; no valid observed digest. |
| `UNSUPPORTED` | `UNKNOWN` | Necessary descriptor-relative/no-follow/nonblocking primitives unavailable; no weak fallback. |

`process_authorship` is always `NOT_PROVEN`; `retry_authorized` is always false.
A preexisting matching file proves only matching observed bytes. Exit code zero,
wait/reap evidence, RuntimeOperationEvidence, CET, expected digests, and model
output never supply or replace observed bytes. Missing/mismatching files do not
mean `NOT_APPLIED`. No observation grants retry, clears an unresolved action or
material reservation, calls reconciliation, or writes journal/chain state.

## Descriptor and read boundary

The collector opens ancestry component by component relative to held directory
descriptors with `O_DIRECTORY`/`O_NOFOLLOW`/`O_NONBLOCK`, starting at `/`. It checks
the root pin and ownership/permissions. Absolute or noncanonical relative targets,
empty components, `.`/`..`, traversal, and symlinks are refused. The final open
also uses `O_NOFOLLOW`/`O_NONBLOCK`; a FIFO cannot block waiting for a writer.
Only an `fstat`-confirmed regular file is read; directories, FIFO, socket, and
device types cannot become valid observations.

Reads use at most 64 KiB chunks and consume at most `max_bytes + 1` bytes, with
an overflow sentinel. Limits are positive integers capped at 16 MiB. Initial stat
size is only an early rejection, never permission for unbounded reading. The
collector compares device/inode/type/owner/group/link count/size/mtime/ctime on
the same file descriptor before and after reading, confirms actual byte count,
rechecks the final pathname's identity and metadata, and rechecks each held
directory and its parent-relative pathname. Detected change/replacement returns
UNKNOWN and discards the digest. Descriptors close on normal and error paths.
If an OS close reports an error, all remaining closes are attempted and the
observation becomes UNKNOWN/CLEANUP_UNCERTAIN. An ambiguous close is not retried
because a concurrent thread could reuse its descriptor number. Actual resource
release after an OS-failed close cannot be guaranteed or classified as success.

These checks do not provide an atomic snapshot under concurrent writers, detect
all same-user ABA activity, authenticate hardlink provenance, or secure arbitrary
filesystems/hostile kernels. Independence describes data provenance and collection
path, not a different kernel or security principal. Finite byte reads are not a
wall-clock guarantee on a stalled filesystem or hostile kernel.

## Integration and preserved gaps

The six existing Phase 5 exit-only scenarios retain their vocabulary and coverage.
New, independently named artifact scenarios execute a controlled no-network
process through the existing bridge/RSE/RuntimeBinding/ProcessAdapter path once,
then collect file evidence separately. No `FILE_WRITE` host event, file material
effect identity, native coverage, or all-layer MATCH is fabricated. Native
`NOTE_EXEC` remains registered-process `PROCESS_EXEC` evidence only. A file
postcondition cannot fill the existing verifier's process-effect slot without
losing these semantics; it stays separate and that slot remains UNKNOWN.

H1 sync failure and H2 actual owner contention still prevent execution. A real
controller crash after file creation/before outcome recording leaves a matching
file, but fresh journal recovery retains ATTEMPTED. The H1 legacy durable-binding
recovery returns UNKNOWN_OUTCOME. The H2 coordinated bridge denies material replay
with RECONCILIATION_REQUIRED/NOT_ATTEMPTED before entering RSE; this refusal to
execute does not classify the original unresolved effect as absent or failed.
Independent collection neither mutates durable evidence nor clears the barrier.

## Verification scope

RED tests were run before collector implementation: missing capability assertions,
not import typos or changed old UNKNOWN expectations. Collector contracts cover
actual A/B digests, missing files, exact/overflow bounds, path/type errors,
deterministic descriptor and pathname replacement, wrong/old bindings, inactive
import, read-only behavior, and descriptor cleanup. Fault injection is confined to
test-side low-level calls; production has no race hooks. FIFO/socket/regular-file
checks are real; device classification uses a stat substitute because privileged
device creation is outside the experiment. Permission denial uses a deterministic
open error, independently from real no-follow checks.

Darwin/APFS runs are actual local validation. Linux collector tests are discovered
by existing CI; local Darwin results do not establish Linux PASS. Linux native
NOTE_EXEC tests remain NOT_RUN via their existing platform skips, not collector
substitutes. Exact-SHA `check-skill`/`formal-schema-gate` and three independent
reviewer verdicts must be retrieved separately. Main schema-integration PASS is
distinct from controlled formal evidence NOT_GENERATED and local formal
BLOCKED_MISSING_DEPENDENCIES; no dependencies are installed to change that state.

```text
H3 SELECTED SLICE: INDEPENDENT LOCAL ARTIFACT OBSERVATION
DELIVERY: REPOSITORY_ONLY_EXPERIMENTAL
OBSERVED: BOUNDED FILE BYTES / IDENTITY AT OBSERVATION
PROCESS AUTHORSHIP: NOT_PROVEN
PROCESS IMAGE IDENTITY: NOT_IMPLEMENTED
ALL EFFECTS VERIFIED: NO
HOSTILE KERNEL INDEPENDENCE: NO
AUTOMATIC RECONCILIATION: NO
G03: PARTIALLY_IMPLEMENTED (H2 boundary unchanged)
G05: PARTIALLY_IMPLEMENTED
MERGE: NOT_PERFORMED
H4–H9: NOT_STARTED
PRODUCTION HARDENING: NOT_COMPLETE
```
