# Plugin Installation

This repository can be used in two ways:

- As a Codex plugin for reusable distribution.
- As direct skills copied into a project under `.agents/skills/`.

## Plugin Installation

**Published stable: v0.7.0.** The selector below targets its immutable release tag.
The v0.7.0 package includes Local Compute Orchestration (Beta); v0.6.0 does not.
Publication does not establish successful installation in a customer's Codex.

After a verified installation, locate the installed `long-horizon-engineering`
Skill root. Its `scripts/local_compute_deployment.py` and
`scripts/local_compute_pool.py` are the only implementation copies. For an
explicitly authorized Python caller, add that exact installed `scripts` path to
`sys.path` in the caller process, then import `local_compute_deployment` or
`local_compute_pool`. No clone, provider, model or new dependency is needed merely
to import these modules. A compatible existing Python 3.10+ runtime is required;
the POSIX journal also requires supported filesystem primitives.

Imports are inert. Invoking a probe needs exact node consent and an approved
read-only reader; invoking workers needs separate authorization and adapters.
Missing adapters are a stop condition, not permission to install a provider.
OpenAI-only remains the normal path. These APIs do not establish host Skill
discovery or model compliance; isolated package tests and real Codex discovery
are separate evidence.

The stable release-state contract names the immutable `v0.7.0` marketplace
reference and sets `policy.installation: AVAILABLE`:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref v0.7.0
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
