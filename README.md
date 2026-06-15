# codex-long-horizon-skill

Reusable Codex skill package for long-horizon software engineering work.

This repository contains the `long-horizon-engineering` skill, which can be
copied into another coding project so Codex has a structured workflow for
multi-step engineering tasks.

## Official Codex Skill Structure

A Codex skill is a directory containing a required `SKILL.md` file. It can also
include optional supporting folders such as `scripts`, `references`, and
`assets`. Codex first reads the skill metadata to decide whether the skill is
relevant. If the skill is selected, Codex then reads the full `SKILL.md`
instructions.

In this repository, the skill is packaged at:

```text
.agents/skills/long-horizon-engineering/
```

## Recommended Installation Path

Place this skill directory in the root of a coding project at:

```text
.agents/skills/long-horizon-engineering/
```

The expected installed structure is:

```text
AGENTS.md
README.md
.agents/
  skills/
    long-horizon-engineering/
      SKILL.md
      references/
        protocol.md
        safety-policy.md
        context-compaction.md
        continuous-improvement.md
        decision-log.md
        external-source-scan.md
        large-migration-playbook.md
        public-agent-capability-review.md
        review-checklist.md
        resume-protocol.md
        stop-conditions.md
        validation-matrix.md
      templates/
        HANDOFF_REPORT_TEMPLATE.md
        PROJECT_MEMORY_TEMPLATE.md
        IMPROVEMENT_SCAN_TEMPLATE.md
        TASK_LOG_TEMPLATE.md
        WORKING_STATE_TEMPLATE.md
      scripts/
        append_project_memory.py
        check_skill_package.py
        github_skill_scan.py
        update_task_log.py
```

## What This Repository Is

This repository is a portable skill package, not an application. It contains:

- Repository-level Codex instructions in `AGENTS.md`
- The required skill instructions in `SKILL.md`
- Supporting workflow references
- Reusable Markdown templates for project memory and task logs
- Small local helper scripts for appending non-sensitive notes

## What The Skill Does

`long-horizon-engineering` gives Codex a repeatable workflow for engineering
tasks that should not be handled as quick one-shot edits. It guides Codex to:

1. Understand the request.
2. Explore the repository before editing.
3. Plan the smallest safe change.
4. Execute with minimal scope.
5. Test or otherwise verify the result.
6. Debug targeted failures.
7. Summarize the outcome.
8. Update memory or logs only when appropriate and safe.

The goal is to make long-running or multi-step work safer, easier to review, and
easier to resume later.

## Why SKILL.md Is Required

`SKILL.md` anchors the skill. Its front matter provides the skill name and
description that Codex can use to decide whether the skill is relevant. The rest
of the file contains the full instructions Codex follows after the skill is
selected.

Do not rename the skill unless you also update every instruction that refers to
`long-horizon-engineering`.

## Optional Supporting Folders

The skill can include optional folders to keep `SKILL.md` focused while still
providing useful supporting material.

### references/

Use `references/` for longer guidance that Codex may consult after the skill is
selected. This package includes:

- `protocol.md` for the long-horizon engineering workflow
- `safety-policy.md` for protected areas and safety expectations
- `context-compaction.md` for preserving lightweight state before interruption
  or context loss
- `continuous-improvement.md` for safe, review-gated periodic skill improvement
- `decision-log.md` for separating facts, assumptions, decisions, evidence,
  risks, and follow-ups
- `external-source-scan.md` for consent-gated scans of local folders, connected
  cloud drives, Gmail, or other external sources
- `large-migration-playbook.md` for phased, reviewable large migrations and
  complex multi-file implementations
- `public-agent-capability-review.md` for safely learning from public frontier
  coding-agent capabilities without copying external code or trusting rumors
- `review-checklist.md` for final scope, evidence, validation, safety, and
  handoff checks
- `resume-protocol.md` for safely continuing interrupted work
- `stop-conditions.md` for knowing when to pause instead of continuing
- `validation-matrix.md` for choosing verification steps by task type

### templates/

Use `templates/` for reusable starter documents. This package includes:

- `HANDOFF_REPORT_TEMPLATE.md` for substantial PR or long-running task handoff
  summaries
- `PROJECT_MEMORY_TEMPLATE.md` for durable, non-sensitive project facts
- `IMPROVEMENT_SCAN_TEMPLATE.md` for periodic skill improvement scans
- `TASK_LOG_TEMPLATE.md` for concise completed-task notes
- `WORKING_STATE_TEMPLATE.md` for resumable in-progress task state

Templates are structure only. They are not a place to store sensitive content.

### scripts/

Use `scripts/` for simple local helpers. This package includes:

- `append_project_memory.py` to append facts to `docs/PROJECT_MEMORY.md`
- `check_skill_package.py` to validate the package structure
- `github_skill_scan.py` to scan public GitHub projects for review-gated
  improvement evidence
- `update_task_log.py` to append completed task entries to `docs/TASK_LOG.md`

The scripts are intentionally local-only. They do not read environment
variables, make network calls, delete files, or require external dependencies.

### assets/

An `assets/` folder may be added later for static support files such as images,
fixtures, or examples. Keep assets non-sensitive and avoid adding large files
unless they are necessary for the skill.

## How AGENTS.md And SKILL.md Work Together

`AGENTS.md` gives repository-level instructions to Codex. In a project using
this package, it should tell Codex when to use the `long-horizon-engineering`
skill and state broad expectations such as reading files before editing, making
small verifiable changes, and avoiding secrets.

`SKILL.md` is the skill-specific instruction file. When the skill is triggered,
Codex should read it and follow its workflow for the current task.

In practice:

- Use `AGENTS.md` to route Codex toward the skill.
- Use `SKILL.md` to define the actual long-horizon workflow.
- Use `references/` when the workflow needs more detail.
- Use `templates/` and `scripts/` only when persistent tracking is appropriate.

## Long-Horizon Resume Support

`docs/WORKING_STATE.md` is optional and can be used for resumable task state
when a task is long-running, interrupted, or likely to continue after context
compaction. It should capture the current goal, status, inspected and changed
files, confirmed facts, assumptions, decisions, failed attempts, test results,
known risks, and the next safest step.

`references/context-compaction.md` describes what to preserve before a task is
paused, interrupted, or compacted.

`references/decision-log.md` helps prevent unsupported assumptions by separating
facts, assumptions, decisions, evidence, risks, and follow-ups.

`references/resume-protocol.md` helps Codex continue safely after interruption
by reading prior memory, task logs, working state, relevant files, and prior logs
before planning the next change.

`references/stop-conditions.md` helps Codex pause when requirements, tools,
repository state, or safety concerns make continued edits risky.

`references/review-checklist.md` helps Codex check scope, evidence, validation,
safety, and handoff quality before finalizing work.

`references/large-migration-playbook.md` helps Codex map a codebase, divide
large migrations into reviewable phases, preserve compatibility where possible,
validate in layers, and stop for user confirmation on high-risk decisions.

`references/validation-matrix.md` helps Codex choose verification steps that
match the task type, such as bug fixes, refactors, migrations, UI changes,
performance work, security-sensitive changes, or documentation-only changes.

`references/external-source-scan.md` explains how Codex should ask before
scanning local folders outside the repository, connected cloud drives, Gmail, or
other external sources. External scans are optional and should use the narrowest
approved scope.

`references/continuous-improvement.md` defines a safe self-improvement loop:
check related public skills and agent projects, record evidence, adapt only
small reusable patterns, run checks, and open a draft PR for review.

`references/public-agent-capability-review.md` helps Codex compare public
frontier-agent capability descriptions, classify source reliability, separate
verified facts from unverified claims, and translate useful themes into small
review-gated improvements.

These files are optional and safety-aware. Do not create or update
`PROJECT_MEMORY.md`, `TASK_LOG.md`, or `WORKING_STATE.md` in sensitive
repositories unless the user explicitly approves. Do not use them to store
private or sensitive content.

## Final Long-Horizon Engineering Supports

This package includes three final lightweight supports for harder engineering
work:

- `references/large-migration-playbook.md` supports large codebase migrations
  and complex multi-file implementations.
- `references/validation-matrix.md` helps Codex choose task-appropriate
  verification instead of using one generic test strategy.
- `templates/HANDOFF_REPORT_TEMPLATE.md` supports human review of substantial
  PRs or long-running tasks.

These supports are optional. They should not create sensitive logs or persistent
handoff files by default, and they should not be used to store secrets, API
keys, legal evidence, family information, private client data, financial account
details, or confidential documents.

## Continuous Improvement

This skill can support a weekly improvement scan, but it should be review-gated.
Codex may check public Codex, Agent Skills, and long-horizon coding-agent
projects for relevant changes, then propose small updates through a draft PR.

The safe loop is:

1. Inspect public sources and related skill projects.
2. Record facts, assumptions, risks, and links.
3. Identify small reusable patterns, not code to copy.
4. Update this repository only when the change is evidence-backed.
5. Run `check_skill_package.py`.
6. Open a draft PR for user review.

Do not auto-merge. Do not push directly to `main`. Do not copy external code
without checking license obligations. Do not store private or sensitive content
in improvement scans.

When a capability comes from public reporting rather than official
documentation or reproducible research, treat it as a signal to investigate, not
as verified fact.

Use the template:

```bash
cp .agents/skills/long-horizon-engineering/templates/IMPROVEMENT_SCAN_TEMPLATE.md docs/IMPROVEMENT_SCAN.md
```

Create or update that file only when persistent tracking is appropriate and the
repository is not sensitive.

To collect public GitHub signals manually:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/github_skill_scan.py --dry-run --limit 3
```

Remove `--dry-run` to write `docs/GITHUB_SKILL_SCAN.md`. Treat the report as
evidence for review, not as permission to copy external code.

## External Source Scans

Codex may sometimes need to know whether related files were added, removed, or
changed outside the current repository. For example, the user may want Codex to
check a selected local folder, connected cloud drive, or Gmail search.

This skill treats those sources as sensitive by default. Codex should ask before
scanning them and confirm:

- Source type, such as local folder, cloud drive, or Gmail
- Exact folder, label, query, or date range
- Whether to inspect file contents or only metadata
- Whether results may be summarized in task notes

Use repository-only scanning when that is enough. Do not scan broad personal
folders, full mailboxes, or cloud drives without a specific approved scope. Do
not store secrets, personal messages, private client data, financial account
details, legal evidence, family information, API keys, or confidential documents
in memory, logs, working state, or generated reports.

## Copying This Skill Into Another Project

From another repository root, copy the skill directory:

```bash
mkdir -p .agents/skills
cp -R path/to/codex-long-horizon-skill/.agents/skills/long-horizon-engineering .agents/skills/
```

Then add or update that project’s `AGENTS.md` with a short instruction such as:

```markdown
When a task involves multi-step engineering work, use the
`long-horizon-engineering` skill.
```

If the target repository already has a `.agents/skills/long-horizon-engineering`
directory, review the files before overwriting local customizations.

## How To Ask Codex To Use It

You can ask directly:

```text
Use the long-horizon-engineering skill.
```

You can also describe a task that clearly matches the skill, such as a
multi-file bug fix, migration, refactor, or long-running implementation.

## Usage Example

Here is an exact prompt you can give Codex:

```text
Use the long-horizon-engineering skill.
Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
```

## When To Use This Skill

Use this skill for:

- Large codebase exploration
- Multi-file changes
- Refactors or migrations
- Bug fixes with uncertain root cause
- Test failure diagnosis
- Security-sensitive changes
- Performance optimization
- API, schema, build, deployment, or CI changes
- Work that may need to be resumed later

## When Not To Use This Skill

Do not use this skill for:

- Simple typo fixes
- One-line edits
- Purely conversational answers
- Tiny formatting-only changes
- Tasks where persistent planning or logging would add unnecessary overhead
- Sensitive repositories where project memory or task logs would be unsafe

## Maintaining PROJECT_MEMORY.md

`docs/PROJECT_MEMORY.md` is optional. Create or update it only when persistent
tracking is appropriate and the repository is not sensitive.

Use it for durable, non-sensitive facts that future Codex runs should remember,
such as:

- Package manager and common commands
- Stable repository conventions
- Architecture notes
- Important technical decisions
- Known safe follow-ups

Create it from the template when appropriate:

```bash
mkdir -p docs
cp .agents/skills/long-horizon-engineering/templates/PROJECT_MEMORY_TEMPLATE.md docs/PROJECT_MEMORY.md
```

Append a fact with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/append_project_memory.py "Use npm for frontend package management."
```

Preview without writing:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/append_project_memory.py --dry-run "Use npm for frontend package management."
```

Only add facts that are expected to remain useful across future tasks.

## Maintaining TASK_LOG.md

`docs/TASK_LOG.md` is optional. Create or update it only when persistent tracking
is appropriate and the repository is not sensitive.

Use it to record completed engineering tasks in a concise, resumable format:

- What changed
- Why it changed
- Files touched
- Verification commands and results
- Remaining risks or follow-ups

Create it from the template when appropriate:

```bash
mkdir -p docs
cp .agents/skills/long-horizon-engineering/templates/TASK_LOG_TEMPLATE.md docs/TASK_LOG.md
```

Append a completed task entry with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_task_log.py \
  --title "Add health check endpoint" \
  --summary "Added a lightweight API health check." \
  --file "src/server.ts" \
  --verification "npm test passed" \
  --notes "No known follow-up."
```

Preview without writing:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_task_log.py \
  --dry-run \
  --title "Add health check endpoint" \
  --summary "Added a lightweight API health check."
```

## Checking The Skill Package

Run the local structure check before publishing changes:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
```

The check verifies the required files, `SKILL.md` front matter, and absence of
nested `.agents` directories.

## Safe Use Warning

Do not store:

- Secrets
- API keys
- Legal evidence
- Family information
- Private client data
- Financial account information
- Confidential documents

Use templates only as reusable structure, not as a place for sensitive content.
Project memory and task logs should contain durable, non-sensitive engineering
context only.
