# Experiment Proposal

## Experiment ID
`MAD-SKILL-005`

## Name
Control Plane / Execution Plane Separation

## Status
`locked`

## Problem Statement
Long-running agent designs need planning, routing, approvals, state, cost, audit, and execution isolation without treating governance as permission.

## Why This Is Relevant
Separating control decisions from a future bounded executor can clarify human approval and containment.

## Source Patterns
ruvnet/ruflo `12ede21767a6dd669df1b79392a5d27d9154f237`, exo-explore/exo `b5375f8cee4368d09e1ce96a56b9f81fb0bc81aa`, and vxcontrol/pentagi `879e87c2c2688c4a95eac9c1aaf3cd6f6123ebe3` are defensive governance leads only.

## Clean-room Boundary
Extract only planning, routing, approval, state, cost, audit, and isolation concepts. Copy no code, agent topology, commands, or security tooling.

## Explicit Non-goals
No auto attack, scan, credential acquisition, exploit, lateral movement, persistence, data theft, infinite loop, or concurrent execution.

## Inputs
Future approved task contract, explicit permission contract, budget, and isolated synthetic fixture.

## Outputs
Future control-plane decision record and execution-plane interface specification.

## Permissions Required
Future execution is separately approved per action; default mutation remains deny.

## Network Requirements
None for design; no security or external network action is permitted.

## Dependency Requirements
None for design; no framework is selected.

## Cost Possibility
Future orchestration can increase token, compute, and operator cost; no cost occurs here.

## Customer Approval Gates
Approve the task, exact tools, paths, concurrency, budget, and every external effect separately.

## Expected Benefits
Clear auditability and containment with future concurrency capped at four.

## Failure Modes
Approval laundering, scope creep, loop escalation, cost amplification, or execution/control confusion.

## Baseline Comparison
Single serial human-approved workflow with no control-plane abstraction.

## Required Hard Gates
All gates; human control, scope, isolation, observability, and rollback are critical.

## Evaluation Categories
Policy fidelity, containment, audit completeness, cost clarity, and baseline task quality.

## Promotion Constraints
Restricted security boundary; remain sandbox-only until defensive synthetic evidence and customer approval exist.

## Rejection Conditions
Reject if it permits autonomous security actions, unbounded loops, or more than four future concurrent workers.

## Open Questions
How can a control plane stay explanatory without becoming an autonomous runtime?
