# 3D Asset Provider Sandbox

Use this optional, explicit-only protocol when a user asks to evaluate or use
an external 3D asset provider, a hosted 3D-generation service, or a 3D asset
MCP server. It is a review and approval protocol, not an installer, MCP
configuration, account connection, asset generator, downloader, or runtime.

## Status And Scope

- Invocation: `EXPLICIT_ONLY`
- Proposal status: `PROPOSAL_ONLY`
- Default permission: `NONE`
- Default network access: `DENY`
- Default external 3D action: `DENY`
- Automatic skill installation: `NO`
- Automatic MCP configuration: `NO`
- Automatic sign-in or OAuth: `NO`
- Automatic asset inventory: `NO`
- Automatic reference upload: `NO`
- Automatic generation, credit spend, download, or workspace write: `NO`
- Automatic remote runtime, CDN, telemetry, or publication: `NO`

This protocol does not install, update, configure, authenticate, invoke,
generate, approve, download, import, render, publish, or remove anything. It
does not read account data, credits, projects, local source files, reference
images, 3D assets, or runtime configuration. It does not add an MCP server to
Codex.

A proposal, public source review, copied command, installed skill, or prior
approval for a different version does not authorize a later action.

Use `external-tool-provider-protocol.md`,
`external-app-runtime-boundary.md`, and
`approved-tool-contract-card.md` before proposing a provider. Use
`templates/THREE_D_ASSET_DELIVERY_APPROVAL_CARD.md` when a written record would
reduce risk.

## Why 3D Providers Need A Separate Boundary

3D assets can contain reference imagery, source geometry, scene metadata,
licenses, supplier details, usage restrictions, generated textures, and
embedded external URLs. A hosted MCP service can reveal account identity,
credits, project names, asset inventories, or generation history. A downloaded
scene can introduce unexpected loader requirements, remote runtime URLs, file
size pressure, or executable build steps.

Treat the following as sensitive or approval-gated by default:

- customer reference images, logos, source models, scenes, and absolute paths
- account identity, project names, credits, invoices, generation history, and
  OAuth scopes
- uploaded source files, prompts, model inputs, and private asset manifests
- downloaded meshes, textures, animations, materials, model provenance, and
  license records
- remote runtime, CDN, collider, or asset URLs and related CSP/CORS settings
- runtime diagnostics, telemetry, analytics, and publication destinations

Do not put any of these items in project memory, task logs, working state,
handoff reports, public commits, public PRs, or reusable examples.

## Separate Approval Gates

One approval never covers another. Ask for the smallest applicable action:

1. **Public-source review**: inspect a named public repository, documentation
   page, license, release, or immutable commit. Network access still needs
   approval.
2. **Skill acquisition**: install one exact reviewed skill version into one
   named location.
3. **MCP configuration**: add one exact endpoint or command to one named
   client configuration.
4. **Account connection**: sign in or grant only the exact reviewed OAuth
   scopes. Reading asset inventory, projects, identity, or credits is a
   separate data-access decision.
5. **Reference input**: upload or otherwise provide one named, non-sensitive
   reference asset after its rights and destination are reviewed.
6. **Generation or revision**: start one named generation, with provider,
   inputs, expected output, cost or credit effect, and retention stated.
7. **Final generation approval**: approve a provider action that creates a
   final output or charges credits. A preview does not approve a final asset.
8. **Asset retrieval and project write**: download one specified artifact to a
   user-approved path after format, license, size, and validation checks are
   known.
9. **Runtime use**: allow a named remote runtime or CDN only after the domain,
   CSP/CORS implications, offline fallback, and data exposure are reviewed.
10. **Sharing or publication**: export, upload, commit, or publish only after a
    separate human review of the selected outputs and rights.

A changed provider, version, command, endpoint, scope, input, output path,
license, runtime URL, or effect class invalidates prior approval.

## Candidate Catalog: Review Only

The following entry preserves a public candidate observed during a source
review. It is not an endorsement, installation instruction, integration, or
default provider. Re-check the source, license, exact ref, and commands before
any later decision.

### Mint Three.js Skills And Mint MCP

- Public skill source: `https://github.com/mintdotgg/mint-threejs-skills`
- Reviewed immutable commit: `e563354fae765ef49b6b0e2bd6b695554689ba40`
- Public MCP documentation: `https://mcp.mint.gg/docs`
- Public 3D product information: `https://mint.gg/features/3d-mcp`
- Observed source license: MIT; provider terms, asset rights, and model output
  terms still need a current review.

The public source separates app direction, gameplay, interaction, UI, visual
systems, debugging/profiling, QA/release, and asset-pipeline guidance. Useful
patterns to adapt are stable logical asset IDs, project-owned manifests,
format-capability checks, deterministic visual QA, and separate browser/mobile
approval. Do not copy its code, prompts, assets, or provider-specific prose.

### Command Revalidation Required

This package deliberately does not preserve copy-ready provider installation
or MCP-configuration commands. At a later, separately approved acquisition or
configuration gate, re-check the current official documentation and the exact
immutable source before showing the customer one command and its expected
effect. Do not use mutable references, global-install flags, or auto-confirm
flags by default.

Explain whether the reviewed command can write a global skill location, modify
a client configuration, begin an OAuth or account flow, download dependencies,
or expose local data. It must not be presented as a local-only, free, offline,
or privacy-preserving action without current evidence. A copied command is not
approval to execute it.

The observed public MCP scope names included `mint:read`,
`mint:generate:start`, and `mint:generate:approve`. Scope names, APIs, credit
behavior, terms, and retention can change; list the exact current scope and
effect before asking for account approval.

## Asset Delivery And Runtime Rules

For a separately approved retrieval, create or update only a project-owned,
user-approved asset record. Prefer stable logical IDs over provider job IDs or
signed URLs. Record only the minimum necessary provenance:

- logical asset key and intended use
- provider, exact source/ref, and retrieval date
- asset type, format, byte size, and checksum when supplied or computed
- known license, attribution, and output-rights status
- required loader extensions and validation result
- exact approved destination relative to the project root
- whether any remote runtime URL is permitted; default is `NO`

Treat unrecognized glTF/GLB extensions, unbounded asset sizes, unsigned
downloads, redirects to unreviewed hosts, and runtime URLs that need remote
access as stop conditions. Do not silently fall back to a remote CDN or modify
CSP/CORS configuration. Do not delete old assets, prune provider artifacts, or
overwrite a destination with `--force`; those are separate destructive actions
requiring exact-path approval.

## Lowest-Risk Pilot

When the user has approved a pilot, propose one narrow, visible action only:

- review one public immutable source with no sign-in
- no local installation, MCP configuration, account access, or asset inventory
- no reference upload, generation, credit spend, download, project write, or
  remote runtime
- record facts, unknowns, risks, and the next separate approval gate

For an approved generation pilot, use only a user-supplied non-sensitive
prompt or reference with documented rights, one named provider action, one
visible output, a stated cost limit, no automatic revision loop, no automatic
download, and no publication. If any effect is unknown, stop and ask rather
than guessing.

## Validation And Rollback

Before a permitted action, define:

- the exact configuration path, account scope, project path, endpoint, command,
  asset destination, and remote domain that could be affected
- the expected provider action, credit or cost effect, output format, size, and
  license/provenance evidence
- how result integrity, required loader support, and project compatibility will
  be checked without reading unrelated files or account history
- the stop condition for an unexpected scope, upload, redirect, write,
  background service, telemetry request, or remote runtime dependency
- the manual rollback for the exact configuration or project asset record

Do not automatically uninstall a skill, revoke a connection, delete generated
assets, remove a provider project, erase account history, or alter CSP/CORS
settings during rollback. Those are separate destructive actions that require
exact-path approval.
