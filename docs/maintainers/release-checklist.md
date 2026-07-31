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
- [ ] Release notes report schema coverage from the formal validator inventory;
      no separate hand-maintained manifest is treated as authoritative.
- [ ] Confirm the current inventory is 23 schemas: 7 fixture-validated and 16
      syntax-only. The local capability catalog and local case provider have
      dependency-free synthetic contracts but remain syntax-only in the formal
      gate.
- [ ] An unreleased candidate keeps marketplace
      `policy.installation: NOT_AVAILABLE` and is never rewritten beneath an
      existing tag. A stable state uses a new version and a separately reviewed
      release-state change after the applicable immutable-candidate and
      isolated marketplace-resolution evidence.
- [ ] A final release-state change uses one exact coherent contract:
      marketplace `AVAILABLE`, both Skill channels `stable`, release manifests
      `channel: stable`, `released: true`, and `risk: reviewed`.
- [ ] `--pre-tag-static` rejects the final release state. Static final-state
      consistency may be checked with `--allow-existing-tag --release-state
      final`, but that result alone is explicitly not release-ready.
- [ ] The content-frozen final release-state candidate reruns the controlled
      formal gate with `--release-state final` before its tag is created.
- [ ] The formal result binds the exact candidate commit, tree, base,
      merge-base, parents, changed paths, diff, schema inventory, and six
      installed wheel filenames/hashes.
- [ ] The final content-frozen release candidate produces its own formal result;
      an earlier PR, `main`, or job-local receipt is not reused.
- [ ] Local release preparation uses a clean linked worktree based on the
      recorded full `origin/main` commit.
- [ ] Full validation reports every optional omission and its scoped waiver
      rationale; the current registry contains exactly 11 known omissions and
      any new or changed warning fails the release warning gate.
- [ ] Routine post-release CI uses `check_release_readiness.py
      --allow-existing-tag --release-state final`.
- [ ] Final Phase B pre-tag gate uses `check_release_readiness.py --pre-tag
      --release-state final`.
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
python3 scripts/check_release_readiness.py --version <version> --pre-tag-static \
  --release-hygiene-base <full-origin-main-commit>
python3 scripts/check_release_readiness.py --version <version> \
  --release-state final --allow-existing-tag
python3 scripts/full_skill_validation.py
```

Suggested Phase B checks after separate dependency and network authorization:

```bash
python3 scripts/validate_formal_schemas.py --check-lock
python3 scripts/validate_formal_schemas.py --verify-acquisition \
  --candidate-base <full-base-commit> \
  --pip-report "$RUNNER_TEMP/formal-schema-pip-report.json" \
  --evidence-dir "$RUNNER_TEMP/formal-schema-evidence" \
  --result "$RUNNER_TEMP/formal-schema-evidence/acquisition-receipt.json"
"$RUNNER_TEMP/lhe-formal-schema-venv/bin/python" \
  scripts/check_release_readiness.py --version <version> --pre-tag \
  --release-state final \
  --formal-schema-candidate-base <full-base-commit> \
  --formal-schema-pip-report "$RUNNER_TEMP/formal-schema-pip-report.json" \
  --formal-schema-acquisition-result "$RUNNER_TEMP/formal-schema-evidence/acquisition-receipt.json" \
  --formal-schema-evidence-dir "$RUNNER_TEMP/formal-schema-evidence" \
  --formal-schema-result "$RUNNER_TEMP/formal-schema-result.json"
```

`--formal-schema-result` is a new output path, not a trusted input receipt.
The CI job performs one approved online acquisition into a fresh temporary
evidence directory. Release readiness invokes the formal validator directly
after that phase; the validator consumes the same raw evidence, acquisition
receipt, and real pip report offline and binds their hashes to its output. It
must not issue a second live acquisition. Routine PR/main CI uses
`--allow-existing-tag` with those candidate-local inputs; only a separately
approved release-candidate invocation uses `--pre-tag` and enforces tag absence.

The fixed bootstrap identity records the reviewed origin of the lock, validator,
and gate definition only. It is provenance evidence, not an expected parent or
path allowlist for later pull requests and grants no approval authority.
Every descendant run receives its own immutable base commit and recomputes the
candidate commit, tree, parents, merge-base, clean state, changed-path
inventory, binary diff hash, and schema inventory. The acquisition receipt and
formal result must bind that complete current identity. A receipt from an older
candidate, another base, another job run, or a different schema inventory
cannot be reused.

The formal invocation must start and finish with a clean candidate worktree.
Any staged, unstaged, or untracked path blocks the gate. Pip report artifact
URLs must use HTTPS on `files.pythonhosted.org` with no userinfo, query,
fragment, direct/VCS marker, or nonstandard port.

Job-local receipts are deterministic evidence records, not cryptographic
signatures or source-to-wheel provenance. They never authorize tagging,
release, Marketplace resolution, installation, or runtime effects.

## GitHub Actions pin evidence

Release workflows pin third-party Actions to immutable full commit SHAs:

- `actions/checkout`: `11d5960a326750d5838078e36cf38b85af677262`
- `actions/setup-python`: `a26af69be951a213d495a4c3e4e4022e16d87065`

The current pins are recoverable from local reviewed repository commit
`20be877a16bf41e3817c8d173aa58053adc02cdc`, whose parent is the current
candidate base `dfa529d705c34ea61b88a607073cc49ce5241735`. Official-source
verification completed on 2026-07-30 and recorded these immutable identities:

- [`actions/checkout@11d5960...`](https://github.com/actions/checkout/commit/11d5960a326750d5838078e36cf38b85af677262)
  is the GitHub-verified commit for
  [release `v4.4.0`](https://github.com/actions/checkout/releases/tag/v4.4.0);
  its fixed-commit `action.yml` blob is
  `24e73e5a12126edc2adb9e5cd1bf245ce85bde56`, and its MIT `LICENSE` blob is
  `a67dca8b4f65d6bd351f6b1e333ce2cd84d843a5`.
- [`actions/setup-python@a26af69...`](https://github.com/actions/setup-python/commit/a26af69be951a213d495a4c3e4e4022e16d87065)
  is the GitHub-verified commit for
  [release `v5.6.0`](https://github.com/actions/setup-python/releases/tag/v5.6.0);
  its fixed-commit `action.yml` blob is
  `efa8de904209196588db1453bdb44079b3c393d7`, and its MIT `LICENSE` blob is
  `a426ef259d6c5d705e9c1405075c3b318093c65e`.

At that check time, each official repository's GitHub security-advisories API
returned an empty list. That is a dated observation, not proof that the Actions
are vulnerability-free or that their transitive runtime artifacts are
reproducible.

An update requires a dedicated review that resolves the intended upstream
release from the official Action repository, records the exact replacement
commit and license/security evidence, reviews the diff from the current pin,
and reruns both workflow contract tests and the full package checks. Major tags
such as `@v4` or `@v5` are documentation hints only and are not accepted in the
executable workflow.

Marketplace/CLI resolution, plugin installation, tagging, GitHub Release
creation, and installed Skill updates remain separate approval stages.
