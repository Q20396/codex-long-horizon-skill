---
name: long-horizon-engineering
description: Use for long-running software engineering work: repository exploration, multi-file changes, debugging, migrations, refactors, CI/build failures, staged validation, PR review response, or safe resumption. Do not use for simple edits, unrelated research, writing, media, or legal/financial tasks.
version: 0.2.0
repo: https://github.com/Q20396/codex-long-horizon-skill
skill_id: long-horizon-engineering
update_channel: stable
---

# Long-Horizon Engineering

Use this skill for non-trivial software engineering work that benefits from
careful exploration, staged implementation, validation, and resumable handoff.
The skill should make engineering decisions more evidence-backed, not broaden
into unrelated research or media workflows.

## Example Prompts

- Use the long-horizon-engineering skill. Explore the repository, plan the
  migration, implement it incrementally, run validation, and open a draft PR.
- Use the long-horizon-engineering skill. Debug this failing integration test
  across modules, identify root cause before editing, and verify the smallest
  safe fix.
- Use the long-horizon-engineering skill. Resume the interrupted refactor by
  reading prior state, checking current code, and reporting the next safest
  step before changing files.

## When To Use

Use this skill when the task involves one or more of:

- unfamiliar repository exploration
- multi-file implementation
- complex debugging or failing tests
- migrations, refactors, API changes, or schema changes
- CI, build-system, dependency, or performance work
- security-sensitive engineering review within authorized scope
- code review response or merge-readiness checks
- interrupted work that needs safe resumption
- validation-heavy engineering handoff

Do not use this skill implicitly for simple typos, one-line edits,
conversational answers, generic writing, video/storyboard planning, stock or
legal research, disaster monitoring, or unrelated data analysis. If the user
explicitly invokes this skill for a safe unusual workflow, follow the explicit
request while preserving the safety boundaries below.

## Failure Recovery

If work is interrupted, tests fail unexpectedly, requirements conflict, or the
repository changes underneath the task, stop and re-establish state before
editing. Re-read relevant instructions, inspect current files, separate facts
from assumptions, and continue only after the next safe step is clear.

Do not make behavioral changes based only on assumptions. Verify important
claims with repository files, tests, logs, command output, official docs, or
user-provided context before editing.

## Core Workflow

### 1. Understand

Restate the request in concrete engineering terms:

- goal
- constraints
- expected deliverable
- known files or modules
- unknowns and assumptions
- safety or privacy risks

### 2. Explore

Inspect relevant files before editing. Look for:

- existing patterns and ownership boundaries
- tests, build scripts, package managers, CI, and lint/typecheck commands
- related modules, schemas, APIs, migrations, and error logs
- prior task state if resuming work
- repository-specific instructions such as `AGENTS.md`

For large unfamiliar repositories, optionally consult
`references/repomix-codebase-context.md`; generated context is a map, not a
replacement for reading files you will edit.

### 3. Plan

Produce a short implementation plan when the work is non-trivial. Include:

- files likely to change
- validation commands
- risk areas
- important assumptions and supporting evidence
- rollback or containment strategy
- user confirmation needed before high-risk steps

For substantial work, also state the Definition of Done, in-scope and
out-of-scope paths, acceptance criteria and evidence, stop conditions, and the
rollback path. A plan is a proposal, not permission to edit, run high-impact
commands, or promote a result.

For complex implementation plans, use `templates/implementation-plan.md` when a
written plan would reduce risk.

### 4. Execute

Make the smallest coherent change that solves the task. Preserve local style,
avoid unrelated refactors, and do not introduce dependencies unless they are
needed and aligned with the project.

### 5. Validate

Run the narrowest relevant checks first, then broader checks when warranted.
Record commands and outcomes. For validation-heavy work, use
`templates/verification-evidence.md` when the reviewer needs a concise evidence
record.

For substantial work, distinguish execution evidence from the evaluator
conclusion. A passing command is evidence, not by itself proof that every
acceptance criterion was met. Map important requirements to direct evidence and
state any remaining gaps.

### 6. Debug

When validation fails, read the error, form a hypothesis, make a targeted fix,
and rerun the relevant check. Avoid blind edits.

### 7. Summarize

End with:

- what changed
- why it changed
- validation run and results
- known risks or limitations
- next safest step

For substantial work, include handoff-quality details: evidence used, decisions
made, what was not changed, reviewer focus, rollback notes, and remaining
uncertainty.

## Resumable State

`docs/PROJECT_MEMORY.md`, `docs/TASK_LOG.md`, `docs/WORKING_STATE.md`, and
handoff reports are optional. Use them only when persistent tracking is
appropriate, useful for resumption, and the repository is not sensitive.

Do not create or update persistent memory, logs, state, or handoff files in
sensitive repositories unless the user explicitly approves. When resuming work,
read existing memory/log/state files if present, then re-check the current
repository before editing. Compare the recorded branch, commit, working diff,
and last verification result with current state before relying on old notes.

Use:

- `references/resume-protocol.md` for interrupted-work recovery
- `references/planner-builder-evaluator-loop.md` for role-based planning,
  execution, evidence review, and human disposition on substantial tasks
- `references/decision-log.md` for fact, assumption, decision, evidence, risk,
  and follow-up tracking
- `templates/WORKING_STATE_TEMPLATE.md` or
  `templates/HANDOFF_REPORT_TEMPLATE.md` only when a persistent record is safe
  and useful

## Core References

Load only the references that match the task:

- `references/protocol.md` for the baseline long-horizon workflow
- `references/safety-policy.md` for safety rules
- `references/client-privacy.md` for client or confidential data
- `references/capability-boundaries.md` for high-impact agent behavior
- `references/stop-conditions.md` for when to pause
- `references/validation-matrix.md` for choosing verification
- `references/systematic-debugging-protocol.md` for root-cause debugging
- `references/large-migration-playbook.md` for broad migrations
- `references/code-review-response-protocol.md` for reviewer or CI feedback
- `references/security-review-protocol.md` for defensive security review
- `references/ship-readiness-protocol.md` for merge/release readiness
- `references/external-search-protocol.md` when current public technical facts
  are necessary

## Explicit-Only Extensions

Some bundled references support adjacent or experimental workflows, but they do
not broaden implicit activation. Use them only when the user explicitly invokes
this skill or explicitly requests that workflow. Do not select this skill
implicitly for those domains merely because a reference exists.

See `references/explicit-only-extensions.md` for the index covering writing,
research, notebook, presentation, financial, jurisdiction, disaster monitoring,
external skill discovery, skill lifecycle, SkillOpt-style optimization, and
other optional workflows.

For explicitly authorized work with an Obsidian vault, Markdown note, JSON
Canvas, or Obsidian Base, use `references/obsidian-knowledge-workflow.md`.
Default to a proposal and exact-path approval; do not scan, index, sync, or
write to a vault automatically.

AI video briefs, storyboards, shot lists, visual prompts, asset manifests, and
render handoffs belong to the `ai-video-production` skill unless the task is
engineering work on a video codebase, such as debugging a multi-file Remotion
rendering bug or migrating a rendering repository.

## Role Boundaries

Planner, Builder, and Evaluator are serial working roles, not autonomous
sub-agents, permission tiers, or a self-approving loop. The Planner proposes a
bounded task contract, the Builder performs only approved work, and the
Evaluator reviews evidence and reports findings. The Evaluator does not edit,
approve its own proposal, or authorize push, merge, deployment, publication, or
other high-impact actions. Human approval remains required for those actions.

## Safe Update / Self-Check Protocol

When the user asks to check for updates, update skills, upgrade skills, or
compare installed skills with GitHub, first ask for explicit permission to
access:

`https://github.com/Q20396/codex-long-horizon-skill`

Explain that this first permission is only for checking updates and temporarily
downloading or cloning the repository. During the check phase, do not install,
replace, delete, or modify installed skills.

After permission, compare installed local skills with the GitHub version.

Installed local paths:

- `~/.agents/skills/long-horizon-engineering`
- `~/.agents/skills/ai-video-production`

Remote repo paths:

- `.agents/skills/long-horizon-engineering`
- `.agents/skills/ai-video-production`

Summarize:

1. local version
2. remote version
3. changed files
4. added files
5. removed files
6. important instruction changes
7. risk level
8. upgrade recommendation
9. backup path that would be used
10. rollback plan

Ask for explicit second approval before applying any update. If applying an
update, create a timestamped backup first, replace only the selected approved
skill folder, validate that `SKILL.md` exists, validate that the folder is not
empty, validate there is no duplicated nested path such as
`.agents/skills/.agents/skills`, report exact files changed, and print the
rollback command. If anything fails, restore from backup where possible.

Never silently update. Never update all skills unless the user explicitly
approves all skills. Prefer check-only mode unless the user clearly asks to
apply an update.

## Safety Rules

Never expose secrets, print API keys, commit credentials, or copy private
content into reusable logs. Treat client, private, legal, financial, family,
medical, identity, business, and confidential research data as sensitive by
default.

Do not auto-merge. Do not store secrets, API keys, private client data, legal
evidence, family information, financial account details, identity documents,
private correspondence, or confidential documents in memory, logs, state files,
handoff files, commits, public PRs, or examples.

Before reading sensitive materials, tell the user why access is needed, which
files or folders would be read, whether metadata is enough, whether content
would be quoted, summarized, or recorded, and how sensitive content will be
minimized or omitted. Wait for explicit approval before reading sensitive
content.

Ask for confirmation before:

- reading, modifying, staging, committing, pushing, or summarizing sensitive
  client or confidential materials
- deleting files or running destructive commands
- using sub-agents for broad or high-impact work
- enabling auto-merge, deployment, or production-affecting commands
- scanning local folders outside the repository
- scanning connected cloud drives, document stores, Gmail, or mailboxes
- using device location, GPS, or precise location data
- modifying auth, payment, security, database migration, production config, or
  major dependency behavior
- uploading source material to external providers or tools

If uncertain whether a file or action is sensitive, stop and ask.

## Final Reporting Contract

For substantial tasks, report:

### Summary

Briefly describe the outcome.

### Changes

List changed files and their purpose.

### Verification

List commands run and results. Say clearly if a command was unavailable or not
run.

### Risks / Notes

Mention unresolved concerns, safety boundaries, and review focus.

### Next Step

Give one recommended next step when useful.
