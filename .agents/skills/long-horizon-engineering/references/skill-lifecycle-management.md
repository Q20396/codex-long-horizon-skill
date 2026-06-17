# Skill Lifecycle Management

Use this optional protocol when an installed project has many skills and the
customer wants a smoother, smaller active skill set.

The goal is to keep core safety and engineering behavior active while moving
rarely used optional skills into a recoverable frozen state. Do not delete
skills automatically.

## Core Rule

Freeze skills only after customer approval. Restore or update skills only after
customer approval. Do not silently download, overwrite, or remove skills.

## Lifecycle States

- `active`: installed under `.agents/skills/<skill-name>/`
- `frozen`: moved to `.agents/skills.disabled/<skill-name>/`
- `available remotely`: not installed locally, but available from an approved
  source such as the public skill package repository
- `unknown`: not installed and no approved source is configured

## Core Skills

Keep the long-horizon engineering skill active by default because it contains
the safety, privacy, update, review, and recovery protocols.

Do not freeze safety, privacy, install, update, or lifecycle management support
unless the customer explicitly understands the impact and has another recovery
path.

## Usage Tracking

Usage tracking must be non-sensitive. Store only:

- Skill name
- Use count
- Last-used timestamp
- Optional lifecycle status

Do not store prompts, private files, code snippets, client names, legal
evidence, financial data, family information, medical information, identity
documents, secrets, or confidential source content.

## Freeze Recommendation

A skill may be suggested for freezing when:

- It is optional.
- It has not been used for a configured number of days.
- It has no usage record and the customer wants a lean active skill set.
- It can be restored from local frozen cache or an approved remote source.

Before freezing, explain:

- Skill name
- Why it is a candidate
- What workflows may stop triggering
- Whether local restore is available
- Whether a remote source can be checked later
- That freezing is reversible

## Restore Or Remote Update

When the user asks for a capability whose skill is frozen or missing:

1. Check active skills.
2. Check `.agents/skills.disabled/`.
3. If frozen locally, ask whether to restore the local cached copy.
4. If missing locally, ask whether to check the approved GitHub source for the
   latest version.
5. Before installing from a remote source, run or request the package safety
   checks and show the expected impact.

Do not automatically download from GitHub, install dependencies, overwrite
local skill files, or send private project content to external services.

## Local Helper

Use `scripts/manage_skill_lifecycle.py` for local lifecycle operations:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py list
python3 .agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py record-usage long-horizon-engineering
python3 .agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py suggest-freeze --inactive-days 30
python3 .agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py freeze ai-video-production
python3 .agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py restore ai-video-production
```

The `freeze` and `restore` commands default to dry-run. Use `--apply` only after
the customer approves.

## Stop Conditions

Stop and ask when:

- The customer asks to delete skills instead of freezing them.
- The requested skill appears to contain private data.
- A frozen skill would remove the only safety or recovery mechanism.
- The restore path requires network access.
- Remote update would overwrite local modifications.
- The customer has not approved the exact skill and target project root.
