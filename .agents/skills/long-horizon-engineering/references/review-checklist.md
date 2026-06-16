# Review Checklist

Use this checklist before finalizing a non-trivial engineering task or opening a
pull request.

## Scope

- The change matches the user request.
- Unrelated refactors were avoided.
- Existing user changes were preserved.
- Public APIs, behavior, and config were changed only when necessary.

## Evidence

- Important assumptions were verified with repository files, tests, logs,
  command output, or user-provided context.
- Decisions have a clear reason.
- Known risks are documented.
- Failed attempts are not repeated without new evidence.

## Validation

- Relevant tests, lint, typecheck, build, or manual checks were run when
  available.
- Failures are explained.
- Skipped checks are named with the reason they were not run.

## Safety

- No secrets, API keys, legal evidence, family information, private client data,
  financial account details, or confidential documents were written to logs,
  memory, state files, commits, or PR text.
- Sensitive repositories do not receive project memory, task logs, or working
  state unless the user explicitly approved it.
- Destructive actions were not taken without explicit approval.

## Privacy Review

- Client data was not copied into logs, memory, state, handoff files, commits,
  or PR text.
- Sensitive details were not stored in `PROJECT_MEMORY.md`, `TASK_LOG.md`,
  `WORKING_STATE.md`, or `HANDOFF_REPORT.md`.
- Only explicit safe paths were staged.
- Raw source documents, evidence files, screenshots, identity documents,
  contracts, and financial records were not staged unless explicitly approved.
- Any sensitive operation was approved by the user.

## Location And Compliance Review

- GPS, device location, precise address, travel history, or client operating
  location was not used without explicit approval.
- Jurisdiction and industry were confirmed before giving legal, regulatory, or
  industry-rule guidance.
- Current public sources were used for jurisdiction-specific facts when needed.
- Output was framed as informational support, not legal advice.
- Cross-region comparison was offered as an option instead of assumed.

## Handoff

- The final summary names files changed.
- Verification commands and outcomes are included.
- Remaining risks and next steps are clear.
- If work may continue later, `docs/WORKING_STATE.md` is updated when
  appropriate and safe.
