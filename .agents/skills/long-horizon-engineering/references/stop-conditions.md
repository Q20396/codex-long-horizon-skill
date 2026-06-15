# Stop Conditions

Use this guide to decide when Codex should pause instead of continuing a
long-horizon engineering task.

Stop and ask the user, or summarize the blocker, when:

- The goal, expected behavior, or acceptance criteria are unclear.
- The repository state conflicts with prior memory, logs, or working state.
- The task touches authentication, authorization, payments, secrets,
  production config, database migrations, or other protected areas.
- A needed command, dependency, service, or credential is unavailable.
- Tests fail for a reason unrelated to the current change.
- The next step would require deleting files, destructive git operations, or
  irreversible data changes.
- The implementation path depends on an important unverified assumption.
- Continuing would require storing sensitive information in memory, logs, or
  working state.
- A file appears to contain client, legal, financial, family, medical, identity,
  private correspondence, or confidential business data.
- The requested action could expose confidential data.
- The user asks to push, upload, publish, or share private files without a
  reviewed subset.
- Codex is unsure whether a file is sensitive.
- The staged diff includes sensitive file names, raw documents, screenshots, or
  evidence files.

When stopping, report:

- What is known
- What remains uncertain
- What was tried
- Why it is unsafe or unproductive to continue
- The smallest user decision or external change needed to proceed

Do not keep editing just to appear busy. Long-horizon work is stronger when it
knows when to pause.
