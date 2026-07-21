# Experiment Proposal

## Experiment ID
`MAD-SKILL-010`
## Name
Privacy-Gated Demonstration-to-Skill
## Status
`locked`
## Problem Statement
Repeated low-risk human operations may be useful to describe, but recording and replay can expose private data or create irreversible external effects.
## Why This Is Relevant
Separating recording approval, operation-extraction approval, replay approval, and external-action approval preserves customer control.
## Source Patterns
Official Codex Record & Replay documentation is platform-gated; it has no repository commit and is not enabled.
## Clean-room Boundary
Use only stated privacy and approval concepts; do not record, invoke Computer Use, copy platform behavior, or access a live application.
## Explicit Non-goals
No recording, replay, login, upload, send, payment, deletion, publish, or external write.
## Inputs
Future customer-approved low-risk synthetic demonstration description.
## Outputs
Future preview-only operation outline and approval matrix.
## Permissions Required
Each recording, extraction, replay, and external action needs its own approval.
## Network Requirements
None for design.
## Dependency Requirements
None for design.
## Cost Possibility
Future platform use may consume quota; none occurs here.
## Customer Approval Gates
Four separate approvals plus exact external-action approval are mandatory.
## Expected Benefits
Transparent reusable operation descriptions without silently capturing or replaying activity.
## Failure Modes
Private capture, accidental replay, external send, deletion, payment, publication, or false preview claim.
## Baseline Comparison
Manual one-off operation with no reusable outline.
## Required Hard Gates
All gates; privacy, human control, scope, rollback, and claim integrity are critical.
## Evaluation Categories
Approval separation, preview fidelity, privacy protection, and baseline utility.
## Promotion Constraints
Platform-gated only; remain locked until platform availability, synthetic evidence, and customer approval exist.
## Rejection Conditions
Reject any recording, Computer Use, real account, external write, payment, deletion, or publish behavior.
## Open Questions
Can a useful preview-only outline be evaluated without any observed interaction?
