# Large Migration Playbook

Use this guide for large codebase migrations, multi-file implementations, and
changes that affect public behavior across modules.

Large migrations should be phased, reviewable, and reversible. Do not make
high-risk migration decisions autonomously; ask the user before changing public
APIs, schemas, auth, payments, production config, or data behavior.

## 1. Map Before Editing

Before making changes, identify:

- Public APIs and exported interfaces
- Database schemas, migrations, and generated types
- Configuration files and environment-dependent behavior
- Tests, fixtures, snapshots, and integration paths
- Risky modules such as auth, billing, data access, security, or deployment
- Entry points, build scripts, and CI commands
- Current behavior that must remain compatible

Record evidence from repository files, tests, logs, or user-provided context.
Avoid guessing from naming alone.

## 2. Define Migration Phases

Break the work into small phases that can be reviewed independently:

1. Preparation and mapping
2. Compatibility layer or feature flag, if useful
3. Narrow implementation change
4. Test updates
5. Call-site migration
6. Cleanup after compatibility is no longer needed

Each phase should have a clear purpose, changed files, validation method, and
rollback path.

## 3. Preserve Compatibility When Possible

Prefer backward-compatible changes when the old and new behavior must coexist.
Use feature flags, adapters, compatibility layers, or temporary wrappers when
they reduce risk and match the codebase style.

Do not add compatibility layers as decoration. Use them only when they make the
migration safer, easier to test, or easier to roll back.

## 4. Keep Scope Tight

- Avoid unrelated refactors.
- Do not rename or reorganize files unless required.
- Do not upgrade dependencies unless the migration requires it.
- Do not change formatting broadly unless the project already enforces it.
- Keep generated files separate from hand-written changes when possible.

If unrelated cleanup is discovered, note it as follow-up instead of mixing it
into the migration.

## 5. Validate In Layers

Run the narrowest relevant checks first:

- Targeted unit or regression tests for the changed path
- Typecheck or lint for affected modules
- Integration tests for cross-module behavior
- Build or package checks
- Broader test suites when the impact justifies the cost

For behavior migrations, compare old and new behavior where possible. Do not
claim a migration is complete without validation evidence.

## 6. Track Progress

For long-running work, record:

- Completed phases
- Remaining phases
- Files changed
- Tests run and outcomes
- Failed attempts
- Known risks
- Rollback plan
- Next safest step

Use `docs/WORKING_STATE.md` or a handoff report only when appropriate and when
the repository is not sensitive, unless the user explicitly approves.

## 7. Rollback Planning

Before making high-impact edits, know how to recover:

- Revert the branch or commit
- Disable a feature flag
- Remove a compatibility layer
- Restore old call sites
- Roll back a migration in the approved project-specific way

Do not run destructive rollback commands without user confirmation.

## 8. Stop And Ask

Pause and ask the user before continuing when:

- The migration changes public APIs, schemas, auth, payments, or production
  config
- Compatibility tradeoffs are unclear
- Tests are missing for high-impact behavior
- The change requires broad deletion or dependency upgrades
- Repository state conflicts with the plan
- Sensitive data or private files are involved
- The safest next step depends on product or business intent
