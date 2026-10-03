# Local Compute Orchestration (Beta) — implementation report

## Decision and authority

Design Authority implementation directive v1.2 authorizes implementation and
testing. The subsequent **Beta GitHub Delivery Authorization v1.0** explicitly
authorizes publishing this current **PARTIAL** implementation in a signed Draft
PR after fresh tests and claim verification. It supersedes the earlier
full-implementation prerequisite for that Beta delivery only. Production
completeness is not claimed. Merge, release and real-device deployment remain
outside this delivery scope.

Beta branch: `codex/local-compute-orchestration-beta`, based on current `main`
`7a5355af11afcc1e830595e0f951d852345c5639`. The separate branding PR is not
included. Pre-existing historical-decision examples were not changed.

## Implemented surface

Repository-level Python development APIs (not packaged in the installed Skill):

- `scripts/local_compute_deployment.py`: consent-filtered probe adapter,
  evidence-based value gate, approved candidate selection, exact effect and
  command binding, bounded deployment sequence, conservative reservations,
  unknown-outcome reconciliation, explicit foreground subprocess adapter,
  POSIX exclusive-owner atomic journal and shared deployment budget ledger.
  Journal recovery rebinds a pending fingerprint to an explicitly supplied
  approved effect; targets, arguments and payloads are not persisted.
- `scripts/local_compute_pool.py`: independently gated node identities and
  qualifications; privacy checks for input and output; bounded concurrent
  independent workers; load-aware assignment; known-failure local retry;
  unknown-outcome retention; migration trust reset; candidate-only topology
  recommendations. Different models/configurations can coexist. Immutable
  content-free health snapshots distinguish observed execution rates/latency
  from caller-supplied memory pressure and correction-rate observations.
- Focused unittest suites exercise these APIs with synthetic callbacks and
  bounded standard-library child processes. They do not run model inference.

Caller-supplied consent and qualification objects are trusted inputs, not proof
of human permission. Worker binding checks are not remote-host authentication.
`LOCAL_ONLY` outputs are withheld unless the trusted caller attests a local
output boundary. This is policy logic, not OS-enforced data isolation.

## Review and corrections

Three independent AI review lenses were used as requested; these are not
endorsements by the named people or projects.

- Matt-inspired: reproduced a second-submit failure that lost ownership of an
  already-running task and permitted duplicate execution. Fixed with retained
  unknown records and submission gates, including an enqueued-then-raising
  executor. Independently rechecked the fix and worker `SystemExit` handling.
- ECC: identified wrong-node subprocess execution and restart budget/unknown
  state loss. Added node binding, pending-effect recovery and a durable shared
  setup budget ledger. A further shared-journal multiple-consumer counter bypass
  prompted exclusive consumer ownership in the concrete durable journal.
  Independent recheck: two controllers sharing that journal yielded one effect
  execution and one reconciliation block; a second pool ledger was rejected;
  two 3 GB reservations against a 5 GB pool allowed only the first.
- Karpathy-inspired: retain a small task-pool-first architecture. Fixed planner
  preference when one node is sufficient and when disjoint qualifications
  require serial use of different nodes. No cluster framework was introduced.

## Verification history

The first full test run was **746 tests, 35 failures, 16 skips**. Adding the two
scripts inside the installed Skill violated its exact package inventory and
dependent snapshot contracts. The modules were moved to repository-level
`scripts/`; package/effect declarations were restored unchanged. This failure
is retained as evidence, not relabelled as a passing run.

After relocation, package validation, generated catalog checks and plugin
validation passed. An intermediate full run passed **756 tests, 16 skipped**
(112.145 seconds). After adding the health/recovery regressions, the final run
passed **766 tests, 16 skipped**, in **111.228 seconds**:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'`.
The three printed preflight ERROR messages are negative-test diagnostics;
the unittest process exited 0 with `OK (skipped=16)`. Skips are not passes.

Focused validation after all current code changes:
`python3 -B -m unittest tests.test_local_compute_pool tests.test_local_compute_deployment -v`
passed **45 tests** (27 pool, 18 deployment). `git diff --check`,
`.agents/skills/long-horizon-engineering/scripts/check_skill_package.py`,
`scripts/generate_skill_catalog.py --check` and
`scripts/validate_plugin_package.py` passed.

## Requirement/test coverage boundaries

### Fresh Beta pre-delivery rerun

After the Beta README/reference edits: targeted tests **45 passed**; full suite
**766 total, 16 skipped, 0 failures/errors** (106.938 seconds). Package,
catalog/documentation, plugin and diff checks passed. The runtime/test code is
unchanged from the reviewed partial implementation. These results authorize no
claim of real provider or hardware validation.

### Coverage

| Requested cases | Evidence and limit |
| --- | --- |
| M1–M7, M9–M10 | Synthetic node activation, exact qualification routing, load/headroom, known-failure retry, privacy, removal and heterogeneous binding tests. No distinct-device transport. |
| M8 and migration | Fresh-gate denial and hint-only trust reset tested; full new-device setup and interrupted migration not implemented. |
| T1–T8 | Bounded independent-task topology selection and distributed gate assertions tested; caller assertions are not measured interconnect/framework compatibility. |
| Assignment failure | Regression verifies retained in-flight records and retry protection; independent review also checked enqueued-then-raising submission. |
| Timeout/provider exception | Synthetic timeout, unknown exception and abnormal worker termination; no actual model-provider failure test. |
| Partial deployment/unknown effect | Approved effect chain stops on unknown; durable restart/reconciliation and conservative reservations tested. No actual partial model download. |
| Network interruption/distributed worker loss | Real transports and distributed runtime absent; no claim of operational coverage. Distributed runtime is optional and remains candidate-only. |

Shared pool setup ceilings require the same `PoolBudgetLedger` to be supplied
to all participating deployment runners. The low-level API permits single-node
use without one; complete orchestration must wire this explicitly.

## Feature production remaining work

These remain unresolved parts of the original implementation objective, **not
blockers to the separately authorized partial Beta publication**:

1. Concrete consent-bound hardware/provider probe, platform handling and
   provider compatibility evidence. Current probe accepts an injected reader.
2. A version/identity-bound provider installation, model download, configuration,
   start and inference integration. Current subprocess recipes are explicit
   caller inputs; no real provider recipe is bundled.
3. Measured auto-tuning and approved-model fallback, with a task-specific
   qualification evaluator. Iterating approved effects and accepting a supplied
   qualification set do not implement these lifecycle stages.
4. Authenticated node-specific transport and end-to-end migration/rebinding.
   In-process synthetic workers and clearing inherited trust do not establish
   operation on distinct devices.
5. Complete recovery/ownership integration across deployment and task execution.
   Deployment now has a POSIX durable journal and shared declared-resource
   ledger; generic user-supplied journals remain trusted integration components.
   Pool task records are currently session-only; a restart must not be treated
   as permission to repeat unresolved external execution. Python threads cannot
   forcibly cancel adapters; real adapters must supply cancellation guarantees.
6. Task dependency planning, complete resource/health evidence and qualification
   validity policy; current planner accepts independent task batches only.
7. Final runtime integration/package decision and complete requirement-to-test
   coverage for stronger production claims. Beta documentation and Draft PR
   delivery do not close these product gaps.

Resource estimates are reservations, not enforcement of actual operating-system
disk, memory or network use. Arbitrary subprocess recipes are trusted executable
code, not a sandbox. Production adapters must enforce approved effects/bounds.

## Explicit non-claims

Distributed inference: candidate planning only; no sharding implementation.
No automatic LAN discovery, service exposure, cluster manager or background
daemon. No installation, model download, actual cloud fallback, real single-node,
multi-device or distributed pilot was run. Cloud usage reduction is unmeasured.
README now describes only the partial Beta and these evidence boundaries.
Stable workflow behavior, release version and installed Skill IDs are unchanged.

## Beta claim verification

| Public claim | Classification | Evidence / boundary |
| --- | --- | --- |
| Repository-level orchestration APIs exist | IMPLEMENTED | Two Python modules; not included in installed Skill package. |
| Exact node/provider/model/config/task qualification checks | SYNTHETICALLY_VALIDATED | Identity and stale-qualification tests; trusted caller supplies qualification evidence. |
| Consent, input/output privacy checks | SYNTHETICALLY_VALIDATED | Explicit node/scope gates and LOCAL_ONLY cloud denial tests; not OS isolation. |
| Bounded concurrent pool and load-aware scheduling | SYNTHETICALLY_VALIDATED | Concurrent injected workers, load/headroom and assignment interruption tests; no real networked nodes. |
| Migration hints with trust reset | SYNTHETICALLY_VALIDATED | Replacement node loses consent/probe/runtime/qualification; operational migration remains partial. |
| OpenAI fallback policy | SYNTHETICALLY_VALIDATED | Injected callback only; both input and output must allow cloud; no actual OpenAI call. |
| Exact effects, declared budgets, POSIX journal recovery | SYNTHETICALLY_VALIDATED | Synthetic effects, temporary journals and bounded child processes; actual resource enforcement is adapter responsibility. |
| Distributed topology recommendation | SYNTHETICALLY_VALIDATED | Boolean evidence-gate tests only; no runtime or measured interconnect verification. |
| Full automatic provider/model deployment and zero-touch tuning | NOT_IMPLEMENTED | Partial effect controller exists, concrete recipes and measured tuning/qualification chain do not. |
| Distributed model sharding | NOT_IMPLEMENTED | Candidate planning only. |
| Potential cloud usage reduction after validation | DESIGN_ONLY | Intended benefit, not measured or guaranteed. |
| Real provider/model/hardware/multi-device validation | NOT_IMPLEMENTED | Evidence absent: all real validation stages NOT_RUN; no REAL_MACHINE_VALIDATED claim. |

Claim verification applies to these bounded statements, not production maturity.

## Changed files

Modified:
`README.md` and
`.agents/skills/long-horizon-engineering/references/local-compute-capability-intake.md`.

Added:

- `scripts/local_compute_deployment.py`
- `scripts/local_compute_pool.py`
- `tests/test_local_compute_deployment.py`
- `tests/test_local_compute_pool.py`
- `docs/superpowers/plans/2026-10-03-local-compute-orchestration.md`
- `LOCAL_COMPUTE_ORCHESTRATION_IMPLEMENTATION_REPORT.md`

Package manifest, effect manifest, installed user Skill, independent
branding work and the three pre-existing historical-decision files are unchanged.
The remote delivery receipt and CI state belong to the Draft PR and final
handoff. Feature production remaining work is nonzero even after Beta delivery.

## Next action

Recommended next milestone: **REAL_SINGLE_NODE_PILOT**, after the missing
provider integration is available and the exact hardware, model, effects,
data scope and budgets are separately authorized. This Beta delivery does not
execute or authorize that pilot.
