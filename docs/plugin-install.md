# Plugin Installation

This repository can be used in two ways:

- As a Codex plugin for reusable distribution.
- As direct skills copied into a project under `.agents/skills/`.

## Plugin Installation

The stable release-state contract names the immutable `v0.5.0` marketplace
reference and sets `policy.installation: AVAILABLE`:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref v0.5.0
```

Before running it, verify the remote annotated tag and peeled commit/tree, the
candidate-bound formal result, published GitHub Release, and isolated
marketplace resolution. Repository metadata alone is not that evidence. Use
`--ref main` only for intentionally mutable repository state:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
```

Do not assume `marketplace upgrade` changes a pinned ref. A stable upgrade must
explicitly rebind registration to the newly reviewed immutable tag in a
separately approved isolated CLI workflow. Actual CLI rebind behavior is
not inferred from static metadata.

Refresh only an intentionally mutable marketplace after updates:

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

For a direct Codex user-level installation, use the canonical Codex skills
directory:

```text
$HOME/.codex/skills/
```

Do not treat `$HOME/.agents/skills/` as the current Codex user-level default.
That legacy/project-style layout is supported only where a caller explicitly
selects it.

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
