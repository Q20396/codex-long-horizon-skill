# Local-First Product Feasibility And Review Plan

Status: static candidate evidence. No implementation or release authority.

## Feasibility Verdicts

| Area | Verdict | Evidence boundary |
| --- | --- | --- |
| Independent read-only review | READY_TO_REPEAT | The candidate is isolated and unstaged. A reviewer must rebind the exact 74-path inventory below, rerun necessary checks, and independently evaluate the remediation. |
| Logical local-commit decomposition | FEASIBLE_WITH_EXACT_HUNK_REVIEW | The manifest below assigns every candidate path to one or more of six slices. Shared files still require the named hunk selectors and per-slice validation. |
| External Local Case Evidence Provider | CONTRACT_FEASIBLE | Static interface, threat model, recursively closed fixtures, and type-first fail-closed checks are present. Runtime, encryption, credentials, connectors, and storage remain unimplemented. |
| One synthetic connector pilot | READY_FIXTURE_ONLY | Two recursively closed synthetic checkpoints exercise delta/hash and customer-outcome contracts without network, accounts, credentials, persistence, or customer data. |
| Product-language boundary | BOUNDED_STATIC_CHECK | Tests scan the exact declared surface allowlist for specific prohibited claims. They do not detect arbitrary wording or prove installed/runtime behavior. |
| Synthetic usability validation | READY_STATIC | Legal, family/office, investment, and incremental-index examples expose FACT, INFERENCE, UNKNOWN, one status, one next safe action, and customer authority. |

`READY` means ready for the stated static review only. It does not mean
release-ready, installed, callable, runtime-enforced, or customer-approved.

## Proposed Local Commit Sequence

No commit is authorized by this document. A future operator should freeze the
exact candidate path inventory before staging and keep each commit locally
reviewable.

1. **Release and supply-chain governance baseline**
   - formal schema acquisition, single-acquisition/offline-replay, Action pin,
     maintenance policy, warning waiver, and release-hygiene changes already in
     the candidate;
   - validate release tooling and formal static checks independently.
2. **No-upload privacy boundary**
   - client privacy, external app/search/source, tool-card, disaster, authoring,
     and sensitive-transfer template changes;
   - include only the matching no-exception negative tests.
3. **Capability catalog, package profile, and Doctor**
   - packaged catalog, catalog schema/fixtures, three sandbox descriptors,
     package profile, Doctor health report, trigger fixtures, and derived
     package evidence;
   - preserve descriptor-only and declared-disabled values.
4. **Local Case Evidence Provider contract and synthetic pilot**
   - provider architecture/contract/schema, provider fixtures, fixture-only
     incremental pilot, and fail-closed tests;
   - include no connector, storage, encryption, credential, or account code.
5. **Customer journey**
   - guided workflow prompt/docs/examples and high-stakes synthetic outcomes;
   - preserve exactly one status and one next safe action per outcome.
6. **Public product and candidate truth**
   - README, Skill/plugin descriptions, release manifests, Marketplace policy,
     release notes, install/upgrade guidance, and release-truth tests;
   - keep `NOT_AVAILABLE`, `candidate`, and `released: false`.

Files shared across concerns, especially `SKILL.md`, `README.md`,
`doctor.py`, `package-manifest.json`, formal inventory, full validation, and
release documentation, require explicit hunk ownership. If a hunk cannot be
assigned without weakening another slice, combine the two slices rather than
manufacturing an artificial commit boundary.

## Exact Candidate Slice Manifest

This inventory is candidate-specific. Each path appears exactly once; multiple
slice IDs mean the path contains explicitly named shared hunks. Reviewers must
compare this list with the frozen candidate inventory before staging anything.

Candidate base: `5afdb1e350a564478990a9b304c0eeb9b689c49e`.
Candidate commit: `c58b5fbf68404fbacbd38e5bfd3e5c2189775ce1`.

The inventory is bound to this base-to-candidate diff. Later repository commits
must not change the historical candidate inventory or make this record fail.

- [S6] `.agents/plugins/marketplace.json` - candidate availability and prospective ref.
- [S6] `.github/workflows/check-skill.yml` - CI-wide bytecode isolation and immutable action/credential guards.
- [S6] `.agents/skills/ai-video-production/SKILL.md` - candidate metadata only.
- [S1/S2/S3/S5/S6] `.agents/skills/long-horizon-engineering/SKILL.md` - selectors: S1=`Sensitive-data limits:`; S2=`## Local Capability Discovery`; S3=`## Local Capability Discovery`; S5=`## Guided Customer Workflow`; S6=`update_channel: candidate`.
- [S2] `.agents/skills/long-horizon-engineering/package-manifest.json` - local-governance profile and catalog component.
- [S1] `.agents/skills/long-horizon-engineering/references/approved-tool-contract-card.md` - no-upload authority boundary.
- [S1] `.agents/skills/long-horizon-engineering/references/capability-boundaries.md` - local-first effect boundary.
- [S1] `.agents/skills/long-horizon-engineering/references/client-privacy.md` - no customer-data upload rule.
- [S1] `.agents/skills/long-horizon-engineering/references/disaster-monitoring-enablement.md` - external transfer prohibition.
- [S3] `.agents/skills/long-horizon-engineering/references/explicit-only-extensions.md` - descriptor-only extension index.
- [S1] `.agents/skills/long-horizon-engineering/references/external-app-runtime-boundary.md` - connector/account boundary.
- [S1] `.agents/skills/long-horizon-engineering/references/external-search-protocol.md` - no-sensitive retrieval boundary.
- [S1] `.agents/skills/long-horizon-engineering/references/external-source-scan.md` - local-first source handling.
- [S1] `.agents/skills/long-horizon-engineering/references/industrial-skill-design-principles.md` - no-upload design principle.
- [S3] `.agents/skills/long-horizon-engineering/references/missing-capability-skill-discovery.md` - suggestion-only discovery.
- [S1] `.agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md` - sensitive-data authoring boundary.
- [S2/S6] `.agents/skills/long-horizon-engineering/scripts/check_skill_package.py` - selectors: S2=`def load_package_contract(`; S6=`def check_skill_front_matter(`.
- [S2/S5] `.agents/skills/long-horizon-engineering/scripts/doctor.py` - selectors: S2=`def capability_health_report(`; S5=`The report reads package declarations only.`.
- [S3] `.agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py` - trigger structure and escalation rejection.
- [S1] `.agents/skills/long-horizon-engineering/templates/disaster-alert-rule.md` - no-upload template.
- [S1] `.agents/skills/long-horizon-engineering/templates/source-upload-consent-checklist.md` - prohibited-transfer replacement.
- [S6] `.codex-plugin/plugin.json` - candidate package identity.
- [S6] `CHANGELOG.md` - candidate and maintenance-line narrative.
- [S6] `INSTALL.md` - unavailable candidate installation boundary.
- [S1/S6] `README.md` - selectors: S1=`LHE never uploads customer-sensitive information`; S6=`## Installation Status`.
- [S1/S6] `SECURITY.md` - selectors: S1=`Do not include secrets`; S6=`## Supported Versions`.
- [S6] `UPGRADE_GUIDE.md` - branch and installation boundary.
- [S2] `docs/design/package-layering-classification-v0.3.json` - authoritative component count/hash.
- [S2] `docs/design/package-layering-classification-v0.3.md` - derived count narrative.
- [S2] `docs/design/package-layering-v0.3.md` - profile/layering narrative.
- [S2] `docs/design/presentation-separate-skill-extraction-v0.3.json` - derived classification binding.
- [S6] `docs/maintainers/release-checklist.md` - release, provenance, and single-acquisition gates.
- [S6] `docs/plugin-install.md` - candidate Marketplace boundary.
- [S1/S2/S4/S5/S6] `docs/releases/v0.3.0.md` - selectors: S1=`customer-sensitive upload exception;`; S2=`local-governance-core profile`; S4=`Local Case Evidence Provider interface`; S5=`customer-first synthetic workflows`; S6=`## Status`.
- [S6] `releases/ai-video-production/latest.json` - candidate metadata and not-assessed risk.
- [S6] `releases/latest.json` - candidate release index.
- [S6] `releases/long-horizon-engineering/latest.json` - candidate metadata and not-assessed risk.
- [S6] `scripts/check_release_readiness.py` - candidate, risk, hygiene, and formal-result gates.
- [S2/S6] `scripts/full_skill_validation.py` - selectors: S2=`def load_required_from_check_script(`; S6=`def enforce_release_warning_allowlist(`.
- [S6] `scripts/validate_formal_schemas.py` - closed formal inventory and acquisition boundary.
- [S3] `tests/expected-triggers.json` - discovery and adversarial trigger fixtures.
- [S6] `tests/test_formal_schema_validation.py` - formal inventory/acquisition tests.
- [S2] `tests/test_goal_driven_delivery_contract.py` - derived count regression.
- [S2] `tests/test_package_layering_v03_spec.py` - authoritative layering/count regression.
- [S2] `tests/test_package_manifest_contract.py` - profile/catalog/package regression.
- [S6] `tests/test_release_tooling.py` - release truth, risk, provenance, and hygiene tests.
- [S2] `tests/test_ui_design_skill_adapter_contract.py` - derived count regression.
- [S2] `.agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json` - packaged descriptor registry.
- [S5] `docs/customer-guided-workflow.md` - customer/operator/engineering flow.
- [S5] `docs/high-stakes-customer-workflows.md` - domain workflow boundaries.
- [S6] `docs/maintainers/local-first-feasibility-review-plan.md` - exact candidate decomposition and limits.
- [S5] `examples/customer-guided-decision/expected-output.md` - customer outcome example.
- [S5] `examples/customer-guided-decision/prompt.md` - synthetic intake example.
- [S5] `examples/customer-guided-decision/workflow.md` - guided workflow example.
- [S5] `examples/high-stakes-customer-workflows.md` - domain golden cases.
- [S5] `prompts/customer-guided-decision.md` - customer-first entry prompt.
- [S2] `sandbox/skill-incubator/architecture/local-capability-catalog.md` - catalog contract and limits.
- [S4] `sandbox/skill-incubator/architecture/local-case-evidence-provider.json` - provider contract record.
- [S4] `sandbox/skill-incubator/architecture/local-case-evidence-provider.md` - provider architecture and static limits.
- [S2] `sandbox/skill-incubator/domain-packs/australian-legal-evidence/pack.json` - legal descriptor.
- [S2] `sandbox/skill-incubator/domain-packs/family-office-document-governance/pack.json` - document descriptor.
- [S2] `sandbox/skill-incubator/domain-packs/public-equity-research/pack.json` - research descriptor.
- [S2] `sandbox/skill-incubator/schemas/local-capability-catalog.schema.json` - closed catalog schema.
- [S4] `sandbox/skill-incubator/schemas/local-case-evidence-provider.schema.json` - provider and pilot schemas.
- [S5] `tests/fixtures/customer-guided-workflow/cases.json` - guided decision cases.
- [S6] `tests/fixtures/formal-authority-boundaries/cases.json` - formal authority negative fixtures.
- [S5] `tests/fixtures/high-stakes-customer-workflows/cases.json` - domain outcome cases.
- [S3] `tests/fixtures/local-capability-catalog/cases.json` - keyword and authority mutations.
- [S4] `tests/fixtures/local-case-evidence-provider/cases.json` - provider threat mutations.
- [S4] `tests/fixtures/local-case-evidence-provider/synthetic-pilot.json` - recursively closed synthetic delta pilot.
- [S5] `tests/test_customer_guided_workflow_contract.py` - fixed three-layer outcome contract.
- [S5] `tests/test_doctor_capability_report.py` - read-only Doctor and provider type checks.
- [S5] `tests/test_high_stakes_customer_workflows.py` - domain golden-case validation.
- [S1/S2/S3/S4/S6] `tests/test_local_first_high_stakes_contracts.py` - selectors: S1=`def test_no_customer_sensitive_upload_exception_remains(`; S2=`def test_catalog_schema_and_fixed_authority_are_fail_closed(`; S3=`def test_trigger_fixture_rejects_non_objects_and_discovery_escalation(`; S4=`def test_fixture_only_pilot_rejects_unknown_runtime_aliases_recursively(`; S6=`def test_product_language_never_claims_connector_or_provider_runtime(`.

Mechanical review must confirm 74 unique paths, no path outside this list, and
at least one path for every slice. Shared paths may be staged only after the
named hunk scopes are independently reviewed; otherwise combine the affected
slices.

## External Provider Architecture

The future provider must remain a separate default-disabled local process:

```text
approved one-run source
  -> local connector adapter
  -> quarantine and deterministic extraction
  -> encrypted case store and immutable locator/version/hash ledger
  -> redacted structured evidence receipt
  -> LHE customer outcome
```

Raw material, credentials, connector tokens, and encryption keys never enter
LHE prompts, repositories, logs, summaries, telemetry, or model memory. LHE
receives only redacted claims, locators, hashes, classifications, and explicit
gaps. Provider execution never grants approval, legal authority, publication,
trading, deletion, or another workflow stage.

## Runtime Prerequisites

Before a real implementation can be considered, a separate envelope must name:

- the local process boundary and operating systems;
- encrypted database and per-case key design;
- OS credential-store integration;
- connector-specific read scopes, pagination, cursors, and revocation;
- active-content quarantine and deterministic parser isolation;
- crash recovery, tamper evidence, retention, deletion, export, and
  counsel-directed legal hold;
- local-only logging/redaction rules and proof of no telemetry;
- one synthetic connector implementation and adversarial tests before any real
  account is connected.

Any missing prerequisite keeps the provider `declared-disabled`.
