# Experiment Proposal

## Experiment ID
`MAD-SKILL-002`

## Name
Capability Contract and Real Output Harness

## Status
`locked`

## Problem Statement
Exit code zero is not evidence that a tool produced correct output or avoided side effects.

## Why This Is Relevant
A reusable contract can bound a future tool's input, output, scopes, permissions, cost, failures, rollback, and acceptance evidence.

## Source Patterns
HKUDS/CLI-Anything at `bc536c9bebb7c3d9f7bb2736a732609139c1acdb` is a methodology lead only.

## Clean-room Boundary
Copy no code, prompt, adapter, command syntax, or fixture from the source.

## Explicit Non-goals
No CLI installation, host control, provider call, filesystem write, or execution.

## Inputs
Future customer-approved fields: input, output, read_scope, write_scope, network, dependencies, permissions, cost, failure_conditions, rollback, acceptance_checks.

## Outputs
Future machine-reviewable contract and real-output acceptance plan.

## Permissions Required
Future exact-tool, path, and side-effect approval; this proposal grants none.

## Network Requirements
None for design; future egress must be declared and approved.

## Dependency Requirements
None for design; no tool is selected.

## Cost Possibility
Future tools can incur compute, provider, quota, or operator cost; none occurs here.

## Customer Approval Gates
Approve tool, operation, read/write scope, fixture, and execution separately.

## Expected Benefits
Acceptance can verify schema, hash, completeness, duration, openability, parsing, behavior, side effects, temp files, and processes.

## Failure Modes
False success, unsafe side effect, stale artifact, hidden process, cost growth, or ambiguity.

## Baseline Comparison
Command exit-code check with no real-output verification.

## Required Hard Gates
All ten Incubator hard gates must pass; score cannot offset a failure.

## Evaluation Categories
Task quality, reliability, safety, permissions, reversibility, efficiency, maintenance, explainability, compatibility.

## Promotion Constraints
`recommended_first_design_candidate: true` is a planning priority, not authorization; remain locked until isolated synthetic evidence and a customer decision exist.

## Rejection Conditions
Reject any contract that cannot bound side effects, evidence, or rollback.

## Open Questions
What smallest common contract works without pretending to support every tool?
