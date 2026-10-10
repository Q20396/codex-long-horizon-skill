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
Recovery is explicit GET-only reconciliation with current authority and the
original action/request identity. Credential replacement does not remove history.

Repository and branch GETs establish bounded provider assertions. PR response/
readback numeric repo IDs and OIDs are also checked; the existing adapter retains
its exact title/body/marker/branch matching and conservative pagination handling.
These reads are not an atomic snapshot or independent trust domain.
Lost synthetic responses are INJECTED_OBSERVATION_LOSS, not a reproduced real
network outage. Empty/ambiguous/invalid/auth-failed/incomplete readbacks do not
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

Original header RED: `/tmp/20396-h6-header-blocker-2026-10-10.md`.
Original material RED: `/tmp/20396-h6-material-red-final.log`, POST count 2 != 1.
These historical local logs are evidence locators, not packaged dependencies.

Tests cover headers, payload rejection, PR identity precision, UNKNOWN/completed
barriers, original-marker reconciliation, durable parsing, real baseline legacy
fixtures, unchanged legacy bytes, mixed history, old-reader refusal, actual
process termination/fresh interpreter recovery and controller contention.
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
