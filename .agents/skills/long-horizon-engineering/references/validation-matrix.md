# Validation Matrix

Use this guide to choose verification steps that match the task. Prefer direct
evidence over confidence by inspection alone.

Validation should be proportional to risk. Small documentation edits need light
checks; security, auth, payment, data, and migration changes need stronger
verification and user confirmation.

## Task Type Matrix

| Task type | Recommended validation |
| --- | --- |
| Bug fix | Reproduce the issue if possible; add or run a targeted regression test; run relevant existing tests. |
| Refactor | Run existing tests; run typecheck or lint when available; confirm public behavior is unchanged. |
| Large migration | Run targeted tests per phase; run integration tests; compare old and new behavior where possible; record completed and remaining phases. |
| UI change | Run build; use screenshots or visual inspection when available; compare against the design goal; check responsive states when relevant. |
| Performance change | Benchmark before and after; record methodology, sample size, and environment; avoid claiming improvement without measurement. |
| Security, auth, payment, or data change | Require user confirmation; minimize the diff; run relevant tests; document risks, assumptions, and rollback plan. |
| Documentation-only change | Check links and structure; confirm examples are accurate; confirm no sensitive data is included. |

## Validation Notes

- Run narrow checks first so failures are easier to diagnose.
- Broaden validation when the change affects shared behavior or public
  contracts.
- If a recommended check is unavailable, say so and use the best available
  substitute.
- Record command names and outcomes in the final summary.
- Do not report tests as passing unless they were actually run.
- Do not treat formatting-only checks as proof that behavior is correct.

## When To Stop

Pause and ask the user when validation requires:

- Production data or credentials
- Destructive commands
- Large dependency installs
- External systems with unclear privacy implications
- Manual product decisions
- Risk acceptance for known failing tests
