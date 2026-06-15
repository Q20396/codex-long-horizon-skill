# External Source Scan Consent Protocol

Use this protocol when a task may benefit from checking sources outside the
current repository, such as local folders, connected cloud drives, or connected
email.

External source scans are optional. Do not scan outside the current repository
unless the user explicitly asks for it or approves a clear request.

## Supported Source Types

Codex may ask permission to scan:

- Specific local folders
- Connected cloud drives or document stores
- Connected Gmail or other mailboxes

Only use connectors or tools that are already available in the current Codex
session. Do not add new integrations, credentials, or background sync behavior
without explicit user approval.

## Consent Question

Before scanning external sources, ask a short question that makes the source
and scope clear. Offer narrow choices when useful:

```text
This may require checking sources outside the repository. Do you want me to scan
only this repo, selected local folders, connected cloud drive files, or Gmail?
```

If the user approves external scanning, confirm:

- Source type
- Folder, drive location, label, query, or date range
- File types or keywords to include
- Whether to inspect file contents or only metadata
- Whether results may be summarized in task notes

## Least-Access Rules

- Prefer repository-only scanning when it is enough.
- Prefer metadata before file contents.
- Prefer specific folders, queries, labels, or date ranges over broad account
  searches.
- Do not scan unrelated personal folders, inboxes, or cloud locations.
- Do not download or copy files unless needed for the task and approved.
- Do not create persistent logs from external sources unless the user approves.

## Privacy Rules

Do not store secrets, API keys, legal evidence, family information, private
client data, financial account details, confidential documents, personal
messages, or sensitive attachments in memory, logs, working state, or generated
reports.

When summarizing findings from external sources:

- Use minimal, task-relevant summaries.
- Avoid quoting private content unless the user explicitly asks and it is safe.
- Redact secrets and private identifiers.
- Record source names only when needed for traceability.

## Change Detection

If the user asks Codex to check whether files were added, removed, or changed:

1. Ask which source should be checked.
2. Prefer timestamps, file names, and stable metadata first.
3. Compare only the approved scope.
4. Report added, removed, and changed items at a high level.
5. Ask before opening sensitive-looking files or attachments.

Do not run continuous monitoring in the background unless the user has set up an
explicit automation and the automation remains review-gated.

## Stop Conditions

Pause and ask the user before continuing if:

- The requested scan is too broad.
- A source appears to contain sensitive personal or client data.
- Connector permissions are missing or unclear.
- The scan would require storing private content.
- The next step would modify, delete, send, move, or share external files or
  emails.
