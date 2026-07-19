# 3D Asset Delivery Approval Card

Do not include secrets, API keys, tokens, passwords, account identifiers,
customer names, private reference images, source models, scenes, legal
evidence, family information, medical information, financial information,
identity documents, private correspondence, or confidential source content.

## Contract Status

- Invocation: EXPLICIT_ONLY
- Proposal status: PROPOSAL_ONLY
- User approval: PENDING
- Permission granted: NONE
- External provider invoked: NO
- This card is not permission to install a skill, configure MCP, sign in,
  inspect an account, upload an asset, start or approve generation, spend
  credits, download an artifact, write a project file, enable a remote runtime,
  publish, or delete anything.

## Default Automation Controls

- Automatic skill installation: NO
- Automatic MCP configuration: NO
- Automatic sign-in or OAuth: NO
- Automatic account, project, credit, or asset-inventory access: NO
- Automatic reference upload: NO
- Automatic generation, revision, or final approval: NO
- Automatic asset download, workspace write, remote runtime, telemetry, or
  publication: NO

## Candidate Identity

- Provider or tool:
- Exact version, immutable tag, checksum, or reviewed commit:
- Public source URL:
- Provider documentation URL:
- License, terms, asset-rights, and retention review:
- Maintainer or owner:
- Local or lower-risk alternative:

## Bounded Purpose

- User-approved outcome:
- Asset type: model / material / texture / animation / world / other
- Intended project and exact relative destination:
- Explicit non-goals:
- One-time or limited duration:

## Review-Only Commands Or Calls

- Exact command, endpoint, API call, or MCP tool call for review:
- Command effect: none / installation / configuration / account connection /
  account read / upload / generation / approval / download / write / runtime
- Client configuration path, if any:
- Expected network destination, redirects, and retention: none / pending
  approval / exact documented destination
- Account scope or credit effect: none / pending approval / exact documented
  scope and limit

## Approved Source And Input Scope

- Public-source review only: yes / no
- Source ref remains immutable and verified: yes / no / unknown
- Input classification: public / user-supplied non-sensitive / sensitive
  (stop)
- Exact approved prompt or reference class:
- Rights, license, and attribution status:
- Reference upload or external transfer: NO
- Account, project, credit, or asset-inventory access: NO

## Asset Delivery Contract

- Logical asset key:
- Provider job ID, signed URL, or account identifier: do not record
- Asset format and required loader extensions:
- Expected maximum size:
- Checksum or integrity evidence:
- License, attribution, and output-rights evidence:
- Local project destination:
- Overwrite existing file: NO
- Remote runtime or CDN URL: NO
- CSP/CORS or external-domain change: NO

## Separate Approval Gates

| Gate | Required? | User decision | Notes |
| --- | --- | --- | --- |
| Public-source review or network metadata | yes / no | PENDING |  |
| Exact skill acquisition | yes / no | PENDING |  |
| Exact MCP configuration | yes / no | PENDING |  |
| Sign-in, OAuth, or account-scope grant | yes / no | PENDING |  |
| Account, project, credit, or asset-inventory access | yes / no | PENDING |  |
| Exact prompt or reference upload | yes / no | PENDING |  |
| Preview generation or revision | yes / no | PENDING |  |
| Final generation approval or credit spend | yes / no | PENDING |  |
| Exact asset download and project write | yes / no | PENDING |  |
| Remote runtime, CDN, CSP/CORS, sharing, or publication | yes / no | PENDING |  |

## Safety And Compatibility Review

- Provider version, source, terms, and license reviewed: yes / no / unknown
- Requested OAuth scopes and account data exposure reviewed: yes / no / unknown
- Credit, billing, quota, and retention behavior reviewed: yes / no / unknown
- Redirect host, download size, checksum, and file type reviewed: yes / no /
  unknown
- glTF/GLB extensions supported by the chosen project loader: yes / no /
  unknown
- Remote runtime, CDN, and CSP/CORS effects reviewed: yes / no / unknown
- Sensitive data excluded:
- Stop condition:

## Minimal Customer Approval Wording

Use one statement only after the user selects the named, bounded action. Each
statement leaves every other gate closed.

- Public-source review only: "I approve reviewing the named public 3D provider
  source at the stated immutable ref. Do not install a skill, configure MCP,
  sign in, inspect my account, upload references, generate, download, write,
  or enable a remote runtime."
- One asset-retrieval review: "I approve reviewing the specified generated
  asset's format, license evidence, checksum, and destination plan only. Do
  not download, write it to the project, overwrite files, or enable a remote
  runtime."

## Validation, Fallback, And Rollback

- Lowest-risk check, if separately approved:
- Expected result:
- Validation evidence:
- Local or placeholder fallback:
- Exact configuration or asset record to reverse:
- Manual rollback steps:
- Rollback validation:

## Review Record

- Reviewer:
- Exact approved action and scope:
- Approved at:
- Invalidation condition: Any changed provider, version, command, endpoint,
  account scope, input, asset destination, license, runtime URL, or effect
  class requires a new review.
