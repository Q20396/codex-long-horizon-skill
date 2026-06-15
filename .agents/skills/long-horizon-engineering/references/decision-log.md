# Decision Log Guidance

Use this guide when a task has uncertainty, competing implementation paths, or
important tradeoffs. The goal is to keep Codex from guessing or making
unsupported engineering changes.

## Terms

- Fact: something directly observed in the repository, logs, tests, command
  output, or user-provided context.
- Assumption: something inferred but not yet verified.
- Decision: what Codex chose to do.
- Evidence: why that decision was made.
- Risk: what could be wrong or what could break.
- Follow-up: what should be checked later.

## How To Use

Record only the entries that are useful for the task. Keep them short and tied
to evidence. If an assumption matters, either verify it before editing or mark it
clearly as unresolved.

Prefer this pattern:

```markdown
- Fact:
- Assumption:
- Decision:
- Evidence:
- Risk:
- Follow-up:
```

## Example

```markdown
- Fact: `package.json` defines `npm test` and `npm run lint`.
- Assumption: The failing behavior is covered by the existing unit tests.
- Decision: Add a focused regression test before changing implementation code.
- Evidence: The related module already has nearby tests for the same public API.
- Risk: The failure may be integration-level and not visible in unit tests.
- Follow-up: Run the relevant integration test if the unit test does not fail.
```

## Safety

Do not record secrets, API keys, legal evidence, family information, private
client data, financial account details, or confidential documents.
