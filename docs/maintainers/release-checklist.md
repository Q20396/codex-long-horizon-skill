# Maintainer Release Checklist

Use this reusable checklist before publishing a release.

- [ ] Release PR merged into `main`.
- [ ] Main CI passes.
- [ ] Working tree is clean.
- [ ] `.codex-plugin/plugin.json` version matches the target release.
- [ ] README skill catalog is synchronized.
- [ ] Package checks pass.
- [ ] Routing contract passes.
- [ ] Safety audit passes.
- [ ] No secrets or private data are present.
- [ ] Release notes use neutral `Release` and `Date` metadata.
- [ ] Release notes contain no preparation markers.
- [ ] CHANGELOG has a dated version section.
- [ ] Routine CI uses `check_release_readiness.py --allow-existing-tag`.
- [ ] Final local pre-tag gate uses `check_release_readiness.py --pre-tag`.
- [ ] Remote tag absence is checked separately.
- [ ] GitHub Release absence is checked separately.
- [ ] Strict plugin-install result is recorded.
- [ ] Fresh `origin/main` commit is recorded.
- [ ] Annotated tag targets the exact validated commit.
- [ ] Annotated tag is pushed before GitHub Release creation.
- [ ] `gh release create --verify-tag` is used.
- [ ] Published Release is not draft.
- [ ] Published Release is not prerelease.
- [ ] Published Release body contains no stale preparation wording.
- [ ] Remote peeled tag target equals the validated release commit.
- [ ] Real user Codex binary, config, marketplaces, plugins, and auth state remain unchanged.

Suggested routine checks:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
python3 scripts/test_fresh_install.py --skip-codex-cli --verbose
python3 scripts/check_release_readiness.py --version <version> --allow-existing-tag
python3 scripts/full_skill_validation.py
```

Suggested final pre-tag checks:

```bash
python3 scripts/check_release_readiness.py --version <version> --pre-tag
python3 scripts/test_fresh_install.py --require-codex-cli --require-plugin-install --verbose
```
