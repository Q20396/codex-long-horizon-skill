# Remote Effect Binding Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the implementation task; designated independent reviewer chats supply the final review gates. Internal checks are not independent certification.

**Goal:** Bind three bounded remote effects to existing RSE authority, exact payload/destination commitments, conservative uncertainty and read-only reconciliation.

**Architecture:** Add a separate inactive remote module. Reuse RSE authorization, broker, journal, CET and Security Chain. Credentials remain opaque host transport state, never model payload or evidence.

**Tech Stack:** Python standard library, unittest, controlled synthetic transports and temporary Git repositories. No new dependencies.

**Spec:** User-supplied Phase 2B Implementation Execution Directive v1.1, sections 0–159 (operator input, not installed package).

## Global Constraints

- BASE_MAIN_SHA: `39b033db4de11059d10a5f4801d43f9928b78d3e` (freshly fetched).
- Branch: `feat/remote-effect-binding`; isolated `/tmp/20396-remote-effect-binding`.
- Only NETWORK_REQUEST, GIT_PUSH and PR_CREATE; no merge/update/release/deploy/install/SSH/secret discovery or later phase.
- No real external account mutation in tests. No secrets in payload, repr, receipts, CET, chain or exceptions.
- Immutable preauthorization digest covers every effect-relevant non-secret field; execution cannot approve itself.
- Exact HTTPS origins/endpoints; no redirect; normal TLS verification; request/response max 8 MiB, headers 64 KiB, timeout default 30 and maximum 120 seconds.
- Git exact fast-forward branch update binds URL, source/ref, old and new OIDs. Preserve Phase 2A transport restrictions.
- UNKNOWN blocks another mutation until reconciliation and a new trusted execution decision. Same-process only, not exactly-once or crash-durable.
- Same action at most one attempt; distinct actions independent. Reuse journal; no parallel ledger.
- Three designated final-SHA reviews before PR; any evidenced blocker stops PR. Never merge.
- Original checkout and its three unrelated untracked files remain unchanged.

## Task 1: Remote governed execution, adapters and behavioral tests

**Files:** Create `.agents/skills/long-horizon-engineering/scripts/remote_runtime_binding.py` and `tests/test_remote_runtime_binding.py`. A narrow compatibility-preserving change to `runtime_safety_envelope.py` and its tests is permitted only if needed for per-action concurrency; no new kernel/journal. Do not alter Phase 2A Git's protocol denial.

**Interfaces:** Produce `RemoteRuntimePayload`, `RemoteRuntimeBinding.execute`, `RemoteRuntimeBinding.reconcile`, `RemoteRuntimeResult`, `RemoteOperationEvidence`, `NetworkRequestAdapter`, `GitPushAdapter`, `PullRequestCreateAdapter`. Consume existing RSE/CET/chain interfaces. The approved-digest snapshot is trusted constructor input, not populated by execute. Transport methods accept immutable bound requests and bounded limits; trusted callbacks are explicitly outside model authority. Real HTTPS transport must be possible, with credentials host-supplied only. Test-only local transport exceptions live exclusively in test doubles, not production flags.

- [x] Read existing RSE evaluate/execute/reconcile, journal locking, Phase 2A chain/CET integration and Git config protections.
- [x] Write RED tests per directive 81–132. At minimum each following behavior must fail before implementation: destination/body substitution, network UNKNOWN, local/remote ref and URL drift, push UNKNOWN, PR duplicate-after-UNKNOWN. Use stateful synthetic providers rather than self-fulfilling mocks.

```python
# Representative acceptance shape: the real binding owns replay prevention.
first = binding.execute(action, payload, **authority)
second = binding.execute(action, payload, **authority)
assert first.receipt.execution_state == 'UNKNOWN_OUTCOME'
assert second.receipt.policy_reason == 'UNKNOWN_OUTCOME_PENDING'
assert provider.mutation_count == 1
```

- [x] Run `python3 -B -m unittest tests.test_remote_runtime_binding -v`; record named RED failures.
- [x] Implement minimal binding/HTTPS/PR/Git operations. Fixed reason codes; no raw exception serialization. Every real outbound readback also stays within preauthorized identity. Guard transport configuration before any send. Push must use explicit old-value protection AND independently prove fast-forward, not just default push behavior.
- [x] Rerun targeted tests to GREEN. Include actual temporary-bare-remote update through a test-only transport double, with production ref/destination checks in front of it.
- [x] Run Phase 2A + RSE + chain/CET regression and `git diff --check`; report evidence and any unsupported real transport behavior honestly.
- [x] Commit only explicit reviewed Task 1 paths; no push, PR or merge by worker.

Task 1 implementation evidence: 51 targeted tests; Phase 2A 63, RSE 52, chain 41,
CET 31, token 37, checkpoint 19 and Local Compute 47 tests passed. Eight initial
missing-implementation RED assertions were followed by semantic RED regressions
for port zero, response framing, identity, mixed-mode concurrency, response
observation, duplicate readback and exact remote-name handling. Tests use no real
external account mutations. These results do not replace independent review.

## Task 2: Package, documentation and regression

**Files:** Create `references/remote-runtime-binding.md` below the skill and `tests/test_remote_runtime_binding_package.py`; update `package-manifest.json`, package checker, README and package/effect documentation or count assertions only where required by new core files. No unrelated formatting.

**Interfaces:** Core-only installed module imports without operational side effects; adapter construction/registration is explicit. Document Task 1 actual signatures and readback contract, not aspirational capabilities.

- [x] Write installed-core import RED test with socket, subprocess, thread and discovery guards; fresh broker contains no remote capabilities.
- [x] Run `python3 -B -m unittest tests.test_remote_runtime_binding_package -v` and record RED.
- [x] Add two inactive core artifacts to manifest/checker. Explain trusted-host credential custody, exact URL/query handling, readback ambiguity, digest-only result channel, same-process lifecycle loss on crash and no exactly-once/network-sandbox claims.
- [x] GREEN package test; `python3 scripts/full_skill_validation.py`; `python3 scripts/validate_formal_schemas.py --check-lock`; `python3 -B -m unittest discover -s tests -p 'test_*.py' -q`; `git diff --check`.
- [x] Record exact test/skip/warning counts. Commit explicit paths and capture final SHA.

## Task 3: Independent review and PR handoff

**Files:** No source edits except bounded reviewer corrections with RED/GREEN and renewed final-SHA review.

- [ ] Send final SHA, worktree, spec, diff and test evidence to the three user-designated reviewer chats. Require role-specific verdict, evidence and final-SHA confirmation. Main is integrator, not independent reviewer.
- [ ] Reproduce blockers safely, correct narrowly, send corrected SHA to originating reviewer and refresh other affected approvals.
- [ ] Once all gates pass, push feature branch and create PR titled `feat: add bounded remote effect binding`, attach PR to chat, await check-skill and formal-schema-gate.
- [ ] Verify original three hashes unchanged; deliver directive section 157 report. MERGE NOT_PERFORMED; Phase 2C NOT_STARTED.

## Task 4: v1.2 bounded recovery-evidence correction

**Authority:** Design Authority Execution Directive v1.2, sections 0–45.
Correction baseline: `7f8cb1bfa3810e60d80cbb802fbda3d68b4b46b5`.
Base main and branch remain unchanged. This supersedes Task 3's review handoff
only as expressly described below; it does not authorize merge or Phase 2C.

**Observed issue:** Reviewer 4 independently reproduced an HTTP 200 PR readback
whose malformed body became `STILL_UNKNOWN` with false no-response evidence.
The existing duplicate-create gate held. Reviewer 2 approved the baseline;
Reviewer 3 did not complete because of a platform restriction. Neither tests nor
Main can replace the missing independent verdict.

**Owned scope:** remote module, its behavioral tests and bounded reference
documentation. No new capabilities, dependency, recovery framework, journal,
secret store, SSH, host observer or Security Chain schema change.

- [x] Reproduce malformed-200 recovery evidence with RED assertions; cover no
  response, valid exact match, ambiguity, non-2xx and oversized/truncated bodies.
- [x] Preserve observed status monotonically, distinguish complete body evidence
  from incomplete/no body, and distinguish parse failure from no response.
  Retain only bounded digest/status metadata; preserve UNKNOWN and no second
  create. Document evidence semantics without strengthening runtime claims.
- [x] Targeted GREEN, all relevant regressions, full suite, package checks and
  local formal schema/lock checks. Keep generated test logs outside the source
  tree; do not weaken absolute-source-path validation.
- [ ] Commit bounded correction, freeze final SHA, and obtain Reviewer 4 closure,
  Reviewer 3 read-only static security verdict, and Reviewer 2 freshness review.
  An entire-review platform block again means STOP, with no workaround or
  substitute reviewer. Restricted probes are not PASS.
- [ ] Only if all same-SHA review and validation gates close, create the approved
  PR and require check-skill plus formal-schema-gate. Do not merge.

Containment: retain the isolated branch and evidence on failure. Do not alter the
original checkout or its three unrelated untracked files. A correction remains
open until its originating reviewer independently closes it.

Correction implementation: `ce99ef4f2caa7cebe661a90d4ae61259a08f259c` changes
exactly the three owned paths. RED: 11 tests, 13 assertion failures; GREEN:
11 recovery tests and 64 remote/package tests (62 + 2). Relevant regressions:
Phase 2A 65, RSE 52, Security Chain 41, token 37, CET 31, checkpoints 19,
Local Compute 47; each passed with zero skips.

Main validation: full suite 1081 total, 1065 passed, 16 skipped; exit 0.
Full package validation exited 0, required checks PASS, 11 unchanged optional
warnings; no failures. Local schema/lock check PASS (32 schemas, 6 locked
distributions), with formal engine execution still PENDING, not CI proof.
Logs and correction report remain outside the worktree. Original checkout and
three untracked-file hashes were rechecked unchanged. Independent final-SHA
reviews, P2 closure, PR and CI remain pending; no merge or Phase 2C.

## Task 5: v1.3 Git ancestry integrity correction

**Authority:** Design Authority Execution Directive v1.3, sections 0–40.
Starting HEAD: `8cfbcb75104576390eaa6e25f487a388ca2170d0`.
At that SHA Reviewer 4 closed P2, Reviewer 2 approved minimality, and Reviewer 3
completed static review with F1/P1 BLOCK: legacy graft ancestry was not excluded.

**Scope:** Only Git push ancestry integrity. Prefer remote module, remote tests,
and remote reference documentation. A small shared Git helper change is allowed
only if needed to enforce this boundary without changing unrelated behavior;
add focused regression coverage for any shared change. Main owns this plan.
No new capabilities, dependencies, graph framework, force/SSH, retry/durability,
provider layer, schema expansion, real account tests, merge or Phase 2C.

- [x] Write and observe RED graft/replace rejection tests with synthetic temp
  repositories, no external endpoint. Preserve a fixture using actual unrelated
  commit objects; demonstrate vulnerable interpretation only if practical.
- [x] Fail closed on non-empty or malformed `.git/info/grafts` and any replace
  namespace entry, including packed refs. Empty graft file may safely pass and
  that rule must be tested and documented. Reject before ancestry/pack/mutation;
  retain existing pre-send recheck, old/local OID and URL binding.
- [x] Verify security-critical Git commands retain `GIT_NO_REPLACE_OBJECTS=1`
  and clean environment/configuration; do not rely on that variable alone.
  Test normal true fast-forward success and real non-fast-forward denial,
  no mutation on rejection, remote unchanged, bounded reason/no raw metadata.
- [x] Run targeted GREEN (baseline 64), Phase 2A, RSE, chain, token, CET,
  checkpoints, Local Compute, full suite (baseline 1081/1065/16), package and
  local formal checks. Keep generated evidence outside worktree.
- [ ] Commit scoped correction and final plan, freeze final SHA. Reviewer 3
  independently closes F1; Reviewer 2 checks minimality and Reviewer 4 checks
  P2/UNKNOWN freshness. All three actual verdicts must apply to that SHA.
- [ ] Only after all gates close, push feature branch, create the approved PR,
  attach it and await check-skill and formal-schema-gate. Never merge.

Containment: preserve original checkout and three untracked files. Retain
isolated branch/evidence on blockers; do not self-close independent findings.
Any newly required capability or unrelated fix returns to Design Authority.

Task 5 implementation: `3bbd7ad3ea03087ab853c58ddb06899be9ff98cb` changes
only the remote module, its behavioral tests and reference. Shared Phase 2A
helper and all schemas remain unchanged. Accepted RED: 10 tests, 11 expected
assertion failures, zero errors; genuine unrelated root commits reproduce the
graft interpretation bypass. GREEN: 10 focused tests, 74 remote/package tests
(72 + 2), zero skips. The real launcher boundary verifies replacement disabling
and exclusion of ambient graft/config injection. Empty regular graft files are
allowed; malformed/nonempty grafts and loose/packed replacement refs are denied.

Main's relevant regressions: Phase 2A 65, RSE 52, Security Chain 41, token 37,
CET 31, checkpoints 19, Local Compute 47; all PASS with no skips. Full suite:
1091 total, 1075 passed, 16 unchanged skips; exit 0. Full package validation:
required checks PASS, 11 unchanged optional warnings, no failures; exit 0.
Local formal schema/lock check: PASS, 32 schemas and 6 locked distributions;
formal engine execution remains PENDING until separately evidenced by CI.
No real external-account mutation, installation into user skills, merge or
Phase 2C. Generated validation logs remain outside the worktree.

Original checkout and all three untracked-file hashes remain unchanged. This
record does not close F1: final frozen-SHA Reviewer 3 closure, Reviewer 2/4
freshness, then gated PR and CI are still required. Independent review results
will be recorded outside the frozen source tree to avoid stale approvals.
