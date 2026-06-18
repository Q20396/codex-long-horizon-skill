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
- [ ] Optional live Codex install tested, or limitation recorded.
- [ ] `v0.1.0` tag does not already exist.
- [ ] GitHub Release is created only after all gates pass.

Suggested final checks:

```bash
python3 scripts/test_fresh_install.py
python3 scripts/check_release_readiness.py --version 0.1.0
python3 scripts/full_skill_validation.py
```
