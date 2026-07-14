# Resume Protocol

Use this protocol before continuing interrupted long-running work.

## Read First

If they exist, read:

- `AGENTS.md`
- `README.md`
- `docs/PROJECT_MEMORY.md`
- `docs/TASK_LOG.md`
- `docs/WORKING_STATE.md`
- Relevant task files
- Relevant prior logs

Then inspect the current repository state before editing.

## Internal Check

Before planning the next change, answer internally:

- What was the last known goal?
- What was already completed?
- What failed?
- What remains uncertain?
- What is the safest next step?

## Repository Drift

Do not blindly continue from old state if the repository has changed. Re-check
the current code, current branch, current diff, and relevant tests before
editing.

If a working-state record exists, compare its recorded branch, base commit,
last verified commit, and last verification result with current state. Inspect
both staged and unstaged diffs. Re-run the most relevant prior validation when
its result could now be stale.

If the branch, commit, diff, files, assumptions, or validation result differs
materially, mark the old state stale. Do not continue the old plan blindly;
make a new bounded plan or ask for direction before editing.

## Updating State

If persistent tracking is appropriate and safe, update `docs/WORKING_STATE.md`
with the current status, evidence, risks, next safest step, and state freshness
check. Do not create or update state files in sensitive repositories unless the
user explicitly approves.

## Safety

Do not record secrets, API keys, legal evidence, family information, private
client data, financial account details, or confidential documents.
