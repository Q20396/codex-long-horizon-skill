# Evidence-Bound Multi-Perspective Research Contract

Status: `sandbox-only`

This is a clean-room, explicit-only, non-executable contract for synthetic
research records. It is not an installed skill, runtime router, retrieval
system, agent swarm, source-verification service, independent review, or
authorization to access private material or perform an external action.

## Purpose

The contract makes a small research workflow structurally reviewable:

1. a bounded research contract states the decision question and evidence time;
2. domain lenses generate questions, not conclusions or authority;
3. atomic evidence cards bind claims to locatable, versioned sources;
4. contradiction records compare proposition boundaries before declaring a
   direct conflict;
5. the deliverable remains general research support; and
6. self-critique identifies gaps without becoming independent review.

The package disposition is `sandbox-only` and activation is `explicit-only`.
Passing static validation never promotes the candidate or authorizes a next
stage.

## Claim semantics

`FACT` means a factual statement supported by a locatable source. It does not
mean objective certainty, a final legal finding, or an unqualified truth.
Claims use structured fields instead of broad natural-language certainty
detection:

- `claim_kind`: `factual_statement`, `analytical_inference`, or
  `research_question`;
- `epistemic_status`: `FACT`, `INFERENCE`, or `UNKNOWN`;
- `certainty_level`: `source_supported`, `bounded`, or `unresolved`; and
- `limitations`: a required non-empty list for FACT and INFERENCE.

FACT requires `source_supported`. INFERENCE requires `bounded`. UNKNOWN
requires `unresolved`. The validator checks those combinations only; it does
not claim to understand arbitrary certainty language.

## Synthetic identity and closed objects

Fixtures use namespace-prefixed identifiers such as `SYN-ENTITY-001` and
`SYN-EVIDENCE-001`. IDs are unique both within their declared namespace and
globally across the record. References must resolve to the correct object
type, not merely to an equal string.

All modeled objects are recursively closed. Unknown fields in nested objects
or array items are rejected. Required fields and expected JSON types are also
checked by the dependency-free validator, including nested object and array
items. Every Schema `enum` and `const` is checked as well. A malformed object
or array item produces stable reasons and is not passed to semantic traversal.
There is no open-ended `metadata`, `extensions`, `payload`, or `extra` object
through which an external action or authority claim can be added.

Synthetic locators use predefined `.invalid` domains only. The contract does
not claim to recognize real people, entities, cases, or private records.

## Source and time boundaries

`source_origin` is one of:

- `primary`
- `authoritative_secondary`
- `secondary`
- `unverified`

An unverified source cannot independently support FACT. It may support UNKNOWN
or a bounded INFERENCE that also cites evidence from a verified source origin.
Every source origin must be present in the research contract's
`approved_source_origins`. Derivative sources record `derivative_of` and must
share the parent's `independence_group`. Multiple sources in the same
independence group do not increase independent evidence strength.

`decision_at`, `as_of`, `published_at`, `available_at`, and `retrieved_at` are
valid ISO 8601 date-times with `Z` or an explicit UTC offset. Evidence with
`available_at > decision_at` is look-ahead and is rejected. Missing time or
timezone data is not inferred or repaired.

Source locators cannot be absolute or relative local paths, `file:` URIs, URLs
with user information, or domains outside the synthetic allowlist.

## Perspective and contradiction boundaries

Lenses contain questions and declare `authority_claimed: false`. A lens is a
prompting perspective, not a persona with decision authority.

Each contradiction binds its competing claims to:

- time;
- jurisdiction or market;
- subject entity; and
- defined terms.

Different boundaries may describe different propositions. `direct-conflict`
requires two distinct claim IDs and a formal normalization record containing:

- `normalization_basis`;
- a complete `normalization_scope`;
- `normalization_evidence_ids`; and
- an ID that is unique and type-correct.

Without that evidence, the contradiction status must be
`not-directly-comparable`. Consensus is not proof.

## Private-evidence lock

The candidate is permanently locked to:

```text
private_evidence_mode: blocked
private_materials_present: false
```

No synthetic authorization, approval reference, or unknown field can override
the lock. This sandbox cannot represent real private-material authorization as
satisfied. Future access to private legal, financial, client, account, or case
material requires a separate task-specific authorization with exact read paths,
minimum disclosure, confidentiality, retention, and output boundaries.

## Deliverable and human-state boundaries

The only deliverable kind is `general_research_support`. Its closed structure
allows findings, risks, limitations, evidence references, contradiction
references, a bounded recommendation, and research-only next actions.

The contract has no field for a legal opinion, representation, filing, contact,
submission, publication, order, account operation, automatic monitoring, or
other external action. Such fields are rejected at any nesting depth.

Candidate human state is fixed:

```text
human_disposition: pending
next_stage_authorized: false
promotion_state: not-promoted
```

No decision ID, hash, timestamp, fixture, or internally consistent record
changes that state. Self-critique uses
`independent_review_claimed: false`; it can find gaps but cannot approve or
independently verify the work.

## Static validation

The Draft 2020-12 Schema is a raw structural gate. Dependency-free validation
adds type-correct reference checks, global identifier integrity, calendar-aware
timestamp parsing, look-ahead comparison, source-origin semantics,
independence-group checks, contradiction normalization rules, private-lock and
human-state checks, and stable reason codes.

These checks can establish consistency of synthetic records only. They cannot
prove:

- that a claim is true;
- that a locator is accessible;
- that a source is authoritative or independent;
- that normalization is correct in the real world;
- that private access was authorized;
- that research is complete or professionally sufficient;
- host-enforced isolation or runtime behavior; or
- complete natural-language detection.

No network, dependency, third-party code, connector, real endpoint, installed
skill, private material, or external action is used by this contract.

## Stable rejection reasons

The machine-readable contract lists the complete stable reason-code set.
Reasons explain rejection only. They do not repair records, infer evidence,
authorize private access, fill a human disposition, retrieve a source, or
trigger a next action.

## Rollback

This candidate adds only sandbox architecture, schema, fixtures, and contract
tests. It creates no runtime state or migration. Before integration, rollback
is discarding the isolated candidate worktree. Any later integration or
promotion requires a separate customer decision.
