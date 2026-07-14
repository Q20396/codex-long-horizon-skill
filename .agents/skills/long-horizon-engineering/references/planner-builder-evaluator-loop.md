# Planner, Builder, Evaluator Loop

Use this lightweight control loop for substantial, risky, or long-running
engineering tasks. It improves continuity and verification without creating an
autonomous multi-agent system.

The roles may be performed serially by one Codex session. They are not separate
agents, do not grant extra permissions, and cannot approve their own work.

## Roles

### Planner

The Planner turns the request into a bounded proposal. It records:

- goal and non-goals
- Definition of Done
- likely files and planned file scope
- assumptions and supporting evidence
- acceptance criteria and validation evidence
- risks, rollback, and stop conditions
- approvals needed before sensitive or high-impact actions

The plan is not write permission. It does not authorize edits, network access,
sensitive reads, installation, push, merge, deployment, publication, or
release.

### Builder

The Builder performs the approved, bounded work. It should:

- inspect current state before each material edit
- keep changes within the approved scope
- report material deviations instead of silently expanding scope
- run the planned checks and retain concise evidence
- stop when a safety boundary, failed assumption, or new approval requirement
  is encountered

The Builder does not promote a change merely because a command passed.

### Evaluator

The Evaluator compares the accepted criteria with evidence from the repository,
tests, command output, and approved sources. It should report:

- each criterion, expected behavior, direct evidence, and result
- missing evidence and known blind spots
- remaining risks and the safest recommended disposition
- whether a correction, re-plan, or human decision is needed

The Evaluator is proposal-only. It must not edit files, silently retry until a
desired result appears, change requirements, weaken validation, approve its own
proposal, or authorize push, merge, deployment, publication, or release.

## Control Flow

1. Planner creates a bounded task contract.
2. A human approves any required scope or high-impact action.
3. Builder makes the smallest coherent change and collects evidence.
4. Evaluator maps evidence to acceptance criteria.
5. A human accepts, rejects, narrows, or requests a bounded correction.

Corrections must remain scoped and be revalidated. Do not run an unbounded
plan-build-evaluate loop, create background jobs, delegate automatically, or
claim completion without evidence.

## Continuity And Context Compaction

For an interrupted task, optional working state may record the last verified
commit, command, result, changed files, known risks, and next safest step. It
is not a substitute for current inspection. Before resuming, compare the
recorded state with the actual branch, commit, staged and unstaged diff,
relevant files, and current checks.

Do not store secrets, API keys, client names, legal evidence, family
information, medical information, financial account details, identity
documents, private correspondence, or confidential content in state, logs, or
handoff records.

## Evidence Standard

Use the strongest practical evidence for the task:

- targeted tests for specified behavior
- package, lint, type, build, or CI checks for affected contracts
- diff inspection for scope and unintended changes
- screenshots or manual verification when a user-facing behavior requires it
- explicit documentation review for documentation-only changes

Formatting, a green command, or an evaluator summary alone does not prove the
requested behavior. State what was not verified and why.

## Human Gate

Human approval is required for sensitive reads, network access, destructive
commands, installation, update, push, merge, deployment, publication, release,
and any other high-impact action. A recommendation does not grant permission.
