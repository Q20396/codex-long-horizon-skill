# Upgrade Guide

Use this guide when updating an installed copy of these skills in another
repository.

For plugin-based installs, see [docs/plugin-install.md](docs/plugin-install.md).

## Upgrade Principles

- Review changes before applying them.
- Back up the existing installed skill first.
- Preserve local project instructions and private project data.
- Preserve local customizations unless the user explicitly chooses to replace
  them.
- Do not run broad copy commands over a target repository.
- Do not auto-merge or deploy as part of a skill upgrade.

## Recommended Upgrade Flow

### Plugin Upgrade

Refresh the configured marketplace:

```bash
codex plugin marketplace upgrade codex-long-horizon-skills
```

If your Codex surface does not show the refreshed plugin immediately, restart
Codex.

### Direct Skill Upgrade

1. Update this public package repository in a separate branch or review the
   latest release diff.
2. Optionally run a read-only update check against a reviewed release tag:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/check_for_updates.py \
     --allow-network \
     --source-tag vX.Y.Z \
     --expected-commit REVIEWED_40_CHARACTER_SHA
   ```

   This is a status check only. It requires explicit network approval, rejects
   mutable refs such as `main`, `master`, `latest`, and branch names, and does
   not install, copy, overwrite, or update files.

   The check accepts public HTTPS remotes only, blocks obvious local or private
   destinations, resolves DNS before a tag lookup, rejects private DNS results,
   disables Git HTTP redirects and proxy inheritance, and verifies that a tag
   resolves to the expected exact commit SHA. These checks reduce accidental
   unsafe lookups, but they are not a complete SSRF defense against DNS rebinding
   or a compromised remote host.

3. Run the doctor check:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
   ```

4. Dry-run an update against the target project:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py --list-skills
   ```

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
     --target-root /path/to/project \
     --skill long-horizon-engineering
   ```

5. Review the printed plan and confirm the target path.
6. Apply only after review:

   ```bash
   python3 .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py \
     --target-root /path/to/project \
     --skill long-horizon-engineering \
     --apply
   ```

7. Run the target project's tests or smoke checks.
8. Commit the update in a branch and open a review PR.

## Compare Installed Skills With v0.1.0

The release tag is a human-readable input. The exact commit SHA is the
reproducible comparison identity.

```text
Use the repository-local long-horizon-engineering skill.

Perform a read-only comparison of my installed skills against this published
release:

https://github.com/Q20396/codex-long-horizon-skill/releases/tag/v0.1.0

Reference identity:

- Repository:
  https://github.com/Q20396/codex-long-horizon-skill
- Requested tag:
  v0.1.0
- Expected exact commit SHA:
  9afa84f96aa2e3feb1f3f5ec6f0615aeaa8761ef

I explicitly authorize limited network access only for:

- Reading public release and tag metadata from
  Q20396/codex-long-horizon-skill
- Resolving tag v0.1.0 to its exact commit SHA
- Reading the referenced public Git objects required for this comparison

Do not access any other repository, service, account, or data source.

Before comparing:

1. Resolve v0.1.0 to an exact commit SHA.
2. Verify that it equals:

   9afa84f96aa2e3feb1f3f5ec6f0615aeaa8761ef

3. Record both the requested tag and resolved SHA.
4. If the SHA differs, stop and report possible tag movement.
5. Do not continue the comparison after an identity mismatch.

Installed-skill scope:

- Compare only installed skill directories that I explicitly provide or that
  are already explicitly declared in this project's skill/package
  configuration.
- Do not search my home directory.
- Do not scan unrelated repositories.
- Do not scan Codex logs, shell history, browser history, hidden files, cloud
  storage, email, or connected services.
- Do not infer or search for other installed locations.
- If the installed skill paths are not explicit, ask me to provide them before
  continuing.

For each corresponding installed skill, compare it with the matching release
directory:

- long-horizon-engineering:
  .agents/skills/long-horizon-engineering

- ai-video-production:
  .agents/skills/ai-video-production

Use the read-only installed-skill self-check capability.

Do not:

- Install anything
- Update anything
- Apply anything
- Replace anything
- Delete unexpected files
- Copy release files into my installation
- Generate or apply a patch
- Modify file permissions
- Modify symbolic links
- Run scripts from the release
- Import or execute compared code
- Create commits or branches
- Push, merge, deploy, publish, or release

Treat files as data only.

For each installed skill, report:

1. Installed skill path label without exposing private absolute paths
2. Reference skill and exact release commit
3. Missing files
4. Unexpected files
5. Changed files
6. File-type changes
7. Executable or meaningful mode changes
8. Symbolic-link target changes
9. Unsupported or special entries
10. Trigger or workflow differences
11. Executable-code differences
12. Dependency or tooling differences
13. Safety, privacy, or approval-policy differences
14. Update or installation behavior differences
15. Risk level for each meaningful difference
16. Whether human review is required

For installed skills that do not exist in the v0.1.0 release:

- Mark them as outside the reference release scope.
- Do not classify them as files that should be deleted.
- Do not recommend removing them automatically.

Conclude with:

- Overall comparison summary
- Highest-risk differences
- Compatibility risks
- Whether an upgrade is recommended
- Recommended dry-run upgrade steps
- Files that would be affected by a later upgrade
- Validation steps required after an upgrade
- Rollback plan
- Checks that were NOT RUN
- Any limitation caused by unavailable metadata or paths

The rollback plan must include:

- Recording the current installed package state
- Creating a backup before any future update
- Recording the current version or file hashes
- Keeping the prior package until validation passes
- Restoring the backup if validation fails
- Verifying the restored package after rollback

Every report must state:

- No files were modified.
- No update was applied.
- The comparison is advisory only.
- Applying an update is a separate user-authorized action.

Do not generate or apply an upgrade patch during this task.

At the end, ask me:

Do you approve preparing a dry-run upgrade plan only?

Do not replace anything unless I separately approve the exact files and
operation after reviewing the dry-run plan.
```

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
- The methodology, search, content, design, notebook, presentation, and video
  protocols are additive. They do not require new external dependencies.
- The SkillOpt-inspired optimization protocol is also additive. It uses
  methodology and templates only by default: rollout logs, reflections, bounded
  skill edits, validation gates, and rejected edit logs. It does not require the
  Microsoft SkillOpt runtime, paid model calls, or automatic skill mutation.
  Human review and validation remain required before adopting a skill change.

## Release Preparedness

v0.1.0 release notes are prepared in
[docs/releases/v0.1.0.md](docs/releases/v0.1.0.md), but the release is not
published until a maintainer reviews, merges, validates from `origin/main`,
creates the tag, and publishes the GitHub Release.
