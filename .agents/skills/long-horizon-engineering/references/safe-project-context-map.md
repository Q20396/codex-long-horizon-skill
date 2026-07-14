# Safe Project Context Map

Use this optional protocol when an unfamiliar or large repository needs a
lightweight structural map before planning a broad engineering change. It is a
planning aid, not a graph database, semantic index, background scan, or source
of write permission.

## Scope And Consent

Before inspecting files beyond ordinary task exploration, state:

- the exact repository-relative paths proposed for the map
- the map purpose and intended decisions it will support
- expected file types and exclusions
- whether metadata is sufficient or file content is needed
- whether the repository may contain sensitive material

Use only paths that are necessary for the approved task. Do not infer approval
to scan the whole repository from approval to inspect one directory.

Never include or index `.env` files, credentials, tokens, secrets, private
client materials, legal evidence, financial records, identity documents,
private correspondence, generated outputs, dependency folders, caches, binary
assets, or user directories outside the repository. If scope may include
sensitive material, stay plan-only and ask before reading it.

## Report-First Workflow

1. Propose an explicit path allowlist and exclusions.
2. Inspect only enough metadata or approved source to build the map.
3. Record facts separately from assumptions and unresolved questions.
4. Produce a compact map of modules, entry points, ownership boundaries,
   dependencies, tests, and relevant configuration.
5. Mark the map with its source scope, generation time, and known gaps.
6. Use the map to choose exact files for normal review; read those files before
   editing.

The map is evidence for planning, not a replacement for current inspection.
Re-check relevant files if the branch, commit, or working tree changes.

## Map Contents

Keep the output bounded. Useful sections are:

- purpose and approved scope
- repository snapshot: branch, commit, and generation time
- confirmed modules and entry points
- dependency or data-flow observations
- tests, build, lint, typecheck, and CI locations
- confirmed facts, assumptions, risks, and unknowns
- recommended next safe file inspection

Do not quote large source files or preserve source content that is not needed
for the task. Prefer paths, concise descriptions, and evidence references.

## Storage And Retention

Create a persistent map only when the repository is non-sensitive and the user
approves durable tracking. Otherwise return it in the task handoff or keep it
ephemeral. Do not commit generated maps unless the user explicitly approves the
exact output path and content.

Use `templates/PROJECT_CONTEXT_MAP_TEMPLATE.md` when a written map is useful.

## Boundaries

This protocol does not:

- install or invoke Graphify, Repomix, vector databases, or graph databases
- scan cloud drives, Obsidian vaults, mailboxes, local folders outside the repo,
  images, PDFs, video, or archives
- contact model providers or external services
- create background indexing, auto-refresh, telemetry, or collaboration sync
- grant permission for edits, installation, push, merge, deployment, or
  publication

This protocol does not authorize edits, installation, push, merge, deployment,
or publication.

For a compressed code-only context bundle, see
`references/repomix-codebase-context.md`. For user-supplied compute constraints,
see `references/local-compute-capability-intake.md`.
