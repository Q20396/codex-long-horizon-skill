# Installation

This repository contains reusable Codex skills:

- `long-horizon-engineering`
- `ai-video-production`

## Install As A Plugin

Plugin installation is the preferred reusable distribution path.

The stable release-state contract records the immutable `v0.6.1` marketplace
reference with `policy.installation: AVAILABLE`:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref v0.6.1
```

Before running it, independently verify the remote annotated tag, peeled
commit/tree, published GitHub Release, and isolated marketplace resolution for
`v0.6.1`. Repository metadata alone does not prove those external stages.
`main` is mutable repository state and is not a stable installation channel:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
```

Do not assume `marketplace upgrade` advances a marketplace pinned to another
tag. A verified upgrade must explicitly remove the prior registration and add
the reviewed tag again; actual CLI rebind behavior requires a separately
approved isolated CLI check.

Refresh a mutable marketplace only when that behavior is intentional:

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

Optional read-only update check from this package repository:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_for_updates.py \
  --allow-network \
  --source-tag vX.Y.Z \
  --expected-commit REVIEWED_40_CHARACTER_SHA
```

Use only reviewed tags with an expected full commit SHA. Do not use mutable
sources such as `main`, `master`, `latest`, or branch names as reproducible
update-check sources. This check reports status only; it does not install,
copy, overwrite, or update files.

For a full customer-facing prompt that compares installed skills with a
published release without applying changes, see [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md).

Dry-run a project-level `.agents/skills/<skill>` update first:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering
```

Apply to a project-level installation after review:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering \
  --apply
```

For an existing Codex user-level installation, use the direct skill directory:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-skill-dir ~/.codex/skills/long-horizon-engineering \
  --skill long-horizon-engineering
```

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-skill-dir ~/.codex/skills/long-horizon-engineering \
  --skill long-horizon-engineering \
  --apply
```

Do not use `~/.codex` as `--target-root`; that would imply the unsupported
duplicate layout `~/.codex/.agents/skills/<skill>`.
Direct skill-directory targets must use a `skills/<skill>` layout, and the
final directory name must match the selected skill.

The updater first compares the complete source and target manifests. If the
target contains paths that are not in the source package, apply stops without
writing anything. Review the listed paths before allowing their removal:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
  --target-root /path/to/project \
  --skill long-horizon-engineering \
  --allow-remove-extra-files \
  --apply
```

Approved target-only files are removed from the active installation by complete
directory replacement, but remain in the retained backup. They are never
silently preserved or silently removed.

Before publish, the updater runs the local read-only `audit_skill_safety.py`,
copies the source into a unique same-filesystem staging directory, and compares
source and staging manifests by relative path, entry type, file size, and
SHA-256. It retains a complete backup under `.codex-skill-backups/` for
project-level installs, or under `skill-backups/` next to the active Codex
`skills/` directory for direct user-level installs. It then replaces the active
skill and verifies the published manifest again. Backups are not automatically
deleted.

If post-publish validation fails, the failed target is retained in a unique
quarantine directory and the updater attempts to restore and verify the prior
target. Recovery is best-effort, not a filesystem transaction. The updater
does not guarantee safety against a hostile same-UID process replacing paths or
inodes concurrently, SIGKILL or power-loss recovery, strong atomicity on
network filesystems, complete ACL/xattr preservation, or a database-level
transaction across multiple skills. Apply supports one explicit skill at a
time and makes no network calls.

## Rollback

For a project-level install, restore the reviewed backup skill directory from
`.codex-skill-backups/` to:

```text
.agents/skills/<skill-name>/
```

For a direct user-level install, use the backup printed by the updater under
the installation root's `skill-backups/` directory and restore it to the exact
reviewed `skills/<skill-name>/` target.

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
