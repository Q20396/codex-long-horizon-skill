# Repomix Codebase Context

Repomix support is optional. Use it only when a compressed codebase map would
help Codex understand a large, unfamiliar, multi-language, or highly connected
repository before editing.

This protocol does not require Repomix and does not add it as a dependency. If
Repomix is unavailable, continue with normal repository exploration.

## When To Use

Consider a Repomix-style context pass when:

- The repository is large or unfamiliar.
- The project spans multiple languages, apps, packages, or services.
- Codex needs a compressed map before planning a broad change.
- A task is blocked because local structure is unclear.
- The user explicitly asks for a codebase context bundle.

Do not use it for small, obvious edits where direct file inspection is enough.

## Privacy Rules

Never include:

- Secrets, `.env` files, credentials, tokens, or API keys
- Private client files or confidential business documents
- Personal data, family information, medical data, or identity documents
- Legal evidence, contracts, financial documents, or tax records
- Generated build outputs, dependency folders, coverage outputs, or caches
- Raw screenshots, exports, databases, archives, or large binary assets

If the repository appears sensitive, stay plan-only and ask before generating a
context bundle.

## Report-First Workflow

Prefer dry-run or report-first behavior:

1. Inspect the repository structure with ordinary shell tools.
2. Propose what would be included and excluded.
3. Ask for approval if sensitive paths may be present.
4. Run Repomix only when useful and approved.
5. Review the generated output path before using it.
6. Do not commit generated context bundles unless the user explicitly approves.

## Example Commands

Basic compressed context:

```bash
npx repomix --compress
```

Safer context file with explicit exclusions:

```bash
npx repomix --compress \
  --ignore "**/.env*,**/.git/**,**/node_modules/**,**/dist/**,**/build/**,**/coverage/**" \
  --output docs/REPO_CONTEXT.md
```

Before running commands that download or execute packages, ask for approval and
explain the privacy implications.

## Codex Use

When a Repomix output exists and is safe to read, use it as a high-level map,
not as a substitute for inspecting the exact files being changed.

Record:

- Command used
- Include/exclude assumptions
- Output file path
- Whether the output was committed, ignored, or deleted
- Any sensitive paths intentionally excluded
