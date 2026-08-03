# Research Review Package: PR-5 Design Baseline

Status: `STATIC_IMPLEMENTATION_AND_REMEDIATION_MERGED`

```text
design_review: APPROVED_FOR_STATIC_IMPLEMENTATION
static_implementation: MERGED
static_contract_remediation: MERGED
runtime_validator: NOT_AUTHORIZED
runtime_execution: NOT_IMPLEMENTED
next_stage: 0.6.0_DEV_ARCHITECTURE_CLOSEOUT_REVIEW
```

This document records the approved static design for the implemented
`Research Review Package` schema. It does not add a validator, research
generator, capability, data source, calculation, grant, runtime observation,
or execution path. It does not supersede the immutable `v0.5.0` release.

## Purpose and fixed boundaries

The implemented static package organizes pre-existing **synthetic** Evidence Record and
Claim Record identifiers with a customer-review-ready structure. Its purpose is
strictly `RESEARCH_REVIEW_ONLY`; it is not an investment recommendation,
decision, signal, portfolio action, or trading instruction.

All future PR-5 fixtures and package instances must retain:

```text
synthetic: true
fixture_only: true
persistence: ephemeral
financial_data_network_access: NOT_PERFORMED
runtime_execution: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN
external_action: NONE
investment_authorization: NONE
trade_authorization: NONE
```

This design does not permit network access, local or remote data retrieval,
account or credential access, a Skill or connector invocation, a calculator,
task logging, persistent memory, publication, notification, orders, brokerage
access, or trade execution.

## Field dictionary

| Field | Type and allowed value | Required | Meaning and prohibited meaning |
| --- | --- | --- | --- |
| `schema_version` | exact `1.0.0` | yes | Structural version only; not runtime capability version. |
| `package_id` | `^SYNTHETIC-REVIEW-PACKAGE-[0-9]+$` | yes | Fixture identity only; not an account, customer, or persistent task ID. |
| `request_id` | existing synthetic Research Task Envelope ID | yes | Static link to one synthetic request; not an authorization token. |
| `purpose` | `RESEARCH_REVIEW_ONLY` | yes | Review organization only; never a recommendation or action. |
| `synthetic` | `true` | yes | Prevents a claim of real research materials or execution. |
| `fixture_only` | `true` | yes | Prevents a claim that the structure is a customer-ready runtime product. |
| `persistence` | `ephemeral` | yes | No storage, history, or monitoring authorization. |
| `subject_identity_digest`, `requested_effects_digest`, `source_scope_digest`, `input_contract_digest`, `evidence_set_digest`, `claim_set_digest` | each `sha256:` plus 64 lowercase hexadecimal characters | yes | Six opaque synthetic linkage fields. Same-name fields may be compared only to test-wrapper declarations; different digest kinds are not required to match. |
| `digest_basis` | `SYNTHETIC_FIXTURE` | yes | Discloses that no real material was hashed. |
| `digest_computation` | `NOT_IMPLEMENTED` | yes | Prevents a claim of canonicalization or digest calculation. |
| `authenticity_verification` | `NOT_PERFORMED` | yes | Prevents a claim of source or material verification. |
| `evidence_record_refs` | non-empty array of synthetic Evidence references | yes | Structural Evidence identifiers only; does not prove a record exists or supports a Claim. |
| `supporting_claim_refs` | non-empty array of synthetic Claim references | yes | Structural supporting-case references only. |
| `strongest_counter_claim_refs` | non-empty array of synthetic Claim references | yes | Structural counter-case references only. |
| `assumption_claim_refs`, `conflict_claim_refs`, `unknown_claim_refs`, `falsification_claim_refs` | arrays of synthetic Claim references; each field required, each may be empty | yes | Closed review classification, not free text, conclusions, confidence scores, or action rules. |
| `valuation_material` | one legal combination below | yes | External material container only; never LHE-calculated, replayed, or verified valuation. |
| `review` | closed object with `adversarial_review: NOT_PERFORMED` and `independent_review: NOT_PERFORMED` | yes | Both members required; rejects all other review assertions. |
| `customer_review_status` | one review-readiness value below | yes | Indicates readability only; cannot grant investment or trade authority. |
| `financial_data_network_access` | `NOT_PERFORMED` | yes | No financial-data network access occurred. |
| `runtime_execution` | `NOT_IMPLEMENTED` | yes | No execution exists. |
| `host_enforcement` | `NOT_PROVEN` | yes | Does not claim host-enforced isolation. |
| `external_action` | `NONE` | yes | No external action is authorized or performed. |
| `investment_authorization` / `trade_authorization` | `NONE` | yes | Cannot signal investment or trade authorization. |

Examples: `schema_version: "1.0.0"` and
`package_id: SYNTHETIC-REVIEW-PACKAGE-001` are valid. A `1.0`,
`REVIEW-PACKAGE-001`, or an unprefixed identifier is not valid.

A Claim reference has exactly:

```yaml
claim_id: SYNTHETIC-CLAIM-001
relevance: MATERIAL
```

Its `claim_id` pattern is `^SYNTHETIC-CLAIM-[0-9]+$`, matching the PR-4
Claim Record `record_id` convention. It cannot embed Claim text, raw evidence,
source URLs, account data, customer material, full model context, or an action
recommendation. PR-5 validates only the synthetic identifier format and
linkage inside a synthetic fixture; it does not prove that a Claim exists, is
correct, or is independent.

An Evidence reference has exactly:

```yaml
evidence_record_id: SYNTHETIC-EVIDENCE-001
relevance: MATERIAL
```

Its identifier pattern is `^SYNTHETIC-EVIDENCE-[0-9]+$`, matching the PR-4
Evidence Record `record_id` convention. It does not prove that an Evidence
Record exists, supports a Claim, has a real source, or has complete material.

## Legal combinations

### Claim-reference sets

`evidence_record_refs`, `supporting_claim_refs`, and
`strongest_counter_claim_refs` each require at least one item. Evidence IDs are
unique within their Evidence set. Claim IDs are unique within every Claim set.
This is an explicit domain rule even though relevance is currently fixed to
`MATERIAL`; it must not rely solely on `uniqueItems`.

Only the two core Claim sets are cross-set exclusive:

```text
supporting_claim_refs ∩ strongest_counter_claim_refs = empty
```

The comparison is by `claim_id`, not whole-object equality. The four
classification sets (`assumption_claim_refs`, `conflict_claim_refs`,
`unknown_claim_refs`, and `falsification_claim_refs`) may reuse a Claim across
different classifications: an unresolved Claim can, for example, be both an
assumption and an unknown. Each classification set remains internally unique.
A future static contract test must implement these ID-based checks.

The design labels for negative fixtures are `CLAIM_REFERENCE_DUPLICATE` and
`SUPPORT_COUNTER_CLAIM_OVERLAP`. They are fixture expectations, not stable
runtime error codes and not a machine-produced error locator.

### Valuation material

Only these two combinations are legal:

| `status` | `provenance` | `calculation_replay` | `calculation_receipt_digest` |
| --- | --- | --- | --- |
| `NOT_PROVIDED` | `NONE` | `NOT_APPLICABLE` | `null` |
| `EXTERNALLY_SUPPLIED_UNVERIFIED` | `USER_SUPPLIED` | `EXTERNALLY_SUPPLIED_UNVERIFIED` | `null` |

`valuation_material` is a closed object with exactly these four required
members: `status`, `provenance`, `calculation_replay`, and
`calculation_receipt_digest`. No third status, omitted member, or extra member
is legal. A future PR-5 package cannot create, populate, infer, or validate a
Calculation Receipt digest. In particular, it cannot say an external valuation
is calculated, verified, replayed, decision-grade, or correct.

### Review-readiness status

The only future values are `DRAFT_FOR_REVIEW`, `MORE_EVIDENCE_NEEDED`,
`READY_FOR_CUSTOMER_REVIEW`, and `BLOCKED`. These are a legal-combinations
table, not a runtime state machine. Every value remains non-authorizing.

`adversarial_review` and `independent_review` are both fixed to
`NOT_PERFORMED` in the first static version. The presence of a strongest
counter case does not imply that either review occurred.

### Synthetic fixture wrapper and linkage

The future `Research Review Package` schema contains the six digest fields and
the Evidence/Claim references above. It never contains `fixture_linkage`.
`fixture_linkage` is a test-fixture-wrapper object only, not a customer field,
runtime linkage receipt, or evidence artifact. It is the only comparison
carrier for future static tests:

```yaml
fixture_id: RRP-FIXTURE-001
research_review_package:
  request_id: RTE-SYNTHETIC-001
  subject_identity_digest: sha256:...
  requested_effects_digest: sha256:...
  source_scope_digest: sha256:...
  input_contract_digest: sha256:...
  evidence_set_digest: sha256:...
  claim_set_digest: sha256:...
fixture_linkage:
  request_id: RTE-SYNTHETIC-001
  subject_identity_digest: sha256:...
  requested_effects_digest: sha256:...
  source_scope_digest: sha256:...
  input_contract_digest: sha256:...
  evidence_set_digest: sha256:...
  claim_set_digest: sha256:...
```

The static test compares `request_id` and each same-named digest one-for-one.
It does not calculate, normalize, validate, resolve, or authenticate a digest,
and it does not parse actual PR-4 records. A passing comparison proves only
that synthetic fixture strings match.

## Fixture matrix for a future implementation

| Fixture | Expected structural result | Boundary it demonstrates |
| --- | --- | --- |
| Minimal review package with Evidence and both synthetic core Claim sets | pass | Required review organization only. |
| Externally supplied valuation container | pass | Unverified external material remains non-calculated. |
| No valuation material | pass | `NOT_PROVIDED` legal combination. |
| Every fixed disclosure constant and a closed review object | pass | Required non-authorizing disclosures. |
| Each of the four allowed customer-review statuses | pass | All review-readiness values remain non-authorizing. |
| Valid synthetic fixture wrapper with all six matching linkage digests | pass | Synthetic string linkage only. |
| Empty Evidence set, supporting set, or counter set | fail | Each core reference collection has `minItems: 1`. |
| Repeated Claim ID within one set, including different object presentation | fail, `CLAIM_REFERENCE_DUPLICATE` expectation | ID uniqueness, not object equality. |
| Repeated Evidence ID within its set, including different object presentation | fail | Evidence ID uniqueness. |
| Same `claim_id` across both sets | fail, `SUPPORT_COUNTER_CLAIM_OVERLAP` expectation | Structural support/counter separation. |
| Bad Claim/Evidence ID prefix, casing, or format | fail | Only PR-4 synthetic ID formats are allowed. |
| Package `request_id` differs from `fixture_linkage.request_id` | fail | Synthetic fixture association mismatch only. |
| Any of six same-name digest linkage mismatches | fail | Wrapper-only string comparison. |
| Third valuation state or non-null receipt digest | fail | No calculation receipt representation. |
| Any changed fixed disclosure, synthetic flag, fixture-only flag, persistence, or review value | fail | No capability, authorization, or review-performance claim. |
| `customer_review_status` outside its four-value enum | fail | Closed, non-authorizing review-readiness disclosure. |
| Unknown root field | fail | Closed package shape. |
| Recommendation, order, account, broker, credential, or monitoring field | fail | No financial execution or sensitive-data surface. |

Negative-fixture metadata may name the relevant fields, including both claim
reference sets for an overlap. It must not claim that a runtime validator
already returns an exact path.

## Explicitly prohibited fields and aliases

The implemented static closed schema rejects this explicit finite field
registry, including these structured aliases:

```text
buy, sell, hold, rating, target_price, price_target, position_size,
portfolio_weight, allocation, order, order_quantity, broker, brokerage,
account, account_id, credential, credentials, api_key, trade_instruction,
execution_instruction, automatic_notification, monitoring_schedule,
watchlist_schedule, source_url, evidence_text, customer_material
```

```text
coverage: EXPLICIT_FINITE_FIELD_REGISTRY
natural_language_alias_detection: NOT_IMPLEMENTED
```

Static fixtures cover every field in this registry. This is not a
natural-language safety classifier: it does not claim detection of arbitrary
spellings, nesting forms, or synonyms outside the registered fields. The
closed root object separately rejects unknown root fields.

## Definition of done for the implemented static package

The static implementation contains only a schema, wholly synthetic fixtures,
static contract tests, formal inventory updates, and minimal `0.6.0-dev`
documentation. It succeeds only if it can honestly report:

```text
research_review_package: STATIC_VALIDATED
fixtures: SYNTHETIC_ONLY
financial_data_network_access: NOT_PERFORMED
runtime_execution: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN
external_action: NONE
investment_authorization: NONE
trade_authorization: NONE
adversarial_review: NOT_PERFORMED
independent_review: NOT_PERFORMED
calculation_replay: NOT_APPLICABLE | EXTERNALLY_SUPPLIED_UNVERIFIED
calculation_receipt_digest: null
digest_computation: NOT_IMPLEMENTED
authenticity_verification: NOT_PERFORMED
persistence: ephemeral
```

It must not add a runtime validator, connector, data client, calculator,
professional Skill invocation, Grant lifecycle, persistent store, release,
tag, installation update, or real-world evidence claim.

## Non-goals and stop conditions

Stop and return to design review if implementation would require real data,
client material, an account, a credential, a network request, a computed
digest, a valuation calculation, a review claim, an external action, or any
new authorization lifecycle. Those needs belong to separately authorized,
later stages and cannot be inferred from this review-package design.
