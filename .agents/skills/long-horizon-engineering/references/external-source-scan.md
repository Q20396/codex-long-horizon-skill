# External Source Scan Consent Protocol

Use this protocol when a task may benefit from checking public sources outside
the current repository. LHE Core must not directly inspect customer-sensitive
connected cloud drives, mailboxes, or account data.

External source scans are optional. Do not scan outside the current repository
unless the user explicitly asks for it or approves a clear request. Approval
does not authorize customer-sensitive information to be sent to a model or
external analysis service.

For provider-neutral web, GitHub, package registry, documentation, or unified
search planning, see `external-search-protocol.md`. Keep this file focused on
consent-gated scanning of local folders, connected drives, mailboxes, and other
external source locations.

## Core-Supported Source Types

LHE Core may propose read-only inspection of:

- exact non-sensitive local paths;
- public documentation or repositories; and
- synthetic fixtures.

Connected Dropbox, Gmail, Outlook, or Google Drive material requires a separate,
default-disabled local evidence provider. LHE Core must not hold connector
credentials, directly read those sources, or receive their raw customer
content. Do not add integrations, credentials, or background sync behavior.

## Consent Question

Before scanning external sources, ask a short question that makes the source
and scope clear. Offer narrow choices when useful:

```text
This may require checking a public or non-sensitive source outside the
repository. Do you approve the exact source and read-only scope?
```

If the user approves a non-sensitive external scan, confirm:

- Source type
- Exact public or non-sensitive locator and date range
- File types or keywords to include
- Whether to inspect file contents or only metadata
- Whether results may be summarized in task notes

## Least-Access Rules

- Prefer repository-only scanning when it is enough.
- Prefer metadata before file contents.
- Prefer specific folders, queries, labels, or date ranges over broad account
  searches.
- Do not scan unrelated personal folders, inboxes, or cloud locations.
- Do not download or copy files unless they are public, synthetic, or
  demonstrably non-sensitive and the exact action is approved.
- Do not create persistent logs from external sources.

## Privacy Rules

Do not store secrets, API keys, legal evidence, family information, private
client data, financial account details, confidential documents, personal
messages, or sensitive attachments in memory, logs, working state, or generated
reports.

When summarizing findings from external sources:

- Use minimal, task-relevant summaries.
- Do not quote customer-sensitive content.
- Redact secrets and private identifiers.
- Record source names only when needed for traceability.

## Change Detection

If the user asks LHE to check whether public or non-sensitive files were added,
removed, or changed:

1. Ask which public or non-sensitive source should be checked.
2. Prefer timestamps, file names, and stable metadata first.
3. Compare only the approved scope.
4. Report added, removed, and changed items at a high level.
5. Stop before opening sensitive-looking files or attachments.

Do not run continuous monitoring in the background unless the user has set up an
explicit automation and the automation remains review-gated.

## Stop Conditions

Pause and ask the user before continuing if:

- The requested scan is too broad.
- A source appears to contain sensitive personal or client data.
- Connector permissions are missing or unclear.
- The scan would require storing private content.
- The next step would modify, delete, send, move, share, upload, or transmit
  external files or emails.
