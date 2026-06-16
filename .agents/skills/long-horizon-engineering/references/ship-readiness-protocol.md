# Ship Readiness Protocol

Use this optional protocol before marking work ready to merge, release, deploy,
or hand to a reviewer. It is a readiness review, not permission to deploy or
merge automatically.

## Core Rule

Report readiness with `PASS`, `WARN`, `FAIL`, or `SKIP`. A `FAIL` blocks the
ship recommendation. A `WARN` requires reviewer attention or explicit risk
acceptance.

## Readiness Areas

- Branch and scope: feature branch, focused diff, no unrelated changes.
- Tests: targeted tests, relevant suite, skipped checks named with risk.
- Quality: lint, typecheck, formatting, build, generated files.
- Secrets: no credentials, tokens, private documents, or sensitive screenshots.
- Dependencies: manifests and lockfiles are consistent; new licenses reviewed.
- Database: migrations exist when schema changes; rollback or recovery is known.
- API: contract changes documented; request and response examples verified.
- Frontend: affected screens checked; accessibility and responsive risks named.
- Documentation: README, docs, examples, and changelog updated when needed.
- Observability: logs, metrics, health checks, or alerts considered when relevant.
- Rollback: revert path, feature flag, backup, or manual recovery plan exists.
- Post-release: what to verify after release and who owns follow-up.

## Workflow

1. Compare the branch against the intended base.
2. Categorize changed files by risk.
3. Run available checks or explain why they are unavailable.
4. Inspect the diff for secrets and unrelated changes.
5. Review docs, migrations, API contracts, and UI evidence when relevant.
6. Produce a readiness report with blockers, warnings, evidence, and next steps.

## Safety

Do not push, merge, deploy, publish, or execute production commands unless the
user explicitly approves the exact action, target, timing, rollback path, and
risk. For client or confidential repositories, default to plan-only mode until
the user approves the reviewed subset.
