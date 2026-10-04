# Signed Checkpoints Implementation Plan

> Execute inline: tightly coupled security contracts. Independent final review belongs only to the three Design Authority designated chats, not internal self-checks.

**Goal:** Verify security-chain prefixes against host-verified signatures and caller-retained external anchors without key custody or network adapters.
**Spec:** Design Authority Phase 1.75 directive, sections 0–153, and approved design choices in this chat.
**Base:** dc671fd2fa7d68e0aeccc406179a898d5d274f64
**Architecture:** One inactive stdlib module with immutable artifacts, canonical JSON, closed algorithms and structured fail-closed results. Snapshot chain records once and use existing structural verification; no chain format changes. Extend management actions only for creation/publication.

## Global constraints

- No new dependencies, home-grown cryptography, private-key storage, real publication adapters, runtime binding or host observer.
- Reject empty chain; strictly increasing checkpoint sequence; non-decreasing caller time.
- Verify signer output before returning a signed checkpoint; host verifier binds algorithm and key identity.
- Unknown publication is never automatically retried. Reader reconciliation uses the same request identity.
- Preserve original checkout and its three untracked files. No merge.

## Tasks

- [x] Baseline: 933 tests, 16 skips, no failures (106.938s).
- [x] RED: initial 14 tests fail because signed checkpoint implementation is absent.
- [x] GREEN: scripts/signed_checkpoints.py supplies immutable SignatureEnvelope/SignedCheckpoint/ExternalAnchor, verifier protocols, creation/verification/history helpers and bounded anchor publication/readback contracts. security_authority_chain.py gains CHECKPOINT_CREATE and ANCHOR_PUBLISH with installation-level guards only.
- [x] Contract coverage: 19 tests pass, including additional negative history, malformed adapter, invalid chain and import-side-effect checks. Fake signers prove no real algorithm.
- [x] Package/docs: core manifest/checker entries, effect inventory, README and signed-checkpoints.md operator walkthrough; update exact core count assertions.
- [ ] Regression: targeted, RSE, chain, token, CET, Local Compute, full suite, package/doctor/catalog/audits/plugin/profile/update/fresh install/formal checks and diff check.
- [ ] Commit final candidate and dispatch exact SHA to Reviewer 2/3/4; reproduce any blockers with failing tests and return fixed SHA to originating reviewer.
- [ ] Push branch, create PR, attach it, wait for both required CI checks. Return actual review findings and limitations, never merge.

## Verification examples

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_signed_checkpoints -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
git diff --check
```

Expected attacks: a valid shorter chain returns CHECKPOINT_AHEAD_OF_CHAIN; an internally rebuilt chain returns CHAIN_DIVERGENCE; a valid extension retains prefix validity. All signatures in unit tests are explicitly fake contract fixtures, not algorithm validation.

Rollback: leave the isolated feature branch unmerged. Stop for new dependency requirements, unauthorized external effects or unresolved security blockers.

Initial validation: 227 targeted/regression tests passed (19 checkpoint, 52 RSE,
41 authority/chain, 37 token, 31 CET, 47 Local Compute). Package checker, doctor,
catalog, descriptions, safety audit, plugin validation, profile tests (16),
update tests (19), trigger tests (66), isolated fresh install and diff check pass.
Local formal tests: 75, 5 skipped; exact-wheel controlled evidence awaits CI.
Independent review and CI are separate gates; these are implementation evidence only.
