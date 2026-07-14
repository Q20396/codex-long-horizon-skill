# Approved Tool Contract Card

Use this optional, documentation-only protocol after a tool or provider has
been selected for a task. It turns a vague request such as "use this CLI" or
"connect this provider" into a bounded proposal that a person can review.

Use `external-tool-provider-protocol.md` and
`templates/tool-provider-capability-map.md` first when comparing candidates.
Use the contract card only for the selected candidate.

## Scope

Use a card when a task involves a new local CLI, MCP server, connected app,
cloud provider, browser session, external script, or other tool that could
read data, write files, use the network, authenticate, upload content, or
affect a system outside ordinary repository tests.

Do not require a card for ordinary local file inspection or an established
repository test command that has no new side effects.

## Core Rule

A completed card is still a proposal, not authorization. It does not grant
permission to install, update, download, run, authenticate, read private
files, write files, open a network connection, upload content, send a
notification, deploy, publish, push, merge, or release anything.

Each action remains separately subject to the repository's approval, privacy,
and capability-boundary rules. The exact command in a card is information for
review; it is not permission to execute that command.

## What The Card Must State

Record only the minimum information needed to review the proposed action:

- Tool identity, version, source, and local alternative.
- The approved task and explicit non-goals.
- Exact proposed command or action, with placeholders instead of secrets.
- Prerequisites and explicitly approved input paths or source classes.
- All applicable effect classes: local read, workspace write, network read,
  external transfer, account or session access, and system or production
  action.
- Lowest-risk first step, such as `--help`, `--version`, a doctor command, or a
  documented dry run.
- Expected output, direct validation evidence, failure fallback, and rollback
  or containment plan.
- Separate approval status for acquisition, execution, writes, network use,
  uploads, account access, and production-facing actions when relevant.

Use `templates/APPROVED_TOOL_CONTRACT_CARD.md` when a written review record
will reduce risk. Do not create or persist a completed card in a sensitive
repository unless the user explicitly approves that record.

## Effect Classes

Classify every material effect. A tool can have more than one class.

| Effect class | Examples | Default treatment |
| --- | --- | --- |
| Local read | Version check, local status command | Use only in approved scope. |
| Workspace write | Generate files, alter configuration | Ask for exact path approval. |
| Network read | Fetch public metadata or documentation | Ask before network access. |
| External transfer | Upload, paste, sync, or notify | Ask for exact source and destination approval. |
| Account or session access | Login, browser cookies, connected app data | Ask before access; do not reuse hidden session state. |
| System or production action | Service control, deployment, billing, permissions | Plan-only until the user confirms the exact action. |

## Review Rules

1. Prefer a local, read-only, reversible alternative before a provider or
   command with broader effects.
2. Use an immutable version, tag, checksum, or reviewed commit when the tool
   source matters. Popularity, stars, or novelty are not evidence of safety.
3. Do not place credentials, API keys, tokens, private paths, client data, or
   private source text in the card or command example.
4. Do not use a contract card to bootstrap automatic installs, updates,
   background services, tool discovery, model routing, telemetry, or scheduled
   work.
5. Treat a changed command, version, source, input scope, or effect class as a
   new proposal. Earlier approval does not carry over automatically.
6. If the requested action is unclear or cannot be bounded, stop and ask for a
   narrower request.

## Decision Outcomes

The reviewer may choose one of the following outcomes:

- **Decline**: do not use the tool; use a local fallback or stop.
- **Preview only**: permit only the explicitly named low-risk check.
- **Approve one bounded action**: permit one exact reviewed command and scope.
- **Defer**: gather no more than approved metadata and wait for a decision.

None of these outcomes authorizes unrelated actions. If validation fails or
the tool behaves outside its card, stop, contain the effect, and follow the
documented fallback or rollback plan.
