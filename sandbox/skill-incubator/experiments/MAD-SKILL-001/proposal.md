# Experiment Proposal

## Experiment ID
`MAD-SKILL-001`

## Name
Safe Project Map and Context Budget

## Status
`locked`

## Problem Statement
Large repositories need a bounded evidence-linked structural map without a repository-wide read, persistent index, or unsupported token-saving claim.

## Why This Is Relevant
An exact-path map may reduce repeated orientation work while preserving privacy and evidence rules.

## Source Patterns
Graphify-Labs/graphify at `edec9eabeceeae6aa2375eddb3835efa1a32c0a3` is a methodology lead only; its implementation and claims are excluded.

## Clean-room Boundary
Design from the stated problem and local governance only. Copy no source code, schema, prompt, terminology, or output.

## Explicit Non-goals
No index, graph database, broad scan, sync, model call, secret discovery, or automatic context injection.

## Inputs
Future customer-approved exact paths and an explicit context budget.

## Outputs
Future reviewable map manifest, evidence links, exclusions, and budget report.

## Permissions Required
Future exact-path read approval; no write approval follows from this proposal.

## Network Requirements
None for design; future egress needs separate approval.

## Dependency Requirements
None for design; no dependency is selected.

## Cost Possibility
Future analysis may consume local compute or tokens; no cost is incurred here.

## Customer Approval Gates
Approve source paths, exclusions, artifact location, and execution separately.

## Expected Benefits
More reproducible orientation and narrower file reads than an unbounded scan.

## Failure Modes
Stale maps, sensitive-file inclusion, misleading structure, and budget overrun.

## Baseline Comparison
Manual exact-path exploration with no persistent map.

## Required Hard Gates
All ten gates, especially scope, privacy, isolation, and claim integrity.

## Evaluation Categories
Task quality, reliability, safety, permissions, reversibility, efficiency, maintenance, explainability, and cross-platform compatibility.

## Promotion Constraints
Remain sandbox-only until separate license, privacy, baseline, and customer approval evidence exists.

## Rejection Conditions
Reject broad reads, hidden persistence, unapproved writes, or no baseline gain.

## Open Questions
What minimum map format helps orientation without becoming a runtime?
