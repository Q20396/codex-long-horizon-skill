# Secrets Scan Checklist

Use this checklist before committing, pushing, publishing, or opening a PR in a
repository that may contain private or confidential material.

Do not include actual secrets, API keys, passwords, tokens, client names, legal
evidence, family information, medical information, financial account details,
identity documents, private correspondence, or confidential source content in
this checklist.

## Scope

- Branch / PR:
- Paths reviewed:
- Staging command used:
- Reviewer:

## File Types Checked

- [ ] `.env`, `.env.*`, local config files
- [ ] Credentials, tokens, API keys, passwords, certificates, private keys
- [ ] Client documents, contracts, legal evidence, raw source files
- [ ] Financial account exports, tax documents, brokerage statements
- [ ] Medical, family, identity, or private correspondence files
- [ ] Screenshots, recordings, logs, generated exports, archives
- [ ] Notebooks, reports, memory, task logs, working state, handoff files

## Git Checks

- [ ] Staged paths were explicit and narrow.
- [ ] Broad staging such as `git add .` was avoided when sensitive files may be
      present.
- [ ] `git diff --cached` was reviewed before commit.
- [ ] PR title/body do not quote private source material.
- [ ] Generated examples use placeholders only.

## Findings

| Path / Area | Issue | Action Taken | Follow-up |
| --- | --- | --- | --- |
|  |  |  |  |

## Result

- [ ] No sensitive material found in staged changes.
- [ ] Sensitive material was found and removed before commit.
- [ ] Review is incomplete; stop and ask for human approval.
