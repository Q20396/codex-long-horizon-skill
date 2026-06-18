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
