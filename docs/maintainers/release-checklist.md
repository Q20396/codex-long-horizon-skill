# Maintainer Release Checklist

Use this checklist before publishing v0.1.0.

- [ ] Release PR merged into `main`.
- [ ] Main CI passes.
- [ ] Working tree is clean.
- [ ] `.codex-plugin/plugin.json` version is `0.1.0`.
- [ ] README skill catalog is synchronized.
- [ ] Package checks pass.
- [ ] Routing contract passes.
- [ ] Fresh-install test passes.
- [ ] Plugin package validation passes.
- [ ] Internal links pass.
- [ ] Safety audit passes.
- [ ] No secrets or private data are present.
- [ ] Release notes reviewed.
- [ ] Fresh clone tested from `origin/main`.
- [ ] Codex CLI version and marketplace/plugin capabilities recorded.
- [ ] Isolated marketplace registration passes, and marketplace add failures are fatal.
- [ ] Actual plugin install passes when the installed CLI supports `codex plugin add`.
- [ ] Plugin list/discovery is verified when supported, or the limitation is recorded.
- [ ] Real `HOME` and `CODEX_HOME` are not modified by release smoke tests.
- [ ] `v0.1.0` tag does not already exist.
- [ ] GitHub Release is created only after all gates pass.

Suggested final checks:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
python3 scripts/test_fresh_install.py --require-codex-cli --verbose
python3 scripts/check_release_readiness.py --version 0.1.0
python3 scripts/full_skill_validation.py
```

If the installed CLI supports `codex plugin add`, also run:

```bash
python3 scripts/test_fresh_install.py --require-codex-cli --require-plugin-install --verbose
```
