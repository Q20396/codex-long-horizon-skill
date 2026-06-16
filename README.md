# codex-long-horizon-skill

Reusable Codex skill package for long-horizon software engineering work.

This repository contains the `long-horizon-engineering` skill, which can be
copied into another coding project so Codex has a structured workflow for
multi-step engineering tasks.

## Quick Links

- [Installation](INSTALL.md)
- [Upgrade Guide](UPGRADE_GUIDE.md)
- [Changelog](CHANGELOG.md)
- [Examples](examples/)
- [License](LICENSE)

## Official Codex Skill Structure

A Codex skill is a directory containing a required `SKILL.md` file. It can also
include optional supporting folders such as `scripts`, `references`, and
`assets`. Codex first reads the skill metadata to decide whether the skill is
relevant. If the skill is selected, Codex then reads the full `SKILL.md`
instructions.

In this repository, the skill is packaged at:

```text
.agents/skills/long-horizon-engineering/
```

## Recommended Installation Path

Place this skill directory in the root of a coding project at:

```text
.agents/skills/long-horizon-engineering/
```

The expected installed structure is:

```text
AGENTS.md
CHANGELOG.md
INSTALL.md
LICENSE
README.md
UPGRADE_GUIDE.md
.github/
  workflows/
    check-skill.yml
examples/
  bug-fix-prompt.md
  large-migration-prompt.md
  resume-task-prompt.md
.agents/
  skills/
    long-horizon-engineering/
      SKILL.md
      references/
        protocol.md
        adversarial-review-protocol.md
        api-integration-protocol.md
        capability-boundaries.md
        client-privacy.md
        safety-policy.md
        context-compaction.md
        continuous-improvement.md
        data-cleaning-protocol.md
        decision-log.md
        evidence-backed-writing.md
        external-search-protocol.md
        external-source-scan.md
        ideation-to-plan-protocol.md
        jurisdiction-industry-compliance.md
        large-migration-playbook.md
        notebook-analysis-protocol.md
        presentation-delivery-protocol.md
        public-agent-capability-review.md
        repomix-codebase-context.md
        review-checklist.md
        resume-protocol.md
        ship-readiness-protocol.md
        skill-authoring-methodology.md
        stop-conditions.md
        tdd-protocol.md
        ui-ux-review-protocol.md
        validation-matrix.md
        writing-humanization-protocol.md
      prompt-styles/
        concise.md
        evidence-first.md
        product-review.md
      templates/
        HANDOFF_REPORT_TEMPLATE.md
        PROJECT_MEMORY_TEMPLATE.md
        IMPROVEMENT_SCAN_TEMPLATE.md
        accessibility-checklist.md
        api-contract-test-plan.md
        implementation-plan.md
        analysis-run-log.md
        claim-evidence-table.md
        data-quality-report.md
        deck-outline.md
        frontend-handoff.md
        new-skill-brief.md
        option-analysis.md
        regression-test-record.md
        risk-challenge-table.md
        slide-qa-checklist.md
        ship-checklist.md
        skill-evaluation-plan.md
        TASK_LOG_TEMPLATE.md
        ui-ux-audit.md
        verification-evidence.md
        voice-calibration.md
        WORKING_STATE_TEMPLATE.md
      scripts/
        append_project_memory.py
        audit_skill_descriptions.py
        check_for_updates.py
        check_skill_package.py
        doctor.py
        github_skill_scan.py
        scan_top_related_skills.py
        test_expected_triggers.py
        update_installed_skill.py
        update_task_log.py
tests/
  expected-triggers.json
```

## Customer Quick Start

1. Copy the skill into a target project:

   ```bash
   mkdir -p .agents/skills
   cp -R path/to/codex-long-horizon-skill/.agents/skills/long-horizon-engineering .agents/skills/
   ```

2. Add a short instruction to the target project's `AGENTS.md`:

   ```markdown
   When a task involves multi-step engineering work, use the
   `long-horizon-engineering` skill.
   ```

3. Verify this package before copying updates:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
   ```

4. Ask Codex to use the skill:

   ```text
   Use the long-horizon-engineering skill.
   Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
   ```

## What This Repository Is

This repository is a portable skill package, not an application. It contains:

- Repository-level Codex instructions in `AGENTS.md`
- The required skill instructions in `SKILL.md`
- Supporting workflow references
- Reusable Markdown templates for project memory and task logs
- Small local helper scripts for appending non-sensitive notes
- Example prompts, installation instructions, CI checks, and an MIT license

## Productized Skill Package v2

This package includes product-grade install, verification, update, rollback,
trigger-test, and review-support pieces around the skills. These additions are
documentation, templates, static checks, and local helper scripts; they do not
patch Codex or add required external services.

## What The Skill Does

`long-horizon-engineering` gives Codex a repeatable workflow for engineering
tasks that should not be handled as quick one-shot edits. It guides Codex to:

1. Understand the request.
2. Explore the repository before editing.
3. Plan the smallest safe change.
4. Execute with minimal scope.
5. Test or otherwise verify the result.
6. Debug targeted failures.
7. Summarize the outcome.
8. Update memory or logs only when appropriate and safe.

The goal is to make long-running or multi-step work safer, easier to review, and
easier to resume later.

## AI Video Production Skill

`ai-video-production` is a separate optional sibling skill for AI-assisted video
planning, storyboard design, image asset planning, and code-rendered video
workflows.

It can support Remotion-style and HyperFrames-style workflows, including
briefing, research boundaries, scripting, storyboard and shot-list creation,
asset manifests, preview planning, and render handoffs.

Optional prompt styles under `ai-video-production/prompt-styles/` can steer
short-form cinematic planning or production handoff formatting without changing
privacy, licensing, or approval gates.

For longer video projects, `references/design-system-for-video.md` and the
`DESIGN.md`, `visual-style-tokens.md`, and `brand-system-for-video.md` templates
help define typography, colors, spacing, motion language, component patterns,
responsive behavior, and design rationale without copying external brands.

For media-skill improvement review, the video module includes a manual scan
helper:

```bash
python3 .agents/skills/ai-video-production/scripts/scan_top_media_skills.py --dry-run --top 3
```

It checks public GitHub repositories related to video/image generation skills,
self-checks code and workflow signals, suggests possible optimizations, explains
upgrade impact, and gives customers manual upgrade options. It does not copy
external code, run remote code, auto-upgrade, or modify `main`; the user decides
whether any upgrade should happen.

This skill does not auto-render, auto-upload, auto-publish, or post media. Human
approval is required before rendering, uploading, publishing, posting, or using
private assets. Sensitive client, private, family, legal, medical, or financial
material requires explicit approval before Codex reads or uses it.

## Why SKILL.md Is Required

`SKILL.md` anchors the skill. Its front matter provides the skill name and
description that Codex can use to decide whether the skill is relevant. The rest
of the file contains the full instructions Codex follows after the skill is
selected.

Do not rename the skill unless you also update every instruction that refers to
`long-horizon-engineering`.

## Optional Supporting Folders

The skill can include optional folders to keep `SKILL.md` focused while still
providing useful supporting material.

### references/

Use `references/` for longer guidance that Codex may consult after the skill is
selected. This package includes:

- `protocol.md` for the long-horizon engineering workflow
- `adversarial-review-protocol.md` for stress-testing plans, claims,
  architectures, launches, and risky assumptions before implementation
- `api-integration-protocol.md` for endpoint mapping, auth boundaries, schema
  handling, retries, rate limits, and contract testing
- `capability-boundaries.md` for deciding which powerful agent behaviors are
  allowed, confirmation-gated, draft-PR-only, plan-only, or forbidden
- `client-privacy.md` for protecting client, legal, financial, family, medical,
  identity, business, and confidential research data
- `safety-policy.md` for protected areas and safety expectations
- `context-compaction.md` for preserving lightweight state before interruption
  or context loss
- `continuous-improvement.md` for safe, review-gated periodic skill improvement
- `data-cleaning-protocol.md` for privacy-first data profiling, cleaning,
  normalization, before/after summaries, and reproducible evidence
- `decision-log.md` for separating facts, assumptions, decisions, evidence,
  risks, and follow-ups
- `evidence-backed-writing.md` for claim-evidence alignment, section
  intent, reviewer mindset, and pre-submission review
- `financial-research-report-protocol.md` for stock, company, sector, market,
  valuation, watchlist, and financial research reports with source and risk
  discipline
- `code-review-response-protocol.md` for evaluating and responding to reviewer
  feedback without blind implementation
- `external-search-protocol.md` for provider-neutral, privacy-first public
  source search planning across web, GitHub, docs, package registries, CVEs, and
  standards
- `external-source-scan.md` for consent-gated scans of local folders, connected
  cloud drives, Gmail, or other external sources
- `ideation-to-plan-protocol.md` for divergent options, tradeoffs, selection
  criteria, and plan conversion
- `large-migration-playbook.md` for phased, reviewable large migrations and
  complex multi-file implementations
- `notebook-analysis-protocol.md` for stateful exploratory analysis,
  incremental notebook work, and clean reruns before claims
- `presentation-delivery-protocol.md` for deck outlines, source-to-slide
  transformation, slide QA, export checks, and handoff
- `public-agent-capability-review.md` for safely learning from public frontier
  coding-agent capabilities without copying external code or trusting rumors
- `repomix-codebase-context.md` for optional Repomix-based compressed codebase
  context on large, unfamiliar, or multi-language repositories
- `review-checklist.md` for final scope, evidence, validation, safety, and
  handoff checks
- `resume-protocol.md` for safely continuing interrupted work
- `security-review-protocol.md` for defensive security review, secrets checks,
  threat modeling, and security-sensitive PR review
- `ship-readiness-protocol.md` for PASS/WARN/FAIL/SKIP readiness reviews before
  merge, release, deployment planning, or reviewer handoff
- `skill-authoring-methodology.md` for eval-driven skill maintenance,
  trigger examples, description quality, and package verification
- `stop-conditions.md` for knowing when to pause instead of continuing
- `systematic-debugging-protocol.md` for root-cause-first debugging of bugs,
  failing tests, regressions, and unexpected behavior
- `tdd-protocol.md` for optional Red/Green/Refactor and regression-test
  workflows when test-first development reduces risk
- `ui-ux-review-protocol.md` for accessibility, responsive behavior,
  interaction states, visual-system consistency, and evidence-backed frontend
  handoff review
- `validation-matrix.md` for choosing verification steps by task type
- `writing-humanization-protocol.md` for voice calibration, AI-pattern audits,
  and meaning-preserving rewrites

### templates/

Use `templates/` for reusable starter documents. This package includes:

- `HANDOFF_REPORT_TEMPLATE.md` for substantial PR or long-running task handoff
  summaries
- `PROJECT_MEMORY_TEMPLATE.md` for durable, non-sensitive project facts
- `IMPROVEMENT_SCAN_TEMPLATE.md` for periodic skill improvement scans
- `accessibility-checklist.md` for practical keyboard, focus, semantics,
  contrast, motion, form, and responsive accessibility checks
- `api-contract-test-plan.md` for API endpoint, auth, request/response, error,
  retry, and contract-test planning
- `implementation-plan.md` for scoped implementation plans
- `analysis-run-log.md` for reproducible analysis records
- `claim-evidence-table.md` for evidence-backed writing
- `data-quality-report.md` for schema summaries, data quality findings,
  cleaning decisions, before/after evidence, and reproducibility notes
- `deck-outline.md` for source-to-slide planning
- `debugging-runbook.md` for recording root-cause investigations and final
  verification
- `frontend-handoff.md` for UI implementation handoffs with design decisions,
  states, accessibility notes, validation, and reviewer focus
- `market-data-source-log.md` for market data sources, dates, units,
  transformations, limitations, and reproducibility notes
- `new-skill-brief.md` for defining trigger scope, source material, safety
  boundaries, package shape, and validation before creating a skill
- `option-analysis.md` for comparing implementation or product directions
- `regression-test-record.md` for bug reproduction, failing tests, fixes, and
  passing evidence
- `risk-challenge-table.md` for adversarial review of assumptions, evidence,
  risks, recommended defaults, and open decisions
- `slide-qa-checklist.md` for presentation QA
- `reviewer-response.md` for tracking review comments, decisions, validation,
  and response drafts
- `ship-checklist.md` for pre-merge or release-readiness blockers, warnings,
  rollback, and post-release checks
- `secrets-scan-checklist.md` for pre-commit and pre-PR checks that avoid
  exposing secrets or confidential files
- `skill-evaluation-plan.md` for skill trigger coverage, instruction quality,
  safety review, validation commands, and reviewer notes
- `stock-research-report.md` for source-backed company, sector, market, and
  watchlist research reports
- `TASK_LOG_TEMPLATE.md` for concise completed-task notes
- `ui-ux-audit.md` for evidence-backed frontend findings and recommendations
- `valuation-assumption-table.md` for valuation inputs, sensitivity, evidence,
  caveats, and sanity checks
- `verification-evidence.md` for merge-readiness and validation evidence
- `risk-disclosure.md` for financial research disclaimers and limitations
- `voice-calibration.md` for writing humanization and tone calibration
- `WORKING_STATE_TEMPLATE.md` for resumable in-progress task state

Templates are structure only. They are not a place to store sensitive content.

### prompt-styles/

Use `prompt-styles/` for optional presentation styles. They can make Codex more
concise, evidence-first, product-review oriented, cinematic, or handoff-focused
without weakening safety rules.

### scripts/

Use `scripts/` for simple local helpers. This package includes:

- `append_project_memory.py` to append facts to `docs/PROJECT_MEMORY.md`
- `audit_skill_descriptions.py` to check skill descriptions for trigger-focused
  metadata
- `check_for_updates.py` to check whether GitHub has a newer package revision
- `check_skill_package.py` to validate the package structure
- `doctor.py` to run product-readiness checks for local installs
- `github_skill_scan.py` to scan public GitHub projects for review-gated
  improvement evidence
- `scan_top_related_skills.py` to review the top related public skill projects
  for safe manual upgrade ideas
- `test_expected_triggers.py` to validate packaged trigger fixtures
- `update_installed_skill.py` to update installed skills with dry-run and
  backup-first behavior
- `update_task_log.py` to append completed task entries to `docs/TASK_LOG.md`

The memory and task-log helpers are intentionally local-only. They do not read
environment variables, make network calls, delete files, or require external
dependencies. The GitHub scan and update-check helpers access public GitHub
metadata only when the user runs them.

### assets/

An `assets/` folder may be added later for static support files such as images,
fixtures, or examples. Keep assets non-sensitive and avoid adding large files
unless they are necessary for the skill.

## Verify And Doctor

From this package repository, run:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
```

`check_skill_package.py` validates required files. `doctor.py` checks
productized package readiness. `audit_skill_descriptions.py` checks description
metadata. `test_expected_triggers.py` validates static trigger examples without
calling a model.

## Update And Rollback

Use the backup-first update helper from this package repository:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py --list-skills
```

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering
```

The default mode is dry-run. To apply after review:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering \
  --apply
```

Existing installed skills are backed up under `.codex-skill-backups/` before
files are copied. The helper does not make network calls, delete files, or
modify `main`.

For more detail, see [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md).

## Reviewer Checklist

Before marking a productization PR ready for review:

- Package checks pass locally and in CI.
- `doctor.py` and `test_expected_triggers.py` pass.
- Update helper defaults to dry-run and backup-first behavior.
- README, INSTALL, and UPGRADE_GUIDE explain install, verify, update, rollback,
  and troubleshooting.
- No secrets, private client data, legal evidence, financial records, or
  hidden/bidirectional Unicode controls were added.

## Optional Repomix Context

For large or unfamiliar repositories, Codex may use
`references/repomix-codebase-context.md` to create a compressed codebase map
before planning. Repomix is optional and not bundled as a dependency. Exclude
secrets, `.env` files, credentials, private client data, legal evidence,
financial documents, generated outputs, dependency folders, and other sensitive
content.

Example:

```bash
npx repomix --compress
```

Ask before running commands that download or execute packages.

## Methodology and Search Protocols

The package includes optional methodology and search guidance for skill
authoring, trigger audits, implementation planning, verification evidence, and
privacy-first external source review. External search is optional,
provider-neutral, and should never receive secrets, private client data, legal
evidence, financial records, or confidential source material without explicit
approval.

## Content, Research, Design, and Presentation Protocols

This package includes additive protocols for:

- writing humanization and voice calibration
- ideation-to-plan option analysis
- evidence-backed writing and claim-evidence alignment
- adversarial review and risk challenge tables
- TDD and regression-test evidence
- API integration and contract-test planning
- ship-readiness checks
- data cleaning and data quality reporting
- financial research reports, valuation assumptions, market data source logs,
  and risk disclosures
- defensive security review and secrets-scan checklists
- notebook/data analysis run logs
- presentation delivery and slide QA
- AI video design systems
- UI/UX review, accessibility checks, and frontend handoffs
- skill brief and skill evaluation planning
- academic source search patterns

These protocols do not add external dependencies. They are guidance, templates,
and validation assets.

## How AGENTS.md And SKILL.md Work Together

`AGENTS.md` gives repository-level instructions to Codex. In a project using
this package, it should tell Codex when to use the `long-horizon-engineering`
skill and state broad expectations such as reading files before editing, making
small verifiable changes, and avoiding secrets.

`SKILL.md` is the skill-specific instruction file. When the skill is triggered,
Codex should read it and follow its workflow for the current task.

In practice:

- Use `AGENTS.md` to route Codex toward the skill.
- Use `SKILL.md` to define the actual long-horizon workflow.
- Use `references/` when the workflow needs more detail.
- Use `templates/` and `scripts/` only when persistent tracking is appropriate.

## Long-Horizon Resume Support

`docs/WORKING_STATE.md` is optional and can be used for resumable task state
when a task is long-running, interrupted, or likely to continue after context
compaction. It should capture the current goal, status, inspected and changed
files, confirmed facts, assumptions, decisions, failed attempts, test results,
known risks, and the next safest step.

`references/context-compaction.md` describes what to preserve before a task is
paused, interrupted, or compacted.

`references/capability-boundaries.md` defines safe defaults for powerful agent
behavior such as sub-agent orchestration, autonomous deployment,
self-improvement loops, auto-merge, production execution, and security
automation.

`references/client-privacy.md` defines privacy rules for client and
confidential data, including no sensitive details in memory, task logs, working
state, handoff reports, public PRs, or this reusable skill repository.

`references/decision-log.md` helps prevent unsupported assumptions by separating
facts, assumptions, decisions, evidence, risks, and follow-ups.

`references/resume-protocol.md` helps Codex continue safely after interruption
by reading prior memory, task logs, working state, relevant files, and prior logs
before planning the next change.

`references/stop-conditions.md` helps Codex pause when requirements, tools,
repository state, or safety concerns make continued edits risky.

`references/review-checklist.md` helps Codex check scope, evidence, validation,
safety, and handoff quality before finalizing work.

`references/large-migration-playbook.md` helps Codex map a codebase, divide
large migrations into reviewable phases, preserve compatibility where possible,
validate in layers, and stop for user confirmation on high-risk decisions.

`references/validation-matrix.md` helps Codex choose verification steps that
match the task type, such as bug fixes, refactors, migrations, UI changes,
performance work, security-sensitive changes, or documentation-only changes.

`references/external-source-scan.md` explains how Codex should ask before
scanning local folders outside the repository, connected cloud drives, Gmail, or
other external sources. External scans are optional and should use the narrowest
approved scope.

`references/continuous-improvement.md` defines a safe self-improvement loop:
check related public skills and agent projects, record evidence, adapt only
small reusable patterns, run checks, and open a draft PR for review.

`references/public-agent-capability-review.md` helps Codex compare public
frontier-agent capability descriptions, classify source reliability, separate
verified facts from unverified claims, and translate useful themes into small
review-gated improvements.

These files are optional and safety-aware. Do not create or update
`PROJECT_MEMORY.md`, `TASK_LOG.md`, or `WORKING_STATE.md` in sensitive
repositories unless the user explicitly approves. Do not use them to store
private or sensitive content.

## Final Long-Horizon Engineering Supports

This package includes three final lightweight supports for harder engineering
work:

- `references/large-migration-playbook.md` supports large codebase migrations
  and complex multi-file implementations.
- `references/validation-matrix.md` helps Codex choose task-appropriate
  verification instead of using one generic test strategy.
- `templates/HANDOFF_REPORT_TEMPLATE.md` supports human review of substantial
  PRs or long-running tasks.

These supports are optional. They should not create sensitive logs or persistent
handoff files by default, and they should not be used to store secrets, API
keys, legal evidence, family information, private client data, financial account
details, or confidential documents.

## Capability Boundaries

Codex can support powerful workflows, but this public skill keeps them bounded:

- Sub-agent orchestration is allowed for narrow, independent research and
  review, with the main agent retaining responsibility.
- Self-improvement is draft-PR-only and review-gated.
- Autonomous deployment and production execution are plan-only by default.
- Auto-merge is disabled by default and requires explicit user authorization.
- Security automation is defensive only and must stay within authorized scope.

The default path is branch, validate, summarize, and open a draft PR for human
review.

## Client Privacy and Confidential Data Protection

This skill is designed to be safer for private repositories that may contain
client information, legal evidence, financial records, family information,
business documents, medical or identity details, private correspondence, or
confidential research materials.

Sensitive repositories should default to plan-only mode until the user approves
specific files, commands, edits, staging paths, and push targets. Codex should
use the minimum necessary exposure and refer to private materials with generic
labels such as "client contract file" or "private evidence document" instead of
copying details.

Do not store client data in memory, task logs, working state, handoff reports,
examples, commits, public PR text, or this reusable skill repository. Public PRs
and public repositories must never include private client data.

Use explicit path staging in sensitive repositories. Do not use broad staging
such as `git add .` when private materials may be present.

This reusable skill repository must contain templates and rules only, never real
client data, legal evidence, financial data, identity documents, family
information, private correspondence, or confidential source content.

## Continuous Improvement

This skill can support a weekly improvement scan, but it should be review-gated.
Codex may check public Codex, Agent Skills, and long-horizon coding-agent
projects for relevant changes, then propose small updates through a draft PR.

The safe loop is:

1. Inspect public sources and related skill projects.
2. Record facts, assumptions, risks, and links.
3. Identify small reusable patterns, not code to copy.
4. Update this repository only when the change is evidence-backed.
5. Run `check_skill_package.py`.
6. Open a draft PR for user review.

Do not auto-merge. Do not push directly to `main`. Do not copy external code
without checking license obligations. Do not store private or sensitive content
in improvement scans.

When a capability comes from public reporting rather than official
documentation or reproducible research, treat it as a signal to investigate, not
as verified fact.

Use the template:

```bash
cp .agents/skills/long-horizon-engineering/templates/IMPROVEMENT_SCAN_TEMPLATE.md docs/IMPROVEMENT_SCAN.md
```

Create or update that file only when persistent tracking is appropriate and the
repository is not sensitive.

To collect public GitHub signals manually:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/github_skill_scan.py --dry-run --limit 3
```

Remove `--dry-run` to write `docs/GITHUB_SKILL_SCAN.md`. Treat the report as
evidence for review, not as permission to copy external code.

To inspect the top three related public skill repositories for manual upgrade
ideas:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/scan_top_related_skills.py --dry-run
```

Remove `--dry-run` to write `docs/TOP_RELATED_SKILLS_SCAN.md`. The report
summarizes repository signals such as `SKILL.md` files, references, templates,
scripts, workflows, examples, and safety files. It does not copy code, execute
remote code, modify this repository, or update the skill automatically.

Use the report as a system prompt for manual review: the user decides whether
to click a PR, request an original small change, copy an approved update, or
skip. Do not auto-merge, auto-update, or directly edit `main`.

## Checking For Skill Updates

Clients can check whether this local skill package may be behind the GitHub
version by running:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_for_updates.py
```

The update check queries the public GitHub repository and compares the latest
`main` commit with the local checkout when this directory is a clone of the
skill repository. It reports status only. It does not pull, overwrite files,
modify local projects, or update installed skills automatically.

If the skill was copied into another project without git metadata, the script
cannot safely compare the installed copy to GitHub. In that case, it prints the
latest remote commit and tells the user to review the GitHub repository before
copying updates.

Use the result as a review signal:

- `Status: up to date.` means the local clone matches the checked GitHub branch.
- `Status: update may be available.` means review the GitHub changes before
  updating.
- `cannot safely compare` means the local copy is not enough to prove whether it
  is current.

Never auto-update skills inside private repositories without human review.
Never overwrite local project instructions, private data, logs, or client
materials.

## External Source Scans

Codex may sometimes need to know whether related files were added, removed, or
changed outside the current repository. For example, the user may want Codex to
check a selected local folder, connected cloud drive, or Gmail search.

This skill treats those sources as sensitive by default. Codex should ask before
scanning them and confirm:

- Source type, such as local folder, cloud drive, or Gmail
- Exact folder, label, query, or date range
- Whether to inspect file contents or only metadata
- Whether results may be summarized in task notes

Use repository-only scanning when that is enough. Do not scan broad personal
folders, full mailboxes, or cloud drives without a specific approved scope. Do
not store secrets, personal messages, private client data, financial account
details, legal evidence, family information, API keys, or confidential documents
in memory, logs, working state, or generated reports.

## Location And Industry Compliance

`references/jurisdiction-industry-compliance.md` guides tasks that need
location-aware or industry-aware legal, regulatory, or rule-of-practice context.

Codex should not silently enable GPS, read device location, infer precise
location from private files, or store precise location in reusable memory or
logs. It should ask whether the user wants to approve device/GPS location use or
manually provide the country, state/province, city, or region. It should confirm
the customer's industry or business activity and use current public sources for
jurisdiction-specific legal or regulatory facts.

Outputs should clearly separate public facts, practical implications, and
recommendations. They should say that the response is informational and not
legal advice. After a local answer, Codex should ask whether the user wants to
compare cross-region laws, regulations, or industry rules before expanding the
scope. It should also ask whether the user wants to load approved skills or
reference files for other regions, using public or non-sensitive sources by
default and excluding private client materials unless explicitly approved.

## Copying This Skill Into Another Project

For the short version, see [INSTALL.md](INSTALL.md).

From another repository root, copy the skill directory:

```bash
mkdir -p .agents/skills
cp -R path/to/codex-long-horizon-skill/.agents/skills/long-horizon-engineering .agents/skills/
```

Then add or update that project’s `AGENTS.md` with a short instruction such as:

```markdown
When a task involves multi-step engineering work, use the
`long-horizon-engineering` skill.
```

If the target repository already has a `.agents/skills/long-horizon-engineering`
directory, review the files before overwriting local customizations.

## How To Ask Codex To Use It

You can ask directly:

```text
Use the long-horizon-engineering skill.
```

You can also describe a task that clearly matches the skill, such as a
multi-file bug fix, migration, refactor, or long-running implementation.

## Usage Example

Here is an exact prompt you can give Codex:

```text
Use the long-horizon-engineering skill.
Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
```

## When To Use This Skill

Use this skill for:

- Large codebase exploration
- Multi-file changes
- Refactors or migrations
- Bug fixes with uncertain root cause
- Test failure diagnosis
- Security-sensitive changes
- Performance optimization
- API, schema, build, deployment, or CI changes
- Work that may need to be resumed later

## When Not To Use This Skill

Do not use this skill for:

- Simple typo fixes
- One-line edits
- Purely conversational answers
- Tiny formatting-only changes
- Tasks where persistent planning or logging would add unnecessary overhead
- Sensitive repositories where project memory or task logs would be unsafe

## Maintaining PROJECT_MEMORY.md

`docs/PROJECT_MEMORY.md` is optional. Create or update it only when persistent
tracking is appropriate and the repository is not sensitive.

Use it for durable, non-sensitive facts that future Codex runs should remember,
such as:

- Package manager and common commands
- Stable repository conventions
- Architecture notes
- Important technical decisions
- Known safe follow-ups

Create it from the template when appropriate:

```bash
mkdir -p docs
cp .agents/skills/long-horizon-engineering/templates/PROJECT_MEMORY_TEMPLATE.md docs/PROJECT_MEMORY.md
```

Append a fact with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/append_project_memory.py "Use npm for frontend package management."
```

Preview without writing:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/append_project_memory.py --dry-run "Use npm for frontend package management."
```

Only add facts that are expected to remain useful across future tasks.

## Maintaining TASK_LOG.md

`docs/TASK_LOG.md` is optional. Create or update it only when persistent tracking
is appropriate and the repository is not sensitive.

Use it to record completed engineering tasks in a concise, resumable format:

- What changed
- Why it changed
- Files touched
- Verification commands and results
- Remaining risks or follow-ups

Create it from the template when appropriate:

```bash
mkdir -p docs
cp .agents/skills/long-horizon-engineering/templates/TASK_LOG_TEMPLATE.md docs/TASK_LOG.md
```

Append a completed task entry with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_task_log.py \
  --title "Add health check endpoint" \
  --summary "Added a lightweight API health check." \
  --file "src/server.ts" \
  --verification "npm test passed" \
  --notes "No known follow-up."
```

Preview without writing:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_task_log.py \
  --dry-run \
  --title "Add health check endpoint" \
  --summary "Added a lightweight API health check."
```

## Checking The Skill Package

Run the local structure check before publishing changes:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
```

The check verifies the required files, `SKILL.md` front matter, and absence of
nested `.agents` directories.

GitHub Actions also runs the package checker and helper `--help` commands on
pull requests and pushes to `main`.

## Safe Use Warning

Do not store:

- Secrets
- API keys
- Legal evidence
- Family information
- Private client data
- Financial account information
- Confidential documents

Use templates only as reusable structure, not as a place for sensitive content.
Project memory and task logs should contain durable, non-sensitive engineering
context only.
