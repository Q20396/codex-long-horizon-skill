# Plugin Installation

This repository can be used in two ways:

- As a Codex plugin for reusable distribution.
- As direct skills copied into a project under `.agents/skills/`.

## Plugin Installation

Add this repository as a marketplace:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
```

Refresh the marketplace after updates:

```bash
codex plugin marketplace upgrade codex-long-horizon-skills
```

Remove the marketplace when you no longer want it:

```bash
codex plugin marketplace remove codex-long-horizon-skills
```

The current CLI exposes `marketplace add`, `marketplace upgrade`, and
`marketplace remove`. It does not expose a `marketplace list` command in the
tested CLI version, so use Codex's plugin UI or the marketplace file to verify
configuration when list output is unavailable.

After adding or upgrading the marketplace, restart Codex if the plugin or skills
do not appear immediately.

Verify that both skills are available:

- `long-horizon-engineering`
- `ai-video-production`

## Direct Skill Installation

For repository-scoped use, copy the skills into a target project:

```text
<project>/.agents/skills/long-horizon-engineering/
<project>/.agents/skills/ai-video-production/
```

For user-scoped use, if supported by your Codex surface, install them under:

```text
$HOME/.agents/skills/
```

Direct installation is useful while authoring or testing a skill in one
repository. Plugin installation is preferred when sharing reusable skills across
projects.

## Verification

From this repository, run:

```bash
python3 scripts/validate_plugin_package.py
python3 scripts/test_fresh_install.py
```

The fresh-install test uses temporary directories and does not modify your real
home directory.
