# Skill Authoring Methodology

Use this reference when maintaining this repository's own skills, trigger
metadata, templates, scripts, or package checks.

Skill maintenance should follow an eval-driven loop:

1. Capture intent
2. Define trigger examples
3. Define non-trigger examples
4. Add borderline examples
5. Write or update the skill
6. Run trigger tests
7. Run package checks
8. Run doctor
9. Review token footprint
10. Update changelog

## Core Principle

Description is trigger metadata, not a workflow summary.

The `description` field should help Codex decide whether the skill is relevant.
The detailed workflow belongs in the body of `SKILL.md` and supporting
references.

## Description Rules

- Start with `Use when...` where natural.
- Describe user situations, symptoms, and tasks.
- Do not summarize the entire workflow.
- Do not include long procedures in the description.
- Include common synonyms and Chinese trigger variants when relevant.
- Keep descriptions concise.

## Skill Update Checklist

- Does the change alter trigger behavior?
- Does it require new expected trigger cases?
- Does it add files that doctor or package-check scripts should verify?
- Does it change customer install or update instructions?
- Does it need a changelog entry?

## Anti-Patterns

- One-off narrative as skill content
- Bloated `SKILL.md`
- Untested trigger changes
- Hidden required dependency
- Description that tries to be a mini-`SKILL.md`

## Pressure Scenarios

### Huge Refactor Without Tests

If the user asks for a huge refactor without tests, define acceptance criteria,
look for existing validation, propose phases, and add or run the smallest useful
checks before broad edits.

### Mark PR Ready Without Validation

If the user asks to mark a PR ready without validation, inspect the diff, run
available checks, name any skipped checks, and only recommend readiness when the
evidence supports it.

### Install Or Update Skill Into Existing Folder

If the user asks to install or update a skill into an existing folder, dry-run
first, list the files that may change, back up the current skill, and avoid
overwriting project-specific instructions without approval.

### Search External Sources With Private Data

If the user asks to search external sources involving private data, separate the
public question from private context, search public docs where possible, and ask
before sending any sensitive details to external providers.
