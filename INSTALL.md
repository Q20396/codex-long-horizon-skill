# Installation

This repository contains reusable Codex skills:

- `long-horizon-engineering`
- `ai-video-production`

## Install As A Plugin

Plugin installation is the preferred reusable distribution path.

Add this repository marketplace:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
```

Refresh after updates:

```bash
codex plugin marketplace upgrade codex-long-horizon-skills
```

Remove when no longer needed:

```bash
codex plugin marketplace remove codex-long-horizon-skills
```

The tested CLI exposes marketplace `add`, `upgrade`, and `remove`. If your
Codex surface does not show the plugin immediately, restart Codex. Detailed
notes are in [docs/plugin-install.md](docs/plugin-install.md).

## Install By Git Clone

Direct skill installation is useful for authoring and repository-scoped use.
Clone this package into a reviewable local folder, then copy only the skill
folder you want into the target project:

```bash
git clone https://github.com/Q20396/codex-long-horizon-skill.git
cd codex-long-horizon-skill
```

## Copy Into A Project

From the target project root:

```bash
mkdir -p .agents/skills
cp -R path/to/codex-long-horizon-skill/.agents/skills/long-horizon-engineering .agents/skills/
```

Then add or update the target project's `AGENTS.md`:

```markdown
When a task involves multi-step engineering work, use the
`long-horizon-engineering` skill.
```

## Recommended Path

```text
.agents/skills/long-horizon-engineering/
```

Optional sibling skill:

```text
.agents/skills/ai-video-production/
```

After installing or updating a skill, restart Codex or start a new Codex session
so the changed skill metadata and instructions are reloaded.

## Verify The Package

From this repository root:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
python3 -m unittest discover -s tests -p "test_*.py"
python3 scripts/validate_plugin_package.py
python3 scripts/test_fresh_install.py --skip-codex-cli
```

For a local release smoke test with your installed Codex CLI, run
`python3 scripts/test_fresh_install.py --require-codex-cli --verbose`. Add
`--require-plugin-install` only when your CLI exposes `codex plugin add`.

## Update An Installed Skill

Dry-run first:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering
```

Apply after review:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering \
  --apply
```

The updater backs up the existing installed skill under `.codex-skill-backups/`
before copying package files. Before `--apply` copies files, it runs the local
read-only `audit_skill_safety.py` check against the package skills. It does not
delete files, make network calls, or modify `main`.

## Rollback

Restore the reviewed backup skill directory from `.codex-skill-backups/` to:

```text
.agents/skills/<skill-name>/
```

Keep rollback scoped to the skill directory. Do not overwrite unrelated project
files or private data.

## Troubleshooting

- Run `doctor.py` if the package appears incomplete.
- Run `check_skill_package.py` before opening a PR.
- Use dry-run update mode before applying changes to another project.
- If optional tools such as Repomix are unavailable, use normal codebase
  exploration instead.
- No external search provider is required; external search remains optional and
  privacy-first.
- External apps, hosted notebooks, browser sessions, provider CLIs, and
  connected services are optional and approval-gated. Use local or metadata-only
  review first, and do not upload private source material without explicit
  customer approval for the exact subset and purpose.
- If content, research, notebook, presentation, or video design protocols are
  not needed, ignore them; they are additive optional references and templates
  and require no new dependencies.
- If the target project is sensitive, ask before reading, copying, staging, or
  summarizing private materials.
- Disaster monitoring setup is privacy-first: manually add monitored locations
  by default, use GPS/current location only as a one-time customer-approved
  option, prefer approximate place and radius, and do not enable continuous
  tracking or location sharing by default.

## Prompt Example

```text
Use the long-horizon-engineering skill.
Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
```

## Safety

Do not store secrets, API keys, legal evidence, family information, private
client data, financial account details, or confidential documents in memory,
logs, state files, examples, or handoff reports.
