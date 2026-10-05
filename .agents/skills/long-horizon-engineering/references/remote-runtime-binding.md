# Bounded Remote Effect Binding — Phase 2B

Status: **experimental, explicitly constructed, same-process only**. This module
can emit real remote effects when a trusted host explicitly wires it up. Import,
installation, a test pass or a receipt alone is not deployment, independent
execution proof or authorization.

## Scope and trusted boundary

`scripts/remote_runtime_binding.py` adds only `NETWORK_REQUEST`, `GIT_PUSH` and
`PR_CREATE`. It reuses RSE policy, authorization, capability broker and journal;
Critical Execution Trace (CET); and Security Chain. The existing capability names
are `network.request`, `git.push` and **`github.pr.create`**. The last name is
preserved for compatibility, not replaced with a new `pr.create` alias.

There is no PR merge/update, release, deployment, package-install, service-control,
secret-store, SSH, Paperclip, Codex runtime-hook or Local Compute adapter. No new
policy engine, generic retry scheduler, durable remote ledger or host observer is
introduced. Core-only and legacy profiles ship the same inactive module/reference.

The host controller owns approval, broker registration, transport construction,
credential custody, approved origins, actor, clock and the lifecycle of the
journal/chain. A hostile host, adapter or transport is outside this boundary.
Do not expose these trusted construction inputs as model-controlled parameters.

## Preauthorization contract

`RemoteRuntimePayload` is a frozen, repr-suppressed value. Its digest commits every
field, with body bytes represented by their SHA-256 digest. It binds action ID,
action class, exact destination and query, method, non-secret headers, body,
request identity, limits, reconciliation identity and the applicable Git/PR
fields. Mutable containers are rejected. Raw bodies are trusted execution input,
not receipt/trace fields; do not put secrets in any payload field.

The trusted controller validates the intended payload **before authorization**
and supplies a copied approval snapshot to:

```python
binding = RemoteRuntimeBinding(
    broker, journal, chain, runtime_actor,
    approved_payload_digests=previously_approved_digests,
)
result = binding.execute(
    action, payload,
    policy_stack=policies,
    authorization=authorization,
    context=trace_context,
    now=trusted_time,
)
```

This is a call-shape illustration, not an executable authorization recipe.
Do not fill the approval snapshot from the incoming execution payload, and do
not treat `payload.digest()` as an approval decision. The action and payload IDs,
classes, targets and request identities must agree. Authorization does not install
a capability; registration does not authorize execution. An empty broker remains
empty after import. Adapters cannot be invoked through plain RSE without binding.

## HTTPS requests

Construct `NetworkRequestAdapter(transport=..., allowed_origins=(... ,))` only in
trusted host code. `HTTPSRemoteTransport` is the included direct HTTPS transport.
Its optional `credential_headers` are opaque host-supplied authentication headers,
never payload fields. No Keychain, `.ssh`, `.netrc`, environment token, proxy or
credential-helper discovery occurs. Do not log a transport's private state.

Supported methods: GET, HEAD, POST, PUT, PATCH, DELETE. Mutation identity is fixed
before authorization; the transport uses the same identity for a supported
idempotency-key contract. Such a header is not evidence that a provider honors
it. If the provider has no reliable readback/duplicate-suppression contract,
UNKNOWN can remain unresolved indefinitely.

Limits are finite: request body at most 8 MiB; response body at most 8 MiB (a
payload can lower it); non-secret request headers and response headers at most
64 KiB; the included transport also bounds combined host/non-secret request
headers to 64 KiB. Timeout defaults to 30 seconds and cannot exceed 120. Request header
names are deliberately restricted to Accept, Content-Type and X-GitHub-Api-Version.
Authorization/Cookie headers cannot be put in the payload. Authentication headers
are host state. Error reasons are fixed codes, not raw transport exceptions.

The destination policy is conservative:

- HTTPS only, no userinfo or fragment; exact trusted origin, no wildcard.
- Host case, explicit/default 443 and IPv6 textual representation are normalized.
- Empty path becomes `/`; escaped paths, dot segments and repeated slashes are
  rejected rather than guessing provider normalization.
- Query is a separate payload field. Ordering and duplicate keys are preserved;
  percent-escape hex case is normalized for sending. Query changes remain bound.
- No redirect is automatically followed, including same-origin redirects.
- TLS certificate and hostname verification stay enabled; no insecure option.

Origin allowlisting is **not** a generic SSRF defense or network sandbox. Trusted
operators must choose destinations intentionally. This does not establish that
DNS resolves to public addresses, prevent DNS rebinding, prove CA/server integrity
or prevent a trusted provider from causing its own further effects. Host resolver
behavior is not independently observed. The socket timeout and response-read
deadline do not provide a hard wall-clock bound on the operating system's DNS
resolver; no resolver process or background timeout worker is installed.

Mutation transport failures after a possible send, response parse/size failures,
redirects and non-success responses are conservatively UNKNOWN. Only a proven
pre-send rejection is a clean no-effect failure. A successful response is
provider/adapter evidence, not independent proof of all downstream effects.

## Exact Git push

`GitPushAdapter` requires a trusted workspace root, pinned Git executable,
transport and allowed origins. A payload binds the repository, remote name,
canonical remote URL (included in the payload/destination digests), local branch,
remote branch, exact old remote OID and exact new local OID.

The supported subset is intentionally small: an **existing SHA-1 branch** updated
fast-forward to an already available local commit. No branch creation, deletion,
force/non-fast-forward, tags, mirror/all push, SHA-256 remote protocol, fetch,
pull, clone, SSH or helper fallback. The old remote commit must already exist
locally so ancestry can be verified without fetching.

Local Git runs through the hardened Phase 2A launcher and controlled environment,
with Git transport protocols denied. Unsafe metadata/configuration, includes,
hooks/helpers, filters, URL rewrites, proxies, credential helpers and lazy-fetch
paths are rejected. The narrow private stdin extension is used only to supply
exact revision input for bounded pack generation (at most the existing local
capture limit of 1 MiB); ordinary local operations keep
DEVNULL stdin. This does not grant arbitrary model-controlled process input.

Ancestry decisions require no local graph overrides: any nonempty
`.git/info/grafts` file (including malformed, whitespace-only or comment-only
content) and any `refs/replace/*` entry (loose or packed, even irrelevant to the
selected commits) are rejected with `GIT_ANCESTRY_OVERRIDE_PRESENT`. An absent
or zero-byte regular grafts file is allowed. Loose namespace presence is checked
even when Git would ignore malformed ref contents; packed refs are enumerated by
the hardened Git command. Graft contents are not read into evidence or errors.
These checks precede local commit resolution, ancestry validation and pack
generation, and are repeated before mutation. Actual local Git subprocesses
retain `GIT_NO_REPLACE_OBJECTS=1`; their clean environment excludes caller-supplied
graft/replacement/config injection. This is a bounded integrity check, not a
general proof against every Git graph mechanism or concurrent hostile filesystem
mutation between checks; the trusted host must control the workspace throughout.
Under those assumptions and with these overrides excluded, Git's own ancestry
commands validate the actual commit-object graph; this is not an independent
graph-parser proof or a guarantee against every Git implementation bug.

Remote discovery and update use a minimal HTTPS smart-protocol exchange, not a
Git network subprocess. The update packet carries **both old and new OIDs** and
one exact ref; this supplies server-side old-value protection in addition to
local fast-forward validation. Local source, configured URL and remote old OID
are rechecked before emission. Invalid or unexpected protocol responses after a possible
update become UNKNOWN. No attempt is made to bypass server hooks/policy.

Protocol references: [Git HTTP protocol](https://git-scm.com/docs/gitprotocol-http)
and [Git pack protocol](https://git-scm.com/docs/gitprotocol-pack).

Git reconciliation reads the prebound remote ref: exact new OID means applied;
exact old OID means not applied; a different OID is conflict; unavailable or
malformed evidence remains unknown. This is a point-in-time observation, not a
proof that a transient update was never applied and later reverted.

## Pull request creation

`PullRequestCreateAdapter` supports a GitHub-compatible create/readback contract
at an explicitly allowlisted API origin, not an arbitrary provider dispatcher.
The payload fixes provider `github`, repository, same-repository head/base,
title, body, draft and stable request identity. The endpoint must exactly match
`/repos/<owner>/<repo>/pulls`. Cross-repository fork creation is not supported.

The title is at most 256 UTF-8 bytes and supplied body at most 64 KiB. The adapter
adds a deterministic request-identity HTML comment to the body; that transformation
is part of the adapter contract, not a model-selected post-authorization change.
The response must match the exact contract and contain stable positive PR IDs.
Evidence stores ID/body/response digests, not raw provider responses.

After a lost response, a second create is blocked. Reconciliation is GET-only,
bounded to one complete page (fewer than 100 entries, no pagination link). Exactly
one matching contract/identity can establish success. Empty results, multiple
matches, incomplete pages and mismatches remain unknown; they do not authorize a
new create. There is no PR update, merge, close, review or release operation.

## Recovery, concurrency and evidence

Use `binding.reconcile(action, payload, policy_stack=..., authorization=...,
context=..., now=...)` with the original prebound payload. Policy and authority
are checked again. Reconciliation never issues a mutation. Generic network
readback is optional: a prebound same-origin GET target/query plus exact expected
response digest can prove a match; absent/mismatching/empty readback does not
prove non-application. Git and PR have the bounded strategies above.

Readback evidence is captured before body interpretation. `request_attempted`
describes the current reconciliation GET reaching the transport boundary, not
a second mutation or proof that bytes were sent. It stays false when no readback
is configured or the request is rejected before that boundary. Each call keeps
its own observations; adapters retain no shared mutable response state.

`response_observed` becomes true only after an HTTP status/response has actually
been observed; its `status_code` survives later framing, body or semantic parsing
failure. The included HTTPS transport also retains a parsed status line when
subsequent header parsing fails. A timeout without response metadata keeps
`response_observed=false` and `status_code=None`.

Two additive evidence fields distinguish body completeness and parsing:

| Observation | `response_body_complete` | `response_digest` | `response_parse_status` |
|---|---|---|---|
| No response metadata | `None` | `None` | `NOT_ATTEMPTED` |
| Observed status, incomplete/over-limit body or rejected headers | `false` | `None` | `NOT_ATTEMPTED` |
| Complete bounded body, malformed JSON/protocol | `true` | SHA-256 of full body | `PARSE_FAILED` |
| Complete bounded body, valid but ambiguous PR list | `true` | SHA-256 of full body | `PARSED` |
| Generic network digest readback (no semantic parser) | `true` | SHA-256 of full body | `NOT_ATTEMPTED` |

`response_digest` never denotes a partial body or a Git OID. Incomplete bodies
have no digest; Git's resolved-ref digest uses `resource_digest`. `PARSED` means
the expected representation/container was interpreted, not that a resource
matched or an effect was proved. An observed non-2xx response retains its status
and any complete bounded body digest, while reconciliation stays conservative.
An HTTP 200 with malformed PR JSON therefore reports response observed, status
200, complete body and `PARSE_FAILED`, while remaining `STILL_UNKNOWN`. Repeating
execution is still blocked; readback never creates another PR.

The same additive fields describe the existing execution response where one is
captured: network requests have no semantic parser, PR creation parses its JSON
object, and Git push parses its mutation report-status response. Git preflight
lookups remain separate from that mutation response. Evidence contains only
bounded status/boolean/enum values and digests; raw bodies and exception text do
not enter receipts, CET or Security Chain. The existing chain anchors the updated
evidence digest without a schema or authorization change.

An UNKNOWN action stays pending and execution returns `UNKNOWN_OUTCOME_PENDING`
without another mutation. Reconciliation reporting not-applied does not itself
retry; a subsequent explicitly authorized execution is a new controller decision.
Conflicting identities on an existing action ID are rejected. Same-action calls
are serialized; distinct actions can wait on different remote operations without
holding a global network lock. Host integrations must retain the same journal.
The legacy transaction API is retained. Mixed legacy/action-scoped calls reserve
the attempt atomically; nested legacy lock-order conflicts fail closed rather
than waiting on a remote action while retaining the global journal lock.
This lock-order safeguard uses CPython's RLock ownership check; unsupported lock
ownership introspection fails closed. Legacy custom journals without action locks
retain global serialization through the existing transaction fallback.

The generic RSE journal is **same-process only**. Process crash, restart or journal
replacement loses in-memory retry protection. A retained Security Chain does not
reconstruct remote action lifecycle automatically. Do not replay uncertain work
after a crash as if it were fresh; require operator/provider reconciliation.
There is no crash-durable exactly-once guarantee.

`RemoteRuntimeResult` carries a receipt, bounded digest-only
`RemoteOperationEvidence`, CET events/divergences and boundary status. A transport
attempt is not proof that bytes were sent; a response is not claimed unless it
was observed. CET source is `ADAPTER_OBSERVED`, not `HOST_OBSERVED`, and coverage
remains partial. The chain seals evidence digests; it does not fabricate token
usage, signed checkpoints or external-anchor acknowledgements. Chain recording
failure after possible mutation preserves uncertainty and blocks blind retry.

## Validation boundary

Tests use synthetic transports/providers and temporary Git repositories, including
a test-only transport feeding production protocol bytes into local receive-pack.
They do not mutate real external accounts, use real credentials, install network
services or perform a production deployment. Installed-core tests guard network,
DNS, subprocess, thread, discovery and environment side effects during import.
These tests are implementation evidence; independent final-SHA review and CI are
separate gates and must not be inferred from this document.
