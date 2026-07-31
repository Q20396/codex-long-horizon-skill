# External App Runtime Boundary

Use this protocol when Codex may interact with an external app, hosted notebook,
browser session, cloud document system, media service, search product, or other
runtime outside the repository.

External apps can be useful, but they may move content outside the local
project. Treat public-source access, account login, browser automation, and
connected-app access as explicit approval gates. Customer-sensitive
information must never be uploaded or sent to an external app.

## Core Rule

Do not upload, paste, import, sync, transmit, or summarize customer-sensitive
source material into an external app, model provider, search service, hosted
notebook, or remote analysis system. Customer approval does not create an
exception. Only public, synthetic, or demonstrably non-sensitive material may
be considered for a separately approved external transfer.

An approved connected source may be read only by a separately installed,
default-disabled local provider that downloads the minimum approved scope into
an encrypted local case store. LHE Core must not connect to the source, receive
credentials, retain raw content, or forward the content to a model provider.

## Sensitive Source Types

Treat these as sensitive by default:

- Client files and source documents
- Legal evidence, contracts, or case materials
- Family information
- Medical or health information
- Financial records, tax documents, bank details, or account statements
- Identity documents
- Private correspondence
- Screenshots of private systems
- Confidential research notes or proprietary datasets
- Secrets, API keys, credentials, tokens, and `.env` files
- Precise location data or travel history

## Before Using An External App

Ask or confirm:

- Which app or runtime will be used
- What public or synthetic source material would be read or transferred
- Whether metadata-only review is enough
- Whether private content will be quoted, summarized, transformed, or stored
- Whether the app stores history, files, cookies, sessions, or derived outputs
- Whether the output is for private use, public sharing, or a PR
- What local alternative exists

Use `templates/source-upload-consent-checklist.md` as an external-transfer
prohibition and non-sensitive-source classification checklist. The legacy file
name does not imply that customer-sensitive uploads can be approved.

## Safe Defaults

- Prefer local files, local scripts, and official public documentation first.
- Prefer dry-run, preview, or plan-only mode before external execution.
- Prefer temporary outputs over persistent external storage.
- Keep browser/account automation visible and user-initiated when possible.
- Do not save external app cookies, sessions, or credentials in the repository.
- Do not commit generated exports that contain private source content.

## Handoff Language

When external-app use is approved, summarize in minimal terms:

- Approved source class, not private details
- Purpose
- Tool/app used
- What was excluded
- Where outputs are stored
- Remaining privacy risk

If approval is not clear, stay local or ask.
