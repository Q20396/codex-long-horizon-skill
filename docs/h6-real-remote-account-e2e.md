# H6 PR_CREATE qualification — repository-only experimental slice

Base: `e266154d72b9aed5b1f426806eecbc60afdb3d0a`.

## Delivery and invocation

This is an explicitly invoked offline qualification harness, not an installed
client or a live-account launcher. Importing
`scripts/remote_account_qualification.py` does not read credentials or execute.
`qualify(manifest)` returns NOT_STARTED. A trusted host must separately provide
launch=True, a bounded OFFLINE_SYNTHETIC transport, an existing RSE Authorization,
policy stack, CET context, current time and trusted agent identity. Manifest data
does not grant authority. There is no CLI or ambient credential discovery.

The strict v1 manifest binds API origin, repository name/numeric ID, head/base and
expected OIDs, exact action/request identity and preapproved payload digest,
synthetic title/body/marker, effect scope, authority reference/expiry, finite
POST/GET/byte/time budgets, storage lifecycle/domain and credential source/scope.
Only primitive fields are accepted; unexpected fields or invalid commitments
reject before transport. Preflight identity reads may occur for a syntactically
valid but incorrect remote identity; they must never lead to POST.

Explicit synthetic credential headers enter the existing HTTPS credential
validator in memory and are used only with the trusted synthetic transport.
No credential is accepted via argv/environment/netrc/helper or written to reports.
The injected transport is trusted test code: its provenance label is not a
network sandbox or proof of TLS. Host callbacks must be bounded; they must not
connect to real services. No production credentials are authorized.

## Protected composition

One CrossProcessOwner controls DurableSecurityJournal, JsonlSecurityChain and
AgentRuntimeBridge. create=True is only for host-established genuinely new
storage; existing or corrupt storage never falls back to an empty journal.
Admission uses existing exact payload commitments, policy and authorization.
ATTEMPTED must be durable before the adapter can POST. A POST-attempt limit of
one applies, and persistent material barriers survive changed correlation IDs.
Authority time advances from the trusted host's initial time using monotonic
elapsed time. Manifest, authorization and policy are rechecked before/after
each transport call and before Bridge execution; expired readback is withheld
from reconciliation and cannot clear UNKNOWN. This is not an atomic wall-clock
transaction or a preemptive deadline over arbitrary trusted host code.
Recovery is explicit GET-only reconciliation with current authority and the
original action/request identity. Credential replacement does not remove history.

Repository and branch GETs establish bounded provider assertions. PR response/
readback numeric repo IDs and OIDs are also checked; the existing adapter retains
its exact title/body/marker/branch matching and conservative pagination handling.
These reads are not an atomic snapshot or independent trust domain.
Deliberately lost observations use the explicit trusted-test
InjectedObservationLoss exception and report INJECTED_OBSERVATION_LOSS, not a
reproduced real network outage. Other transport/validation exceptions remain
SYNTHETIC_TRANSPORT_OR_VALIDATION_FAILURE; no raw exception text is returned.
Each invocation separately reports adapter_response and get_readback (null/empty
when not observed), response SHA-256, HTTP status, total object count and at most
two numeric object IDs/numbers. These are bounded synthetic observations, not
adapter acceptance or reconciliation authority. Raw bodies/headers are omitted.
Independent corroboration remains NOT_VALIDATED. Empty/ambiguous/invalid/auth-failed/incomplete readbacks do not
clear UNKNOWN. No remote cleanup or automatic reconciliation/retry is provided.

## PR intended-effect identity

PR_CREATE alone uses deterministic existing canonical encoding of:
PR_INTENDED_V1, action class, normalized target, destination, provider, repository,
head, base, title, original body bytes and draft flag. Proposal/action/request IDs
are excluded from this duplicate-effect key. User body text is never stripped.
Request identity remains in exact payload digest and provider marker matching;
the material key never replaces execution authorization.

The fixed User-Agent `20396-remote-runtime-binding` is constructed inside the
PR adapter for POST and GET. Payload whitelist and generic NETWORK_REQUEST
behavior are unchanged.

## Durable binding v2 and legacy fallback

New Bridge bindings persist an explicit envelope with exactly:
format_version=2, effect_class, material_identity_version, digests.
PR_CREATE uses PR_INTENDED_V1; other effects use EXISTING_V1 without changing
their material computation. Digests remain the existing material/payload pair;
no body, raw authorization or credential is persisted. Metadata grants no power.

The new reader strictly distinguishes original two-digest lists from v2
envelopes. Unknown/missing fields, types, versions, unsupported effect/version
pairs and per-action identity conflicts fail closed. Legacy records are never
assigned v2 semantics. Mixed histories are parsed strictly, without modifying
old bytes. New metadata is append-only; no conversion service or sidecar exists.

Historical records lack effect class and reversible PR fields. They cannot be
mapped to an intended PR. A transaction-protected classification query returns
bounded copied metadata and a conservative historical barrier classification.
Any unclassified history beyond PROPOSED/BLOCKED denies new PR admission with
LEGACY_PR_MATERIAL_UNRESOLVED. Completed history is included. Even legacy
NOT_APPLIED cannot establish fresh authorization for a newly mapped intended PR;
its opaque history is not silently released. This restriction is PR-only.
No transparent migration or automatic unlock is promised. There is no supported
reset/path-change/credential-change mechanism to discard these barriers.

Classification, admission and execution retain the existing owner/transaction
scope. No new state machine or Security Chain format is introduced. Original
action/request semantics remain necessary for reconciliation; new proposal IDs
cannot supply evidence for old attempts. The old reader rejects v2 envelopes.
After v2 writes, do not downgrade or mix old/new writers in that storage domain.

## Evidence and limits

### Experimental observations and byte-bound evidence

The PR supervision candidate separately exposes DIRECT_WORKER_COMPLETION as
an observation-only diagnostic. It requires a completed framed protocol with
valid response envelope, parent ownership and one cleanup claimant, settled
launcher/cleanup, matching captured direct identity, zero-exit direct reap,
closed owned pipes and quiescent owner, plus unexpired current authority.
Missing facts, pending ownership, permission/timeout failures and expired or
denied authority produce UNKNOWN. This is trusted-host bookkeeping, not an
authenticated worker-image or immutable dependency-closure attestation.

DIRECT_WORKER_COMPLETION is not GROUP_EXTINCTION. The existing group status,
cleanup success predicate and transport quarantine remain separate: the
production cleanup path still records UNKNOWN and cannot accept a PR result
on the strength of this diagnostic. It grants no execution or reconciliation
authority and cannot release UNKNOWN/material retry barriers. Original action
and request marker are still required for explicit GET-only reconciliation.

Evidence is separate by bytes and scope, not a single blanket qualification:

| Evidence | Bound scope | Does not establish |
| --- | --- | --- |
| Historical finite fake/IPC and B3/P2 corrections | Original budget/handle, ownership and UNKNOWN assertions under recorded substitutes | Current native/full-suite PASS |
| Historical N9 PR-worker observations | Older frozen production/test bytes and selected predicates only | A refresh on this candidate or complete transport qualification |
| Four selected cross-process fixture cases, 2026-10-17 | Candidate input manifest `e4afecac3879a0711d4d1db96f5e85d697ad5487edcce121664c68ee11116790`; original assertions and separate normal-path qualification; three actual report approvals | Entire cross-process module, PR worker, negative cleanup paths or group extinction |
| External supervision finite validation | Supervision manifest `e198bbcd2c1d0ca07c649e0e86dcd11a1d77bfa485ef8b8fb567c28a597736b6`; input manifest `8413c39d81b9bc405ceadf77e3c7e43df0c10c18c80ebb8fae3fc59a738effe7`; 32 outer methods, 51 vector labels, 34 reference/entry records and three actual report approvals | Real wait/reap, signals, hard deadlines, all-descendant cleanup or executable final configuration |
| This B1/B2/B4 test/document correction | Static authorship only; final full-file manifest is external to the candidate | Tests, full regression or CI not run for these new bytes |

The cumulative P1 candidate contains five changed repository paths; this next
increment edits only the existing test and documentation paths. Copied Git HEAD
identifies the base, not the modified candidate. The original H6 base near the
top of this document is historical and distinct from that P1 lineage.

The four normal cases are fork-owner denial, fork-during-construction,
controlled-exec-child owner release, and parent-death UNKNOWN/recovery. Their
report SHA256 is `be5ee2fd9b48d7750553c801865e4e5455ae6ae99fce1ffa01e960d77c64fa65`;
native review completion SHA256 is
`b74a9edd16f9eaa88adc1e71147d2948598c07d1bd974db13d778ce8e0e2b5d0`.
The finite supervision report SHA256 is
`22d890c73a838eb5f00c2e9f6b9bc993b05a7c3944fd796431ec6adbc721b228`.
These are immutable external evidence locators, not packaged runtime inputs.
Original assertions, separate qualification and final archive completion must
not be conflated; a provisional archive record alone is not completion proof.

B1 preserves the actual launch class and exact original budget references,
with each stall/malformed mode in an independent fixture. B2 preserves
UNKNOWN/quarantine and the original handle: repeated POST is blocked and that
same quarantined wrapper cannot spawn GET (POST1/GET0). Generic-adapter trusted
original-marker GET/reconciliation tests remain separate and unchanged.

No evidence establishes that interpreter/imports/native resolver/TLS or host
cannot spawn descendants. External reaper absence is a cooperative-host premise,
not mechanically proven. Parent-only telemetry, root APFS metadata, cached child
exit and empty roots do not prove all child paths or descendants/group extinct.
No universal parent-death cleanup, hard realtime, real remote success,
exactly-once or production qualification is claimed. Historical EPERM cause
and resource state remain UNKNOWN; group UNKNOWN and quarantine stay preserved.
Real execution remains blocked. Final supervision execution configuration and
native/skip inventory require separate binding/review/authorization; fake GREEN,
native normal-path observations, review, merge or CI grant none of those effects.

Original header RED: `/tmp/20396-h6-header-blocker-2026-10-10.md`.
Original material RED: `/tmp/20396-h6-material-red-final.log`, POST count 2 != 1.
These historical local logs are evidence locators, not packaged dependencies.

Tests cover headers, payload rejection, PR identity precision, UNKNOWN/completed
barriers, original-marker reconciliation, durable parsing, real baseline legacy
fixtures, unchanged legacy bytes, mixed history, old-reader refusal, actual
process termination/fresh interpreter recovery and controller contention.
The creation/crash test persists a synthetic provider object before terminating
the client, then a fresh interpreter uses original-identity GET reconciliation;
the cumulative POST count remains one. Resource cleanup is owned by each
original fixture/production lifecycle, not a new outer reaper. The selected
normal native fixture paths have bounded cleanup observations; uncertain roots
are retained and no all-child or arbitrary-abrupt-exit cleanup guarantee follows.
Historical fixtures execute git-archived source at the exact base; they are not
fabricated by the new serializer. Test checkout needs that commit available
(existing CI fetch-depth=0). Synthetic services never establish real-account E2E.

The harness limits calls and bytes and checks elapsed time/cancellation at
boundaries. It cannot preempt an arbitrary trusted callback and does not bound
DNS. Live execution remains LIVE_EXECUTION_BLOCKED_UNBOUNDED_DNS_OR_TRANSPORT.
Existing storage/platform restrictions apply; no universal filesystem,
power-loss, anti-tamper, exactly-once or global deduplication guarantee is added.

DELIVERY: REPOSITORY_ONLY_EXPERIMENTAL
REAL REMOTE-ACCOUNT E2E: NOT_VALIDATED
REAL CREDENTIAL LIFECYCLE: NOT_VALIDATED
REMOTE INDEPENDENT CORROBORATION: NOT_VALIDATED
LOCAL FORMAL: BLOCKED_MISSING_DEPENDENCIES
H5 FULL ACCEPTANCE: NOT_COMPLETE
H6 FULL ACCEPTANCE: NOT_COMPLETE
PRODUCTION HARDENING: NOT_COMPLETE

Any later real validation requires separate exact account/repository ID,
head/base/OIDs, credential delivery/lifecycle, object/GET/byte/time budgets, cost,
retention, cleanup owner/actions and independent corroboration authorization.
All remain UNKNOWN here. A code delivery PR and CI are not provider validation.

## Selected live admission seam (not an enabled launcher)

`qualify()` and its v1 `OFFLINE_SYNTHETIC` contract remain unchanged.
`qualify_live()` is a separate, default-disabled admission function, restricted
to `https://api.github.com/repos/Q20396/20396-acceptance-sandbox`, a draft
synthetic PR, exact repository/ref/OID commitments, and live v1 metadata.
Preflight metadata must match these commitments and be at most 30 seconds old;
its provenance label is a trusted-host convention, not a signature or authority.
Repository identity and ref observations are not an atomic provider-side lock.

No approved host credential-delivery integration currently exists.
Consequently even valid live metadata returns
`BLOCKED_CREDENTIAL_CHANNEL_UNCONFIRMED`, with zero requests, no credential FD
read, and no journal creation. Missing/malformed metadata is rejected. Caller
flags, credentials, or a string claiming host provenance cannot remove this
gate. There is no execution/recovery branch behind the gate: enabling one
requires reviewed host integration and existing Bridge authorization, durable
ownership/material/legacy barriers, and the original prepared request identity.
This is admission groundwork, not completed live transport qualification.

Two reserved private seams have offline tests only. `_live_adapter` constructs
the exact existing `PullRequestCreateAdapter` and `PRCreateBoundedHTTPS` types;
it must eventually be registered directly through `RemoteRuntimeBinding` so
the original binding selects `_PRBudget`. No generic wrapper, subclass,
unbounded HTTPS fallback, callback carrying real traffic under a synthetic
label, or custom retry layer is permitted. `_read_live_credential` accepts an
explicit read-only FIFO-class FD (not standard FDs, regular files, argv,
environment, netrc, token export, or discovery), at most 8192 printable ASCII
bytes followed by EOF within a software five-second deadline. It closes the
owned FD on success/rejection and emits no token diagnostics. The disabled
public entry does not call it or take ownership of a supplied FD.
FIFO type/access cannot distinguish a named FIFO from an anonymous pipe or
identify its producer. Anonymous origin and trusted-producer binding remain
unimplemented prerequisites for the future host integration, not facts proven
by this helper. The final acceptance rechecks the original deadline after EOF;
no new timing interval or retry is started.

The proposed future producer is a user-approved existing password manager or
trusted host UI; its availability is **UNCONFIRMED**. A dedicated fine-grained
PAT should cover only this repository, PR read/write and metadata read, with
the shortest provider-supported expiry (at most 24 hours), and a host authority
window at most ten minutes. Actual required scopes/expiry must be confirmed;
no automatic scope expansion or token creation is implemented. The host/user
must revoke it after success, failure, cancellation or UNKNOWN and provide
non-secret lifecycle evidence. Python token strings and worker memory are not
guaranteed erased. Closing a pipe or terminating a process is not revocation.

Proposed live ceilings are one PR POST, ten total GETs including other-client
readback, 120 seconds overall software budget, and the existing per-operation
30-second worker budget including its cleanup reserve. The admission manifest
limits title/body to 128/4096 UTF-8 bytes, individual response limit to 256 KiB,
and authority expiry to ten minutes; it does not yet enforce a live aggregate
counter because execution is disabled. Lower core limits still apply. No
hard-real-time DNS, all-descendant extinction, or universal transport guarantee
follows. Unconfirmed cleanup stays UNKNOWN/quarantined under the original
handle owner; no group reaper or takeover is added.

Post-creation readback from another client to GitHub would be same-provider
cross-observation, not independent retention or third-party corroboration and
not reconciliation authority. Actual lost-response recovery, if it occurs,
must be explicitly authorized GET-only reconciliation of the original action,
marker and journal; no automatic POST retry or replacement identity is allowed.
Do not deliberately create a second PR to collect recovery evidence. Existing
UNKNOWN, completed material barriers, legacy fences, and journal bytes are not
changed by this admission code. No real request, credential lifecycle,
independent corroboration, fee precheck, remote cleanup, or live recovery is
validated by these offline tests. No remote objects are created here; journal
and evidence retention/cleanup require their existing explicit authority.

## Human-operated host execution and fixed prepaid phases

The legacy `qualify_live()` admission-only API remains blocked. The separate
`run_live_host()` entry and `--live-create-once /absolute/manifest.json` /
`--live-recover-once /absolute/manifest.json` CLI now implement the selected
human-operated path. Import/default calls perform no execution. These commands
must **not** be run merely because offline implementation/review passed: live
authorization, an actual isolated sandbox/repository ID/ref OIDs, validated
platform/transport prerequisites and the user's credential steps remain gates.

Only a user at a trusted real local `/dev/tty` may confirm the displayed exact
manifest digest/scope and trusted clock/storage/revocation responsibilities,
then enter a dedicated repository-only PAT through `getpass` with echo disabled.
No TTY, active signal supervision, input timeout, warning indicating fallback,
incorrect confirmation, malformed secret, or unsupported terminal means reject.
There is no stdin/env/argv/file/netrc/connector-token source or caller-provided
credential/host-confirmed flag in this entry. No agent-driven PTY, Terminal UI
automation or chat token transfer is part of this path. The input software
budget is 60 seconds; submitted tokens are limited to 8192 printable ASCII
characters, without claiming bounded hostile terminal input allocation or
Python memory erasure. The old private FIFO helper is not this host producer.

Create the authorized `Q20396/20396-acceptance-sandbox` and synthetic base/head
branches **before** creating its fine-grained PAT. Repository/bootstrap writes
use an existing authorized safe connector or the user's GitHub UI, not the
execution credential. The latter is limited to PR read/write, metadata read
and necessary contents read, shortest supported expiry at most 24 hours. The
user must revoke it after every success/failure/UNKNOWN and supply only
non-secret lifecycle evidence; neither expiry, process exit nor HTTP 401 proves
revocation. Recovery may use a replacement token without changing the original
action/request/material identity or journal. No token generation/revocation is
automated. Account/cost/resource conflicts stop rather than expanding scopes.

The canonical non-secret manifest is owner-only, no-follow, bounded JSON using
the live v1 fields. It must specify an already established private empty
storage directory for first create (0700, same trusted owner); an existing
session is never reset or re-created. Host code builds the exact context,
prepared action, policy and current authorization after human confirmation.
Original prepared time and digest are saved for deterministic recovery; saved
JSON and authority labels themselves grant no permission. Policy allows only
the exact PR action/target on the sandbox. The original exact adapter and
`PRCreateBoundedHTTPS` are registered directly through `RemoteRuntimeBinding`
and `AgentRuntimeBridge`; no wrapper/subclass or unbounded HTTPS fallback is
used. Metadata GETs have their own explicit original `_PRBudget` under that
same scoped authorization, not a general network capability.

`PRCreateBoundedHTTPS` adds a private qualification context restricted to this
fixed repository, exact head/base refs and an already observed/matched positive
integer PR number. Parent and worker validate canonical URL, method and empty
GET body. Only repo metadata, those two branch endpoints, the exact PR list,
and that bound PR object are permitted. Encoded alternate spellings, query
injection, other origins/repos/refs/numbers and metadata POST are rejected.
The original PR POST/recovery route, protocol/GO, TLS, fixed User-Agent, original
handle cleanup/ownership and general NETWORK_REQUEST behavior remain intact.
HTTP redirect/pagination and partial or identity-mismatching results do not
promote acceptance. Ref reads and POST are not an atomic provider transaction.

The new host auxiliary state is explicitly separate from RSE journal and
Security Chain: `session.json` (at most 32 KiB) binds the manifest, source hashes,
prepared/material digests, original time and directory device/inode. Two fixed
`create-reserved.json` and `recover-reserved.json` records (at most 4 KiB each)
are written once with O_EXCL/no-follow, full-write verification, file fsync and
parent-directory fsync while the original storage owner is held. Any failed,
short, conflicting or corrupt record is retained and fails closed. A reserve
consumes the **whole** phase allowance even if no request was sent; no refund,
restart of the same phase, journal migration/reset, or automatic repair exists.
Missing or untrusted lifecycle state cannot mean a new safe session. Local
rollback/deletion/malicious-controller attacks are not prevented.

Create prepays at most 8 GET + 1 PR POST, 1 MiB worst-case response reservation
and 60 seconds software operation time. Recover prepays 2 GET + 0 POST, 1 MiB
and 60 seconds. The total session allowances are therefore at most 10 GET,
1 PR POST, 2 MiB and 120 cumulative phase-operation seconds; unused allowances
are not borrowed. Core limits are charged before launch, including uncertain
sends, using the full response limit with no error refund. Phase deadlines
clamp the existing 30-second per-operation budget including original cleanup
reserve. The session expires within ten minutes on the explicitly trusted host
clock; backward/expired observations fail closed, without claiming hostile
clock anti-rollback or including offline time between phases in the 120 seconds.

Create performs repo/head/base GETs twice, then the single original Bridge
execute. Success may use the remaining two GETs for list/object readback.
Recovery uses only original Bridge reconciliation GET plus the bound object
GET; no execute/POST branch is called. Existing legacy fences, durable-before-
effect, UNKNOWN/completed material barriers and exact original marker remain.
The phase's immutable outcome record binds finite cleanup facts. A missing
outcome after an abrupt failure, or unresolved cleanup, blocks recovery rather
than assuming old worker extinction. There is no group reaper or ownership
takeover. A crash can exhaust a phase without producing useful evidence.

Readback implemented here is explicitly **same-provider/same-client** bounded
observation. There is no invented bridge to export connector credentials or
invoke the connected client from a local process; independent client/provider
corroboration remains NOT_RUN/NOT_VALIDATED. An external observation, if later
authorized, must be budgeted separately rather than silently appended to an
already consumed phase. No new real-account, native worker, credential
lifecycle, independent retention, billing or full-suite evidence follows from
offline tests. Failed/UNKNOWN effects are not retried with another ID/token.

Before user invocation: obtain final reviewed source/manifest, actual sandbox
identity/refs, confirm all remaining live/platform/cost gates, prepare the
private canonical manifest/storage, then the user alone confirms the digest
and enters the dedicated token at the real terminal. Do not run these steps
now as part of offline delivery. Keep remote repo/PR/branches and local journal/
evidence until explicit DA disposition; no merge, close/delete, deployment or
background retry/monitor is implemented.

## Selected direct-worker private completion (cooperative host only)

The H6 host explicitly opts the original exact transport into a default-off
`selected_direct` private mode, available only with the existing exact
qualification limits and fixed sandbox/ref commitments. Model payloads,
diagnostic strings and network responses cannot select this mode. All other
transport users keep the original default group-cleanup acceptance behavior.

Current-response admission reuses the actual original launch, process handle,
sole parent claimant, immutable direct-finalization record and paired legacy
record. The protocol budget must be the same object as both original request
budget references, and the process/identity/records must remain paired. Only
the existing normally terminated READY/request/ARMED/GO/result/ACK/EOF path can
seal the protocol; malformed/rejected/unsealed/abort paths do not qualify.
Return code must be exact int zero, reaped/pipes-closed/quiescent and both
launcher/cleanup notifications true, direct outcome COMPLETE, no errno, and
original deadline/authority still valid at acceptance. The original budget's
2-second cleanup reserve and sole original-handle waiter are unchanged.

This decision does not consume the public `DIRECT_WORKER_COMPLETION` string as
authority. It neither changes legacy `cleaned`, group/status/phase nor promotes
group extinction. Each selected terminal launch stays CLEANUP_UNKNOWN with
UNKNOWN group quarantine. Complete response framing still must pass the old
status/body/identity checks; direct completion is not effect success or retry
permission. Any protocol, record, identity, wait, pipe, deadline, authority or
ownership uncertainty fails closed. Oversize rejection and nonzero/unsealed
diagnostics never become selected normal completion.

Next-request admission may reuse only finite already-accepted direct terminal
facts from that same phase and exact payload identity. Original launch/handle/
budget/paired-record references are retained in a bounded private history
(at most9 create or2 recover), so replacing the current pointer cannot erase
old group-UNKNOWN quarantine facts. An unfinished or modified prior state
blocks the next worker. Historical acceptance does not reset old deadlines or
authorize a new effect: each new call still checks its own current policy,
budget and prepaid counters. No group reaper, handle takeover or new ledger is
introduced; history is not cross-process coordination or hostile-host proof.

Host auxiliary outcomes now use strict private `20396.h6.outcome.v2`, binding
the same session digest with `direct_completion`, `group_cleanup=UNKNOWN` and
`descendants=UNKNOWN`. Direct completion is either
SELECTED_DIRECT_WORKER_COMPLETE, reliably NO_WORKER_LAUNCHED, or UNKNOWN.
Legacy v1 is not automatically migrated, rewritten or promoted. Recovery
accepts only the first two validated finite conditions for the exact original
session, then still requires current authorization, original journal/request
and the single GET-only recover slot. Missing/corrupt/UNKNOWN outcomes remain
blocked, including uncertain crash cleanup. Material/legacy/UNKNOWN barriers
and no-refund phase reservations are unchanged.

This selected change requires same-object native qualification after its
finite offline review. Old native receipts or another manifest do not qualify
new worker behavior. Native process/pipe tests with synthetic child HTTP still
do not prove real DNS/TLS/provider behavior, independent corroboration, PAT
lifecycle or production acceptance. No live invocation is authorized by this
code/documentation or its offline tests.
