# Local Compute Orchestration Implementation Plan

> Execute with executing-plans and test-driven-development. Specialist reviews
> are required before conditional remote delivery.

**Goal:** Explicitly invoked, consent-gated local compute orchestration with
bounded task parallelism and truthful evidence stages.

**Architecture:** Standard-library Python modules separate deployment effects
from node/task policy. Injected adapters permit deterministic synthetic testing;
their presence is not proof of real provider or remote-node support. Distributed
inference is a separately gated recommendation, not a sharding runtime.

**Spec:** Design Authority execution directive v1.2 supplied in this conversation.
No real device installation, downloads, network discovery or inference is allowed
in this implementation run. No modification to the independent brand PR #155.

## Files and execution sequence

- [x] Add repository-level `scripts/local_compute_deployment.py` and
  `tests/test_local_compute_deployment.py`: consent, evidence-based value gate,
  approved candidate selection, budget reservations, bounded effects/tuning,
  unknown-outcome reconciliation. Write failing behavioral tests before code.
- [x] Add repository-level `scripts/local_compute_pool.py` and
  `tests/test_local_compute_pool.py`: per-node/model/config/task qualification,
  privacy-first selection, atomic capacity reservations, concurrency, failure
  isolation, migration invalidation and topology recommendations. Test actual
  concurrent execution using synthetic workers, not real model inference.
- [ ] Complete runtime integration before changing stable package declarations.
  Incomplete development APIs remain outside the installed package.
  Reference documentation must describe the callable
  API, trust boundary and unimplemented transports explicitly.
- [x] Run both focused suites, then existing unittest discovery, package and
  generated-documentation checks. Preserve pre-existing untracked files.
- [x] Obtain Matt-inspired dispatch review, Karpathy-inspired minimality review,
  and ECC security review. Resolve material findings with regression tests.
- [x] Write `LOCAL_COMPUTE_ORCHESTRATION_IMPLEMENTATION_REPORT.md` with exact
  coverage/gaps, evidence stages and real pilot requirements. README may describe
  only verified implemented behavior, not a planned adapter as working deployment.
- [ ] Deliver the partial implementation as Beta under the subsequent explicit
  Beta GitHub Delivery Authorization v1.0: fresh tests, bounded public claims,
  signed commit and Draft PR. No merge, release or real-device pilot.

## Checkpoint

Local primitives and three review passes are complete; the product objective is
not. The implementation report lists required provider, qualification, transport
and recovery integration. Passing synthetic component tests does not satisfy
those remaining criteria. The later Beta authorization permits partial remote
delivery without claiming those production criteria have been met.

## Acceptance and containment

No dependency installation, daemon, database, LAN discovery, credential copying,
automatic topology creation or real cloud fallback during testing. LOCAL_ONLY
inputs and outputs stay local. Unknown effects do not authorize retries. Model,
node or config changes invalidate qualifications. Existing workflow semantics
remain unchanged. Revert only this feature's exact additions/edits if rejected;
do not reset the checkout or delete existing user files.
