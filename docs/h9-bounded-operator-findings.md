# H9 — bounded read-only findings presentation

REPOSITORY_ONLY_EXPERIMENTAL. This is the selected G16 presentation slice,
not full H9 acceptance, core stability, installation or production readiness.
H5/H6 FULL ACCEPTANCE and PRODUCTION HARDENING remain NOT_COMPLETE;
H8 OVERALL remains PARTIAL. No token/compute integration or performance tuning.

## Invocation and authority

`scripts/h9_operator_findings.py` exports `render_findings(findings) -> str`.
The trusted caller first resolves the existing `cross_layer_verification`
module using its existing repository import setup, then imports this helper.
The helper does not change sys.path, load arbitrary source paths or find
credentials. There is no CLI, journal reader, storage initialization, network,
subprocess, execution, retry, reconciliation, observer control or persistence.
Normal Python import machinery reads module files; this is not an import sandbox
or protection against malicious code already running in the same interpreter.

Only safe synthetic, non-secret inputs are qualified here. Syntax validation
cannot detect all secrets in opaque identifiers. No raw body, credential,
journal content or live account input is supported.

## Contract

- An exact inert list or tuple, at most1024 elements, for one action.
- Exact existing `VerificationFinding` type, not a subclass, mapping or iterator.
- All ten fields retain their existing meanings: action_id, layer_a, layer_b,
  result, effect_class, effect_ref, reason, evidence_refs, coverage_status,
  compared_effect_ref. Optional None is printed as JSON null.
- Exact primitive field types are checked before the existing constructor
  validates its enum/reference/pair contract. Canonical tuple evidence refs
  must already be normalized; malformed/tampered refs are rejected, not repaired.
- Preserve finding order and duplicates; never filter, deduplicate, recompute
  findings, authenticate sources or infer permission from metadata.
- At most1MiB UTF-8 output. Oversize or invalid input raises fixed
  `ValueError('H9_PRESENTATION_INPUT_INVALID')`; no partial/truncated output.
- Empty input displays NO_FINDINGS_SUPPLIED, not PASS or proof of no effects.

Each `FINDING ` line is escaped, ASCII JSON text containing all ten fields.
The whole document is plain text with a fixed legend, not a persisted schema
or an installed core API. No automatic links, terminal controls or commands.
The legend includes READ_ONLY_PRESENTATION, SOURCE_TRUST_NOT_ESTABLISHED and
NOT_EXECUTION_OR_RETRY_AUTHORITY. It does not assign an aggregate outcome.

MATCH is scoped agreement, not all-effects proof. MISSING/EXTRA depend on the
verifier's scoped coverage; DIVERGED is unique material difference, not intent.
UNKNOWN is missing/ambiguous evidence; NOT_OBSERVED is partial observation, not
proof no effect occurred. Coverage, reasons, both refs and evidence refs remain
visible. No signer trust, freshness, readiness score or retry recommendation.
Use the core cross-layer reference for source normalization, not this helper.

## Synthetic task and proxy qualification

Before implementation, eight scenarios and literal answers were frozen in
`tests/test_h9_operator_findings.py:SCENARIOS`: match, diverged, unknown,
not_observed, gap, missing_vs_empty, duplicate and references. Separate integration
cases invoke the real verifier with absent/empty/gapped/divergent evidence.

The task is to retrieve result, reason, coverage, counterpart and evidence refs,
and retain the guarantee boundaries. Scoring requires exact answers in all
eight cases, all ten fields retained, no semantic promotion and a fixed boundary
legend in the same output. The original dataclass repr already exposes all
ten fields: baseline missing-field count is zero, not an invented improvement.
Its output lacks the three fixed boundary markers and explanatory legend.
The only proposed proxy improvement is co-location of that context with fields.
It is not a measurement of human lookup counts, cognitive burden or efficiency.

H9 HUMAN BENEFIT: NOT_VALIDATED. No human was recruited, contacted or simulated.
H9 original measured-benefit criterion is not automatically satisfied by this
proxy. If co-located context is not obtained with exact fields, report
BENEFIT_PROXY_NOT_MET even if unrelated regressions pass. Runtime measurements
are environment observations, not evidence of performance improvement.

Tests use native `python3 -B -m unittest discover -s tests -p
'test_h9_operator_findings.py' -v` from the repository root. Broader tests use
the same discovery semantics. Core state transitions, durable-before-effect,
UNKNOWN/material barriers, ownership, legacy fence and all reconciliation/trust
contracts are unchanged. No journal migration, downgrade or mixed writers.

The approved execution target is existing local Darwin/Python3.9.6 only.
No new Linux CI/platform claim. LOCAL FORMAL remains BLOCKED_MISSING_DEPENDENCIES;
LOCAL SIGNATURE retains its actual trust-configuration blocker. Skips are not
PASS. Tests and source review are not hostile-host isolation evidence.

The initial local stage used an uncommitted three-file candidate with a SHA256
manifest and independent reviews. A later bounded publication authorization
permits signed commits, a dedicated branch push, a Draft PR and the existing
required CI, followed by independent reviews bound to the final commit/tree.
Historical Darwin results remain Darwin evidence; new CI results must record
their own commit, checkout, platform and runtime. No new workflow is authorized.
Merge, deployment, installation and full H9 acceptance remain unauthorized.
