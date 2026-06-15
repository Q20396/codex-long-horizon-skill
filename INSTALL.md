# Installation

This repository contains the reusable `long-horizon-engineering` Codex skill.

## Copy Into A Project

From the target project root:

```bash
mkdir -p .agents/skills
cp -R path/to/codex-long-horizon-skill/.agents/skills/long-horizon-engineering .agents/skills/
```

Then add or update the target project's `AGENTS.md`:

```markdown
When a task involves multi-step engineering work, use the
`long-horizon-engineering` skill.
```

## Recommended Path

```text
.agents/skills/long-horizon-engineering/
```

## Verify The Package

From this repository root:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
```

## Prompt Example

```text
Use the long-horizon-engineering skill.
Explore the codebase first, make a plan, then implement the change in a new branch and open a draft pull request for review.
```

## Safety

Do not store secrets, API keys, legal evidence, family information, private
client data, financial account details, or confidential documents in memory,
logs, state files, examples, or handoff reports.
