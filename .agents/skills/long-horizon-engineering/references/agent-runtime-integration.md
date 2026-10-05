# Agent Runtime Integration — Experimental Foundation

Phase 2C is an explicitly constructed, provider-independent thin bridge from
bounded untrusted proposals to the existing RSE ActionRequest and Phase 2A/2B
payload contracts. It reuses those bindings, CET and the existing Security Chain;
it introduces no adapter dispatcher, authority system or durable ledger.
Installation and import activate nothing and grant no capabilities or authority.

## Explicit boundaries

| Boundary | Status |
|---|---|
| MODEL OUTPUT | UNTRUSTED PROPOSAL |
| MODEL SELF-AUTHORIZATION | NO |
| MODEL SELF-GRANTED CAPABILITY | NO |
| MODEL AUTHORITY MUTATION | NO |
| DIRECT ADAPTER INVOCATION | NO THROUGH GOVERNED BRIDGE |
| UNKNOWN-EFFECT NEW-PROPOSAL BYPASS | BLOCKED SAME_PROCESS |
| CROSS-PROCESS UNKNOWN SUPPRESSION | NOT_IMPLEMENTED |
| CRASH-DURABLE AGENT LIFECYCLE | NO |
| PHASE 2A/2B | REUSED |
| HOST OBSERVER | NOT_IMPLEMENTED |
| OS SANDBOX | NOT_IMPLEMENTED |
| PROPRIETARY CODEX INTERCEPTION | NOT CLAIMED |

The bridge governs only calls routed through it. It does not intercept arbitrary
Python code, provider SDKs, raw tool calls or proprietary host execution. No
monkeypatch, daemon, watcher, service, dependency or automatic discovery is added.
Paperclip and Local Compute runtime integrations remain outside this phase.

## Public API and trusted inputs

`AgentActionProposal` is a frozen bounded data contract with required
`proposal_id`, `requested_action_class`, `requested_target` and optional
`requested_parameters`, `declared_effects`, `reason_text`, `untrusted_agent_ref`,
`untrusted_provider_ref`, `untrusted_model_ref`, `correlation_ref`, `action_id`.
Nested containers are copied and frozen. A dict proposal accepts only these
known fields; authority/capability injection, raw tool proposals and malformed
parameters reject. Optional `action_id` is untrusted correlation only.

`AgentRuntimeBridge()` creates an empty same-process guard. Its methods are:

```python
prepare(proposal, *, context, trusted_agent_id, authorization_ref,
        data_classification, now, expires_at=None)
execute(prepared, *, binding, expected_payload_digest, expected_prepared_digest,
        policy_stack, authorization, context, now)
reconcile(prepared, *, binding, expected_payload_digest, expected_prepared_digest,
          policy_stack, authorization, context, now)
```

`prepare()` is effect-free: no subprocess, network, filesystem mutation,
capability registration or authority mutation. It requires a host-supplied
`critical_execution_trace.TraceContext` with trusted action/run/task/project/
installation/provider/model/runtime identity. `trusted_agent_id`, authorization
reference, classification and times are separate host inputs. Untrusted proposal
attribution cannot replace them. Provider/model identity is attribution, never
authority; context and authorization must be obtained independently of model
output. The host decides policy, approved scope and capability registration.

Supported action classes are the existing bounded file read/create/write/delete/
move, allowlisted process, local Git stage/commit, HTTPS request, exact Git push
and PR create contracts. There is no PR update/merge, release, deployment, package
installation, service-control or secret-store action. Existing payload validation
and local/remote limitations still apply; see [Runtime Binding](runtime-binding.md)
and [Remote Runtime Binding](remote-runtime-binding.md). Process proposals require
an explicit absolute `cwd`; preparation does not discover a workspace default.

`AgentRuntimePrepareResult(status, prepared)` returns `PREPARED` with a
`PreparedAgentAction`, or `NOT_SUPPORTED` / `MALFORMED_PROPOSAL` without one.
The frozen prepared contract contains `proposal_digest`, hashed `proposal_ref`,
`trusted_agent_id`, `context`, `action_request`, `payload_kind` (`LOCAL`/`REMOTE`),
`normalized_payload`, `payload_digest`, `material_effect_identity`,
`trusted_capability_name`, `declared_effects`, `declaration_status`,
`prepared_at`, `expires_at`, `prepared_digest`. The capability name is mapped by
the bridge from existing supported action classes; naming it does not register it.

The host must save **both** `prepared_digest` and `payload_digest` before
authorization, independently of the prepared object later supplied for execution.
Pass those saved commitments as `expected_prepared_digest` and
`expected_payload_digest` to both execution and reconciliation. Deriving the
expected values from current incoming/model-controlled data at execution grants
no authority and defeats the intended preauthorization commitment boundary.
Both commitments are mandatory, alongside each binding's separate approved
payload-digest snapshot keyed by the trusted host action ID.

The host explicitly constructs exact `runtime_binding.RuntimeBinding` or
`remote_runtime_binding.RemoteRuntimeBinding` instances with registered broker
capabilities, existing journal, chain, SecurityAuthority actor, approved digests,
adapters/transports and workspace/destination policy. `execute()` validates the
prepared contract, current matching context, commitments, expiry and existing
binding type, then delegates only to `binding.execute()`. The existing RSE policy
stack, scoped current Authorization and SecurityAuthority checks still control
effects. Preparation or a declaration is never approval. The bridge pins the
journal/chain/broker/actor objects for each local/remote lifecycle; fresh binding
snapshots may reuse those same objects, but replacing lifecycle objects rejects.

`AgentRuntimeExecutionResult(status, receipt, runtime_result, events, causal_refs,
token_usage_status)` preserves the underlying result and receipt. Successful
delegation reports the receipt's final disposition; validation, pending mutation
and reservation-limit failures return bounded denial statuses. UNKNOWN is an
uncertain outcome requiring reconciliation, never a successful execution claim.

## Material identity, reservation and recovery

Material effect identity binds action class, normalized target/destination and
the action's material payload: file bytes, process argv/cwd/environment, Git stage
paths or exact tree/parent/message, network method/query/headers/body/request
identity, Git repository/ref/old/new OIDs, or PR provider/repository/head/base/
title/body/draft/request identity. It excludes proposal/action IDs, attribution,
reason, correlation and execution limits. Logical paths, URL query escape case,
environment pair order and Git-stage path order are normalized without target
alias discovery. This bounded identity is not a universal equivalence proof for
filesystem aliases, arbitrary providers or effects internal to a trusted child.

At most 1024 unresolved mutation reservations are held by one bridge. Reservation
ownership serializes EXECUTING, UNKNOWN and RECONCILING for the same material
effect, including equivalent proposals with changed cosmetic IDs. Distinct
effects proceed independently; file reads and GET/HEAD reads do not consume this
mutation reservation. Proven known failure releases; UNKNOWN or conflicting
readback retains suppression. Creating another bridge or restarting the process
loses this protection. Retain the same bridge, journal and binding lifecycle.

`reconcile()` requires the original prepared action, both independently saved
commitments and the exact binding object reserved by the UNKNOWN action. It
delegates to existing readback, never issues a mutation, and rechecks current
policy/authorization and SecurityAuthority. For Phase 2A, these existing checks
are applied by the bridge before its older read-only binding reconciliation API.
Prepared expiry blocks new execution but permits recovery of the original
UNKNOWN action under current valid authority. Expired/revoked current authority
still denies recovery before readback. `RECONCILED_SUCCESS` or
`RECONCILED_NOT_APPLIED` clears the reservation without retrying; unresolved or
conflicting results retain it. Not-applied evidence does not authorize a retry.

If causal reporting fails after handoff, the bridge attempts to mark the
**existing** RSE journal RECONCILIATION_REQUIRED and retains EXECUTING until this
uncertainty handling finishes. A guaranteed final transition publishes UNKNOWN,
including when reporting raises, so concurrent reconciliation cannot clear a
reservation before a late journal update. A failing journal can require host
repair; retained in-memory suppression does not establish durable recovery.

## Declarations and causal evidence

An absent or empty declaration remains `UNKNOWN`. Actual nonempty effect
declarations have `DECLARED` status and CET `DECLARED` source; disagreement with the translated
action is `DECLARATION_ACTION_MISMATCH`. These are untrusted claims, not authority
or independently observed effects. Existing adapter observations and divergences
are preserved, including Phase 2B observed response status, complete-body digest
and parse-failure evidence. Recovery adds an existing
`RECONCILIATION_OBSERVED` event when bounded reconciliation evidence is available.
There is no `HOST_OBSERVED` assertion or new observer coverage.

Receipt evidence references anchor proposal, prepared action, material effect,
trusted agent and context digests in the one existing Security Chain. Raw proposal
text, parameters, file bytes, response bodies, process output and credentials are
not added as causal evidence. A sealed digest is integrity evidence, not proof of
all downstream effects. Chain/journal recording failures remain failure-closed
and may require operator repair. No token records or token metrics are fabricated;
`token_usage_status` remains `UNKNOWN`. Optional usage correlation is not shipped.

## Validation boundary

Package tests assemble an isolated temporary core and guard subprocess, network,
DNS, HTTP, thread, discovery, filesystem-effect and environment surfaces during
import and empty bridge construction. Bridge/binding regressions use controlled
temporary resources and synthetic remote transports, not external account writes
or credentials. Passing implementation tests, installation and documentation do
not establish final-SHA independent review, CI, publication or runtime activation.
