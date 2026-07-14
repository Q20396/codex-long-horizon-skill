# Codex Long Horizon Skills

Production-oriented Codex skills for large engineering projects, long-running
tasks, repository migrations, PR workflows, AI-assisted development, and
review-gated execution.

Designed for:

- Large repositories
- Multi-hour engineering sessions
- Controlled execution with validation
- Recoverable workflows
- Repeatable validation

Install once. Reuse everywhere.

## Skill Catalog

<!-- skill-catalog:start -->
| Skill | Purpose | Best For |
| --- | --- | --- |
| [`ai-video-production`](.agents/skills/ai-video-production/SKILL.md) | Use for AI-assisted video or animation planning: video briefs, scripts, storyboards, shot lists, visual prompts, asset manifests, preview plans, and render handoffs. Do not use for general repository engineering or automatic rendering, uploading, publishing, or posting. | Video briefs, scripts, storyboards, visual prompts, asset manifests, and render handoffs. |
| [`long-horizon-engineering`](.agents/skills/long-horizon-engineering/SKILL.md) | Use for long-running software engineering work: repository exploration, multi-file changes, debugging, migrations, refactors, CI/build failures, staged validation, PR review response, or safe resumption. Do not use for simple edits, unrelated research, writing, media, or legal/financial tasks. | Large refactors, migrations, debugging, PR workflows, resumable tasks, and validation-heavy engineering. |
<!-- skill-catalog:end -->

## Quick Start

Add the repository marketplace:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
```

Then enable the plugin in your Codex surface if prompted. See
[Plugin installation](docs/plugin-install.md) for verification, upgrade, and
removal notes.

Or clone this repository for direct skill installation:

Clone this repository:

```bash
git clone https://github.com/Q20396/codex-long-horizon-skill.git
cd codex-long-horizon-skill
```

Copy the skills into a target project:

```bash
mkdir -p /path/to/project/.agents
cp -R .agents/skills /path/to/project/.agents/
```

Verify the installed skills from the target project:

```bash
cd /path/to/project
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py --installed
```

Ask Codex to use a skill:

```text
Use the long-horizon-engineering skill.
Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
```

## Copy-Paste Prompt Library

These prompts are also available as files under [prompts/](prompts/).

### Large Refactor

Use the long-horizon-engineering skill.

Perform a repository-wide refactor.

Requirements:

- Explore first
- Produce implementation plan
- Work incrementally
- Validate after each phase
- Open draft PR

### Bug Investigation

Use the long-horizon-engineering skill.

Investigate root cause before changing code.

Deliver:

- Findings
- Proposed fix
- Validation evidence
- Risk assessment

### Resume Interrupted Work

Use the long-horizon-engineering skill.

Resume previously interrupted work.

Recover:

- Current state
- Completed tasks
- Remaining tasks
- Blockers
- Next actions

### PR Review

Use the long-horizon-engineering skill.

Review this pull request.

Deliver:

- Findings
- Risks
- Validation gaps
- Merge recommendation

### Repository Migration

Use the long-horizon-engineering skill.

Migrate this repository.

Requirements:

- Explore existing architecture
- Preserve behavior
- Validate functionality
- Produce migration report

## Why This Exists

Long-running coding-agent sessions can break down when they lose context, skip
validation, rely on unverified assumptions, or cannot recover cleanly after
interruption.

These skills provide structured workflows that improve reliability and
reproducibility.

## What Is Included

- `.agents/skills/long-horizon-engineering/` for multi-step engineering,
  planning, validation, debugging, PR workflows, migrations, resumable work,
  privacy-first evidence tracking, and review-gated skill improvement.
- `.agents/skills/ai-video-production/` for AI video briefs, scripts,
  storyboards, shot lists, visual prompts, asset manifests, and render handoffs.
- [prompts/](prompts/) for copy-paste task prompts.
- [templates/](templates/) for reusable project, validation, findings, and
  migration reports.
- [examples/](examples/) for sample prompt and smoke-test artifacts.
- [scripts/generate_skill_catalog.py](scripts/generate_skill_catalog.py) for
  README catalog generation and product-documentation checks.
- [INSTALL.md](INSTALL.md), [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md),
  [CHANGELOG.md](CHANGELOG.md), and [CONTRIBUTING.md](CONTRIBUTING.md) for
  installation, updates, release history, and contribution workflow.

## Awesome Codex Skills Ecosystem

- [Official skill catalog](#skill-catalog)
- [Prompt library](prompts/)
- [Examples](examples/)
- [Templates](templates/)
- [Plugin installation](docs/plugin-install.md)
- [Demo recording guide](docs/demo/README.md)
- [Contribution guide](CONTRIBUTING.md)
- [First contribution guide](docs/first-contribution.md)
- [Community skills registry](COMMUNITY_SKILLS.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)

## Official Codex Skill Structure

Codex skills are the workflow authoring format. A skill is a directory
containing a required `SKILL.md` file and optional supporting folders such as
`scripts`, `references`, `templates`, and `assets`. Codex first reads skill
metadata to decide whether the skill is relevant. If selected, Codex then reads
the full `SKILL.md` instructions.

Codex plugins are the installable distribution unit. This repository now
includes `.codex-plugin/plugin.json` and a repo marketplace at
`.agents/plugins/marketplace.json` so the canonical skills can be distributed
without duplicating the skill directories.

Release checks distinguish static plugin package validation, direct skill
installation, marketplace registration, and actual plugin installation. Actual
plugin installation is claimed only when the installed Codex CLI exposes and
passes `codex plugin add`.

Recommended installation path:

```text
.agents/skills/<skill-name>/
```

## Skill Quality Standard

Every skill must contain:

- `SKILL.md`
- Usage guidance
- Validation workflow
- Safety boundaries
- Failure recovery strategy
- Example prompts

Optional:

- `references/`
- `templates/`
- `scripts/`
- `assets/`

## Industrial Skill Design Principles

Industrial skills should trigger accurately, run with least privilege, use
progressive disclosure, match workflow depth to task risk, and maintain an
evaluation loop. `SKILL.md` should stay concise; long protocols, templates,
scripts, and assets should live in their supporting folders.

For larger skill systems, this repository favors router patterns, invocation
permission layers, and shared design vocabulary while keeping external ideas
review-gated instead of copied or auto-installed.

Keywords: router patterns, invocation permission layers, shared design vocabulary.

## Role-Based Engineering Loop

For substantial engineering tasks, the long-horizon skill uses a lightweight
Planner -> Builder -> Evaluator -> Human Gate flow. The Planner defines scope,
completion criteria, evidence, and stop conditions; the Builder performs only
approved work; the Evaluator maps results to evidence and reports gaps; the
human decides whether to accept or request a bounded correction.

These are serial working roles, not autonomous sub-agents. They do not grant
new permissions or enable automatic edits, installs, pushes, merges, deploys,
or releases. Optional working state supports safe resumption only after current
branch, diff, and validation state have been re-checked.

## Text To Visual Analysis

The `ai-video-production` skill can turn supplied text into visual plans before
generation. It analyzes the complete text first, selects only high-value
concepts for visualization, and produces diagram, storyboard, explanatory
graphic, image-prompt, or text-only recommendations. It does not generate,
upload, publish, or bill media automatically.

## Self-Check and Review-Gated Improvement

Self-check follows: Observe → Compare → Explain → Recommend → Wait for approval.
In this mode, self-check is read-only, and all findings remain proposal-only
until the user approves a separate action. Updating or applying a change is a
separate explicit action, not part of self-check.

## Manual Update Check

Customers can ask Codex to check for an approved skill update, but the check is
manual, read-only, and network-gated. It does not run in the background, install
files, overwrite local skills, or update from mutable sources such as `main`,
`master`, `latest`, or branch names.

In tag mode, the checker accepts public HTTPS remotes only, blocks obvious local
or private destinations, checks DNS results before the Git lookup, disables Git
HTTP redirects and proxy inheritance, and verifies that the tag resolves to the
expected exact commit SHA. This reduces accidental unsafe lookups, but it is not
a complete SSRF defense against DNS rebinding or a compromised remote host.

Example prompt:

```text
Use the long-horizon-engineering skill.
Check whether my installed codex-long-horizon-skill package has an approved update.
Ask before using network access, compare only against tag vX.Y.Z and expected commit <reviewed-40-character-sha>, and do not apply the update.
```

From this package repository, the read-only check can be run after explicit
network approval:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_for_updates.py \
  --allow-network \
  --source-tag vX.Y.Z \
  --expected-commit REVIEWED_40_CHARACTER_SHA
```

For an exact commit already supplied by the user, compare locally without a
remote lookup:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_for_updates.py \
  --source-commit REVIEWED_40_CHARACTER_SHA
```

Treat the result as advice only. Applying an update remains a separate
backup-first action with `update_installed_skill.py`.

For a customer-facing copy-paste prompt that compares installed skills with the
published `v0.1.0` release, see [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md).

## Safe skill update self-check

This GitHub repository is the source of truth for the latest published skills.
Customers may have older installed versions under `~/.agents/skills`. The
self-check compares local installed skills with the GitHub version. The default
check is read-only: Codex asks before online checking, asks again before
updating, creates backups before replacement, prints rollback commands, and does
not auto-update.

Customer prompt:

```text
Use the skill-installer skill.

Compare my installed Codex skills with:
https://github.com/Q20396/codex-long-horizon-skill

Check long-horizon-engineering and ai-video-production.
Do not install or replace automatically.
Summarize differences, risks, upgrade recommendation, and rollback plan.
Ask me before making changes.
```

Check only:

```bash
python3 scripts/skill_update_selfcheck.py
```

`--skills` is restricted to the bundled supported skills:
`long-horizon-engineering` and `ai-video-production`. For release-grade
comparison, prefer an immutable tag or exact commit with `--ref`.

Apply after explicit typed confirmation:

```bash
python3 scripts/skill_update_selfcheck.py --apply
```

`--apply` still does not silently update. It prints a summary and requires the
user to type exactly one of:

```text
UPDATE long-horizon-engineering
UPDATE ai-video-production
UPDATE ALL
```

Apply mode refuses traversal paths, unsupported skill ids, symlinked skill
targets, symlinked remote skill folders, and unsafe symlinks before replacing
anything.

Backups are created under:

```text
~/.agents/skills/.backups/YYYYMMDD-HHMMSS/<skill_id>
```

Rollback can be done by copying the backup folder back to:

```text
~/.agents/skills/<skill_id>
```

## Install, Verify, Update

Validate this source package:

```bash
python3 scripts/generate_skill_catalog.py --check
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
```

Run the broader local validation suite:

```bash
python3 scripts/full_skill_validation.py
```

`scripts/full_skill_validation.py` uses the system temp directory by default.
Override it when needed:

```bash
CODEX_SKILL_TMP_ROOT=/path/to/tmp python3 scripts/full_skill_validation.py
```

Preview an update into another project:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering
```

Apply only after review:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering \
  --apply
```

The update flow is dry-run by default and backup-first when `--apply` is used.

## Safety Model

Do not store secrets, API keys, legal evidence, family information, private
client data, financial account information, confidential documents, identity
documents, or private correspondence in reusable prompts, templates, memory,
logs, state files, commits, public PRs, or examples.

Sensitive repositories should default to plan-only mode until the user approves
specific files and actions. Use explicit path staging; do not use broad
`git add .` for confidential work.

## Community Skills

Community skills are welcome when they are original, reviewable, and safe by
default.

Contribution workflow:

1. Create a branch.
2. Add or update a skill under `.agents/skills/`.
3. Include examples, validation guidance, safety boundaries, and recovery notes.
4. Run the validation commands in [CONTRIBUTING.md](CONTRIBUTING.md).
5. Open a draft PR with the problem, design, risks, and validation evidence.

Do not copy external repository code or prose into this repository. Learn from
patterns, then write original implementation and documentation.

## Repository Map

```text
.agents/skills/
  ai-video-production/
  long-horizon-engineering/
.agents/plugins/
  marketplace.json
.codex-plugin/
  plugin.json
docs/
examples/
prompts/
scripts/
templates/
tests/
```

## Maintainer Notes

Regenerate the README catalog after adding, renaming, or changing a skill
description:

```bash
python3 scripts/generate_skill_catalog.py
```

Check that generated docs, skill quality, and internal links are still valid:

```bash
python3 scripts/generate_skill_catalog.py --check
```

The canonical trigger fixture is [tests/expected-triggers.json](tests/expected-triggers.json).
Skill-local response styles remain under each skill's `prompt-styles/`
directory; root [prompts/](prompts/) contains copy-paste task prompts for users.

## License

MIT. See [LICENSE](LICENSE).
