# Goal-Driven Delivery Contract: <title>

This bundled-optional template is an explicit-only planning and evidence
surface for a substantial, resumable engineering task. It does not create a
new role, lifecycle, permission tier, or runtime. Do not create or persist an
instance unless the customer approves its exact file path.

## Existing Contract References

Use the existing contracts rather than redefining them:

- `references/planner-builder-evaluator-loop.md` defines the serial Planner,
  Builder, Evaluator, and human-disposition boundaries.
- `templates/implementation-plan.md` defines scope, acceptance criteria,
  planned files, validation, stop conditions, and rollback.
- `templates/WORKING_STATE_TEMPLATE.md` defines optional resumable state and
  freshness checks.
- `templates/verification-evidence.md` defines validation evidence.
- `references/decision-map-and-frontier.md` may recommend a next safe task when
  planning complexity warrants it.
- `references/skill-routing-and-promotion-contract.md` keeps routing,
  authority, package disposition, and promotion separate.

These references remain authoritative. This template only links their bounded
records for one task.

## Goal And Success

- Goal:
- Non-goals:
- Observable success criteria:
- Evidence required:
- Stop conditions:

## Approved Task Boundary

- Approved read paths:
- Approved write paths:
- Approved commands or tools:
- Approved external effects:
- Explicitly prohibited actions:
- Approval references:
- Rollback or containment:

Blank fields grant nothing. This contract does not implicitly authorize writes,
network access, installation, downloads, publication, external actions, or
scope expansion.

## Linked Records

- Implementation plan:
- Working-state record:
- Verification-evidence record:
- Decision Map, if explicitly used:
- Last freshness check:

Do not duplicate detailed logs or sensitive evidence here. A linked record is
not permission and must be rechecked against current repository state before
resumption.

## Fixed Human State

- `human_disposition: pending`
- `human_actor: none`
- `decision_reference_status: unverified_claim`
- `decision_reference: none`
- `promotion_state: not-promoted`
- `next_stage_authorized: false`

These values are fixed for this template. No model, Planner, Builder,
Evaluator, synthetic record, identifier, timestamp, hash, recommendation,
computed Frontier, or `verified` result may change them or grant a next stage,
execution, merge, release, deployment, publication, or other external action.
Only a separately verified, customer-controlled approval source could establish
a later authorization, and this template does not implement that source.

## Evidence Handoff

- Acceptance criteria mapped to evidence:
- Checks run and actual results:
- Known gaps:
- Evaluator recommendation:
- Customer decision required:

An Evaluator recommendation is proposal-only. It is not independent review,
customer approval, runtime enforcement, or host-enforced isolation.

## Privacy And Persistence

Persistence is denied by default. If the customer approves an exact artifact
path, record only the minimum non-sensitive task metadata needed for review or
resumption.

Do not record secrets, credentials, tokens, private keys, client materials,
account data, private communications, legal or financial evidence, sensitive
project content, or confidential source content. Do not create logs, caches,
memory files, background state, or copies of evidence unless each exact path
and retention purpose is separately approved.

## Completion Boundary

- Current verified state:
- Remaining uncertainty:
- Next safe proposal:
- Customer disposition still required: YES

Completion of this record does not complete the task or authorize another
stage. Report anything not directly verified as unverified.
