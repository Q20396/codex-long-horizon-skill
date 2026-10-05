# Phase 2C Governed Agent Runtime Integration Implementation Plan

> For agentic workers: use subagent-driven-development or executing-plans and test-driven-development. Independent approval belongs only to the three Design Authority designated reviewers.

**Goal:** Translate untrusted proposals to existing governed bindings without adding authority, capabilities, or an agent framework.

**Architecture:** A pure preparation stage returns deeply immutable existing ActionRequest/payload objects and separate proposal/prepared/material digests. A trusted host prebinds payloads before explicit execution. A small same-bridge reservation map closes concurrent and UNKNOWN equivalent-effect replay paths; reconciliation delegates to existing bindings.

**Tech Stack:** Python standard library; existing RSE, Security Authority, Security Chain, CET, Phase 2A and Phase 2B.

**Spec:** Design Authority Phase 2C IMPLEMENTATION EXECUTION DIRECTIVE v1.1, supplied 2026-10-05, sections 0–151 (operator attachment, not packaged).

## Global Constraints

- BASE_MAIN_SHA: cd061c1deb7ffb831825ef6c29f3338ee250f1ab.
- Branch: feat/agent-runtime-integration; isolated workspace only.
- NEW DEPENDENCIES = NONE. No capability classes added. No schema/hash canonicalization changes.
- Runtime modules remain agent-unaware; any compatibility fix requires documented necessity.
- No merge, Phase 3, observer, sandbox, daemon, provider SDK, release/deploy, real external-account tests or installed-skill update.
- Original checkout and its three historical-decision-mode untracked files remain untouched.
- LHE/Main implementation checks are not independent review evidence.
- No PR until three designated reviewers have final-SHA verdicts and no unresolved blocker; then require both CI gates and STOP.

## Task 1: Pure preparation and governed lifecycle

**Files:** Create `scripts/agent_runtime_integration.py` beneath the LHE skill and `tests/test_agent_runtime_integration.py`.

**Interfaces:** AgentActionProposal, PreparedAgentAction, AgentRuntimePrepareResult, AgentRuntimeExecutionResult, AgentRuntimeBridge.prepare/execute/reconcile. Consume existing RuntimePayload, RemoteRuntimePayload, ActionRequest, Authorization, bindings and CET context. Do not hold direct adapter dispatch tables.

- [ ] Read existing payload validators, binding execute/reconcile and RSE journal/policy semantics; reuse test fixtures.
- [ ] Write RED behavior tests before implementation, covering directive sections 85–126. Exercise real bindings with synthetic transports/temporary repositories; no external accounts.
- [ ] Capture RED: `python3 -m unittest discover -s tests -p 'test_agent_runtime_integration.py' -v`. Missing feature must be reported as missing feature, not a proven security exploit.
- [ ] Implement strict untrusted input validation, deeply frozen parameters, trusted identity/action allocation, action-specific lexical target normalization and separate digests.
- [ ] Implement immutable prepared validation and independently supplied prebound digest checks, trusted action-to-capability mapping, delegation through existing RSE bindings.
- [ ] Implement bounded same-process reservations across lookup/handoff; reserve before releasing lock, fail closed on uncertain exceptions, retain UNKNOWN until delegated reconciliation. Distinct effects remain independently governed. Reads do not inherit mutation suppression.
- [ ] Bind bounded causal proposal/prepared references to existing evidence without raw reasons, prompts, bodies or fabricated token metrics.
- [ ] Run targeted GREEN, Phase 2A/2B regressions and diff checks. Record exact commands and counts externally; commit only scoped task files after checking staged tree and parent.

## Task 2: Package and claims

**Files:** Create reference `agent-runtime-integration.md`, package test `tests/test_agent_runtime_integration_package.py`; update README, package-manifest.json, package checker and existing package/effect documentation only as required by repository conventions.

**Interfaces:** Uses Task 1 public API and immutable contracts; no runtime semantics changes.

- [ ] Add package behavior tests for CORE assembly/import inactivity and run RED.
- [ ] Declare inactive CORE placement, explicit construction, existing allowed effect routes and no auto-registration.
- [ ] Document actual API example and trust boundary, same-process/same-bridge/non-durable limits, no interception/sandbox claims. Use directive section 137 README wording.
- [ ] Run package GREEN, full validation and full repository suite. Keep optional pre-existing warnings separate from new warnings.

## Task 3: Independent final-SHA review and handoff

- [ ] Freeze implementation SHA. Send exact SHA, base, directive, bounded scope and evidence to Reviewer 2, Reviewer 3 and Reviewer 4 designated chats.
- [ ] Retrieve actual verdicts. Reproduce findings, RED then bounded correction, rerun tests and return new SHA for independent re-review. No majority override.
- [ ] After gates close, create `feat: add governed agent runtime integration` PR with section 146 body, attach it, observe check-skill/formal-schema-gate.
- [ ] Verify original worktree hashes and report using section 149. Do not merge.

## Acceptance, containment and recovery

Acceptance is the v1.1 sections 85–127 test matrix plus all regression/gate/reviewer requirements. Same-process reservations are not a second journal or cross-process proof. Pure prepare must not inspect filesystem/network/process state; real state checks remain downstream. Unexpected baseline movement before implementation, required new dependency, unauthorized scope expansion or unresolvable governance defect stops work. Containment: leave work on this isolated branch, never reset or alter original checkout. Rollback is not merging this branch.

## Progress

- Baseline fetched and verified exact before code changes.
- Native worktree tool returned `Not a git repository` for chat cwd; Git fallback created isolated worktree from the existing isolated repository, leaving original checkout untouched.
- Core implementation and task-scoped review complete at `5c2759c9c73db932a863ef0b5483049c06dc8024`; 40 targeted tests passed. Task review closed two recovery findings after RED/GREEN corrections. This is not designated independent approval.
- Package integration and task-scoped review complete at `e0a7880f3d73a29db3489d07c3d77e2e6584204b`. Full repository suite: 1133 tests, 1117 passed and 16 skipped. Full validation: PASS_WITH_WARNINGS (11 existing optional warnings). Formal lock metadata passed; local schema execution unavailable because locked dependencies are absent.
- Final-SHA designated reviews, PR and CI remain pending; no merge authorization.
