# Approved Tool Contract Card

Do not include secrets, API keys, tokens, passwords, client names, private
paths, legal evidence, family information, medical information, financial
account details, identity documents, private correspondence, or confidential
source content.

## Contract Status

- Contract status: PROPOSAL_ONLY
- User approval: PENDING
- Permission granted: NONE
- This card is not permission to install, run, authenticate, write, upload,
  publish, deploy, push, merge, or release.

## Tool Identity

- Tool or provider:
- Tool type: local CLI / MCP server / connected app / cloud service / script
- Version, immutable tag, checksum, or reviewed commit:
- Source URL or local source path:
- Maintainer or owner, if relevant:
- Local or lower-risk alternative:

## Bounded Task

- Approved task:
- Explicit non-goals:
- Why this tool is needed:
- Expected duration or one-time scope:

## Exact Proposed Invocation

```text
<tool-or-command> <approved-arguments-only>
```

- This invocation is for review only and must not run automatically.
- No shell expansion, hidden command, secret, credential, or unreviewed input:

## Preconditions And Input Scope

- Prerequisites already verified:
- Exact approved input paths or public source classes:
- Excluded paths, data classes, accounts, and destinations:
- Does the tool follow symlinks or resolve paths outside scope? yes / no / unknown

## Effect Classification

Mark every applicable class. A blank or `no` does not grant permission.

| Effect class | Applies? | Exact scope | Approval required? | Status |
| --- | --- | --- | --- | --- |
| Local read | no |  | yes | PENDING |
| Workspace write | no |  | yes | PENDING |
| Network read | no |  | yes | PENDING |
| External transfer or notification | no |  | yes | PENDING |
| Account, session, or browser access | no |  | yes | PENDING |
| System, billing, permission, or production action | no |  | yes | PENDING |

## Lowest-Risk First Step

- Proposed doctor, status, `--help`, `--version`, or dry-run command:
- Why it is lower risk:
- Expected result:
- Validation command or observation:

## Evidence And Safety Review

- Evidence for tool identity and version:
- Evidence for selected scope:
- Privacy risk and data minimization:
- Security or supply-chain risk:
- Compatibility risk:
- Known limitations or unknowns:

## Approval Gates

- Tool acquisition or installation: PENDING / not needed
- Exact command execution: PENDING
- Workspace writes: PENDING / not applicable
- Network access: PENDING / not applicable
- External transfer: PENDING / not applicable
- Account or session access: PENDING / not applicable
- System or production action: PENDING / not applicable

## Failure, Fallback, And Rollback

- Stop condition:
- Local fallback:
- Containment step if the tool exceeds scope:
- Rollback command or manual restoration step:
- Validation after rollback:

## Review Record

- Reviewer:
- Approval wording and exact permitted action:
- Approved at:
- Invalidation condition: Any changed command, version, source, input scope, or effect class requires a new review.
