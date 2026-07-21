# Experiment Proposal

## Experiment ID
`MAD-SKILL-007`
## Name
Allowlisted Local Knowledge Vault Bridge
## Status
`locked`
## Problem Statement
Local knowledge workflows need useful context without bulk vault scans, hidden writes, external directories, shell, MCP, or network access.
## Why This Is Relevant
An explicit path allowlist, secret exclusion, and write-diff approval can define a least-privilege future bridge.
## Source Patterns
Claudian is `verification_blocked`; no source commit, code, or compatibility claim is used.
## Clean-room Boundary
Use only the stated local-governance requirements; do not read a real Vault or external directory.
## Explicit Non-goals
No Vault indexing, sync, shell, MCP, network, external directory access, write, or daemon.
## Inputs
Future customer-approved exact local paths and exclusion rules.
## Outputs
Future read-only contract and future write-diff approval design.
## Permissions Required
Exact-path read approval; future writes require a separate exact diff approval.
## Network Requirements
None; future default remains false.
## Dependency Requirements
None; no connector is selected.
## Cost Possibility
Future local analysis may consume compute; no cost occurs here.
## Customer Approval Gates
Approve every path, exclusion, write diff, and external action separately.
## Expected Benefits
Bounded local context with visible permissions and no silent vault mutation.
## Failure Modes
Private-note exposure, path escape, hidden index, stale permissions, or accidental write.
## Baseline Comparison
Manual exact-path note reading with no bridge.
## Required Hard Gates
All gates; privacy, scope, isolation, rollback, and human control are critical.
## Evaluation Categories
Allowlist fidelity, secret exclusion, read-only behavior, and baseline utility.
## Promotion Constraints
Separate-skill only after real-path consent, synthetic evidence, and customer approval.
## Rejection Conditions
Reject bulk scan, external path, shell/MCP/network enablement, or implicit write.
## Open Questions
Can a portable allowlist work without assuming an Obsidian-specific runtime?
