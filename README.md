# codex-long-horizon-skill

Codex long-horizon engineering skill package for multi-step software work.

## What This Skill Does

`long-horizon-engineering` gives Codex a repeatable workflow for engineering
tasks that need more than a quick edit. It emphasizes understanding the request,
exploring the repository, making small safe changes, validating the result, and
recording durable context so future runs can resume with less rediscovery.

## When To Use It

Use this skill when a task involves:

- Multi-file code changes
- Refactors or migrations
- Debugging with uncertain root cause
- Test failure triage
- Build, deployment, or CI changes
- Security-sensitive or data-sensitive areas
- Work that may need to be resumed later

Do not use it for tiny one-line edits, simple formatting fixes, or answers that
do not require repository changes.

## Recommended Repository Structure

Install the skill package in the repository with this structure:

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
      templates/
        PROJECT_MEMORY_TEMPLATE.md
        TASK_LOG_TEMPLATE.md
      scripts/
        append_project_memory.py
        update_task_log.py
```

Projects using the skill may also keep runtime notes in:

```text
docs/
  PROJECT_MEMORY.md
  TASK_LOG.md
```

Use the templates as starting points for those `docs/` files. Keep the files
short, factual, and safe to store in the repository.

## How Codex Should Use AGENTS.md And SKILL.md

`AGENTS.md` is the repository-level instruction file. It tells Codex when to use
the `long-horizon-engineering` skill and sets general expectations for safe work
inside the repo.

`SKILL.md` is the skill contract. When Codex uses the skill, it should read and
follow the workflow in `SKILL.md`:

1. Understand the user request.
2. Explore relevant files before editing.
3. Plan the smallest safe change.
4. Execute the change.
5. Test or otherwise verify it.
6. Debug targeted failures.
7. Summarize what changed.
8. Update memory or task logs when useful.

The reference files provide supporting guidance:

- `references/protocol.md` describes the long-horizon engineering workflow.
- `references/safety-policy.md` lists protected areas and safety rules.

## Maintaining PROJECT_MEMORY.md

`docs/PROJECT_MEMORY.md` should contain durable, non-sensitive facts that future
Codex runs should remember, such as:

- Package manager and common commands
- Project architecture notes
- Stable repository conventions
- Important technical decisions
- Known safe follow-ups

Create it from:

```bash
cp .agents/skills/long-horizon-engineering/templates/PROJECT_MEMORY_TEMPLATE.md docs/PROJECT_MEMORY.md
```

You can append a fact with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/append_project_memory.py "Use npm for frontend package management."
```

Only add facts that are expected to remain useful across future tasks.

## Maintaining TASK_LOG.md

`docs/TASK_LOG.md` should record completed engineering tasks in a concise,
resumable format. Each entry should include:

- What changed
- Why it changed
- Files touched
- Verification commands and results
- Remaining risks or follow-ups

Create it from:

```bash
cp .agents/skills/long-horizon-engineering/templates/TASK_LOG_TEMPLATE.md docs/TASK_LOG.md
```

You can append a completed task entry with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/update_task_log.py \
  --title "Add health check endpoint" \
  --summary "Added a lightweight API health check." \
  --file "src/server.ts" \
  --verification "npm test passed" \
  --notes "No known follow-up."
```

## Safety Warning

Never store secrets, private client data, legal evidence, family information,
API keys, tokens, credentials, or other sensitive personal data in public logs,
templates, task history, or project memory.

The helper scripts are intentionally simple: they append local Markdown files
under `docs/`, create those files if missing, do not read environment variables,
do not make network calls, and do not delete files.
