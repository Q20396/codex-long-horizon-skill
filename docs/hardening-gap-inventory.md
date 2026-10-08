# H0 — Hardening Gap Inventory & Prioritization

20396 Dedicated Hardening Program. Audit baseline:
`31d69d9067a28de92cbb23f069239b69147f6476` (2026-10-08).
Architecture phases 1–5 are complete; production hardening is NOT_COMPLETE.
This is an inventory and proposed sequence, not authorization to implement H1.
Main coordinates this audit; neither Main nor a 20396 self-check is independent
review evidence. Reviewer 2/3/4 approvals and CI must bind the final H0 SHA.

This single repository document is intentionally outside the installed package.
`check_skill_package.py:load_package_contract` requires the manifest's legacy
file set to equal its hard-coded installed-file contract. Adding a packaged
reference would require checker changes; H0 changes no production/test code,
package contract, dependency, or lock. This follows the existing repository-only
`docs/end-to-end-security-runtime.md` convention.

## Evidence scope and interpretation

Below, `S/` means `.agents/skills/long-horizon-engineering/scripts/`, `R/` means
the adjacent `references/`, and `T/` means repository `tests/`. Symbol/test names
are baseline locators, not mutable line-number assertions. Evidence is current
source, tests, reference documents, package metadata and workflow definitions.
Historical phase statements do not override merged code.

PASS means only the named bounded check, never production readiness. BETA means
partial implementation or missing target validation. UNKNOWN is missing evidence,
not success or zero. NOT_IMPLEMENTED describes absent capability; NOT_RUN describes
an unperformed validation. Qualifiers identify scope rather than new verdicts.

Priority: P0 = material trust/security correctness gap capable of undermining core
claims; P1 = important reliability/durability/real-world trust; P2 = platform or
operational completeness; P3 = performance/UX/optional expansion. These are future
hardening priorities, not vulnerability scores or demonstrated exploit claims.

## Ranked top five

| Rank | Current fact and consequence | Why above the next item | Next stage |
| --- | --- | --- | --- |
| 1 | Core action journal, local pre-effect evidence and bridge reservations are in memory. Reconstructed controllers lose UNKNOWN_OUTCOME / RECONCILIATION_REQUIRED retry barriers; a surviving chain alone cannot restore them. | Restart is sufficient to lose the guard even without concurrent controllers; durable state is prerequisite to reliable coordination. | H1 |
| 2 | Core locks/reservations/dedupe are object/process scoped. A second controller can independently pass those guards. | This bypasses an existing safety boundary, whereas the next issue concerns strengthening explicitly bounded evidence. | H2 |
| 3 | Phase 5 process reality uses the same RuntimeBinding wait/reap provenance as adapter evidence; it proves EXITED/0, not independent effects or image identity. | Correlated evidence can limit assurance about the effect itself; signing such evidence cannot make it independently true. | H3 |
| 4 | Checkpoint APIs have injected signer/verifier contracts; FakeSigner/FakeVerifier tests do not establish real cryptography, key custody or trusted identity. | Real cryptography and operational trust are prerequisites for meaningful deployment of the next item's trusted anchors. | H4 |
| 5 | External publication/readback contracts exist, but no production adapter or independently retained trusted anchor is supplied. | Whole-history replacement cannot be excluded locally. This precedes broader real-account interoperability testing; anchoring still does not prove effects. | H5 |

The initial H1/H2 order is retained. Independent reality moves from the initial
H5 hypothesis to H3; signer/anchor move to H4/H5. This ranks truth provenance before
attesting it, without claiming a technical dependency of signing on sensors.
H6 real-account tests remain essential before production remote claims. They do
not replace restart, coordination, reality or trust work.

## Material gap records

### G01

- area: Core execution/reconciliation durability.
- current_state: NOT_IMPLEMENTED — NO_CRASH_DURABILITY for core retry guards.
- evidence: `S/runtime_safety_envelope.py:InMemorySecurityJournal`, `evaluate_and_execute`; `S/runtime_binding.py:RuntimeBinding._evidence`, `execute`, `reconcile`; `S/remote_runtime_binding.py:RemoteRuntimeBinding`; `S/agent_runtime_integration.py:AgentRuntimeBridge._pending/_lifecycles`; corresponding R/ documents.
- risk_if_unfixed: Restart/new objects discard action states, local original evidence, material reservations and lifecycle pins; UNKNOWN_OUTCOME and RECONCILIATION_REQUIRED cannot be assumed to survive. Old chain records are evidence, not an implemented recovery algorithm. Re-proposal after state loss may reach another effect; no crash exploit was run in H0.
- hardening_goal: Recover unresolved decisions and their required evidence without blind retry, including failures between effect and recording.
- priority: P0.
- recommended_hardening_stage: H1.
- explicit_non_goal: Distributed exactly-once execution; automatically retrying ambiguous effects.

### G02

- area: Core cross-process coordination.
- current_state: BETA — bounded H2 implementation under validation; legacy modes remain SAME_PROCESS_ONLY. H2 acceptance is not COMPLETE.
- evidence: `S/runtime_safety_envelope.py:CrossProcessOwner`, coordinated journal; `S/agent_runtime_integration.py:AgentRuntimeBridge`; coordinated `S/host_observer.py:HostObservationIngestor` and `S/security_authority_chain.py:JsonlSecurityChain`; `T/test_cross_process_coordination.py`; `docs/h2-cross-process-coordination.md`. Actual Darwin/APFS multiprocess evidence is distinct from pending Linux CI and independent review.
- risk_if_unfixed: A second journal/bridge/ingestor instance, including a second process, has independent guards. Concurrent JSONL controllers can read the same head before appending; per-instance locks are not a shared writer protocol. Same-material suppression, action serialization, host dedupe and chain sequencing are not globally enforced.
- hardening_goal: Establish single authoritative ownership/coordination for the protected state across controllers.
- priority: P0.
- recommended_hardening_stage: H2, after H1.
- explicit_non_goal: Cluster scheduling, distributed consensus or hostile-controller containment.

### G03

- area: Host observation restart continuity.
- current_state: PARTIALLY_IMPLEMENTED — H2 preserves consumed session/observation claims and forces explicit new-session gaps; native continuity and durable trace recovery remain NOT_IMPLEMENTED.
- evidence: coordinated `S/host_observer.py:HostObservationIngestor`, existing-chain SECURITY_ALERT claims, and fresh-interpreter handoff tests in `T/test_cross_process_coordination.py`; `S/host_observer_macos.py:MacOSExecObserver._registered/_sequence` and `R/host-observer.md` limits remain unchanged. See `docs/h2-cross-process-coordination.md` for the remaining G03 boundary.
- risk_if_unfixed: Restart loses duplicate IDs, per-session sequence/gap history, sticky failure latch and native registrations. Retained chain records do not automatically reconstruct ingestion state; continuity cannot be asserted across the gap. Ingestion also writes chain then trace, not a durable atomic transaction across both.
- hardening_goal: Preserve trustworthy restart/gap semantics before asserting continued observation.
- priority: P1.
- recommended_hardening_stage: H1 recovery semantics, H2 controller ownership.
- explicit_non_goal: New event classes or a background observer service.

### G04

- area: Security-chain storage and whole-history protection.
- current_state: BETA — single-controller hash-linked/tamper-evident storage; complete crash guarantees UNKNOWN.
- evidence: `S/security_authority_chain.py:JsonlSecurityChain` creates/appends with flush/fsync, validates bounded canonical records and blocks an uncertain instance; constructor resets the in-memory uncertainty latch. `R/security-authority-chain.md`; `T/test_security_authority_chain.py`.
- risk_if_unfixed: Fsync of a file is not an established end-to-end action/chain recovery protocol or proof of power-loss durability. Partial invalid records fail closed; a valid surviving prefix still does not restore action state. Local whole-file deletion/replacement remains within host/storage trust, and no independently retained latest head is guaranteed.
- hardening_goal: State and validate storage/recovery guarantees, then bind retained history to independently trusted checkpoints/anchors.
- priority: P1.
- recommended_hardening_stage: H1 storage recovery; H4/H5 whole-history trust.
- explicit_non_goal: Calling a hash-linked local file tamper-proof or universally append-only against its owner.

### G05

- area: Independent process target reality.
- current_state: NOT_IMPLEMENTED — NO_INDEPENDENT_REALITY_SENSOR; bounded wait/reap evidence exists.
- evidence: `docs/end-to-end-security-runtime.md` Distinct evidence and normalization; `T/test_end_to_end_security_runtime.py`; `S/runtime_binding.py:_capture_started`; `S/cross_layer_verification.py:_compare`.
- risk_if_unfixed: Adapter/result agreement shares one provenance. EXITED/0 with a bound payload is not executed-image identity, proof of all child side effects, or an independent hostile-host sensor. ProcessAdapter has no reconciler; uncertain outcomes remain unknown.
- hardening_goal: Establish independently sourced, explicitly bounded target facts before stronger cross-layer assurance claims.
- priority: P1.
- recommended_hardening_stage: H3.
- explicit_non_goal: Turning every MATCH into a security verdict, universal side-effect verification or a new enforcement layer.

### G06

- area: Real checkpoint cryptography.
- current_state: NOT_IMPLEMENTED for supplied production signer/verifier integration — TEST_CONTRACT_ONLY validation.
- evidence: `S/signed_checkpoints.py:CheckpointSigner`, `CheckpointVerifier`, `create_checkpoint`, `verify_checkpoint`; `R/signed-checkpoints.md`; `T/test_signed_checkpoints.py` FakeSigner/FakeVerifier reused by Phase 5.
- risk_if_unfixed: Algorithm identifiers and injected valid results establish API contracts, not cryptographic math/security. Exact-message fake lookup cannot support a real-signature deployment claim.
- hardening_goal: Validate an actual cryptographic implementation under the existing bounded checkpoint contract.
- priority: P1.
- recommended_hardening_stage: H4.
- explicit_non_goal: Inventing a cryptographic algorithm or broad PKI framework.

### G07

- area: Signer identity and production key lifecycle.
- current_state: UNKNOWN trusted deployment identity; operational key management NOT_IMPLEMENTED.
- evidence: `R/signed-checkpoints.md` host trust/key limitations; injected verifier outcome in `S/signed_checkpoints.py:verify_checkpoint`.
- risk_if_unfixed: A mathematically valid signature does not establish trusted ownership. Key ID is not custody, authorized signer identity, rotation/revocation policy or compromise handling. Formal tooling or Git commit verification does not establish runtime-checkpoint signer trust.
- hardening_goal: Establish operational trust/custody/lifecycle evidence separately from cryptographic validity.
- priority: P1.
- recommended_hardening_stage: H4.
- explicit_non_goal: Treating UNKNOWN as TRUSTED because tests, passwords or signatures validate.

### G08

- area: External anchor publication and readback adapter.
- current_state: NOT_IMPLEMENTED real deployment; protocol behavior TEST_CONTRACT_ONLY.
- evidence: `S/signed_checkpoints.py:AnchorPublisher`, `AnchorReader`, `publish_anchor`, `reconcile_anchor`; `R/signed-checkpoints.md` external publication boundaries.
- risk_if_unfixed: Protocol acceptance/readback comparison is not evidence that a real service published the checkpoint. Ambiguous publication requires retention of checkpoint/request identity; no durable publication queue/recovery is supplied.
- hardening_goal: Validate bounded real publication and read-only reconciliation with durable unresolved identity.
- priority: P1.
- recommended_hardening_stage: H5, after H1 and H4.
- explicit_non_goal: Re-publishing blindly on timeout, an additional ledger framework or H0 account access.

### G09

- area: Anchor independence, retention and external trust domain.
- current_state: UNKNOWN operational independence/retention; no supplied independently trusted deployment.
- evidence: `R/signed-checkpoints.md` publisher-attested versus readback-verified semantics and latest-anchor requirement; `S/signed_checkpoints.py:verify_security_history`.
- risk_if_unfixed: Same-controller or same-failure-domain readback may agree on replacement history. A genuine but stale checkpoint does not establish the newest tail. Readback matching is not independent retention or trusted external identity.
- hardening_goal: Demonstrate independently retained, trusted and sufficiently fresh anchor evidence.
- priority: P1.
- recommended_hardening_stage: H5; key management remains G07, not an implied anchor feature.
- explicit_non_goal: Claiming storage independence from an interface name or successful local readback.

### G10

- area: Real remote-account validation and credentials.
- current_state: NOT_RUN — NO_REAL_EXTERNAL_ACCOUNT_E2E; synthetic transports and temporary Git fixtures are the available integration evidence.
- evidence: `S/remote_runtime_binding.py:HTTPSRemoteTransport`, `NetworkRequestAdapter`, `GitPushAdapter`, `PullRequestCreateAdapter`; `T/test_remote_runtime_binding.py`; `R/remote-runtime-binding.md` validation limits.
- risk_if_unfixed: Production provider API/Git host/PR compatibility, credential issuance/expiry/rotation, provider idempotency and network ambiguity are not established by injected responses or temporary receive-pack. Development GitHub PR operations are not tests of these adapters.
- hardening_goal: Separately validate each bounded remote effect and credential lifecycle against an explicitly authorized real account, retaining uncertainty evidence.
- priority: P1.
- recommended_hardening_stage: H6; H1/H2 guard recovery/concurrency, H3 defines reality scope.
- explicit_non_goal: Adding providers, general credential discovery or live account tests in H0.

### G11

- area: Remote target-reality independence and transport assumptions.
- current_state: BETA — NO_INDEPENDENT_REALITY_SENSOR, NO_REAL_EXTERNAL_ACCOUNT_E2E.
- evidence: `S/remote_runtime_binding.py:_request`, adapter `_readback` methods and `RemoteRuntimeBinding.reconcile`; effect-specific matrix below; `R/remote-runtime-binding.md` DNS/idempotency limits.
- risk_if_unfixed: Same-endpoint assertions/readback are not independent reality; response success is not all-side-effects proof. Origin binding/TLS is not a DNS-rebinding/SSRF sandbox, and synchronous DNS is not proven bounded by the request timeout. An idempotency header does not prove provider behavior.
- hardening_goal: Define effect-specific independent corroboration and validate real transport/failure boundaries before stronger remote claims.
- priority: P1.
- recommended_hardening_stage: H3 evidence boundary; H6 real network validation.
- explicit_non_goal: Universal network interception or inferring non-occurrence from an ambiguous response.

### G12

- area: Host sensor breadth and operation.
- current_state: BETA — SINGLE_PLATFORM_ONLY; real macOS registered PROCESS_EXEC with PARTIAL coverage.
- evidence: `S/host_observer_macos.py:MacOSExecObserver` uses EVFILT_PROC/NOTE_EXEC/EV_ONESHOT with explicit PID registration; `T/test_host_observer_macos.py`; `R/host-observer.md`.
- risk_if_unfixed: No global discovery, fork/new-PID birth, process-exit sensor, filesystem/network sensor, other-platform backend or daemon/service continuity. PID is a short-session reference, not durable image identity. Absence means NOT_OBSERVED/UNKNOWN, not no effect.
- hardening_goal: Select only evidence-justified observer extensions after the trust core; preserve partial coverage semantics.
- priority: P2.
- recommended_hardening_stage: H7; restart/dedupe belongs earlier in G03, other-platform validation in H8.
- explicit_non_goal: Treating every missing event class as P0 or building a universal host agent.

### G13

- area: Token accountability integration/durable accounting.
- current_state: BETA contract foundation; real provider usage/cost UNKNOWN when absent; live collection/billing/enforcement NOT_IMPLEMENTED.
- evidence: `S/token_accountability.py` module contract, usage fields, `evaluate_budget`; `R/token-accountability.md` Current Enforcement/Public Claim Boundary; `T/test_token_accountability.py`.
- risk_if_unfixed: Supplied histories, prices and attribution are trusted inputs. Missing usage cannot become zero; deterministic budget/anomaly reports are not quota enforcement or theft detection. Chain-anchored records do not supply complete durable provider accounting/recovery.
- hardening_goal: Preserve honest accounting/unknown semantics; consider durable history and real provider usage only after core effect safety.
- priority: P2.
- recommended_hardening_stage: H9 candidate only after separate selection; no automatic integration commitment.
- explicit_non_goal: Billing platform, live budget enforcement, fraud attribution or token optimization in H0.

### G14

- area: Local Compute production maturity.
- current_state: BETA — SYNTHETIC_ONLY orchestration; real single/multi-node/provider/model/hardware/distributed validation NOT_RUN; cloud-reduction benefit UNKNOWN (existing docs: UNMEASURED); model sharding NOT_IMPLEMENTED.
- evidence: `README.md` Local Compute Orchestration; `R/local-compute-capability-intake.md`; `S/local_compute_pool.py`; `S/local_compute_deployment.py:DurableJournal`; `LOCAL_COMPUTE_ORCHESTRATION_IMPLEMENTATION_REPORT.md`.
- risk_if_unfixed: Injected-worker success cannot prove model quality, installation, hardware compatibility, cross-node authentication or savings. The deployment API DOES have POSIX flock, atomic replacement, file/directory fsync and pending recovery on a trusted local filesystem; it is not wired into G01's core runtime and must not be erased from the inventory.
- hardening_goal: Retain narrow API/persistence evidence while requiring separately authorized provider/model/hardware qualification before production claims.
- priority: P3.
- recommended_hardening_stage: Deferred optional expansion after H9 selection, not a mandatory security-core milestone.
- explicit_non_goal: Multi-node rollout, sharding, model downloads or cloud-saving promises.

### G15

- area: Formal and platform validation coverage.
- current_state: BETA local formal environment; portable contracts are not universal platform validation.
- evidence: `.github/workflows/check-skill.yml` Linux x64/Python 3.11 formal route; `requirements-release.txt`; `scripts/validate_formal_schemas.py`; `S/runtime_binding.py` dirfd/O_NOFOLLOW/fchdir/process groups/local Git; `S/host_observer_macos.py` native guard.
- risk_if_unfixed: Local macOS cannot substitute for the locked official formal target; Linux CI cannot establish native macOS observation. Filesystem/process/Git primitives and trusted local-filesystem assumptions limit support; unsupported paths fail closed, not silently portable. Missing target coverage limits reproducibility claims, not proof of production failure.
- hardening_goal: Maintain exact-SHA complementary validation and document tested platform boundaries before extending support.
- priority: P2.
- recommended_hardening_stage: H8; current CI remains required now.
- explicit_non_goal: Installing a Linux environment, changing dependencies, or adding Windows support in H0.

### G16

- area: Claim drift, test-only boundaries and operator diagnosis.
- current_state: BETA documentation consistency; controlled architecture tests PASS only in their stated scope.
- evidence: `docs/end-to-end-security-runtime.md`; historical R/ statements listed below; `S/cross_layer_verification.py` transient findings; bounded journals/receipts/digests.
- risk_if_unfixed: Historical phase-local absence statements can be misread as current global status. Test PID rendezvous, fake signatures and injected mismatch are not deployment features. Operators have receipts/reasons/chain verification, but not a crash-recovery diagnostic service or durable cross-layer finding history; digests cannot recover absent underlying artifacts.
- hardening_goal: Preserve precise claims and actionable evidence boundaries; prioritize recovery diagnosis with H1, optional presentation only later.
- priority: P2.
- recommended_hardening_stage: H0 inventory; future bounded documentation correction/diagnostics, H9 optional UX.
- explicit_non_goal: Dashboard, alerting, telemetry subsystem or silently promoting test fixtures to runtime code.

## Remote effect-specific evidence

| Effect | Prebound | Observed and reconciled | Still unknown / validation limit |
| --- | --- | --- | --- |
| NETWORK_REQUEST | Origin/URL/query, method, body/header commitments, timeout/size limits, optional request identity/readback target+digest | Request attempted; response status/body completeness/digest. Optional GET readback with expected digest can reconcile success. No automatic mutation retry. | Attempted is not proof of bytes sent. Provider side effects/idempotency and independent reality remain unknown; non-2xx mutation/transport ambiguity stays unknown. Synthetic transport evidence, no real-provider E2E. |
| GIT_PUSH | Repository, exact existing SHA-1 branch, old/new OIDs and remote HTTPS endpoint; fast-forward/ancestry/config checks | Receive-pack status and remote ref reread; reconciliation new OID = success, old = not-applied classification, other = conflict, unavailable = unknown | Old ref does not rule out a transient update/reversal; no independent history sensor. Temporary repositories/transport fixtures are not real Git-host/account validation. No force/new-branch/SSH/general protocol support. |
| PR_CREATE | GitHub-compatible repository/head/base/title/body/draft and request marker | Matching create response; bounded complete one-page GET must have exactly one exact and one plausible match for success | Empty/multiple/mismatched/incomplete readback stays unknown; absence is not proof no PR ever existed. Same provider assertions, no real PR-provider/account/credential-lifecycle E2E. |

Readback evidence is monotonic: attempted/response/status/complete-body digest are
captured before parsing; parser failure does not erase already observed facts.
Reconciliation rechecks current authority/policy and reads only; it is not retry.

## Claim-versus-evidence matrix

| Capability | Current bounded claim | Actual evidence | Current status | Before stronger claim |
| --- | --- | --- | --- | --- |
| RSE + authority | Caller-invoked policy/authorization and uncertainty guards | InMemorySecurityJournal, authority checks, lower-layer tests | PASS bounded; SAME_PROCESS_ONLY / NO_CRASH_DURABILITY | G01/G02; no universal interception |
| Local binding | Prebound real file/process/Git operations under narrow host assumptions | Real temp filesystem/process/Git regression tests | PASS bounded; platform-limited | G01/G02/G05/G15; not a sandbox |
| Remote binding | Bounded HTTPS/network/Git/PR contracts and conservative reconciliation | Production adapter source, synthetic transport/temp Git tests | BETA; NO_REAL_EXTERNAL_ACCOUNT_E2E | G10/G11; effect-specific reality |
| Agent bridge | Governed prepare/execute/reconcile, material reservation | Normalization and duplicate/unknown tests | PASS bounded; SAME_PROCESS_ONLY | G01/G02; no global dedupe |
| CET | Declared/adapter/host evidence separated | Existing event contracts/chain references | PASS bounded; supplied provenance trusted | G03/G05/G11; events are not complete truth |
| Security chain | Hash-linked tamper evidence and local verified history | JSONL checks/fsync and mutation tests | PASS bounded; BETA storage/trust envelope | G04/G09; not tamper-proof |
| Token foundation | Explicit reported/unknown usage and deterministic budget/anomaly facts | Pure arithmetic/contracts and supplied records | BETA; provider completeness UNKNOWN | G13; no billing/theft/enforcement claim |
| Signed checkpoints | Canonical head binding under host signer/verifier contract | FakeSigner/FakeVerifier contract tests | TEST_CONTRACT_ONLY; real integration NOT_IMPLEMENTED | G06/G07; validity != trusted identity |
| External anchor | Publish/readback/history protocol under trusted independent inputs | Injected protocol fixtures | TEST_CONTRACT_ONLY; deployment NOT_IMPLEMENTED | G08/G09; prove independence/freshness |
| Host observer | Registered macOS exec event, PARTIAL | Native kqueue test and ingestion tests | PASS narrow; BETA / SINGLE_PLATFORM_ONLY | G03/G12/G15; not complete lifecycle |
| Cross-layer verifier | Read-only factual comparison; ambiguous evidence UNKNOWN | F1 coverage/identity tests, no effect/write calls | PASS bounded | G05/G11; MATCH is not an all-effects verdict |
| Phase 5 integration | One controlled real path plus one synthetic mismatch | Native PID-synchronized exec, wait/reap, existing chain and fake checkpoint | PASS bounded architecture test | G01–G12 as applicable; no production deployment |
| Local Compute | Optional injected-worker APIs, bounded POSIX deployment recovery | Synthetic orchestration and DurableJournal tests | BETA; real deployment NOT_RUN | G14; no savings/sharding claim |
| Formal validation | Locked Linux x64/Python 3.11 formal route | Existing CI definitions and exact-SHA run evidence | Local BETA; baseline CI PASS | G15; H0 CI must be checked separately |

## BETA inventory (8 meaningful groups)

| Group | Reason | Existing bounded PASS evidence | Missing target evidence; priority impact |
| --- | --- | --- | --- |
| Core controller/recovery | In-memory/process-scoped operational envelope | RSE/binding/bridge regressions | Crash/multi-controller recovery; drives H1/H2 |
| Chain storage/trust | Local single-controller history, no independent newest head | Hash/link/canonical/fsync-path tests | Crash/power-loss protocol and replacement resistance; H1/H4/H5 |
| Remote effects | Synthetic transport, narrow protocols | Adapter ambiguity/readback/temp Git tests | Real accounts/networks/credentials; blocks stronger deployment claims, H6 |
| Host operation | Narrow macOS PARTIAL event/session | Native NOTE_EXEC + ingestion checks | Restart continuity and selected other scopes; core continuity first, H7/H8 breadth later |
| Token foundation | Supplied usage/history, no live integration | Arithmetic/unknown/authority tests | Provider completeness/durable accounting/enforcement; not ahead of H1–H6 |
| Local Compute | Partial APIs and injected workers | Orchestration/POSIX journal tests | Real provider/model/hardware/multi-node; optional, not core blocker |
| Local formal/platform assurance | Official formal target differs from local macOS; native tests differ from Linux | Local native suite and baseline Linux CI | Exact-H0-SHA CI still required; developer limitation alone is not production failure |
| Documentation/operator maturity | Phase-local historical wording and transient reports | Current source + bounded diagnostic/verification tests | Consistent global claims/restart diagnosis; no new UI required |

## UNKNOWN inventory (7 architecture-level groups)

1. Complete post-crash effect history/recoverability where volatile execution and
   reconciliation evidence is gone (G01/G03/G04).
2. Operational runtime-checkpoint signer identity/custody/trust (G07).
3. External anchor independent retention, trust domain and newest-head freshness (G09).
4. Independent process image/side-effect truth and effect-specific remote reality (G05/G11).
5. Real provider/Git-host/PR-provider behavior, credentials and network ambiguity (G10/G11).
6. Unavailable provider usage/cost/completeness: missing is not zero; anomaly is not theft (G13).
7. Real Local Compute compatibility/quality/resource benefit/cloud reduction (G14).

Absence of implemented restart/cross-process mechanisms is known, not UNKNOWN;
the lost real-world outcome is unknown. No individual runtime event is counted here.

## Strategic NOT_IMPLEMENTED inventory (9 groups)

1. Core durable action/uncertainty/reservation recovery (not the separate Local Compute journal).
2. Core cross-controller ownership/duplicate suppression and shared chain/ingestor coordination.
3. Durable host sequence/dedupe/registration continuity.
4. Independent bounded target-reality backend; process-outcome reconciler absent.
5. Supplied real cryptographic checkpoint integration and operational key lifecycle.
6. Real external publication adapter and independently retained trusted anchor deployment.
7. Additional selected host-event/platform/service backends (deferred, not all required).
8. Live provider accounting/billing/quota integration (optional later scope).
9. Concrete complete Local Compute provider/model setup and sharding/distributed runtime (deferred).

Real external-account and hardware experiments are NOT_RUN, not themselves missing
algorithms. Existing POSIX binding and Linux formal routes must not be labeled absent.

## Proposed H1–H9 and cut line

| Stage / goal | Why now | Dependencies | Success criterion | Non-goals |
| --- | --- | --- | --- | --- |
| H1 — Crash durability + persistent uncertainty | Volatile state loses retry safety on restart | Current bounded contracts | Crash/restart evidence preserves unresolved barriers and required recovery facts | Automatic retry, distributed exactly-once |
| H2 — Cross-process coordination | Separate controllers bypass local guards | H1 state semantics | Two controllers cannot independently admit the same protected mutation/state transition | Cluster orchestrator |
| H3 — Independent target reality | Shared evidence provenance limits assurance | H1/H2 operational envelope; effect-specific scope selection | Independently sourced bounded facts with honest gaps/identity | All-effect or hostile-kernel proof |
| H4 — Real signer + checkpoint trust | Fake contract evidence is not cryptographic deployment | Current checkpoint contract; explicit key/trust authority | Real crypto and separately established signer trust/lifecycle evidence | New crypto/PKI platform |
| H5 — Real external anchor | Local history cannot exclude whole-history replacement | H1 unresolved publication recovery; H4 trusted signatures | Authorized publication/readback plus independent retention/freshness evidence | Another ledger or automatic retries |
| H6 — Real remote-account E2E | Interoperability/ambiguity still synthetic | H1/H2; H3 reality definitions; exact account authority | Each selected effect validated with real provider, credentials and bounded failures | More providers or general internet agent |
| H7 — Selected host expansion | Close demonstrated observation needs after core trust | H1/H2 continuity; H3 evidence requirements | One selected additional scope has native evidence and explicit gaps | Universal observer/automatic daemon rollout |
| H8 — Multi-platform validation/support | Broaden only after trust contracts stabilize | Core stages; platform selection | Exact supported matrix demonstrates required primitives/gates and fail-closed unsupported paths | Implicit Windows/Linux observer commitment |
| H9 — Bounded operator UX/performance | Presentation/efficiency must not outrank safety | Core stable; demonstrated operator need | Measured improvement without weaker evidence or safety semantics | Dashboard/telemetry/policy platform by default |

HARDENING CORE: H1–H6, including minimal recovery diagnosis and honest claims.
HARDENING EXPANSION: H7–H9 and optional token/Local Compute integrations.
Stage order is proposed prioritization, not nine implementation authorizations.
H4 can be investigated independently of sensor design once separately authorized;
cryptography never authenticates an unobserved effect. No schema/framework design
or dependency choice is made here.

Deferred: extra host event classes, global discovery, Linux/Windows observers,
service/daemon deployment, dashboards, alerting, batching, performance tuning,
policy automation, billing/enforcement, provider proliferation, multi-node Local
Compute, model sharding and cloud-reduction optimization. Reprioritize only on
new evidence/Design Authority selection, not feature attractiveness.

## Prior fixes and claim audit

No security regression found in source inspection and the baseline existing suite:

| Preserved fix | Source / regression evidence |
| --- | --- |
| Git tree/parent prebinding | `S/runtime_binding.py:LocalGitAdapter`; `T/test_runtime_binding.py:test_git_preauthorized_tree_mutation_denied`, `test_git_preauthorized_parent_mutation_denied`, postcheck tree/parent tests |
| Process uncertainty | ProcessAdapter/capture cleanup and journal barriers; `test_process_timeout_unknown`, `test_environment_unknown_override_and_nonzero_unknown`, post-effect retry/reconciliation tests |
| Graft/replace rejection | `S/remote_runtime_binding.py:GitPushAdapter._ancestry`; remote tests for unrelated graft, loose/packed/malformed/irrelevant replace and actual subprocess environment |
| PR readback monotonic evidence | `_request`, `PullRequestCreateAdapter._readback`, `RemoteRuntimeBinding.reconcile`; remote recovery response/parse/status tests |
| Material normalization | `S/agent_runtime_integration.py` prepare/normalization and `_material`; bridge tests for effective query, environment order, Git trailing slash and stage-path order |
| F1 unique DIVERGED | `S/cross_layer_verification.py:_compare` requires one unmatched pair, both SCOPED_COMPLETE, no unresolved alternatives; `T/test_cross_layer_verification.py:test_f1_*` preserves real unique divergence and UNKNOWN on partial/gap/unresolved cases |

The audit searched README, docs and architecture references for production-safe,
tamper-proof, kernel truth, complete host observation, universal interception,
exactly-once, crash durability, cross-process safety, all-effects verification,
real crypto and independent reality claims, then checked context against source.
No affirmative unsupported strong security claim was found in that scoped audit;
most matches are explicit exclusions. This is not proof about all external marketing.

Discrepancies recorded, not silently treated as current absence:

- `R/agent-runtime-integration.md` Phase 2C table says HOST_OBSERVER NOT_IMPLEMENTED;
  current Phase 3B source supplies the narrow macOS observer.
- `R/host-observer.md` phase-local text says cross-layer verifier/Phase 4 not implemented;
  current `S/cross_layer_verification.py` and Phase 5 tests supersede global reading.
- `R/token-accountability.md` Non-Enforcement/Future Runtime Binding lists CET,
  signatures and host observer as absent: these remain absent *from token live
  enforcement*, not absent from the merged architecture.
- `R/signed-checkpoints.md` historical core-file count is 56; current package
  manifest lists 67 core paths. Inventory does not change the package.

Test-only: Phase 5 PID/release-file rendezvous coordinates one controlled test;
FakeSigner/FakeVerifier is exact-message contract validation; the one
CONTROLLED_VERIFICATION_FIXTURE injects comparison descriptors only. None is a
production handshake, real crypto deployment, real adversarial mutation or sensor.

## Validation and stop boundary

Baseline local comprehensive runner: 1216 existing tests, 16 skipped, no failures;
package/catalog/plugin/fresh isolated install and release-state checks passed.
Optional warnings/skips remain; skipped checks are not PASS. No dependency was
installed. Local formal remains BETA, not FAIL and not official formal PASS.
Baseline main CI check-skill/formal-schema-gate passed (run 37709281221); the main
formal route is schema integration, not controlled PR formal evidence.

The final H0 SHA must independently pass local package/diff checks, receive all
three designated independent reviews, then get its own PR check-skill and
formal-schema-gate PASS. External exact-SHA review/CI evidence belongs in the PR
and completion report, not a self-referential SHA baked into this document.
No production/test changes, H1 implementation, merge, release or deployment is
authorized by completion of this inventory.
