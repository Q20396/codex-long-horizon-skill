# Public Equity Research Governance Contract

Status: `candidate_only`

This is a clean-room, non-executable contract for synthetic public-equity
research records. It is not a registered skill, a data connector, an agent
runtime, an installed Public Equity Investing extension, or an authorization
to monitor markets or take investment action.

## Purpose

The contract makes four research-governance requirements machine-checkable:

1. each core claim records a bull case, bear case, supporting and
   disconfirming evidence, a falsification condition, and data still needed;
2. decisions are append-only and preserve the customer's non-execution
   `human_disposition`;
3. historical research uses point-in-time evidence and blocks look-ahead;
4. recommendations have a fixed research-only output and a research-only next
   action.

## Evidence contract

Every source has a stable `source_id`, non-sensitive `source_locator`, and
`source_version`. A locator may be a public URL, an ASX announcement number, a
content SHA-256, or an approved internal document ID. It must not contain a
credential, account identifier, private absolute path, or raw customer
material. A source ID without a locator and version is not decision-grade.
Accepted locator forms are HTTPS URLs without user information or sensitive
query keys, `urn:` references, `sha256:` digests, `asx-announcement:` IDs, and
`internal-document-id:` IDs. Relative filesystem paths, absolute paths on any
platform, `file:` URIs, and credential- or account-bearing locators are
rejected. For HTTPS locators, the path, query, and fragment are decoded until
stable for at most three rounds, then checked consistently. Invalid percent
escapes, content that still changes after the decoding bound, account path
segments such as `account` or `accounts`, account identifier parameters,
credentials, and broker or execution endpoints are not valid evidence
locators.

Draft 2020-12 Schema validation is a raw structural gate. It cannot perform URL
canonicalization, so decoded locator validation by the dependency-free
validator is mandatory even when a formal Schema engine is available.

Evidence references in claims and decisions must resolve to sources in the
same record. Risk and missing-evidence references must also resolve locally.
Source, core-claim, assumption, scenario, risk, missing-evidence, and decision
entry IDs are unique within one record. Duplicate IDs are rejected rather than
collapsed into a set.
The contract never fetches, uploads, copies, or redistributes a source.

## Point-in-time contract

All non-null fields ending in `_at`, plus `research_as_of`, use the following
fixed RFC3339-like timestamp profile. Sources record `time_precision` and
`timezone_basis`.

- The Schema is the lexical gate: four ASCII year digits; an uppercase `T`;
  an uppercase `Z` or a numeric UTC offset; fractional seconds with one to six
  digits; and no trailing CR, LF, `U+2028`, or `U+2029`.
- The lexical gate permits months `01`--`12`, days `01`--`31`, hours
  `00`--`23`, and minutes and seconds `00`--`59`. Leap seconds (`:60`) are
  forbidden.
- Numeric offsets have an absolute maximum of `14:00`; `-00:00` is forbidden
  because it denotes an unknown local offset. `Z` and `+00:00` are allowed.
- The dependency-free contract validator is the Gregorian calendar gate. It
  rejects year `0000`, a non-leap-year 29 February, impossible month/day
  combinations, and any lexical timestamp that cannot be calendar-parsed.

`format: date-time` remains a compatibility annotation and defence-in-depth
signal. Calendar validity does not rely on a host treating `format` as an
assertion: the dependency-free Gregorian gate in
`scripts/validate_public_equity_research_governance_contract.py` is mandatory
and fail-closed. The timestamp reasons are
`TIMESTAMP_LEXICAL_PROFILE_INVALID`, `TIMESTAMP_CALENDAR_INVALID`,
`TIMESTAMP_OFFSET_INVALID_OR_REQUIRED`, and `TIMESTAMP_CONTAINER_INVALID`;
malformed values and containers never escape as raw parser exceptions.

The same dependency-free verifier is the record-level timestamp gate. It
explicitly validates root, research-context, source, and decision-log timestamp
fields, then compares each available source instant with `decision_at` using
offset-aware microsecond precision. A source available after the decision
produces `POINT_IN_TIME_VIOLATION` unless the supplied record is explicitly
`point_in_time_blocked` for `AVAILABLE_AFTER_DECISION`.

The current lexical Schema identity is
`sha256:6c0ea9739ef65301d3185f622d22d2edbd0d671004ac3c93739a3bf29dfcd5e7`.
This records the current byte identity only; it makes no claim about an
immediately preceding candidate.

The formal verifier is deliberately limited to timestamp field validity and
point-in-time temporal relations. It does not replace the Schema local-shape
gate and does not validate locators, claims, boundaries, or other contract
semantics. The broader contract tests remain static composition checks; they
do not establish runtime capability or host enforcement.

Timestamp-field coverage uses two fixed identities, not a partial Draft
2020-12 interpreter. The formal inventory is the sole mapping for this
verifier: each entry pins a Schema JSON Pointer, closed condition identifier
and context, required/nullability rule, container path/type,
repetition/minimum size, field, and temporal role. No parallel temporal-role
table is permitted. A supplied inventory must exactly equal this formal tuple;
unknown, missing, duplicate, reordered, mistyped, or redirected descriptors
fail closed.

<!-- PUBLIC_EQUITY_TIMESTAMP_INVENTORY_MANIFEST
sha256:85e2936cbc172351d5a81db33a92ba3bae654e7c3ba2609a5e1fe791d0083fb8
canonicalization:json-sort-keys-compact-separators
-->

<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST
sha256:94d8f534b9883bf2811194421b01864e16e0debce9495ac8e98b267258492748
canonicalization:utf-8-json-sort-keys-compact-separators-array-order-preserved
annotation_pointers:/,/$defs/offsetDateTime,/$defs/nullableOffsetDateTime,/properties/sources,/allOf/0/then/properties/sources/items/allOf/1
annotation_keys:title,description,$comment
-->

The semantic Schema digest serializes the complete Schema JSON tree with UTF-8,
sorted object keys, compact separators, preserved array order, and JSON
`allow_nan=false`. Only exact builtin JSON types are accepted; subclasses,
non-finite floats, non-string object keys, and cyclic structures fail closed.
Only
string-valued `title`, `description`, and `$comment` at the exact annotation
pointers recorded above are excluded. Identically named keys inside
`properties` or `$defs` remain validation data. Every other property, required
list, enum, applicator, `$ref`, wrapper, and timestamp occurrence affects the
digest. The inventory manifest separately hashes the ordered descriptor array,
including every field, `null`, booleans, and temporal role. Each marker must
occur exactly once: occurrence is counted by marker name before the unique
instance's complete syntax, canonicalization identifier, and digest are
verified. A malformed, partial, or conflicting second marker fails closed.

The verifier requires the expected semantic digest for every alignment call;
there is no successful digest-free alignment path. Its inventory gate accepts
only an exact builtin tuple of exact `TimestampFieldSpec` entries, with strict
field types before any digest, traversal, or temporal comparison. Temporal-role
names are a single closed set used by the same inventory gate and relation
lookup. Block-reason input is likewise accepted only as an exact list of exact
strings before iteration or set construction.

The sole public record-level timestamp entry point applies this fixed order:
manifest uniqueness and syntax, manifest digest verification, Schema semantic
identity, inventory shape, then record timestamp and point-in-time checks.
The lower-level record walker is private and unchecked; it is not a public
acceptance result. Static aggregate tests use the public entry point for every
successful record judgment.

The full Draft 2020-12 Schema engine remains the authority for structural
semantics. The verifier validates only the fixed inventory, timestamp values,
and role-driven point-in-time relations; it does not evaluate Schema keywords.

The formal Public Equity aggregate has two required gates for every positive
synthetic fixture: first Draft 2020-12 validates the complete record shape,
then the public timestamp gate validates the uniquely marked architecture
manifest, semantic Schema digest, formal inventory, and record-level temporal
relations. A failure of either gate is an aggregate failure; the timestamp
gate never substitutes for the Draft engine or enables runtime behaviour.

Before any non-timestamp aggregate traversal, the static aggregate admits only
acyclic, finite, exact-builtin JSON values with exact-string object keys. A
public timestamp-gate reason is preserved verbatim in aggregate output; an
additional structural reason may coexist but cannot replace it. The public
timestamp entry point is keyword-only and requires explicit `schema`,
`markdown`, `record`, `inventory`, and `expected_semantic_digest` inputs.

Conditional inventory entries are executed by the verifier. In the
`point_in_time_ready` condition, all four source timestamps must be non-null;
in `point_in_time_blocked`, their explicit `null` values remain permitted by
their unconditional nullable contract. The point-in-time comparison locates
the sole `decision_instant` and `source_available_instant` roles from the
inventory. Missing, duplicate, or redirected temporal roles fail closed before
any relationship comparison.

```text
draft202012_behavior_4_25_1: VERIFIED
exact_locked_4_26_0_formal_execution: UNVERIFIED
full_repository_tests: UNVERIFIED
```

Historical research is ready only when:

- source time precision is `exact_timestamp`;
- required timestamps are present and offset-qualified;
- each source has `available_at <= decision_at`;
- no timestamp conflict is recorded.

Date-only, unknown, missing, conflicting, or future-available evidence makes
the record `point_in_time_blocked`. The contract does not infer a publication
time, assume an end-of-day timestamp, or repair a record automatically.

## Core claims and recommendation

Each core claim contains:

- `bull_case`
- `bear_case`
- `supporting_evidence_ids`
- `disconfirming_evidence_ids`
- `falsification_condition`
- `data_to_verify`

The recommendation contains only conclusion, basis, opposing view, risks,
missing evidence, a research-only next action, and the latest customer
disposition. It cannot contain order, quantity, broker, account, credential,
execution, or automatic-rebalancing material.
Dependency-free validation walks the complete recommendation structure and all
research-output text. Nesting a forbidden key or moving an execution
instruction into a conclusion, opposing view, claim, decision entry, or other
research text does not bypass the contract.

The text check is contextual rather than a single-word blacklist. Public
`broker research`, `broker consensus`, and other non-executing source
descriptions remain valid. Combinations that describe a broker payload,
transmission to a broker, an account identifier or number, a credential or API
token, an execution endpoint, an order or proposed quantity, order submission,
simulated submission, explicit account access or operation, credential-based
account access, or automatic/automated trading or rebalancing are rejected.

This is bounded static detection over an explicit separator and phrase set. It
is not complete natural-language understanding and does not claim to identify
every paraphrase, language, Unicode confusables or obfuscation, or adversarial
expression. Non-executing phrases such as `accounting research`, professional
or analyst credentials, automated valuation, and automatic data cleaning remain
valid.

For HTTPS source locators, the raw Schema gate rejects percent-encoding in the
authority. Dependency-free validation additionally checks the parsed authority
and performs bounded repeated decoding of path, query, and fragment components.
An encoded authority, malformed encoding, unresolved encoding after the fixed
decode limit, account reference, credential, or execution endpoint fails
closed. This canonicalization is a finite rule set, not a URL safety guarantee.

Allowed next actions are limited to:

- `source_review`
- `data_validation`
- `thesis_revision`
- `risk_review`
- `scenario_update`
- `request_customer_disposition`

## Append-only decision log

A decision entry records source, assumption, scenario, risk, and missing
evidence IDs, as-of time, recommendation, opposing view, customer disposition,
and disposition time.

An entry is never overwritten. A correction adds a new entry with
`supersedes_entry_id`; the referenced entry remains present, must occur
earlier, and the supersession graph must be acyclic. `human_disposition` is
limited to:

- `accepted_for_monitoring`
- `request_more_evidence`
- `deferred`
- `rejected`
- `superseded`

These are research dispositions. They do not authorize an order, position,
account operation, rebalance, external write, connector action, or background
monitoring. `accepted_for_monitoring` means only that a future monitoring
proposal may be considered; it does not create a schedule or permission.

## Static validation boundary

The Schema and dependency-free structural tests validate synthetic records.
They do not constrain the currently installed Public Equity Investing runtime
and do not provide host-enforced isolation. Future runtime integration needs a
separate implementation envelope, owner approval, negative runtime tests, and
an independent review.

Every declared boundary assertion must be present and exactly `false`.
Dependency-free validation applies this rule even when a formal Draft 2020-12
engine is unavailable. It does not treat a false boundary assertion as proof
of host enforcement; it only validates the supplied synthetic record.

The contract does not import or execute TradingAgents or other third-party
code. It introduces no LangGraph, agent debate runtime, dependency, provider,
connector, network access, real endpoint, credential, account, holding, order,
or customer-data fixture.

## Stable rejection reasons

- `EVIDENCE_LOCATOR_REQUIRED`
- `EVIDENCE_VERSION_REQUIRED`
- `TIMESTAMP_LEXICAL_PROFILE_INVALID`
- `TIMESTAMP_CALENDAR_INVALID`
- `TIMESTAMP_OFFSET_INVALID_OR_REQUIRED`
- `TIMESTAMP_CONTAINER_INVALID`
- `TIME_PRECISION_BLOCKED`
- `POINT_IN_TIME_VIOLATION`
- `DECISION_REFERENCE_INVALID`
- `DECISION_SUPERSESSION_REQUIRED`
- `HUMAN_DISPOSITION_TIMESTAMP_REQUIRED`
- `HUMAN_DISPOSITION_INVALID`
- `CORE_CLAIM_COMPLETENESS_REQUIRED`
- `ORDER_FIELD_FORBIDDEN`
- `QUANTITY_FIELD_FORBIDDEN`
- `BROKER_PAYLOAD_FORBIDDEN`
- `SENSITIVE_ACCOUNT_OR_CREDENTIAL_FORBIDDEN`
- `ORDER_INSTRUCTION_FORBIDDEN`
- `SIMULATED_ORDER_SUBMISSION_FORBIDDEN`
- `AUTOMATION_EXECUTION_FORBIDDEN`
- `REAL_ENDPOINT_FORBIDDEN`
- `REAL_CUSTOMER_DATA_FORBIDDEN`
- `HOST_ENFORCEMENT_CLAIM_FORBIDDEN`
- `BOUNDARY_ASSERTION_FORBIDDEN`
- `ENTITY_ID_DUPLICATE`
- `RESEARCH_OUTPUT_EXECUTION_OR_ACCOUNT_SEMANTICS_FORBIDDEN`
- `LOCATOR_ACCOUNT_REFERENCE_FORBIDDEN`
- `AUTOMATED_EXECUTION_SEMANTICS_FORBIDDEN`
- `ACCOUNT_ACCESS_SEMANTICS_FORBIDDEN`
- `LOCATOR_AUTHORITY_PERCENT_ENCODING_FORBIDDEN`

Reason codes explain rejection only. They do not authorize repair, infer
timestamps, fill a customer disposition, retrieve data, or trigger an external
action.

## Non-guarantees

This contract does not:

- validate real market data, valuation accuracy, suitability, tax, legal, or
  fiduciary conclusions;
- eliminate model, source, selection, or data-snooping bias;
- prove that all forms of look-ahead are absent;
- guarantee balanced bull and bear arguments;
- implement monitoring, portfolio management, brokerage, orders, or trading;
- modify the installed Public Equity Investing plugin.
