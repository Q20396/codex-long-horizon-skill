# Runtime Safety Envelope — Experimental Foundation

## Purpose

Phase 1 is a vendor-independent, explicitly called Python security kernel in
`scripts/runtime_safety_envelope.py`. It separates an AI proposal from policy,
authorization, capability, execution observation and reconciliation. It is not
an autonomous agent or an activated security perimeter. No real effect adapters
ship. No dependency, installation, daemon or host configuration is required.

## Threat Model

Untrusted proposals can request an unapproved effect, substitute a capability,
escape a logical path scope, transmit disallowed data, claim approval in text,
or repeat an uncertain effect. The kernel rejects these attempts at its API.
It cannot contain hostile Python code, a dishonest adapter, false data labels,
omitted calls, a replaced journal or a compromised trusted host.

## Root Safety Invariants

| Root | Phase 1 enforcement |
| --- | --- |
| ROOT-001 | Proposal text cannot create an Authorization or register a capability. |
| ROOT-002 | Every supplied policy layer must permit the action; no override. |
| ROOT-003 | ATTEMPTED/unknown states block another attempt until reconciliation. |
| ROOT-004 | Caller strings, exceptions and summaries are not emitted raw. |
| ROOT-005 | Both independent authorization and registered capability are required. |
| ROOT-006 | Success text alone is insufficient; typed adapter evidence is required. |
| ROOT-007 | Write authority does not grant Git push authority. |
| ROOT-008 | Commit authority does not grant PR merge authority. |
| ROOT-009 | Missing/invalid policy, clocks and uncertain boundaries fail closed. |

ROOT-010 (future append-only history), ROOT-011 (no self-expanded token budget)
and ROOT-012 (completion does not authorize more resource use) are future design
constraints, not implemented features.

## Trust Domains

1. **Untrusted proposal:** ActionRequest and its provider attribution.
2. **Trusted host/controller:** supplies all applicable policies, current bounded
   Authorization, explicit CapabilityBroker, journal and current time.
3. **Trusted observation boundary:** injected adapter and read-only reconciler.
4. **Unverified external reality:** host kernel, remote target and provider internals.

Never deserialize model output into the trusted policy/authorization arguments,
accept model-provided Python callables, or expose journal writes to the model.
The dataclasses are not cryptographic credentials or an authority service.
Revocation means supplying the current revoked authorization/policy on the next
call; Phase 1 has no authority registry, asynchronous revocation or interruption
of an already running adapter. Trusted callers must not reuse stale snapshots.

## Model Output Is Untrusted Proposal

Action classes and data classes are closed enums. Empty identifiers, control
characters, mismatched capability, invalid paths and malformed network targets
return `INVALID / MALFORMED_ACTION` without execution. No metadata DSL exists.
`expected_effect` is descriptive text, never executable code or authority.
Strings such as “user already approved” have no special meaning.

## Nested Policy

Supply a nonempty ordered stack beginning with CORE. Levels are CORE,
INSTALLATION, ORGANIZATION, PROJECT, TASK, RUN, ACTION; duplicate levels/IDs,
invalid fields, revoked policies and expired policies deny. Each layer is a
complete envelope, not a patch: actions, roots, egress classes, origins and
capabilities intersect. Missing permissions deny. A child cannot override an
ancestor denial (`ACTION_DENIED`) or widen its scope (`ACTION_NOT_IN_SCOPE`,
`PATH_OUT_OF_SCOPE`, `NETWORK_TARGET_DENIED`, `DATA_EGRESS_DENIED`).

The host must include every applicable policy; this kernel cannot discover an
omitted organizational policy. The same input snapshots and time produce the
same decision. No callbacks, scripting, plugin policies or global manager.

## Authorization vs Capability

An Authorization binds its ID to the proposal's `authorization_ref`, task ID,
explicit action set, **exact normalized targets**, capability set and finite
expiry. No target prefix or glob matching. Both MOVE targets must be named.
Expiry is exclusive: `now >= expires_at` denies. There is no bare approved flag.
An authorization may cover multiple actions/runs of its named task within its
declared scope; it is not a one-use credential. RSE answers **may execute**, not
whether a planner should include the action.

CapabilityBroker accepts only declared names and explicit trusted adapters with
`execute(action)`. Duplicate/unknown registrations raise a fixed ValueError;
missing lookups raise a fixed LookupError. No discovery or automatic fallback.
Each Git stage, commit, push, PR create, PR merge, release and deploy has its own
action/capability. Tests, a PR approval, task completion or a Paperclip assignment
cannot substitute for deployment authorization.

## Execution Flow

`evaluate_and_execute(action, policy_stack, authorization, capability_broker,
journal, now)` validates, checks lifecycle history, evaluates all policy gates,
checks authorization and capability, records AUTHORIZED then ATTEMPTED, invokes
one adapter, records its result and returns an immutable SecurityReceipt.
`evaluate_policy` is pure and does not inspect the broker; ALLOW there is not an
execution receipt. Time is caller-supplied nonnegative finite seconds on the
same time base as expiry, not read from a hidden clock. Times must be at most
2**53 seconds; larger integers, nonfinite values and invalid types fail closed.

The in-memory journal serializes evaluation/attempt/reconciliation, including
concurrent calls; reentrant attempts see ATTEMPTED and are blocked. No background
thread is created. The kernel cannot force a blocking adapter to stop: only
bounded, controlled fake adapters are used in Phase 1 validation.

## Unknown Outcome

`ExecutionResult` has KNOWN_SUCCESS, KNOWN_FAILURE or UNKNOWN_OUTCOME. A known
failure attests no unresolved effects; a nonzero process exit would not by itself
justify that state. Exceptions, malformed results and success without evidence
become UNKNOWN_OUTCOME then RECONCILIATION_REQUIRED. Exception text is discarded.
An interrupted ATTEMPTED state also blocks retry. No timeout or model request
authorizes a blind retry.

KNOWN_SUCCESS and RECONCILED_SUCCESS return final `ALREADY_COMPLETED` on repeated
calls, without invoking the adapter. Policy disposition is DENY and reason is
ALREADY_COMPLETED; that is an idempotent completion response, not a new denial of
the original effect. Blocked proposals cannot erase pending/success states.
An action ID is bound to a digest of its immutable request except authorization
reference, allowing renewed authority but not a changed effect under the same ID.
Resumption must retain the original request fields, including `run_id`; a new
run may inspect/reconcile that original request, not rebind its action ID.
`idempotency_key` is optional correlation metadata, **not** cross-ID deduplication.
The host owns stable action IDs; changing IDs can represent a new action.

## Reconciliation

`reconcile(action, journal, reconciler)` calls a trusted read-only observer only
for the exact pending action. Its typed result is EFFECT_APPLIED,
EFFECT_NOT_APPLIED or STILL_UNKNOWN. These record RECONCILED_SUCCESS,
RECONCILED_NOT_APPLIED or RECONCILIATION_REQUIRED respectively. Invalid/untyped
results and exceptions remain unknown. Model text is not a reconciler.

Reconciliation does not execute or retry the effect. After NOT_APPLIED, the
caller must explicitly call the controller again with current policy,
authorization, time and capability. Every gate is re-evaluated. The reconciler
attests its observation; independent target-reality verification is not provided.

## Security Journal

InMemorySecurityJournal implements `append`, `latest`, `history` and a
`transaction()` context manager. Alternative trusted journals must serialize the
entire transaction, return immutable histories, append atomically or fail, and
retain ATTEMPTED when later writes fail. Do not replace/discard the journal to
resume an unknown action. Restart persistence is not implemented.

Entries are immutable structured state plus opaque identity/request/evidence
references. No raw prompt, secret, payload, target, provider, exception or summary
is copied into controller-generated entries. This is a structured security
journal, **not** tamper-proof, cryptographically append-only, immutable storage
or a forensic ledger. SHA-256 references bind/locate inputs; they are not a
Security Chain, encryption or a guarantee against guessing low-entropy inputs.

## Security Receipt

Version: `20396-rse-receipt/v1`. Includes action/task/run/provider/runtime,
action class, target locator, policy disposition/reason, authorization reference,
capability, execution/reconciliation state, evidence references and final disposition.
All free-form input fields are opaque SHA-256 references (absent/invalid fields:
REDACTED); enums, capability names and fixed reason codes stay readable.
The trusted caller can correlate references locally without logging raw content.

Execution state preserves known lifecycle uncertainty: a pending prior attempt
or post-attempt journal failure reports UNKNOWN_OUTCOME, never NOT_ATTEMPTED.
Reconciliation reports RECONCILED_SUCCESS or RECONCILED_NOT_APPLIED; unresolved
reconciliation reports UNKNOWN_OUTCOME. An unreadable history also reports
UNKNOWN_OUTCOME conservatively. NOT_ATTEMPTED describes a checked fresh attempt
that did not reach adapter invocation; it is not proof about effects outside this boundary.

Receipt evidence proves only what the configured boundary reported. A typed
KNOWN_SUCCESS with evidence does not authenticate that evidence or prove target
reality, invisible effects, provider internals, host containment or storage integrity.
No verified-effect status is inferred from model or tool success text.

### Reading a blocked receipt

| Reason | Next bounded action |
| --- | --- |
| MALFORMED_ACTION | Correct the proposal; do not execute it. |
| POLICY_INVALID / POLICY_INACTIVE | Ask trusted host owner to repair/currently resolve policy. |
| ACTION_DENIED / ACTION_NOT_IN_SCOPE | Revise the plan or request a separate policy decision. |
| PATH_OUT_OF_SCOPE / NETWORK_TARGET_DENIED | Select an approved target; no automatic widening. |
| DATA_EGRESS_DENIED | Do not send that data; approval cannot override the privacy boundary. |
| AUTHORIZATION_MISSING / EXPIRED / REVOKED (AUTHORIZATION_ prefix) | Supply valid current bounded authority only if the action remains required. |
| CAPABILITY_MISSING | A trusted integration must explicitly supply the ability; approval alone is insufficient. |
| UNKNOWN_OUTCOME_PENDING | Reconcile; do not retry. |
| ALREADY_COMPLETED | Continue the plan without repeating this effect. |
| ACTION_ID_CONFLICT | Resolve identity binding; do not evade pending history with a new ID. |
| JOURNAL_OR_BOUNDARY_FAILURE | Repair the trusted boundary and reconcile before resumption. |

## Data Egress

External actions (network, Git push, PR create/merge, release, deploy and package
install) require an allowed origin and PUBLIC or NON_SENSITIVE classification
allowed by **every** policy. SECRET, LOCAL_ONLY, UNKNOWN and SENSITIVE egress
deny even if a policy includes them. This preserves `client-privacy.md`: customer
approval does not permit raw sensitive external transfer. Classification is a
trusted integration responsibility; there is no content inspection or DLP.

## Secrets

SECRET_ACCESS requires the same independent policy, exact authorization and
`secret.read` capability gates. Only synthetic opaque secret references are
used in tests. No secret manager, secret values or real credential access ships.
ActionRequest/Authorization/ExecutionResult repr suppresses fields. Do not put
raw secrets into these objects: explicit serialization by a caller can still
expose their contents. Controller outputs suppress free text, not arbitrary
third-party logging or a malicious journal implementation.

## Filesystem Logical Boundary

Absolute POSIX paths are normalized lexically; components, not naive prefixes,
determine scope. `/repo/docs/../secret` is outside `/repo/docs`, and
`/repo/docs-private` is not its child. Relative paths, double-leading slash,
backslashes and controls are invalid. READ uses read roots; write/create/delete,
MOVE (both source and destination), config and local Git use write roots.
No realpath/stat/read is performed. Symlinks, mounts, races, Windows paths and
actual filesystem containment require a separately reviewed host binding.

## Network Logical Boundary

DENY_ALL or an exact scheme/hostname/port ALLOWLIST; scheme/host case and default
ports normalize. HTTP(S) only. Credentials, query strings and fragments are
rejected in this deliberately narrow prototype. Subdomains do not inherit an
origin's permission; HTTP does not inherit HTTPS permission. No DNS lookup,
redirect handling, proxy validation, connection or packet enforcement occurs.
EXECUTE_PROCESS/service/secret targets are opaque exact references, not shell
commands. Hidden network or filesystem effects inside adapters are out of scope.

## Provider Independence

OpenAI, Anthropic, Google, Local, Paperclip worker and unknown provider labels
receive identical policy decisions. Labels are attribution only, never trust.
No SDK or vendor API is imported. Paperclip is not a dependency.

## Current Enforcement

Pure policy/authorization validation, explicit capability selection, serialized
in-memory lifecycle gates, logical path/network scope, deterministic egress
denial, redacted outputs and explicit reconciliation are executable and tested
using fake adapters. No filesystem/network/GitHub/deploy adapter is installed.

## Non-Enforcement

No real runtime binding, OS sandbox, kernel hook, firewall, daemon, credential
storage, authority service, durable journal, Security Chain, token accounting,
critical trace, signed checkpoint or external anchor. No host/provider security
guarantee. Existing Local Compute behavior is unchanged and is not routed through
RSE by this PR. Installing the package does not activate an envelope around Codex.

## Existing Security Inventory and Package Placement

- **Executable:** Local Compute's Effect/Approval, exact fingerprints, bounded
  runner, UNKNOWN/reconciliation gate, durable deployment journal and task-pool
  failure states. Those remain unchanged.
- **Document-only:** safety-policy, client-privacy, capability-boundaries,
  approved-tool-contract-card, external-app-runtime-boundary,
  security-review-protocol, stop-conditions and resume-protocol govern workflow;
  they do not supply this generic runtime controller.
- **Reusable semantics:** explicit permission versus ability, exact identity,
  unresolved effects stop progression, explicit trusted reconciliation.
- **Duplication risk:** confusing deployment SUCCEEDED/UNKNOWN/APPLIED with RSE
  KNOWN_SUCCESS/UNKNOWN_OUTCOME/RECONCILED_SUCCESS, or assuming a journal supplies
  authority. The documented meanings align; no cross-runtime conversion exists.
- **Missing primitives supplied here:** generic closed action/data vocabulary,
  nested policy intersection, bounded action authorization, broker and receipt.
- **Decision B:** independent small kernel, semantically aligned. Extracting
  shared types would couple this pure prototype to deployment budgets, process
  recipes and persistence and broaden the change unnecessarily.
- **Placement: CORE.** The script and boundary reference are explicitly included
  in the core manifest because execution safety is vendor-independent. They
  require only stdlib and do not activate effects merely by being packaged.

## Future Security Chain

Phase 1.25 only after separate approval: authority roles (root owner,
installation admin, project/task authority), policy/authorization/revocation
history and a unified SecurityEvent. Existing receipt fields can be referenced
by event/action/run/task/provider/runtime IDs. Future sequence, timestamp,
installation/project/trace/actor/model, payload digest, policy version and
previous/record hashes belong to a new versioned envelope, not implemented stubs.
Hash chaining would be **tamper-evident**, not tamper-proof. Future break glass
needs strong authority, scope, reason, duration, capabilities, automatic expiry,
recorded event and post-event review: temporary, never silent override.

Phase 1.75 signed checkpoints need sequence/head/time/installation/key/signature
and an independent external anchor to detect whole-chain replacement. No
cryptocurrency, mining, token or consensus network is required or implemented.

## Future Token Accountability

Phase 1.35 only after separate approval: usage ownership by installation,
project, task, run, agent and model call, provider/model/purpose, input/cached/
output/reasoning tokens, cost/currency, timing and parent-call reference.
Unavailable measurements remain UNKNOWN. Nested budgets cannot self-expand;
creation/warning/exceeded/extension-request/extension-granted need authority.
Orphan, post-completion, unreconciled-retry, retry/context amplification and low
progress/high-token patterns are anomalies, not evidence of theft. Correlate
with acceptance criteria, verified outputs and resolved blockers, not lines of
code. No token counter or budget subsystem is implemented in Phase 1.

## Future Critical Execution Trace

Phase 1.5 only after separate approval: boundary events for file/process/network/
secret/package/config/Git/GitHub/deploy/policy/authority, linked by trace,
project/task/run/action/parent/provider/model/runtime. Compare declared effects
to observed effects; undeclared reads/writes/processes/network become divergence
events. Sensitive-read → process → network is a future deterministic pattern,
not AI intent detection. No function tracer or graph database is introduced.

## Host Enforcement Boundary

Phase 2 real bindings, Phase 3 host observation and Phase 4 comparison of model
declaration, RSE authorization, adapter observation, host observation and target
reality require separate PRs and explicit approval. No VM or manual-only test is
needed for this phase. Tests run and finish automatically with synthetic inputs.

## Public Claim Boundary

“Experimental vendor-independent Runtime Safety Envelope foundation” means
tested **logical in-process gates with trusted fake boundaries**, not production
security, provider-internal verification, host sandboxing, kernel security or a
packet firewall. A PR, passing CI, package availability or documentation is not
runtime activation, deployment or verification of real-world containment.
