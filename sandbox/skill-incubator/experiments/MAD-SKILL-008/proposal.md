# Experiment Proposal

## Experiment ID
`MAD-SKILL-008`
## Name
Composable Skill Router and Progressive Disclosure
## Status
`locked`
## Problem Statement
Skill packages need clearer selection and loading boundaries without implicit permission escalation or platform-field assumptions.
## Why This Is Relevant
Explicit-only, model-eligible, and router categories plus four disclosure levels may reduce context load while preserving reviewability.
## Source Patterns
mattpocock/skills at `9603c1cc8118d08bc1b3bf34cf714f62178dea3b` is a methodology lead only; compatibility, token, and download claims remain unverified.
## Clean-room Boundary
Copy no code, command map, field, prompt, terminology, or installation behavior.
## Explicit Non-goals
No automatic invocation, install, download, update, permission grant, or execution.
## Inputs
Future local capability inventory and customer-approved trigger contract.
## Outputs
Future recommendation-only route decision and disclosure plan: Level 0 identity/risk/mode, Level 1 trigger/disable, Level 2 SKILL instructions, Level 3 requested references/scripts/assets.
## Permissions Required
Recommendation is not write permission, approval, or execution authority.
## Network Requirements
None for design.
## Dependency Requirements
None for design.
## Cost Possibility
Future routing may affect context cost; no estimate or cost occurs here.
## Customer Approval Gates
Approve routing rules, any path read, and every invoked action separately.
## Expected Benefits
More transparent selection and lower unnecessary context exposure.
## Failure Modes
False routing, hidden load, trigger overreach, unsupported field claim, or permission confusion.
## Baseline Comparison
Manual skill selection with all instructions read eagerly.
## Required Hard Gates
All gates; scope, human control, claim integrity, and no regression are critical.
## Evaluation Categories
Route accuracy, disclosure correctness, safety, ambiguity handling, and baseline utility.
## Promotion Constraints
Sandbox-only methodology until true routing evaluation and customer approval exist.
## Rejection Conditions
Reject automatic execution, unsupported Codex metadata claims, or permission bypass.
## Open Questions
Which disclosure signals can be expressed without depending on non-Codex fields?
