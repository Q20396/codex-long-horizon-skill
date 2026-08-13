# External Capability Source and Effect Assessment Design

Status: `STATIC_CONTRACT_CANDIDATE — RUNTIME_NOT_IMPLEMENTED`

## Purpose and fixed boundary

This document defines a static assessment model and its exact, synthetic-only
candidate package for an external capability source and its claimed effect. It
creates no provider, connector, registry entry, host integration, or runtime
capability.

It does not read or write governed targets; resolve paths; inspect symlinks;
query Authorization; render content; write output; access a network; or call
Obsidian, memory, Hooks, MCP, or a scheduler. It does not alter the formal
Schema inventory or release evidence in `sandbox/skill-incubator/schemas/`,
`docs/releases/`, or `releases/`.

K7-A is the design input for the single future Runtime Gate. This document is
compatible with its boundary: a source descriptor or effect assessment is not
a Runtime Gate request, an authorization decision, host evidence, or execution
evidence.

```text
runtime_execution: NOT_IMPLEMENTED
governed_target_io: NOT_IMPLEMENTED
real_file_read_write: NOT_AUTHORIZED
path_resolution: NOT_IMPLEMENTED
symlink_check: NOT_IMPLEMENTED
authorization_lookup: NOT_IMPLEMENTED
renderer: NOT_IMPLEMENTED
writer: NOT_IMPLEMENTED
network: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN

schema_fixture_validator_test_implementation: STATIC_ONLY_IMPLEMENTED
git_commit_push_pr_release: NOT_PERFORMED
```

## One design-only assessment boundary

The only proposed assessment boundary is **External Capability Source and
Effect Assessment**. It is a design description, not an implemented or
callable public interface. It may inform a separately authorized future
Runtime Gate input, but it cannot invoke a provider or adapter.

Its conceptual input is a static declaration containing exactly these design
subjects:

| Subject | Design-only meaning | Must not mean |
| --- | --- | --- |
| `source_reference` | An opaque reference to a proposed external capability source. | A credential, endpoint, connection, lookup, or enabled provider. |
| `source_class` | A declared class: `EXTERNAL_PROVIDER`, `HOST_CAPABILITY`, or `DECLARED_STATIC_ARTIFACT`. | Evidence that the source exists, is trusted, or is callable. |
| `declared_effects` | The source's claimed effects from the closed effect taxonomy below. | Observation, task request, permission, or execution. |
| `observed_static_indicators` | Non-secret, static indicators asserted by a future review package. | Proof that any effect occurred or that the source is callable. |
| `task_requested_effects` | The closed effects requested by one bounded future task. | Authorization, host permission, or execution. |
| `task_authorized_effects` | The subset an exact future Human/Authorization decision would authorize for that task. | A provider activation, host permission, or execution. |
| `operation_binding` | The future task, intent, target, range, and disposition references claimed by the assessment. | A reusable authorization or decision snapshot. |
| `evidence_minimum` | The minimum non-secret claims that a future authorized implementation would need to assess. | Host observation, execution receipt, or source output. |

The only planned assessment results are:

```text
BLOCKED | OUT_OF_SCOPE | EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY
```

No result permits source access, path access, rendering, writing, network use,
or a later runtime action without separate Human authorization.

## Orthogonal effect model

Every future assessment must keep exactly four distinct layers:

| Layer | Scope | Must not be treated as |
| --- | --- | --- |
| `declared_effects` | What a source claims it could do. | Evidence that it did, may do, or is authorized to do it. |
| `observed_static_indicators` | Non-secret static claims available to a future review. | Runtime observation, provider response, or execution evidence. |
| `task_requested_effects` | What one bounded task asks to be assessed. | Authorization or a permission grant. |
| `task_authorized_effects` | What an exact future decision could authorize for that same task. | Host permission or execution. |

The following identities are deliberately never collapsed:

```text
declared != observed
observed != authorized
authorized != executed
```

No layer may silently populate another. In particular, a declared effect cannot
be inferred from an indicator, an indicator cannot produce authorization, and
an authorized effect cannot produce an attempt, host observation, completion,
or receipt.

## Closed effect taxonomy

The assessment classifies members of the four layers only from the following
closed vocabulary. It does not infer effects from a source, retrieve source
metadata, or inspect a host.

| Effect | Static disposition | Reason |
| --- | --- | --- |
| `NO_EXTERNAL_EFFECT` | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` | A declaration remains only a design artifact. |
| `STATIC_CONTRACT_ANALYSIS` | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` | Static analysis can be designed without activating an external capability. |
| `TARGET_CONTENT_READ` | `OUT_OF_SCOPE` | Reading governed or external content is not implemented or authorized. |
| `TARGET_CONTENT_WRITE` | `OUT_OF_SCOPE` | Writing is not implemented or authorized. |
| `PATH_RESOLUTION_OR_SYMLINK_INSPECTION` | `OUT_OF_SCOPE` | These are future K5/K7 adapter seams only. |
| `AUTHORIZATION_LOOKUP` | `OUT_OF_SCOPE` | K3/K5 lookup remains unimplemented. |
| `RENDER_OR_RETENTION_PROCESSING` | `OUT_OF_SCOPE` | Rendering and retention assessment require future adapters and host evidence. |
| `NETWORK_OR_PROVIDER_REQUEST` | `OUT_OF_SCOPE` | Network and provider activation are not authorized. |
| `HOST_CONTROL_OR_SCHEDULING` | `OUT_OF_SCOPE` | Host enforcement, Hooks, MCP, and scheduling are not implemented. |
| `subprocess_execution` | `OUT_OF_SCOPE` | No subprocess execution capability is implemented or authorized. |
| `package_installation` | `OUT_OF_SCOPE` | Dependency installation is not implemented or authorized. |
| `dynamic_import` | `OUT_OF_SCOPE` | Dynamic loading is not implemented or authorized. |
| `model_context_disclosure` | `OUT_OF_SCOPE` | No source or target material may be disclosed to model context. |
| `background_upload` | `OUT_OF_SCOPE` | Upload or background transfer is not implemented or authorized. |
| `process_spawn` | `OUT_OF_SCOPE` | Process creation is not implemented or authorized. |

An unknown, composite, missing, or internally inconsistent effect is not
normalized or downgraded. It is `BLOCKED`.

### Requested-effect host-enforcement map

The following closed map is the only future basis for
`host_enforcement_required`. It is derived from
`task_requested_effects` only; `declared_effects`,
`observed_static_indicators`, and `task_authorized_effects` cannot trigger
host-enforcement routing.

| Requested effect | Requires host enforcement |
| --- | --- |
| `NO_EXTERNAL_EFFECT` | `false` |
| `STATIC_CONTRACT_ANALYSIS` | `false` |
| `TARGET_CONTENT_READ` | `true` |
| `TARGET_CONTENT_WRITE` | `true` |
| `PATH_RESOLUTION_OR_SYMLINK_INSPECTION` | `true` |
| `AUTHORIZATION_LOOKUP` | `false` |
| `RENDER_OR_RETENTION_PROCESSING` | `true` |
| `NETWORK_OR_PROVIDER_REQUEST` | `false` |
| `HOST_CONTROL_OR_SCHEDULING` | `true` |
| `subprocess_execution` | `true` |
| `package_installation` | `true` |
| `dynamic_import` | `true` |
| `model_context_disclosure` | `false` |
| `background_upload` | `false` |
| `process_spawn` | `true` |

For a multi-effect request, `host_enforcement_required` is `true` exactly
when at least one requested member maps to `true`. A future contract must
reject a supplied boolean that disagrees with this map.

## Ordered fail-closed assessment plan

The future assessment must apply the first matching row and stop. A later row
cannot override an earlier one.

| Priority | Design condition | Planned result |
| --- | --- | --- |
| 1 | A field's own value is missing, has the wrong type or local structure, is outside its closed enum, contains a duplicate array member, or fails another single-field local consistency rule. A supplied `host_enforcement_required` that disagrees with the closed map derived from top-level `task_requested_effects`, and `host_enforcement_claim: NOT_APPLICABLE` for a host-required requested effect, are local inconsistencies. Both uniquely yield `BLOCKED / STRUCTURE_OR_REFERENCE_INVALID`. This row does not compare an `operation_binding` member with its top-level counterpart. | `BLOCKED` |
| 2 | Source provenance, sensitivity, redaction, or retention classification is `UNKNOWN`, incomplete, contradictory, or protected content is declared. | `BLOCKED` |
| 3 | `operation_binding.task_requested_effects` does not exactly match top-level `task_requested_effects`, or `operation_binding.task_authorized_effects` does not exactly match top-level `task_authorized_effects`; or the binding is expired or revoked. Task, intent, evaluation, target, range, proposal/disposition reference, prior effect scope, expiry, and revocation are authoritative fields inside `operation_binding` and have no top-level counterpart. This static candidate intentionally has no persistent reuse evidence and makes no reuse-detection claim. Thus an `operation_binding.task_requested_effects` value that differs from the top-level `task_requested_effects` uniquely yields `BLOCKED / BINDING_OR_DECISION_INVALID`. | `BLOCKED` |
| 4 | The declaration asks to expand a prior read-only, static, or no-effect assessment into a write, render, host-control, or broader-target effect. | `BLOCKED` |
| 5 | A requested effect mapped to `false` above requires actual source access, Authorization lookup, network/provider request, `model_context_disclosure`, background upload, Hook, MCP, or scheduling. | `OUT_OF_SCOPE / ACTUAL_CAPABILITY_NOT_AUTHORIZED` |
| 6a | A requested effect mapped to `true` above requires host enforcement and its claim is `FUTURE_VERIFIABLE`, `NOT_AVAILABLE`, `NOT_PROVEN`, or `CONFLICTING`. `FUTURE_VERIFIABLE` means that a future observation format might be defined; it is not host-enforcement proof. | `OUT_OF_SCOPE / HOST_ENFORCEMENT_NOT_PROVEN` |
| 6b | A requested effect mapped to `true` above has passed every prior static gate, including a separately defined future static condition that does not assert, imply, or require host enforcement, but still requests an actual capability. No current field, baseline, or fixture satisfies that prospective condition. | `OUT_OF_SCOPE / ACTUAL_CAPABILITY_NOT_AUTHORIZED` |
| 7 | None of the preceding conditions applies and the declaration is only `NO_EXTERNAL_EFFECT` or `STATIC_CONTRACT_ANALYSIS`. | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` |

This plan does not replace K7-A Runtime Gate ordering. A future Runtime Gate
would separately apply its own structure, sensitivity, Authorization,
target/effect/range, host-attestation, and actual-capability gates.

## Binding and evidence minimization

A future assessment is single-task, non-transferable, non-reusable, and
design-only. Its `operation_binding` must bind exactly one task reference,
operation intent, `task_requested_effects`, `task_authorized_effects`,
exact target, exact range, and
proposal-or-disposition reference. It must never bind or contain credentials,
tokens, secret headers, source content, absolute paths, stable host identity,
or raw host observations.

`evidence_minimum` may describe only whether a future authorized review would
need a source provenance claim, an effect declaration, a sensitivity/redaction
classification, and a bounded authorization/disposition reference. It must not
store source payloads, rendered output, target content, file names, account
identifiers, execution receipts, or an authorization secret.

`UNKNOWN` remains a first-class value. It cannot be replaced by a default
allow, a fallback provider, a cached disposition, or an earlier assessment.

## Relationship to K5 and K7-A future seams

The following K5 future-runtime scenarios remain exactly design-only:

```text
symlink
directory
resolved containment
Authorization lookup
renderer
capability-expansion activation
host enforcement
```

Each remains:

```text
OUT_OF_SCOPE / NOT_EXECUTED / NOT_PROVEN
```

This document does not add an adapter. If a future implementation is separately
authorized, it must remain inside K7-A's one Runtime Gate and its internal
adapter seams: `AuthorizationDecisionAdapter`, `PathContainmentAdapter`,
`SymlinkInspectionAdapter`, `RendererAdapter`, `WriterAdapter`, and
`HostEnforcementAttestationAdapter`. An External Capability Source and Effect
Assessment is neither an additional adapter nor a way to call any of them.

## Future static-contract field dictionary

This field dictionary is the normative design input for the exact static-only
candidate package listed below. It is not a runtime payload, provider API, or
authorization for any external effect.

| Field | Required future type and closed rule | Design-only meaning |
| --- | --- | --- |
| `source_reference` | Required opaque task-local reference; no URL, credential, absolute path, account identifier, or source content. | Identifies one declared source without accessing it. |
| `source_class` | Required closed enum: `EXTERNAL_PROVIDER`, `HOST_CAPABILITY`, or `DECLARED_STATIC_ARTIFACT`. | Classifies a claimed source; does not attest to existence or trust. |
| `declared_effects` | Required non-empty ordered array of unique taxonomy members. | Source claims only. |
| `observed_static_indicators` | Required array of closed non-secret indicator categories; no source response, host observation, or execution receipt. | Static review assertions only. |
| `task_requested_effects` | Required non-empty ordered array of unique taxonomy members. | Effects requested for exactly one task. |
| `task_authorized_effects` | Required ordered array of unique taxonomy members; it must be an exact subset of requested effects. | A future decision's bounded authorized set, never host permission or execution. |
| `operation_binding` | Required closed object containing exactly task reference, operation intent, evaluation time, `task_requested_effects`, `task_authorized_effects`, exact target, exact range, proposal-or-disposition reference, prior effect scope, expiry, and revocation state. | One non-transferable task binding, including the exact current and prior effect scopes. |
| `evidence_minimum` | Required closed object of non-secret provenance, sensitivity/redaction, and bounded reference claims. | The minimum future review evidence; never raw source or target material. |
| `host_enforcement_required` | Required boolean derived only from `task_requested_effects` in a future static contract. | Routes a requested host-enforced effect; it cannot be inferred from authorization alone. |
| `host_enforcement_claim` | Required closed enum: `NOT_APPLICABLE`, `FUTURE_VERIFIABLE`, `NOT_AVAILABLE`, `NOT_PROVEN`, or `CONFLICTING`. | A future static claim only; it is neither a host observation nor proof of host enforcement. |
| `planned_outcome` | Required closed enum: `BLOCKED`, `OUT_OF_SCOPE`, or `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY`. | A static planned result, never execution evidence. |
| `reason_category` | Required closed enum from the categories below. | Deterministic explanation of the first matching result. |

The four effect fields are intentionally orthogonal. A future static contract
must retain the following invariants:

```text
declared_effects != observed_static_indicators
observed_static_indicators != task_authorized_effects
task_authorized_effects != execution
task_authorized_effects ⊆ task_requested_effects
```

The subset invariant does not make a requested effect authorized, and neither
array authorizes any source access or runtime effect.

### Nested closed-field ownership and derived-result consistency

The future Schema is the sole owner of every record-local shape rule, including
the nested objects below. The static validator must not duplicate local type,
format, enum, cardinality, nullable, or unknown-field checks.

| Nested object | Required closed local fields and future Schema rules |
| --- | --- |
| `operation_binding` | Exact required fields: `task_reference`, `operation_intent`, `evaluation_at`, `task_requested_effects`, `task_authorized_effects`, `target`, `range`, `proposal_or_disposition_reference`, `prior_effect_scope`, `expires_at`, and `revocation_state`; `additionalProperties: false`. All reference, intent, target, range, and disposition fields are non-null strings from their future closed vocabularies. Both effect fields and `prior_effect_scope` are non-empty unique arrays of taxonomy strings. `evaluation_at` and `expires_at` are non-null offset-aware ISO 8601 strings. `revocation_state` is a non-null closed enum: `NOT_REVOKED` or `REVOKED`. |
| `evidence_minimum` | Exact required fields: `provenance_classification`, `sensitivity_classification`, `redaction_classification`, `retention_classification`, and `bounded_reference_claim`; `additionalProperties: false`. Every field is a non-null string from a future closed vocabulary; no nullable form, array, object, raw source, target content, credential, absolute path, host observation, or receipt is allowed. |

`planned_outcome` and `reason_category` are required record-local closed enum
fields so fixtures can declare an expected result. After the Draft Schema gate,
the prospective validator derives the first-match result from priorities 1–7.
If either supplied field differs from that one derived outcome/category pair,
the validator must fail closed as `BLOCKED / STRUCTURE_OR_REFERENCE_INVALID`;
it must never ignore, overwrite, or normalize the supplied assertion.

The validator's sole prospective responsibilities are cross-field or
cross-record binding, evaluation/expiry/revocation time relationships, the
ordered first-match plan, and this derived-result comparison. Schema remains
the sole owner of all local closed shape, type, format, enum, cardinality,
nullable, and unknown-field rules.

### Closed observed-static-indicator shape

`observed_static_indicators` must be an ordered array of unique exact strings
from this closed enum; it must contain no object, nested array, null, number,
boolean, source response, host observation, or execution receipt:

```text
SOURCE_REFERENCE_DECLARED
SOURCE_CLASS_DECLARED
PROVENANCE_CLASSIFIED
SENSITIVITY_CLASSIFIED
REDACTION_CLASSIFIED
DECLARED_EFFECTS_CLASSIFIED
TASK_REQUESTED_EFFECTS_CLASSIFIED
TASK_AUTHORIZED_EFFECTS_CLASSIFIED
OPERATION_BINDING_DECLARED
HOST_ENFORCEMENT_UNAVAILABLE
HOST_ENFORCEMENT_UNPROVEN
HOST_ENFORCEMENT_CONFLICTING
```

The indicator list is static review metadata only. Its presence does not
confirm that a source was contacted, a host was inspected, or an effect ran.

### Planned closed reason categories

| Category | Planned outcome | Applies to |
| --- | --- | --- |
| `STRUCTURE_OR_REFERENCE_INVALID` | `BLOCKED` | Missing, malformed, non-closed, duplicated, or inconsistent fields. |
| `SOURCE_OR_SENSITIVITY_UNKNOWN` | `BLOCKED` | Unknown provenance, sensitivity, redaction, retention, or protected content. |
| `BINDING_OR_DECISION_INVALID` | `BLOCKED` | Binding mismatch, expiry, revocation, or task/disposition mismatch. |
| `EFFECT_EXPANSION_BLOCKED` | `BLOCKED` | Requested or authorized effect expands the bounded static declaration. |
| `ACTUAL_CAPABILITY_NOT_AUTHORIZED` | `OUT_OF_SCOPE` | A request requires source access, lookup, path/symlink work, rendering, writing, network, process, import, installation, upload, context disclosure, Hook, MCP, or scheduling. |
| `HOST_ENFORCEMENT_NOT_PROVEN` | `OUT_OF_SCOPE` | A requested host-enforced effect has unavailable, unproven, or conflicting host evidence. |
| `STATIC_DESIGN_ONLY` | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` | A complete closed static declaration without an external effect request. |

## Synthetic fixture matrix design

Every future fixture must be synthetic, fixture-only, non-secret, and local.
The following named baseline literals are complete, lawful, and immutable.
They each contain every required field; a fixture harness must not supply an
implicit value. The listed planned outcome is the baseline's first-match result,
not execution evidence.

### Complete immutable baseline literals

`STATIC-DESIGN-BASELINE` is the zero-mutation positive control:

```text
source_reference: SOURCE-SYNTHETIC-001
source_class: DECLARED_STATIC_ARTIFACT
declared_effects: [STATIC_CONTRACT_ANALYSIS]
observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]
task_requested_effects: [STATIC_CONTRACT_ANALYSIS]
task_authorized_effects: [STATIC_CONTRACT_ANALYSIS]
operation_binding: {task_reference: TASK-SYNTHETIC-001, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [STATIC_CONTRACT_ANALYSIS], task_authorized_effects: [STATIC_CONTRACT_ANALYSIS], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-001, prior_effect_scope: [STATIC_CONTRACT_ANALYSIS], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}
evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-001}
host_enforcement_required: false
host_enforcement_claim: NOT_APPLICABLE
planned_outcome: EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY
reason_category: STATIC_DESIGN_ONLY
```

`HOST-REQUIRED-BASELINE` is a complete priority-6a baseline. Its
`FUTURE_VERIFIABLE` claim is explicitly unproven, not a way to pass host
enforcement:

```text
source_reference: SOURCE-SYNTHETIC-101
source_class: DECLARED_STATIC_ARTIFACT
declared_effects: [TARGET_CONTENT_WRITE]
observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]
task_requested_effects: [TARGET_CONTENT_WRITE]
task_authorized_effects: [TARGET_CONTENT_WRITE]
operation_binding: {task_reference: TASK-SYNTHETIC-101, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [TARGET_CONTENT_WRITE], task_authorized_effects: [TARGET_CONTENT_WRITE], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-101, prior_effect_scope: [TARGET_CONTENT_WRITE], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}
evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-101}
host_enforcement_required: true
host_enforcement_claim: FUTURE_VERIFIABLE
planned_outcome: OUT_OF_SCOPE
reason_category: HOST_ENFORCEMENT_NOT_PROVEN
```

`ACTUAL-CAPABILITY-BASELINE` is a complete priority-5 baseline:

```text
source_reference: SOURCE-SYNTHETIC-201
source_class: DECLARED_STATIC_ARTIFACT
declared_effects: [model_context_disclosure]
observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]
task_requested_effects: [model_context_disclosure]
task_authorized_effects: [model_context_disclosure]
operation_binding: {task_reference: TASK-SYNTHETIC-201, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [model_context_disclosure], task_authorized_effects: [model_context_disclosure], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-201, prior_effect_scope: [model_context_disclosure], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}
evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-201}
host_enforcement_required: false
host_enforcement_claim: NOT_APPLICABLE
planned_outcome: OUT_OF_SCOPE
reason_category: ACTUAL_CAPABILITY_NOT_AUTHORIZED
```

The following five effect-specific entries are likewise complete immutable
route-control baselines, not mutations. Each row explicitly fixes every
variable literal; the full indicator and evidence arrays are repeated to avoid
inheritance. `FUTURE_VERIFIABLE` is unproven, so each host-required control
reaches priority 6a; non-host-required controls reach priority 5. They exist
to prove route selection without requiring an artificial source-reference
mutation.

| Baseline ID | Complete fixed literal |
| --- | --- |
| `ACTUAL-BACKGROUND-UPLOAD-BASELINE` | `source_reference: SOURCE-SYNTHETIC-202`; `source_class: DECLARED_STATIC_ARTIFACT`; `declared_effects: [background_upload]`; `observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]`; `task_requested_effects: [background_upload]`; `task_authorized_effects: [background_upload]`; `operation_binding: {task_reference: TASK-SYNTHETIC-202, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [background_upload], task_authorized_effects: [background_upload], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-202, prior_effect_scope: [background_upload], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}`; `evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-202}`; `host_enforcement_required: false`; `host_enforcement_claim: NOT_APPLICABLE`; `planned_outcome: OUT_OF_SCOPE`; `reason_category: ACTUAL_CAPABILITY_NOT_AUTHORIZED`. |
| `HOST-SUBPROCESS-BASELINE` | `source_reference: SOURCE-SYNTHETIC-301`; `source_class: DECLARED_STATIC_ARTIFACT`; `declared_effects: [subprocess_execution]`; `observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]`; `task_requested_effects: [subprocess_execution]`; `task_authorized_effects: [subprocess_execution]`; `operation_binding: {task_reference: TASK-SYNTHETIC-301, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [subprocess_execution], task_authorized_effects: [subprocess_execution], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-301, prior_effect_scope: [subprocess_execution], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}`; `evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-301}`; `host_enforcement_required: true`; `host_enforcement_claim: FUTURE_VERIFIABLE`; `planned_outcome: OUT_OF_SCOPE`; `reason_category: HOST_ENFORCEMENT_NOT_PROVEN`. |
| `HOST-PACKAGE-INSTALLATION-BASELINE` | `source_reference: SOURCE-SYNTHETIC-302`; `source_class: DECLARED_STATIC_ARTIFACT`; `declared_effects: [package_installation]`; `observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]`; `task_requested_effects: [package_installation]`; `task_authorized_effects: [package_installation]`; `operation_binding: {task_reference: TASK-SYNTHETIC-302, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [package_installation], task_authorized_effects: [package_installation], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-302, prior_effect_scope: [package_installation], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}`; `evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-302}`; `host_enforcement_required: true`; `host_enforcement_claim: FUTURE_VERIFIABLE`; `planned_outcome: OUT_OF_SCOPE`; `reason_category: HOST_ENFORCEMENT_NOT_PROVEN`. |
| `HOST-DYNAMIC-IMPORT-BASELINE` | `source_reference: SOURCE-SYNTHETIC-303`; `source_class: DECLARED_STATIC_ARTIFACT`; `declared_effects: [dynamic_import]`; `observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]`; `task_requested_effects: [dynamic_import]`; `task_authorized_effects: [dynamic_import]`; `operation_binding: {task_reference: TASK-SYNTHETIC-303, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [dynamic_import], task_authorized_effects: [dynamic_import], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-303, prior_effect_scope: [dynamic_import], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}`; `evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-303}`; `host_enforcement_required: true`; `host_enforcement_claim: FUTURE_VERIFIABLE`; `planned_outcome: OUT_OF_SCOPE`; `reason_category: HOST_ENFORCEMENT_NOT_PROVEN`. |
| `HOST-PROCESS-SPAWN-BASELINE` | `source_reference: SOURCE-SYNTHETIC-304`; `source_class: DECLARED_STATIC_ARTIFACT`; `declared_effects: [process_spawn]`; `observed_static_indicators: [SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]`; `task_requested_effects: [process_spawn]`; `task_authorized_effects: [process_spawn]`; `operation_binding: {task_reference: TASK-SYNTHETIC-304, operation_intent: STATIC_ASSESSMENT, evaluation_at: 2030-01-01T00:00:00Z, task_requested_effects: [process_spawn], task_authorized_effects: [process_spawn], target: SYNTHETIC_EXTERNAL_CAPABILITY, range: DECLARATION_ONLY, proposal_or_disposition_reference: DISPOSITION-SYNTHETIC-304, prior_effect_scope: [process_spawn], expires_at: 2030-12-31T23:59:59Z, revocation_state: NOT_REVOKED}`; `evidence_minimum: {provenance_classification: DECLARED, sensitivity_classification: DECLARED_NON_SENSITIVE, redaction_classification: DECLARED_COMPLETE, retention_classification: DECLARED_NON_RETAINING, bounded_reference_claim: DISPOSITION-SYNTHETIC-304}`; `host_enforcement_required: true`; `host_enforcement_claim: FUTURE_VERIFIABLE`; `planned_outcome: OUT_OF_SCOPE`; `reason_category: HOST_ENFORCEMENT_NOT_PROVEN`. |

Every route-control positive is a zero-mutation complete baseline control. Each
negative matrix row starts from the complete named baseline and changes exactly
one field. `before` and `after` state the complete value of that field. The
table is the exact design-to-fixture alignment matrix: its case ID, baseline,
field, before value, after value, outcome, and reason must match the synthetic
fixture files and their tests. This table does not create a JSON fixture, test,
Schema, or validator.

| Future synthetic case | Baseline ID | Single field mutation | Before | After | Unique expected outcome | Unique reason category |
| --- | --- | --- | --- | --- | --- | --- |
| `missing-source-reference` | `STATIC-DESIGN-BASELINE` | `source_reference` | `SOURCE-SYNTHETIC-001` | missing | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `unknown-source-class` | `STATIC-DESIGN-BASELINE` | `source_class` | `DECLARED_STATIC_ARTIFACT` | `UNKNOWN_SOURCE_CLASS` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `unknown-declared-effect` | `STATIC-DESIGN-BASELINE` | `declared_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[UNKNOWN_EFFECT]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `duplicate-requested-effect` | `STATIC-DESIGN-BASELINE` | `task_requested_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[STATIC_CONTRACT_ANALYSIS, STATIC_CONTRACT_ANALYSIS]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `declared-observed-confusion` | `STATIC-DESIGN-BASELINE` | `declared_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[SOURCE_REFERENCE_DECLARED]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `observed-authorized-confusion` | `STATIC-DESIGN-BASELINE` | `task_authorized_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[TASK_AUTHORIZED_EFFECTS_CLASSIFIED]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `unknown-static-indicator` | `STATIC-DESIGN-BASELINE` | `observed_static_indicators` | `[SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]` | `[UNKNOWN_INDICATOR, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `duplicate-static-indicator` | `STATIC-DESIGN-BASELINE` | `observed_static_indicators` | `[SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]` | `[SOURCE_REFERENCE_DECLARED, SOURCE_REFERENCE_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `indicator-non-array` | `STATIC-DESIGN-BASELINE` | `observed_static_indicators` | `[SOURCE_REFERENCE_DECLARED, SOURCE_CLASS_DECLARED, PROVENANCE_CLASSIFIED, SENSITIVITY_CLASSIFIED, REDACTION_CLASSIFIED, DECLARED_EFFECTS_CLASSIFIED, TASK_REQUESTED_EFFECTS_CLASSIFIED, TASK_AUTHORIZED_EFFECTS_CLASSIFIED, OPERATION_BINDING_DECLARED]` | `SOURCE_REFERENCE_DECLARED` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `host-enforcement-map-mismatch` | `STATIC-DESIGN-BASELINE` | `host_enforcement_required` | `false` | `true` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `planned-outcome-mismatch` | `STATIC-DESIGN-BASELINE` | `planned_outcome` | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` | `OUT_OF_SCOPE` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `reason-category-mismatch` | `STATIC-DESIGN-BASELINE` | `reason_category` | `STATIC_DESIGN_ONLY` | `ACTUAL_CAPABILITY_NOT_AUTHORIZED` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `requested-effect-binding-mismatch` | `STATIC-DESIGN-BASELINE` | `operation_binding.task_requested_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[TARGET_CONTENT_WRITE]` | `BLOCKED` | `BINDING_OR_DECISION_INVALID` |
| `authorized-not-requested` | `STATIC-DESIGN-BASELINE` | `task_authorized_effects` | `[STATIC_CONTRACT_ANALYSIS]` | `[TARGET_CONTENT_WRITE]` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |
| `expired-operation-binding` | `STATIC-DESIGN-BASELINE` | `operation_binding.expires_at` | `2030-12-31T23:59:59Z` | `2029-12-31T23:59:59Z` | `BLOCKED` | `BINDING_OR_DECISION_INVALID` |
| `revoked-operation-binding` | `STATIC-DESIGN-BASELINE` | `operation_binding.revocation_state` | `NOT_REVOKED` | `REVOKED` | `BLOCKED` | `BINDING_OR_DECISION_INVALID` |
| `effect-expansion` | `HOST-REQUIRED-BASELINE` | `operation_binding.prior_effect_scope` | `[TARGET_CONTENT_WRITE]` | `[STATIC_CONTRACT_ANALYSIS]` | `BLOCKED` | `EFFECT_EXPANSION_BLOCKED` |
| `renderer-retention-risk` | `STATIC-DESIGN-BASELINE` | `evidence_minimum.retention_classification` | `DECLARED_NON_RETAINING` | `CONTRADICTORY` | `BLOCKED` | `SOURCE_OR_SENSITIVITY_UNKNOWN` |
| `host-required-unproven` | `HOST-REQUIRED-BASELINE` | `host_enforcement_claim` | `FUTURE_VERIFIABLE` | `NOT_PROVEN` | `OUT_OF_SCOPE` | `HOST_ENFORCEMENT_NOT_PROVEN` |
| `host-required-not-applicable` | `HOST-REQUIRED-BASELINE` | `host_enforcement_claim` | `FUTURE_VERIFIABLE` | `NOT_APPLICABLE` | `BLOCKED` | `STRUCTURE_OR_REFERENCE_INVALID` |

## Required future review gates

Any expansion beyond this exact Schema, synthetic fixture, validator, and test
candidate package requires a separate Human gate, a new exact file allowlist,
and a new static contract design. That proposal must show:

1. a closed source-class and effect vocabulary;
2. non-secret synthetic-only examples and negative cases;
3. deterministic first-match, fail-closed outcomes;
4. exact binding and expiry/revocation treatment;
5. evidence minimization and receipt ordering;
6. a threat model for source substitution, effect expansion, renderer
   retention, and host-evidence conflict; and
7. fresh independent review after each candidate-byte change.

This document grants no provider, adapter, runtime, or external-effect action.
The static-only candidate package remains confined to the exact allowlist.

## Static implementation candidate boundary (runtime not authorized)

This section defines the smallest static-contract candidate package. Its
Schema, synthetic fixtures, dependency-free validator, and tests are created
only under the exact allowlist below. They remain static evidence: this section
does not authorize a provider, adapter, runtime, or external effect.

### Static candidate file allowlist and responsibilities

This batch uses the exact Human-approved allowlist below. It must not silently
add provider, adapter, runtime, registry, release, or formal-inventory changes.

| Candidate path | Sole static responsibility | Explicitly not responsible for |
| --- | --- | --- |
| `sandbox/skill-incubator/external-capability-source-effect-assessment/external-capability-source-effect-assessment.schema.json` | Draft 2020-12 record-local closed shape, exact field vocabulary, local type rules, closed enums, and array uniqueness. | Cross-record binding, host observation, provider access, path work, or execution. |
| `tests/fixtures/external-capability-source-effect-assessment/positive/cases.json` | Fully synthetic, fixture-only complete positive controls with deterministic expected static outcomes. | Source descriptors from real systems or execution evidence. |
| `tests/fixtures/external-capability-source-effect-assessment/negative/cases.json` | Fully synthetic, fixture-only complete baselines plus exactly one negative mutation per case. | Composite mutations, real targets, credentials, or source payloads. |
| `scripts/validate_external_capability_source_and_effect_assessment.py` | Dependency-free static admission and deterministic first-match assessment after a Draft Schema gate has accepted record-local shape. | Schema replacement, adapter invocation, source lookup, path resolution, symlink inspection, rendering, writing, network, process, or host enforcement. |
| `tests/test_external_capability_source_and_effect_assessment.py` | Regression evidence for the formal static validator, Schema alignment, first-match result, and synthetic fixture matrix. | Runtime, provider, integration, filesystem, network, or host-enforcement tests. |

The existing K6 artifact layout is only a naming reference. The paths above do
not authorize a modification to K6, its formal Schema inventory, or any
unlisted validator, fixture, or test.

### Future contract boundary

A candidate Schema owns only the closed, record-local fields declared in this
document:

```text
source_reference
source_class
declared_effects
observed_static_indicators
task_requested_effects
task_authorized_effects
operation_binding
evidence_minimum
host_enforcement_required
host_enforcement_claim
planned_outcome
reason_category
```

A candidate Schema must preserve the closed `source_class`, effect taxonomy,
indicator vocabulary, host-claim vocabulary, planned outcomes, and reason
categories already specified here. It must own every record-local check,
including nested closed objects, field types, string formats, closed enums,
nullability, cardinality, duplicate array members, and unknown-field
rejection. It must not claim to decide cross-field binding,
expiry relationships, revocation, effect expansion, host evidence, or
actual-capability routing.

After the Draft 2020-12 record-local gate has accepted the complete record,
the candidate validator may perform only cross-field or cross-record binding,
evaluation/expiry/revocation relationships, and the first-match decisions that
depend on those values. It must not repeat priority-1 local-shape validation,
without reordering or adding a default allow:

```text
1. local structure and local consistency
2. source, sensitivity, redaction, retention, or protected-content failure
3. operation-binding mismatch, expiry, or revocation
4. effect expansion
5. non-host-enforced actual-capability request
6a. host-enforced request with unavailable, unproven, or conflicting evidence
6b. host-enforced actual-capability request after 6a passes
7. static design-only declaration
```

The only prospective results remain closed:

```text
BLOCKED
OUT_OF_SCOPE
EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY
```

The corresponding reason category must be exactly one of the closed categories
in `Planned closed reason categories`; a future validator must return the
first matching category and stop. A static result is not an authorization,
attempt, observation, completion, receipt, or execution claim.

### Synthetic fixture and evidence rules

Every candidate fixture must be fully synthetic, fixture-only, local, non-secret,
and self-contained. Each fixture must explicitly identify its baseline and
expected first-match result. A positive control is a complete immutable
baseline with zero mutations. Every negative case must be:

```text
complete lawful named baseline
+ one assessment-input field-level mutation
+ explicit before value
+ explicit after value
+ one expected outcome
+ one expected reason category
```

For a negative record, `planned_outcome` and `reason_category` are expected
derived-result assertions, not assessment-input mutations. They are updated
only to the unique result required by the one mutated input field and are
separately checked against the validator's derivation. No second assessment
input field may change.

For the static candidate, the positive fixture `baselines` object is the
immutable baseline authority. Every `baseline_id` in either fixture file must
resolve to one of its exact records; the tests materialize each negative record
from that record before applying its sole mutation. The prose literals above
remain explanatory, rather than a parallel machine-readable baseline source.

No fixture may inherit omitted values, combine mutations, use a real source,
absolute path, credential, endpoint, account identifier, content payload,
host observation, or execution receipt. The future test suite must prove that
each matrix row has one baseline and one mutation, and that each expected
outcome follows only the first matching priority.

Evidence must remain minimized to the closed declaration fields and bounded
non-secret reference claims. The future static package must neither store nor
emit source content, target content, absolute paths, stable host identities,
credentials, raw Authorization records, raw host observations, renderer output,
or execution receipts.

### Adapter and runtime exclusion

The six K7-A seams remain internal future seams only:

```text
AuthorizationDecisionAdapter
PathContainmentAdapter
SymlinkInspectionAdapter
RendererAdapter
WriterAdapter
HostEnforcementAttestationAdapter
```

The future static package may name these seams only to assert that it does not
invoke them. It must not implement an adapter, provider, connector, registry,
or lifecycle activation, and must not access a source, filesystem target,
network, process, host, model context, or scheduler.

```text
runtime_execution: NOT_IMPLEMENTED
governed_target_io: NOT_IMPLEMENTED
real_file_read_write: NOT_AUTHORIZED
path_resolution: NOT_IMPLEMENTED
symlink_check: NOT_IMPLEMENTED
authorization_lookup: NOT_IMPLEMENTED
renderer: NOT_IMPLEMENTED
writer: NOT_IMPLEMENTED
network: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN
```

### Static candidate acceptance and review gate

The Human gate authorized the exact files, exact base/HEAD, and static
implementation scope for this candidate. It must provide all of the following
evidence before an independent read-only review:

1. Draft 2020-12 validation for every synthetic fixture, using an already
   available offline environment and without installation or network access;
2. formal validator regressions proving closed fields, reason categories,
   first-match routing, and no default allow;
3. fixture-matrix checks proving a complete baseline plus one mutation per
   negative case;
4. JSON parsing, Python compilation, targeted tests, `git diff --check`, exact
   changed-file allowlist/status, no `.pyc`/`.pyo`, and SHA-256 values for all
   candidate files; and
5. two new independent read-only reviews bound to the same base/HEAD and exact
   candidate bytes.

Passing these static checks remains evidence only. It does not authorize
Git staging, commit, push, PR, merge, release, provider access, actual I/O,
network use, or runtime activation. Those effects require separate Human
authorization after a future fixed-identity review.

## Design matrix

| Scenario | Required planned result | Rationale |
| --- | --- | --- |
| Unknown source provenance | `BLOCKED` | An undeclared or unverifiable source cannot be assessed safely. |
| Missing redaction classification | `BLOCKED` | Sensitivity is not default-allow. |
| Expired or revoked operation binding | `BLOCKED` | A stale binding cannot support a new assessment. |
| Read-to-write effect expansion | `BLOCKED` | Exact effect binding prevents privilege escalation. |
| Renderer-retention risk | `BLOCKED` | Protected content and retention uncertainty fail closed. |
| Actual provider, network, process, installation, import, upload, or context-disclosure request | `OUT_OF_SCOPE` | No such capability exists here. |
| Actual path, symlink, lookup, render, or writer request | `OUT_OF_SCOPE` | These remain K5/K7 future seams. |
| Required host evidence absent or conflicting | `OUT_OF_SCOPE` | Only a requested effect that requires host enforcement reaches this row. |
| Audit/receipt requested as execution evidence | `OUT_OF_SCOPE` | This design emits no attempt, effect, or receipt. |
| Static, closed, no-effect declaration with no host-enforced effect | `EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY` | The only non-blocked design outcome is not execution. |

## Stop state

```text
external_capability_source_effect_assessment: STATIC_CONTRACT_CANDIDATE
runtime_execution: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN
schema_fixture_validator_test_implementation: STATIC_ONLY_IMPLEMENTED
real_file_read_write: NOT_AUTHORIZED
network: NOT_AUTHORIZED
git_commit_push_pr_release: NOT_PERFORMED

next_action: INDEPENDENT_READ_ONLY_DESIGN_REVIEW
```
