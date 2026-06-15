# Context Compaction Guide

Use this guide before a long-running task may lose context, be interrupted, or
continue in a later Codex run.

## What To Preserve

When persistent tracking is appropriate and safe, update `docs/WORKING_STATE.md`
with:

- Current goal
- Current status
- Current branch
- Base commit or last known good commit
- Files inspected
- Files changed
- Current diff summary
- Confirmed facts
- Assumptions still needing verification
- Decisions made and evidence
- Failed attempts
- Test results
- Known risks
- Next safest step
- Things not to repeat

## Before Compacting Or Pausing

Prefer a short, factual state update over a long narrative. The next Codex run
should be able to answer:

- What is the task?
- What has already been done?
- What evidence supports the current direction?
- What remains uncertain?
- What should happen next?

## Resume Safety

Do not treat old working state as truth if the repository has changed. On
resume, re-check the branch, current diff, relevant files, and relevant tests
before editing.

## Safety

Do not record secrets, API keys, legal evidence, family information, private
client data, financial account details, or confidential documents.
