# Phase 2A implementation plan

## Authority and baseline

Design Authority's Phase 2A Implementation Execution Directive v1.1 approves
implementation, synthetic local-effect tests, independent review, PR and CI.
No merge or later phase is authorized. Base main:
`0f60bbb15833d20eaa8cfd3d3a09ba01e5c91f89`.
Branch: `feat/real-runtime-binding`; isolated workspace only.

## Architecture and constraints

One runtime binding orchestrates existing RSE, explicitly registered adapters,
adapter-observed CET and Security Chain. No second policy, authorization,
capability registry or durable journal. Trusted controller establishes immutable
payload digest before authorization; execute compares against that approval.
Only bounded regular-file operations, explicitly allowlisted processes and local
Git exact staging/commit. No network, remote Git, package installation, secret
store, service control, Paperclip or runtime hook adapters. No default activation.
Experimental same-process lifecycle, not host observation or an OS sandbox.

## Task 1 — implementation and RED → GREEN

Files: `runtime_binding.py` under skill scripts; `tests/test_runtime_binding.py`.

1. Read existing RSE/CET/chain APIs and use their existing governance contracts.
2. Write failing behavioral tests before implementation: real file read, denied
   execution, payload substitution, symlink escape, create-existing/write-missing,
   directory deletion, move escape, executable/shell denial, timeout UNKNOWN,
   non-inherited environment, exact Git staging and helper suppression.
3. Implement immutable bounded payload and one RSE entrypoint, then safe adapters.
4. Extend RED → GREEN for uncertainty/reconciliation, actual trace/divergence,
   chain privacy, concurrent replay protection, import inactivity and limits.
5. Run targeted suite. Use only synthetic temporary files/repos/process fixtures.

Validation: `python3 -m unittest tests.test_runtime_binding -v`.
Required evidence: initial expected failures, final passes, no unknown-effect retry.
Rollback: discard only this feature's reviewed changes; preserve user checkout.

## Task 2 — package and operator documentation

Files: skill `package-manifest.json`, `references/runtime-binding.md`, `README.md`,
and package-install coverage if needed.

1. Include inactive module/reference in Core without registering capabilities.
2. Document explicit roots, preapproval digest lifecycle and trust boundary.
3. State no-follow/platform requirements and bounded TOCTOU claims.
4. Document same-process UNKNOWN reconciliation, hidden child effects, Git helper
   controls, output limits and all remote/non-goals.
5. Validate assembled/install profiles and package checks.

## Task 3 — verification and independent review

Run targeted and existing RSE, chain, token, CET, checkpoint, Local Compute
regressions, full tests, package/doctor/catalog/description/safety/plugin checks,
profile assembly/update selfcheck/isolated install, formal tests and diff check.
Main cross-checks implementation, but is not an independent reviewer of 20396.
Commit exact reviewed files and send fixed HEAD to the three designated reviewer
chats. Retrieve actual reports, preserve disagreements; reproduce blockers with
RED regressions and request originating reviewer re-review at corrected HEAD.

## Task 4 — PR, CI, stop

Create `feat: add bounded real local runtime binding` PR with limitations and
non-goals. Require `check-skill` and `formal-schema-gate` PASS at final HEAD.
Return Design Authority's prescribed report. Do not merge or begin Phase 2B.

## Integration checks

Tasks 1 and 2 share only module/reference paths in package manifest. No edits to
existing RSE/CET/chain are planned. Existing tests must remain passing. Any need
to weaken governance or use non-synthetic real effects is a stop condition.
Review completion is not approval; approval is not merge authority.

## Bounded correction cycle — directive v1.2

The Design Authority authorizes two payload fields for the expected staged tree
and parent captured before authorization, not regenerated during execution.
The correction remains in this isolated worktree. The original checkout and its
three untracked files remain outside the write scope.

1. Capture failing real Git tests for post-authorization tree and parent mutation.
2. Bind expected tree and parent in the payload digest; verify them immediately
   before commit and verify the resulting commit object afterward.
3. Reject no-op, amend, merge and ambient operation/conflict states; validate
   repository object format without a SHA-1-only assumption.
4. Preserve and re-test the Reviewer 4 post-launch uncertainty correction.
5. Run targeted, existing security/Local Compute, full and package/formal checks.
6. Send the same final corrected SHA to designated Reviewers 2, 3 and 4. Reviewer
   3's read-only review is explicitly authorized by v1.2. Only originating
   independent review can close each finding; Main does not self-close them.
7. Create the PR only after all blockers close and regressions pass, wait for
   both required CI jobs, return the prescribed report and stop. No merge,
   C31509 merge-approval request, runtime remote effects or Phase 2B.

## Implementation evidence

- Clean baseline: 952 tests passed, 16 skipped, at the approved base tree.
- Initial runtime RED: 14 expected missing-implementation failures. Additional
  regressions exposed metadata symlinks, lost uncertainty evidence, default
  timeout and descriptor-cwd portability before their corrections.
- Runtime GREEN: 41 tests; Core isolated import/install: 2 tests. The runtime
  suite also passes with ResourceWarning treated as an error.
- Existing RSE/chain/token/CET/checkpoint/Local Compute regression: 227 passed.
- Package integration RED: missing effect declaration and two stale Core-count
  assertions/documents. Corrected without weakening checks; 16 related tests pass.
- Profile assembly: 16 passed; update selfcheck: 19 passed; fresh isolated direct
  install/update passed. Marketplace/Codex CLI operations explicitly skipped.
- Formal dependency-free tests: 75 run, 5 skipped. Lock check passes; controlled
  formal execution evidence must come from the required CI job, not this check.
- Full implementation regression: 995 tests passed, 16 skipped, after package
  integration corrections. Package/doctor/catalog/description/safety/plugin,
  routing fixtures, Python compilation and release-state consistency pass.
- These results are implementation evidence, not independent review or permission
  to merge. Designated reviewers must inspect the locked final commit.

## Correction evidence (supersedes the initial targeted count)

- Reviewer 4's post-launch status-read/selector/cleanup failures were reproduced
  as false known failures permitting a duplicate effect. The correction preserves
  UNKNOWN and blocks retry when target non-start cannot be proved.
- Reviewer 2 RED: both authorized-tree mutation and parent advance tests returned
  `COMPLETED` against the old implementation (two failed assertions). Adding the
  prebound fields and late comparisons made both pass.
- Further RED cases exposed no-op, ambient operation/unmerged-index state and
  post-commit object mismatch; the bounded checks make these regressions pass.
- A remove-all-staged-content RED returned `GIT_NOTHING_TO_COMMIT`; moving the
  no-op decision after tree comparison now returns `GIT_TREE_BINDING_MISMATCH`.
- Targeted implementation run: 61 passed (59 runtime plus 2 package), with
  ResourceWarning treated as an error. Real temporary SHA-256 repositories cover
  both initial and subsequent exact-parent commits; no SHA-256 skip was needed.
- Same-process serialization does not exclude concurrent external Git writers.
  `write-tree` may create local tree objects during validation; rejection means
  no commit invocation, not that Git performed no metadata writes at all.
- Final Main validation and the three designated independent verdicts are still
  required. No finding is closed by this implementation evidence alone.

## Reviewer 3 F1 bounded correction

- Reviewer 3 independently blocked ff41f5b: promisor lazy fetch could invoke a
  local upload helper during an object-read precheck, then return KNOWN_FAILURE.
- Main captured three RED failures: promisor configuration accepted, local
  transport allowed despite the local-only adapter contract, and precheck launch
  uncertainty misclassified. All three pass after the minimum correction.
- Reject promisor/uploadpack/receivepack configuration before object reads;
  all Git calls deny every transport through an empty allowlist and protocol
  policy. Lazy-fetch disabling is additional protection, not the sole guard.
- A real missing-object temporary fixture verifies no helper marker on initial
  execution or retry, including a direct object read below configuration checks.
- Preserve UNKNOWN and retry blocking for precheck launch uncertainty.
- Main targeted result: 65 tests OK with ResourceWarning treated as an error.
  Full/package/formal checks and independent final-SHA re-review remain gates.
