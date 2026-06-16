# Upgrade Guide

Use this guide when updating an installed copy of these skills in another
repository.

## Upgrade Principles

- Review changes before applying them.
- Back up the existing installed skill first.
- Preserve local project instructions and private project data.
- Do not run broad copy commands over a target repository.
- Do not auto-merge or deploy as part of a skill upgrade.

## Recommended Upgrade Flow

1. Update this public package repository in a separate branch or review the
   latest release diff.
2. Run the doctor check:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
   ```

3. Dry-run an update against the target project:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py --list-skills
   ```

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
     --target-root /path/to/project \
     --skill long-horizon-engineering
   ```

4. Review the printed plan and confirm the target path.
5. Apply only after review:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
     --target-root /path/to/project \
     --skill long-horizon-engineering \
     --apply
   ```

6. Run the target project's tests or smoke checks.
7. Commit the update in a branch and open a review PR.

## Rollback

The update helper stores backups under:

```text
.codex-skill-backups/
```

To roll back, copy the reviewed backup skill directory back into:

```text
.agents/skills/<skill-name>/
```

Do not restore unrelated private files or broad repository snapshots.

## Troubleshooting

- If `doctor.py` fails, fix missing package files before copying the skill.
- If a target repository appears sensitive, keep the update plan-only until the
  user approves exact paths.
- If local project instructions conflict with this package, preserve the local
  repository's `AGENTS.md` and ask before changing it.
- If optional tools such as Repomix are unavailable, continue with normal file
  exploration.
- If adopting the content, research, notebook, presentation, or video design
  protocols, review whether the target project should copy all templates or only
  the ones it will actually use.
