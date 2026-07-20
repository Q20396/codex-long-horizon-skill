# Experiment Proposal

## Experiment ID
`MAD-SKILL-003`

## Name
Auditable Source-to-Skill Compiler

## Status
`locked`

## Problem Statement
Customers need a traceable way to turn material they are authorized to use into a bounded candidate Skill structure.

## Why This Is Relevant
Source location, rights, citation index, glossary, patterns, cheatsheet, confidence, applicability, expiry, and on-demand loading can improve reviewability.

## Source Patterns
virgiliojr94/book-to-skill at `d8d9f2cf309d29687fcf2e20f972dd790e2db79d` is a methodology lead only.

## Clean-room Boundary
Copy no code, book text, source examples, or proprietary organization. Do not read unapproved books, PDFs, or private files.

## Explicit Non-goals
No document ingestion, OCR, full-text copying, private corpus, automatic Skill creation, or external upload.

## Inputs
Future customer-approved source manifest with rights and citation boundaries.

## Outputs
Future source index, glossary, pattern inventory, confidence labels, and bounded candidate outline.

## Permissions Required
Future exact-file read approval and proof of use rights; no write approval follows.

## Network Requirements
None for design; future network use needs separate approval.

## Dependency Requirements
None for design; no parser or model is selected.

## Cost Possibility
Future extraction may cost local compute or provider quota; none occurs here.

## Customer Approval Gates
Approve each source, rights assertion, citation range, output location, and later execution separately.

## Expected Benefits
Reusable knowledge with provenance and boundaries rather than an opaque copied prompt.

## Failure Modes
Copyright breach, sensitive-content retention, unsupported inference, stale provenance, or overbroad reuse.

## Baseline Comparison
Manual notes with no structured provenance or applicability record.

## Required Hard Gates
All gates; source identity, license, privacy, scope, and claim integrity are critical.

## Evaluation Categories
Traceability, task quality, safety, permissions, reversibility, maintenance, and explainability.

## Promotion Constraints
Remain sandbox-only methodology until rights, attribution, synthetic evidence, and a customer decision exist.

## Rejection Conditions
Reject if rights are unclear, source text must be copied broadly, or applicability cannot be bounded.

## Open Questions
What smallest provenance schema is useful without creating a knowledge vault?
