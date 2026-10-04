# Critical Execution Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement the authorized Phase 1.5 adapter-observed trace foundation.

**Architecture:** One inert Python module owns bounded immutable artifacts, an in-memory trace container and pure analysis. Existing RSE supplies action/data enums and logical target normalization; existing Security Chain stores digests only. Main implements; the three designated chats independently review immutable commits.

**Tech Stack:** Python standard library, unittest, existing RSE and Security Chain.

**Spec:** Design Authority Phase 1.5 directive supplied in this conversation, sections 0–143; five-point implementation design approved on 2026-10-04.

## Global Constraints

- Base main: 82da01011b3429b8e8f07c66d6bc62ab046ee3b3.
- Branch: feat/critical-execution-trace; isolated workspace only.
- No new dependencies, host observation, runtime interception, telemetry, database or later phase.
- Existing RSE, Token Accountability and Local Compute behavior unchanged.
- Only three new Security Chain event enum values; no schema/hash changes.
- Synthetic CET tests only; no real target effects or secret access.
- Independent Reviewer 2/3/4 required; no self-certification or majority voting.
- Create PR, await CI, DO NOT MERGE.

## Task 1: Trace artifacts and declared/observed comparison

Files: create `tests/test_critical_execution_trace.py` and `.agents/skills/long-horizon-engineering/scripts/critical_execution_trace.py`.

Interfaces: `TraceContext`, `CriticalEvent`, `DeclaredEffects`, `ObservedEffects`, `compare_effects(declared, observed)`, `declared_from_action(action, context)`.

- [ ] Write literal tests for all ten divergence categories, target normalization, source/time/size validation, RSE mapping parity and untrusted prose.
- [ ] Run `python3 -m unittest tests.test_critical_execution_trace -q`; require expected missing-implementation failures.
- [ ] Implement immutable artifacts, closed enums, bounded canonical collections and fieldwise observed-minus-declared comparison.
- [ ] Repeat targeted command; require passing assertions such as:

```python
assert compare_effects(DeclaredEffects(context, reads=('/repo/a',)),
    ObservedEffects(context, reads=('/repo/a',))).divergences == ()
```

## Task 2: Causal structure, risk patterns and RSE correlation

Files: same module and test file.

Interfaces: `CriticalTrace.append/events/events_for_action/children_of/verify_structure`, `detect_trace_risks`, `analyze_trace`, `correlate_rse`.

- [ ] Add RED fixtures for cycle, absent parent, self-parent, rebinding, reverse time, depth, duplicate, unknown/partial completeness and unrelated chronological events.
- [ ] Implement bounded iterative parent traversal. Missing parents downgrade completeness; cycles/rebinding/time reversal reject. Complete needs explicit coverage refs.
- [ ] Add RED tests for the six required causal patterns and receipt denial/class/identity contradictions.
- [ ] Implement strict ancestor + nondecreasing event time predicates, explicit internal/approved origins, deterministic severity and digest-bound findings. Do not infer a causal edge between same-action events.
- [ ] Run targeted tests and unchanged RSE/Token tests. Exact observations, not intent, are the acceptance criterion.

## Task 3: Chain integration, packaging and operator documentation

Files: extend `security_authority_chain.py` enum only; add `references/critical-execution-trace.md`; update package manifest, package checker required sets, effect manifest, README and existing Core count assertions/documentation.

Interfaces: `record_critical_event`, `record_trace_divergence`, `record_trace_risk` reuse existing evidence-record authority checks.

- [ ] Add RED tests for authority scope, duplicate events, legacy hash, raw marker suppression and Token history coexistence.
- [ ] Implement stable scoped identities and artifact-digest anchoring only.
- [ ] Document threat boundary, pure operator walkthrough, completeness, configured severity, investigation evidence and non-goals; exercise example in tests.
- [ ] Run package/doctor/catalog/audits/plugin/profile/update/fresh-isolated-install and full unittest suite.
- [ ] Commit explicit task files, never original checkout or unrelated files.

## Task 4: Independent review and delivery

- [ ] Send final fixed SHA and directive to the three user-designated chats, with distinct minimality/security/operator responsibilities.
- [ ] Reproduce valid findings as RED tests, correct and obtain originating reviewer's recheck.
- [ ] Rerun all final-SHA regressions and package/formal gates; disclose unavailable local formal engine separately from CI.
- [ ] Push feature branch; create `feat: add Critical Execution Trace foundation` PR and attach it to this chat.
- [ ] Await check-skill and formal-schema-gate PASS. Return exact Design Authority report without merging.

## Stop / containment

Stop if schema changes or later-phase effects become necessary, baseline tests fail, or authority/scope becomes unclear. Preserve branch and isolated workspace for rollback/review; no destructive cleanup. Complete means evidence-bound acceptance plus three actual reviews and CI, not runtime or host-truth certification.
