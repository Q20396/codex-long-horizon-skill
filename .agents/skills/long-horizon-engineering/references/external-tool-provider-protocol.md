# External Tool Provider Protocol

Use this protocol when a task may rely on optional external tools, search
providers, connected apps, local CLIs, MCP servers, or cloud services.

The goal is to make tool choice explicit, reversible, and privacy-aware. A tool
provider is evidence, not authority.

## When To Use

Use this protocol when:

- Multiple tools or providers could answer the same question.
- A provider may require network access, login state, files, credentials, or
  private repository content.
- A task needs fallback behavior if a provider is unavailable.
- The user asks Codex to compare, install, update, or use external capabilities.

Do not use this protocol for simple local file inspection or ordinary test
commands that do not expose data outside the repository.

## Provider Capability Map

Before using a provider, identify:

- Provider name
- Purpose
- Data it needs
- Whether it reads local files, browser state, account data, or external APIs
- Whether it writes files, opens a network connection, uploads content, or sends
  notifications
- Required user approval
- Safer local alternative, if any
- Failure fallback
- Privacy risk

Use `templates/tool-provider-capability-map.md` when a written map would help.

## Approved Tool Contract Card

The capability map compares candidates. Once a candidate is selected, use
`references/approved-tool-contract-card.md` to document the exact proposed
tool action when it has material permissions or side effects.

Use `templates/APPROVED_TOOL_CONTRACT_CARD.md` only when a written record will
reduce risk. The card must identify the exact command or action, approved input
scope, effect classes, lowest-risk first step, validation evidence, fallback,
and rollback or containment plan.

A completed card is still proposal-only. It does not authorize installation,
execution, network access, file mutation, external transfer, account access,
deployment, publication, or any other side effect. Ask for the exact approval
needed before each applicable action.

## Approval Rules

Ask before using a provider when the action may:

- Read private files, connected cloud storage, email, browser sessions, or
  account data
- Upload, paste, summarize, or transmit private content
- Install or run a new external tool
- Authenticate into a third-party service
- Create, publish, send, or share content
- Store provider output in memory, logs, state, or reusable templates

Prefer metadata-only inspection when content is sensitive.

Do not install, update, or run a provider automatically because it appears in a
capability map or contract card. A changed command, version, source, input
scope, or effect class needs a new review.

## Doctor-First Pattern

When a provider has a local doctor, check, status, or dry-run command, prefer
running that before relying on the provider.

Record:

- What was checked
- Whether the provider is available
- What permissions or configuration are missing
- Whether fallback is needed

Do not treat an unavailable provider as a reason to guess.

## Fallback Pattern

For provider-backed tasks:

1. Try the lowest-risk source first.
2. Prefer official documentation or local files when available.
3. Use broad web or social sources only when authoritative sources are
   insufficient.
4. If sources conflict, report the conflict and prefer primary sources.
5. If no approved provider can answer safely, stop and ask.

## Output Rules

When summarizing provider use, include:

- Provider used
- Query or task class
- Data exposure level
- Important evidence
- Confidence
- Any skipped provider and why

Do not include secrets, private source text, credentials, account identifiers,
legal evidence, family information, medical information, financial account
details, identity documents, or confidential client content.
