# Recommended Skill Architecture

This is a design proposal only. It does not create, move, or install any
directory described below.

```text
codex-long-horizon-skill
|
|-- core/
|   |-- skill-router
|   |-- spec-and-scope
|   |-- capability-contract
|   |-- evidence-harness
|   |-- decision-log
|   |-- worktree-isolation
|   |-- rollback
|   `-- handoff
|
|-- bundled-optional/
|   |-- repo-cartographer
|   |-- traceability-pipeline
|   |-- docs-and-pr-narrator
|   |-- browser-qa-planner
|   `-- onboarding-map
|
|-- separate-skills/
|   |-- codebase-memory-indexer
|   |-- browser-execution
|   |-- video-production
|   |-- local-knowledge-vault
|   |-- scheduled-automation
|   |-- mcp-builder
|   |-- finance
|   `-- secure-notifications
|
`-- sandbox/
    |-- MAD-SKILL-001 ... MAD-SKILL-011
    |-- MAD-SKILL-012 candidate
    |-- MAD-SKILL-013 candidate
    `-- MAD-SKILL-014 candidate
```

Core should contain only safe, dependency-free policy and evidence contracts.
Bundled optional content can provide documentation and planners but should not
become an install hard requirement. Any runtime, account, provider, model,
MCP, network, scheduler, or external-write capability belongs in a separate
skill or remains sandbox-only.

## Router Boundary

The future router is recommendation-only. Candidate-only designs do not
participate in routing, and locked experiments do not execute by default.
Partial, adjacent, and no-overlap records must not be automatically routed.
Only a `full` mapping with `strong` evidence and a separate customer approval
may be suggested. A router may display at most three candidates and cannot
install, invoke, or grant permission to any of them.

## Source Boundary

The current source ledger records zero verified GitHub sources, ten
`verification_blocked` leads, and five `ambiguous_source` leads. Architecture
recommendations therefore remain local design mappings, not third-party
compatibility, performance, or licensing claims.
