# Skill Routing And Promotion Contract

Use this contract when a routing or package-promotion decision needs to be
reviewable and machine-verifiable. It is a static governance layer. It does not
implement a runtime router, install a capability, execute a selected route,
change the package layout, or enforce permissions at the host level.

The canonical machine-readable shape is
`schemas/skill-routing-decision.schema.json`. Semantic rules that cannot be
expressed completely in JSON Schema remain mandatory contract checks.

## Existing Authority

This contract reuses, and does not replace:

- `planner-builder-evaluator-loop.md` for role boundaries;
- Incubator governance and promotion policy for customer decisions;
- existing source and experiment lifecycle records for lifecycle status;
- `package-manifest.json` for current package disposition; and
- capability boundaries and stop conditions for effects and escalation.

The contract records a lifecycle namespace and status supplied by those
authoritative systems. It MUST NOT invent or transition a parallel lifecycle.
The accepted namespace/status pairs are deliberately closed:

- `installed-skill-lifecycle`: `active` or `frozen`;
- `incubator-experiment-lifecycle`: `locked`, `proposed`,
  `approved_for_design`, `approved_for_isolated_build`, `testing`, `rejected`,
  `retained_in_sandbox`, `candidate_optional`, `approved_optional`,
  `candidate_core`, `approved_core`, or `deprecated`; and
- `source-lifecycle`: `locked`.

Adding a new lifecycle status requires changing its authoritative lifecycle
first and then updating this projection. The routing record cannot introduce
one ad hoc.

## Routing Inputs

A routing record contains:

- the requested intent;
- an optional exact target;
- an optional explicit workflow;
- the current safety gate;
- authority already granted for the task; and
- a complete set of candidates considered for this decision.

Each candidate declares availability, activation policy, intent match,
exact-explicit match, whether the candidate is an executable route, and its
required effect classes. Candidate records MUST use identifiers and capability
metadata, not secrets, credentials, account data, or customer content.

## Fixed Precedence

Evaluate exactly one decision using this order:

1. `safety-stop-gate`: a stop condition blocks selection.
2. `explicit-exact-installed-callable`: an exact, installed, callable target
   may be selected.
3. `explicit-unavailable`: an explicitly named target that is missing or not
   callable is reported unavailable; it is not selected.
4. `explicit-workflow`: an explicitly requested callable workflow may be
   selected when no exact target was supplied.
5. `single-implicit-intent`: exactly one installed, callable, executable
   candidate with `activation_policy: implicit` may be selected.
6. `ambiguity`: more than one eligible implicit candidate requires
   clarification.
7. `no-match`: no eligible candidate produces no route.

The recorded precedence step MUST match the inputs and candidate set. The
router MUST NOT skip a higher-priority applicable step.

## Selection Boundaries

`selected` means only that one route matches the static routing contract.

- Selection MUST preserve the authority granted before routing.
- Required effects MUST be a subset of already granted effects.
- `authority_expanded` MUST remain false.
- Routing MUST NOT authorize installation, execution, network access, external
  transfer, account access, or promotion.
- Recommendation MUST NOT be interpreted as any of those authorizations.
- Actual tool use or execution remains subject to the task's existing approval
  and capability boundaries.

Candidates marked `explicit-only` MUST NOT be selected implicitly. Candidates
marked `proposal-only` or `sandbox-only` MUST NOT be selected as executable
routes under any precedence step. Their candidate record MUST declare
`executable: false`. A `proposal` route kind MUST use `proposal-only` for both
availability and activation policy. A `sandbox-candidate` route kind MUST use
`sandbox-only` for both fields. Relabeling either route kind as installed and
callable does not make it selectable.

When an explicit target is unavailable, the result may explain a safe fallback
or separately governed recommendation path, but the routing record itself
cannot request installation.

## Promotion Assessment

Routing and promotion are separate. A routing decision may include a promotion
assessment, but route selection provides no promotion evidence.

The assessment records:

- the authoritative lifecycle namespace and current lifecycle status;
- current and proposed package disposition;
- immutable source identity;
- license, security, architecture, and validation gates;
- eligibility;
- promotion state; and
- customer disposition.

Package disposition is one of `core`, `bundled-optional`, `separate-skill`,
`sandbox-only`, `rejected`, `deferred`, or `archived`. It is not a lifecycle
status.

`eligible` means only that all recorded prerequisite gates pass. It never means
`promoted`. This static contract cannot verify customer approval. Its promotion
assessment is valid only when:

- immutable source identity is present;
- no mutable source reference is used;
- all required gates pass;
- default-profile change is false;
- `approval_required` is true;
- the human disposition remains `pending` with actor `none`;
- `promotion_state` remains `not-promoted`;
- `next_stage_authorized` remains false; and
- any optional `decision_reference` is marked `unverified_claim`.

Planner, Builder, and Evaluator may propose or assess evidence. The Evaluator
MUST NOT write an approved customer disposition. No role, input record,
decision ID, audit ID, hash, timestamp, or internally consistent structure may
turn the pending disposition into approval or promote a candidate. A failed
gate makes the assessment ineligible regardless of score or recommendation.

A `decision_reference` is an opaque, non-authoritative pointer retained only
for later human review. Its shape is not evidence that the referenced decision
exists, belongs to the customer, or authorizes any action. If future governance
must prove customer approval, it requires a separate, customer-controlled,
immutable evidence source, an explicitly approved read scope, and a new
implementation envelope. This contract does not implement that source.

## Static Validation

Contract validation MUST reject:

- precedence or outcome inconsistent with the inputs;
- ambiguous routing recorded as selected;
- implicit selection of an `explicit-only` candidate;
- any executable `proposal-only` or `sandbox-only` candidate;
- an unknown or duplicate effect in any granted- or required-effects list;
- authority expansion or required effects outside granted effects;
- installation, execution, or promotion authorization attributed to routing;
- `eligible` with a failed evidence gate;
- any `promoted` state;
- any non-pending human disposition or disposition actor other than `none`;
- `approval_required` set to false;
- any next-stage authorization;
- a decision reference not explicitly marked `unverified_claim`;
- a lifecycle status outside the authoritative namespace/status pair;
- missing or mutable source identity;
- a default-profile change;
- secret, credential, account, token, password, or private-key fields; and
- unknown fields that could conceal authority or external effects.

Synthetic fixtures and dependency-free contract validation demonstrate
consistency of this static record format only. The JSON document is defined by
a Draft 2020-12 schema, but a formal Draft 2020-12 engine result must be
reported as unverified when that engine is unavailable. Neither form of
validation proves live Codex routing, complete natural-language intent
recognition, host-enforced isolation, runtime availability, installation
safety, customer approval, or promotion readiness. A synthetic or externally
supplied decision reference remains an unverified claim; it does not itself
grant installation, execution, promotion, merge, release, default-profile
change, or any host/runtime permission.

## Review And Rollback

Reviewers should verify the source record, candidate inventory, precedence
derivation, effect-set equality, gate evidence, and human disposition
independently.

This feature adds no runtime state and performs no migration. Rollback is the
removal of this reference, its schema and tests, the SKILL entry, and the
corresponding manifest/checker evidence rebind.
