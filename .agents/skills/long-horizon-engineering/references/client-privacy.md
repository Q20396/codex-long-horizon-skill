# Client Privacy And Confidential Data

Use this guide when a repository may contain client, private, legal, financial,
family, medical, identity, business, or confidential research material.

Treat uncertain data as sensitive until the user confirms otherwise.

## Sensitive Data Categories

Sensitive data includes:

- Client names and contact details
- Legal evidence
- Contracts
- Financial records
- Bank account details
- Tax documents
- Identity documents
- Family information
- Medical or health information
- Private correspondence
- Screenshots of private systems
- Source documents supplied by clients
- Confidential business information
- API keys, tokens, passwords, and credentials
- Private research notes or corpus content

## Core Rules

- Do not store sensitive data in `PROJECT_MEMORY.md`, `TASK_LOG.md`,
  `WORKING_STATE.md`, or `HANDOFF_REPORT.md`.
- Before reading sensitive materials, tell the user why access is needed, which
  files or folders would be read, whether metadata is enough, whether content
  would be quoted, summarized, or recorded, and how sensitive content will be
  minimized or omitted. Wait for explicit approval before reading sensitive
  content.
- Do not quote private source material unless the user explicitly asks and it is
  necessary for the task.
- Do not summarize sensitive documents into public or reusable logs.
- Prefer references such as "client contract file", "private evidence
  document", or "confidential source material" instead of copying details.
- Use the minimum necessary exposure for the task.
- Keep client-specific work in the private target repository, not in this
  reusable skill repository.
- Never commit real client data into this public skill repository.
- Never push private client data to GitHub unless the user explicitly approves
  the exact reviewed subset.
- If unsure whether data is sensitive, treat it as sensitive and ask.

## Repository Modes

### Public Reusable Skill Repository

This repository must contain templates, rules, examples, and helper scripts
only. It must never contain real client data, private evidence, personal
records, confidential source documents, or credentials.

### Private Target Repository

Codex may work with private materials only within the approved task scope. Use
minimal references in summaries, logs, and PR text. Avoid copying raw content
into persistent files.

### Sensitive Repository

For legal, financial, family, medical, client, or confidential research
repositories, default to plan-only mode until the user approves specific files,
commands, edits, staging paths, and push targets.

## Before Reading Sensitive Content

When sensitive content may need to be read, ask first and include:

- Why the material is needed
- Which files, folders, labels, or records would be read
- Whether metadata-only review is enough
- Whether private content would be quoted, summarized, or recorded
- Where any summary would appear
- How sensitive details will be minimized, omitted, or redacted

Do not proceed from metadata inspection to content inspection until the user
explicitly approves the sensitive read scope.

## Git Safety

- Do not use broad staging such as `git add .` in sensitive repositories.
- Stage explicit reviewed paths only.
- Inspect staged file names before committing.
- Do not stage raw source documents, screenshots, evidence files, exports,
  identity documents, contracts, or financial records unless explicitly
  approved.
- Ask before pushing any branch that may contain private data.
- Do not open public PRs containing private data.

## Output Safety

When reporting on sensitive work:

- Summarize structure and decisions without exposing private content.
- Use generic labels for confidential materials.
- Redact secrets and private identifiers.
- Mention that sensitive details were intentionally omitted.
- Avoid copying private source text into chat unless explicitly requested and
  safe.

## Stop And Ask

Pause before continuing if:

- A file appears to contain client, legal, financial, family, medical, identity,
  or confidential business data.
- A requested action could expose confidential data.
- The user asks to push, upload, publish, or share private files without a
  reviewed subset.
- The staged diff includes sensitive file names, raw documents, screenshots, or
  evidence files.
- Codex is unsure whether a file is sensitive.
