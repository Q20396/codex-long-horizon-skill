# Obsidian Knowledge Workflow

Use this optional protocol only when the user explicitly asks to work with an
Obsidian vault, Obsidian Markdown, a `.canvas` file, or an Obsidian Base. It
does not broaden the default scope of `long-horizon-engineering`.

## Purpose

Create a bounded, portable knowledge artifact from material the user has
explicitly supplied or explicitly authorized. Prefer a proposal first, then a
read-only inspection, then an exact-path write only after a separate approval.

Supported artifact plans:

- Obsidian-compatible Markdown notes with deliberate frontmatter, links, and
  callouts when the user requests those features.
- JSON Canvas plans for visualizing goals, evidence, decisions, risks, and
  next steps.
- Obsidian Base proposals when the user has supplied the intended note schema
  and fields.

This protocol is original guidance. It does not require Obsidian CLI, Defuddle,
or any external package, and it does not install, invoke, or copy from a
third-party tool.

## Default Contract

Before reading or writing a vault, state the following plainly:

- Workflow mode: `PROPOSAL_ONLY`
- Vault read approval: `NO`
- Vault write approval: `NO`
- Exact vault path: `PENDING`
- Exact target artifact path: `PENDING`
- Background scan, indexing, synchronization, or link maintenance: `NO`

A vault is user-owned content, not a default memory source. Do not infer that a
request to make a note authorizes access to the full vault.

## Permission Gates

### 1. Supplied-content proposal

When the user supplies non-sensitive text in the conversation, create a plan or
draft without reading local files. Identify the requested artifact type, the
proposed target filename, and any uncertain links, properties, or schema.

### 2. Exact read approval

Ask for approval before reading any vault file. The approval must name the
exact vault root and the exact file or narrow glob needed. Confirm whether the
content could contain private, client, legal, financial, medical, family, or
other confidential material.

Do not read:

- an entire vault by default
- hidden folders, application settings, plugin data, or caches
- private journals, archived correspondence, attachments, or unrelated notes
- files reached through a symlink outside the approved vault root

If sensitivity is uncertain, use a minimal metadata-only request or stop and
ask for clarification.

### 3. Exact write approval

A plan, preview, or readable draft is not permission to write. Before creating
or modifying an artifact, require approval that names:

- the exact target path relative to the approved vault root
- whether creation or replacement is allowed
- the artifact type (`.md`, `.canvas`, or `.base`)
- whether an existing file must be backed up

Use an explicit target path, not a broad folder wildcard. Do not bulk rewrite
notes, generate backlinks, rename files, update tags, or maintain a Base unless
the user separately authorizes each bounded operation.

## Artifact Guidance

### Obsidian Markdown

Use standard Markdown unless the user asks for an Obsidian extension. When
needed, keep frontmatter small and intentional; use `[[wikilinks]]` only for
known, user-approved in-vault note names; use normal Markdown links for public
URLs. Do not invent backlinks, aliases, tags, or embeddings from guesses.

### JSON Canvas

Use JSON Canvas when visual relationships help a reviewer understand a plan.
For each canvas, make the evidence flow inspectable:

1. Create text nodes for the goal, confirmed facts, assumptions, decisions,
   risks, and next safe step.
2. Use edges only when a relationship is explicit, such as `supports`,
   `depends on`, `risks`, or `requires approval`.
3. Keep node IDs unique and ensure every edge resolves to an existing node.
4. Validate the file with `scripts/validate_json_canvas.py` before presenting
   it as ready.

The validator is local and read-only. It makes no network calls and does not
write, repair, or format the canvas.

### Obsidian Bases

Treat a `.base` file as a structured view definition, not an automatic index.
Propose a minimal filter and view based only on fields the user has supplied or
authorized. Do not create a Base automatically, and do not rely on unverified
formulas or properties.

## Validation And Handoff

Before a user-approved write, show:

- exact target path and artifact type
- whether an existing file would be replaced
- source files or supplied text used
- content classification and privacy risks
- validation command and expected result
- rollback method, such as restoring the named backup

After a write, validate only the approved target. For a canvas, run:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/validate_json_canvas.py \
  path/to/approved.canvas
```

Do not claim that an artifact rendered correctly in Obsidian unless the user or
an authorized local check has actually verified it.

## Stop Conditions

Stop and ask before proceeding when:

- the request implies scanning or organizing the entire vault
- the target path is unclear, broad, outside the approved root, or symlinked
- content is sensitive or its classification is unknown
- a requested operation would create external links, sync data, install a
  plugin, invoke Obsidian CLI, or alter a large set of notes
- a Base schema, Canvas relationship, or Markdown link would be guessed

## Non-Goals

This protocol does not provide automatic vault indexing, background monitoring,
cloud synchronization, plugin installation, CLI control, browser extraction,
or a persistent copy of vault contents. It never turns an Obsidian vault into a
shared project memory file without the user's explicit approval.
