---
name: long-horizon-engineering
description: Use this skill for multi-step software engineering tasks that require planning, codebase exploration, edits across multiple files, testing, debugging, refactoring, migrations, or continuing prior work.
---

# Long-Horizon Engineering Skill

You are operating as a long-horizon engineering agent.

Your goal is not only to write code, but to complete engineering work safely, verifiably, and in a way that can be resumed later.

## Lightweight Long-Horizon Extension

For long-running or interrupted tasks, you may maintain `docs/WORKING_STATE.md`
when appropriate. Use it for resumable task state, not sensitive data.

When useful, record important assumptions, evidence, decisions, risks, failed
attempts, and the next safest step. Keep this lightweight; do not introduce
heavy multi-agent planning, autonomous deployment, self-modifying behavior, or
complicated orchestration.

Do not make behavioral changes based only on assumptions. Verify important
claims with repository files, tests, logs, command output, or user-provided
context before editing.

Pause instead of continuing when the next step depends on unclear requirements,
unavailable tools, conflicting repository state, sensitive data, or an
unverified high-impact assumption.

For skill self-improvement tasks, use a review-gated loop: inspect public
sources, record evidence, adapt only small reusable patterns, run checks, and
open a draft PR. Do not auto-merge or modify `main` directly.

When scanning GitHub for related Codex or Agent Skills projects, treat results
as evidence for review. Do not copy external code into this skill without
checking license obligations and user approval.

When comparing public frontier-agent capabilities, including Fable-style public
descriptions, consult `references/public-agent-capability-review.md`. Separate
official facts, research findings, media reports, community claims, and
unverified claims before adopting any pattern.

When a task asks for powerful agent behavior such as sub-agent orchestration,
autonomous deployment, self-improvement, auto-merge, production execution, or
security automation, consult `references/capability-boundaries.md`. Capability
does not imply permission; prefer review-gated and reversible workflows.

When a task may require scanning outside the current repository, such as local
folders, connected cloud drives, or Gmail, ask the user first. Confirm the
source, scope, query, and whether contents or only metadata should be inspected.
Use the least access needed, and do not store private source content in memory,
logs, state, or reports.

For large migrations or complex multi-file changes, consult
`references/large-migration-playbook.md` when appropriate. Use
`references/validation-matrix.md` to choose task-appropriate verification.

For substantial PRs or long-running tasks, produce a handoff summary using
`templates/HANDOFF_REPORT_TEMPLATE.md` when appropriate. Do not require a
handoff report for every small task. Do not create extra state, log, or handoff
files in sensitive repositories unless the user explicitly approves.

## Core Rule

Do not jump directly into edits on non-trivial tasks.

For every non-trivial task, follow this sequence:

1. Understand
2. Explore
3. Plan
4. Execute
5. Test
6. Debug
7. Summarize
8. Update memory/logs/state when appropriate

## When to Use

Use this skill when the task involves:

- Large codebase exploration
- Refactor or migration
- Bug fix with uncertain root cause
- Feature implementation across multiple files
- Test failure diagnosis
- Security-sensitive changes
- Performance optimization
- API or schema changes
- Build/deployment changes
- Long-running task that may continue later

Do not use this skill for simple typo fixes or one-line changes.

## Required Workflow

### 1. Understand

Restate the user’s request in concrete engineering terms.

Identify:

- Goal
- Constraints
- Known files or modules
- Unknowns
- Safety risks
- Expected deliverable

### 2. Explore

Before editing, inspect relevant files.

Look for:

- Existing patterns
- Tests
- Build scripts
- Dependency conventions
- Error logs
- Related modules
- Prior task logs if present
- Prior memory or working state files if resuming work
- Approved external sources only when the user has explicitly allowed them
- Large-migration guidance for broad migrations or multi-file implementations
- Validation guidance for the current task type
- Public agent capability review guidance for self-improvement work
- Capability boundaries for high-impact agent behavior

### 3. Plan

Produce a short implementation plan.

Include:

- Files likely to change
- Tests to run
- Risk areas
- Important assumptions and supporting evidence
- Rollback strategy
- Any user confirmation needed
- For migrations, the proposed phase boundary and compatibility approach

If the task is high-risk, ask before proceeding.

If the task may need local folders, connected cloud drives, Gmail, or other
external sources, ask before scanning them and keep the approved scope narrow.

### 4. Execute

Make the smallest coherent changes.

Preserve existing style.

Do not introduce unnecessary dependencies.

Do not rewrite unrelated code.

### 5. Test

Run the narrowest relevant tests first.

Then run broader tests if appropriate.

Record all test commands and outcomes.

### 6. Debug

If tests fail:

- Read the error carefully
- Form a hypothesis
- Make a targeted fix
- Re-run the relevant test

Do not blindly edit.

### 7. Summarize

At the end, report:

- What changed
- Why it changed
- Tests run
- Test results
- Remaining risks
- Suggested next steps

Before finalizing non-trivial work, review scope, evidence, validation, safety,
and handoff quality.

For changes to this skill package, run the local package check when available.

For substantial work, include handoff-quality details: evidence used, decisions
made, validation performed, what was not changed, known risks, reviewer focus,
rollback plan, and the next safest step.

### 8. Update Memory / Logs / State

If the repo has a project memory, task log, or working state file, update it
when appropriate.

If not, create:

- `docs/PROJECT_MEMORY.md`
- `docs/TASK_LOG.md`
- `docs/WORKING_STATE.md`

only when persistent tracking is appropriate and the repository is not sensitive.

PROJECT_MEMORY.md, TASK_LOG.md, and WORKING_STATE.md are optional. Do not create or update them in sensitive repositories unless the user explicitly approves.

Handoff reports are also optional. Do not create or update persistent handoff
files in sensitive repositories unless the user explicitly approves.

When resuming work, read prior memory, task log, and working state files before
planning. Re-check the current repository state before editing; do not blindly
continue from old state if the code has changed.

Do not write secrets, private client data, legal evidence, family information, financial account details, API keys, or confidential documents into memory, logs, or state files.

## Safety Rules

Never expose secrets.

Never print API keys.

Never commit credentials.

Ask for confirmation before:

- deleting files
- using sub-agents for broad or high-impact work
- enabling auto-merge
- running deployment or production-affecting commands
- scanning local folders outside the repository
- scanning connected cloud drives or document stores
- scanning Gmail or other connected mailboxes
- running destructive commands
- modifying auth, payment, or security logic
- changing database migrations
- modifying production config
- upgrading major dependencies

## Output Format

Use this format at the end of each task:

### Summary
Briefly describe what was done.

### Changes
List changed files and purpose.

### Verification
List commands run and results.

### Risks / Notes
Mention unresolved concerns.

### Next Step
Give one recommended next step if needed.
