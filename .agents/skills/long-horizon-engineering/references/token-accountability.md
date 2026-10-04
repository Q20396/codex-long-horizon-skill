# Token Accountability — Experimental Foundation

## Purpose

Phase 1.35 supplies immutable local artifacts, pure accounting functions and
explicit Security Chain recording helpers. It is inactive by default, including
after Core installation. Standard library only. No second ledger or database.

## Attribution Hierarchy

Installation → project → task → run → agent → model call. IDs are opaque caller
identifiers, not authenticated identities. The host supplies authoritative
relationships. Missing ownership is retained, never invented.

## Measurement Honesty / Unknown Is Not Zero

`None` means UNKNOWN per numeric field. Zero means an explicit zero observation.
`MetricSource` is PROVIDER_REPORTED, RUNTIME_REPORTED or UNKNOWN; an UNKNOWN
source cannot carry known token measurements. Input, cached input, output,
reasoning and total remain independent categories. No automatic total is made:
cached input can be a subset of input; reasoning can be a subset of output.

## Provider Independence

Names do not grant trust or alter rules. The same functions accept OpenAI,
Anthropic, Google, local, unknown or future Paperclip-injected observations.
There are no provider adapters or SDKs here.

## UsageRecord

`TokenUsageRecord` validates identifiers, closed `UsagePurpose`, bounded times
and non-negative integer metrics (bool is invalid). Individual numeric values
are at most 2**53; aggregation uses Python's exact integers. `started_at` cannot
exceed `finished_at`. Optional parent call and explicit retry group/attempt are
metadata, not a causal trace. Retry attempt indices start at 1. No prompt or
response field exists; purpose is not authorization. Reprs suppress identifiers.

History inputs are bounded to 10,000 records. Duplicate installation/usage IDs
or installation/call IDs are rejected rather than counted twice. A retry must
have a new call and usage identity. Caller owns artifact retention.

## Token Budget / Nested Budget Authority

`TokenBudget` levels: INSTALLATION, PROJECT, TASK, RUN. Scope must match level.
`validate_budget_stack(..., now=...)` checks current times, scope, distinct levels
and all supplied ancestor limits. A child limit above a parent is rejected, not
silently clamped. Child `None` means no additional cap, not an override.
Cost caps with different currencies cannot be intersected.

The trusted host MUST supply the complete current applicable ancestor stack;
the module has no authoritative budget inventory and cannot detect omitted
ancestors. It MUST also supply complete lifetime usage for every budget scope,
including sibling tasks/runs for parent caps. Missing history is not detectable.
Budgets have no period reset. Superseding a budget does not erase prior usage.
Expired/not-yet-issued budgets fail closed rather than disappearing from checks.

`evaluate_budget(history, stack, proposed_or_observed_usage=None, now=...)`
returns WITHIN_BUDGET, WARNING, EXCEEDED or UNKNOWN. Each scope is accumulated
separately. A known exceeded cap dominates; otherwise any required unknown
metric or ambiguous attribution prevents a within-budget claim. No cap means
UNKNOWN, not unlimited. Default warning threshold is 8000 basis points and is
explicitly configurable in each budget. Evaluations are not provider blocking.

`record_budget` reuses `authorize_management_change`: installation/project/task/
run policy actions, not a new role system. RUNTIME cannot create or increase a
budget. Authority snapshots must be current and authentic as supplied by host.

## Budget Extension

`request_budget_extension` records a request only. The old budget does not change.
An authorized `record_budget(..., previous=old, extension_request_id=...)` emits
EXTENSION_GRANTED with new digest and previous digest, making supersession
explicit in that one append. Ordinary replacements emit SUPERSEDED. Creation
emits CREATED. Old artifacts/history remain. A prior recorded budget and matching
request are required for a grant; an already superseded artifact cannot fork.
The host chooses the actual new limit; a request is not an automatic grant.
No separate DENIED event is introduced. Helpers reject invalid requests with a
fixed error and no append. No wall-clock reads or hidden current-budget state.

## Cost Attribution / Reported vs Estimated Cost

Money is integer micro-units with explicit uppercase three-letter currency.
PROVIDER_REPORTED is labelled REPORTED; EXPLICIT_RATE_DERIVED is labelled
ESTIMATED and requires caller-supplied `pricing_snapshot_ref`; UNKNOWN stays
unknown. The host calculates any explicit-rate estimate before submission.
This module neither fetches prices nor embeds tariffs. It does not certify the
rate arithmetic or invoice. Reported and estimated subtotals remain separate
and partitioned by currency. No FX conversion or combined all-currency total.

## Deterministic Anomalies

`detect_anomalies(records, snapshot, rules)` is pure. Host supplies a scoped
`ExecutionAccountabilitySnapshot`; rules use integer thresholds/basis points.
The same records in different input order produce identical findings. A finding
is a candidate for operator investigation, never proof of waste or intent.

### Orphan Usage

Missing project/task/run/agent produces ORPHAN_USAGE; trusted invalid parent-call
IDs can also flag orphan evidence. Incomplete artifacts can be recorded by an
authority whose scope covers them; a narrowly scoped runtime cannot claim
unknown task ownership. The sealed chain scope uses only a valid hierarchy
prefix, while the artifact preserves all supplied fields.

### Post-Completion Usage

Start strictly after trusted `task_verified_complete_at`, within matching scope.
Model text, PR state and Paperclip status are not completion evidence.

### Unreconciled Retry Usage

Requires `reconciliation_required` AND matching explicit unresolved retry group
in the snapshot. It does not infer unresolved work from similar prompts.

### Retry Amplification

Within one scoped run/agent/retry group, at least `retry_attempt_threshold`
distinct attempts and last known total / first positive known total crossing
`retry_growth_bps`. Unknown endpoints do not imply growth. No prompt matching.

### Context Amplification

Within the same scoped run/agent, last input / first positive known input crossing
`context_growth_bps`. Unknown endpoints do not imply growth. This indicates
context growth only; it does not judge its usefulness.

### Low-Progress High-Token

Requires all known cumulative totals crossing `low_progress_token_threshold`
and a trusted progress snapshot: remaining work unchanged/increased, no criteria
closed, no evidence added, no blockers resolved. Missing progress is not zero.
Any of those forms of real progress suppresses this simple candidate rule.

Anomalies anchor rules, trusted snapshot and full usage-set digest. `usage_ids`
contains at most the first 128 IDs; `usage_count` explicitly identifies the full
set size. Full corresponding artifacts are needed to investigate larger sets.
This stays within existing chain canonical bounds without a schema change.

## Security Chain Integration

`record_model_usage`, `record_budget`, `request_budget_extension`,
`record_budget_decision`, `record_anomaly` append to the existing chain.
MODEL_USAGE uses stable usage event identity and a duplicate call guard.
Warnings/exceeded events use one stable identity per budget/state so repeated
queries cannot flood the chain; their digest anchors the accounting decision.
Queries alone write nothing. Repeated recording raises a fixed rejection.

Only EventType vocabulary extends: MODEL_USAGE, TOKEN_BUDGET_CREATED,
TOKEN_BUDGET_SUPERSEDED, TOKEN_BUDGET_EXTENSION_REQUESTED,
TOKEN_BUDGET_EXTENSION_GRANTED, TOKEN_BUDGET_WARNING, TOKEN_BUDGET_EXCEEDED,
TOKEN_ANOMALY. Schema v1, sealed fields, canonical encoding and hashing unchanged.
Legacy chains remain valid. No RSE or Local Compute behavior changes.

Security Chain anchors artifact identity/history, not measurement truth.
Aggregation requires the corresponding approved TokenUsageRecord artifacts.
Use one trusted serialized controller for read/check/append helpers, including
budget/duplicate guards. There is no multiwriter transaction or global replay
database. Low-level append remains a trusted storage interface, not an authority
entrypoint. Retain trusted chain heads externally as described in Phase 1.25;
this phase adds no signing, external anchor or host-tamper protection.

## Operator Example

With the packaged scripts directory on Python's import path:

```python
from token_accountability import *

u = TokenUsageRecord('usage-1', 'installation-1', 'call-1', 'vendor', 'model',
    UsagePurpose.REVIEW, 10, 11, project_id='project-1', task_id='task-1',
    run_id='run-1', agent_id='agent-1', total_tokens=120,
    metric_source=MetricSource.PROVIDER_REPORTED)
b = TokenBudget('budget-1', TokenBudgetLevel.PROJECT, 'installation-1', 1,
    project_id='project-1', max_total_tokens=100)
d = evaluate_budget((u,), (b,), now=12)
report = summarize((u,), budget_decision=d)
assert report.budget_state == 'EXCEEDED'
assert report.unknown_cost_records == 1
assert report.unknown_total_token_records == 0
```

Use `by_project`, `by_task`, `by_run`, `by_provider`, `by_model` to answer who used
what. Hierarchical grouping keys include ancestor IDs; model keys include vendor
to avoid conflating identically named models. Reports include known metric sums
and unknown counts for every category; a known subtotal of zero alongside an
unknown count is NOT a measured zero total. For who approved a budget, resolve
the chain's authority digest to the approved authority artifact. REQUESTED alone
does not count as approval. Resolve anomaly evidence digests to inspect why.

## Privacy Boundary

No raw prompt, response, source, document, secret or credential belongs in these
artifacts. Callers must supply non-sensitive opaque identifiers, including refs.
Chain stores only digests/opaque refs, never raw provider/model/project names.
Fixed validation errors do not echo inputs. No telemetry or external reporting.

## Current Enforcement

Pure contract validation, authority checks on recording helpers, deterministic
arithmetic/detection, stable append identities and local chain verification.

## Non-Enforcement / Future Runtime Binding

No live quota enforcement, provider collection/billing, runtime interception,
daemon, polling, dashboard, CET, signatures, host observer, Paperclip dependency
or local/cloud optimization. Phase 2 binding is a separate authorization.

## Public Claim Boundary

20396 includes an experimental Token Accountability foundation for attributing
model usage to projects/tasks/runs, applying nested token budgets, distinguishing
reported versus unknown metrics, and detecting deterministic usage anomalies.
No fraud/theft classification or real provider/runtime monitoring is claimed.
