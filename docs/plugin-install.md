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

Codex CLI capabilities vary by installed version. Current official
documentation describes marketplace add/list and plugin add/list commands, while
older installed CLIs may expose only marketplace add/upgrade/remove. Treat these
as capability differences: marketplace registration is not the same as actual
plugin installation.

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
python3 -m unittest discover -s tests -p "test_*.py"
python3 scripts/test_fresh_install.py --skip-codex-cli
```

The deterministic fresh-install test verifies package validation and direct
skill installation without requiring Codex CLI. To test the locally installed
Codex CLI as a pre-release gate, run:

```bash
python3 scripts/test_fresh_install.py --require-codex-cli --verbose
```

Add `--require-plugin-install` only when the installed CLI exposes
`codex plugin add`. All Codex CLI smoke tests use temporary `HOME`,
`CODEX_HOME`, and XDG paths, and must not modify your real Codex configuration.
