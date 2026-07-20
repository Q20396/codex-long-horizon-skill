# Experiment Proposal

## Experiment ID
`MAD-SKILL-004`

## Name
Plan and Render Separation

## Status
`locked`

## Problem Statement
Media workflows can blur low-risk planning with high-impact rendering, upload, provider selection, and cost.

## Why This Is Relevant
Separating planning -> script -> storyboard -> asset needs -> provider choice -> customer approval -> render -> acceptance protects users before any media action.

## Source Patterns
Emily2040/seedance-2.0 at `57d01dc66f93ecb03c2475be5f22dc416d9b701d` and existing planning principles are methodology leads only.

## Clean-room Boundary
Copy no provider code, visual prompt, model behavior, media asset, or external workflow implementation.

## Explicit Non-goals
No provider call, upload, model download, media generation, voice synthesis, image synthesis, rendering, or external publish.

## Inputs
Future customer-approved brief, factual source list, audience, style, and delivery constraints.

## Outputs
Future script, storyboard, asset plan, provider-neutral handoff, and acceptance checklist.

## Permissions Required
Planning is separate from provider, file-read, upload, and render approvals.

## Network Requirements
None for design and planning; future provider access needs separate approval.

## Dependency Requirements
None for design; no renderer or model is selected.

## Cost Possibility
Rendering and providers may cost money or quota; no cost occurs here.

## Customer Approval Gates
Approve source use, asset plan, provider choice, render settings, output destination, and publish separately.

## Expected Benefits
Reviewable creative decisions before cost, external transfer, or irreversible output.

## Failure Modes
Inaccurate script, rights issue, unsuitable asset, provider mismatch, cost surprise, or accidental publication.

## Baseline Comparison
Direct generation request with no separated plan or approval gate.

## Required Hard Gates
All gates; privacy, source rights, provider scope, cost, and human control are critical.

## Evaluation Categories
Plan completeness, factual accuracy, rights clarity, approval clarity, safety, and rollback readiness.

## Promotion Constraints
Remain bundled-optional planning only until synthetic evidence and customer approval exist.

## Rejection Conditions
Reject if planning implies provider execution, upload, hidden cost, or publication.

## Open Questions
Which handoff fields are portable across renderers without claiming compatibility?
