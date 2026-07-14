# Explicit-Only Extensions

These references preserve optional workflows without broadening implicit
activation for `long-horizon-engineering`.

Use them only when:

- the user explicitly invokes `long-horizon-engineering`, or
- the user explicitly asks for the specific workflow, and
- the workflow is safe, authorized, and relevant to the repository task.

Do not select `long-horizon-engineering` implicitly for these domains merely
because the files exist.

## Skill Authoring And Optimization

- `skill-authoring-methodology.md` for maintaining this skill package.
- `industrial-skill-design-principles.md` for trigger boundaries, minimal tool
  scope, progressive disclosure, task-depth matching, and evaluation loops.
- `skill-optimization-protocol.md` for bounded, review-gated skill edits.
- `skillopt-training-layer.md` for optional benchmark-style skill text
  comparison.
- `missing-capability-skill-discovery.md` for proposing new skills when local
  capability is missing.
- `external-skill-adoption-safety-review.md` for reviewing public skill
  candidates.
- `skill-lifecycle-management.md` for freezing or restoring optional installed
  skills with user approval.

## Personal Workflow Review

- `personal-workflow-review.md` for proposal-only analysis of explicitly
  supplied non-sensitive work summaries, candidate reusable rules, and
  repeated workflows without history scanning or automatic persistence.

## Research, Writing, And Analysis

- `writing-humanization-protocol.md` for audience-aware rewriting that preserves
  meaning and evidence.
- `evidence-backed-writing.md` for claim-evidence alignment.
- `ideation-to-plan-protocol.md` for options and tradeoffs before execution.
- `notebook-analysis-protocol.md` for stateful exploratory analysis.
- `presentation-delivery-protocol.md` for deck planning and slide QA.
- `financial-research-report-protocol.md` for source-backed market or stock
  research that is not investment advice.

## External Tools And Source Gathering

- `external-tool-provider-protocol.md` for approval-gated external tools.
- `external-app-runtime-boundary.md` for connected apps, notebooks, or provider
  runtimes.
- `external-source-scan.md` for public source discovery boundaries.
- `public-agent-capability-review.md` for comparing public agent capability
  claims without adopting unsupported patterns.

## Domain-Specific Optional Protocols

- `jurisdiction-industry-compliance.md` for location-aware legal, regulatory, or
  industry-rule questions with current-source checks and legal-advice caveats.
- `disaster-monitoring-enablement.md` for privacy-first alert-rule design.
- `data-cleaning-protocol.md` for reproducible data cleaning when explicitly in
  scope.
- `ui-ux-review-protocol.md` for evidence-backed frontend, accessibility, and
  responsive UX review.

## Engineering Adjacent Protocols

- `adversarial-review-protocol.md` for challenging high-risk plans.
- `tdd-protocol.md` for red-green-refactor workflows.
- `api-integration-protocol.md` for external API integration plans.
- `ship-readiness-protocol.md` for release and merge gates.

## Templates

Use templates in `templates/` only when they fit the explicit workflow and the
repository is not sensitive, or when the user explicitly approves persistent
records. Templates are reusable structure, not a place for secrets, client data,
legal evidence, family information, financial account details, API keys, or
confidential documents.
