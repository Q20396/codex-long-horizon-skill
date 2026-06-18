# Contributing

Thanks for helping improve Codex Long Horizon Skills.

## Create A Skill

1. Add a new directory under `.agents/skills/<skill-name>/`.
2. Add a required `SKILL.md` with YAML front matter:

   ```markdown
   ---
   name: skill-name
   description: Use this skill when...
   ---
   ```

3. Keep the description trigger-focused: it should explain when Codex should
   choose the skill.
4. Add examples, validation guidance, safety boundaries, and failure recovery
   notes to the skill instructions.
5. Put long guidance in `references/`, reusable structures in `templates/`, and
   local helpers in `scripts/`.

## Required Files

Every skill must include:

- `SKILL.md`
- Usage guidance
- Validation workflow
- Safety boundaries
- Failure recovery strategy
- Example prompts

Optional support folders:

- `references/`
- `templates/`
- `scripts/`
- `assets/`

## Validation Process

Run these checks before opening a PR:

```bash
python3 scripts/generate_skill_catalog.py --check
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
python3 .agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py
git diff --check
```

For a broader local audit:

```bash
python3 scripts/full_skill_validation.py
```

## PR Checklist

- [ ] Skill metadata is trigger-focused.
- [ ] README skill catalog is synchronized.
- [ ] New prompts or templates contain placeholders only.
- [ ] No secrets, client data, legal evidence, family information, API keys, or
      confidential documents were added.
- [ ] Validation commands pass.
- [ ] The PR is reviewable and does not merge or deploy automatically.
