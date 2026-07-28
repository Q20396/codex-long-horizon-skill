# Maintainer Release Checklist

Use this reusable checklist across the local static-candidate and later release
stages. Completing Phase A does not establish release readiness.

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
- [ ] Phase A uses `check_release_readiness.py --pre-tag-static`.
- [ ] Phase A records formal Draft 2020-12 validation as UNVERIFIED.
- [ ] No `requirements-release.txt` or release dependency is created or
      installed during Phase A.
- [ ] Phase B dependency intake is separately approved and records exact
      versions and hashes before formal schema validation.
- [ ] `requirements-release.txt` contains only the six reviewed distributions,
      exact pins and hashes, `--only-binary=:all:`, and `--require-hashes`.
- [ ] The Phase B job uses `ubuntu-24.04`, CPython 3.11 x64, an ephemeral venv,
      `permissions: contents: read`, and checkout without persisted credentials.
- [ ] PyPI yanked state, wheel hash, license, dependency metadata, Trusted
      Publisher attestation, source tag/license blob, and OSV status are
      rechecked before each intake.
- [ ] The `rpds-py` native wheel exception and missing source-to-wheel SLSA
      provenance remain recorded limitations.
- [ ] Dependency-free fallback and formal Draft 2020-12 results are reported
      separately; neither result substitutes for the other.
- [ ] The formal result binds the exact candidate commit/tree and six installed
      wheel filenames/hashes.
- [ ] Routine post-release CI uses `check_release_readiness.py --allow-existing-tag`.
- [ ] Final Phase B pre-tag gate uses `check_release_readiness.py --pre-tag`.
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
python3 scripts/check_release_readiness.py --version <version> --pre-tag-static
python3 scripts/full_skill_validation.py
```

Suggested Phase B checks after separate dependency and network authorization:

```bash
python3 scripts/validate_formal_schemas.py --check-lock
python3 scripts/validate_formal_schemas.py --verify-acquisition \
  --result "$RUNNER_TEMP/formal-schema-acquisition.json"
"$RUNNER_TEMP/lhe-formal-schema-venv/bin/python" \
  scripts/check_release_readiness.py --version <version> --pre-tag \
  --formal-schema-pip-report "$RUNNER_TEMP/formal-schema-pip-report.json" \
  --formal-schema-acquisition-result "$RUNNER_TEMP/formal-schema-acquisition.json" \
  --formal-schema-result "$RUNNER_TEMP/formal-schema-result.json"
```

`--formal-schema-result` is a new output path, not a trusted input receipt.
Release readiness invokes the formal validator directly, which rechecks the
acquisition receipt against the approved live sources and binds both input
hashes to its output. Routine PR/main CI uses `--allow-existing-tag` with the
same formal inputs; only a separately approved release-candidate invocation
uses `--pre-tag` and enforces tag absence.

The formal invocation must start and finish with a clean candidate worktree.
Any staged, unstaged, or untracked path blocks the gate. Pip report artifact
URLs must use HTTPS on `files.pythonhosted.org` with no userinfo, query,
fragment, direct/VCS marker, or nonstandard port.

Marketplace/CLI resolution, plugin installation, tagging, GitHub Release
creation, and installed Skill updates remain separate approval stages.
