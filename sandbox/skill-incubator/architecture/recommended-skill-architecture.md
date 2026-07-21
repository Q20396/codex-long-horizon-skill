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

`catalog_visible` is not `recommendation_eligible`, and neither is `execution_routing_allowed`. The current router may display catalog-visible items and explain their locked state only. Every current experiment and candidate has recommendation and execution routing disabled. Candidate-only designs do not participate in routing. A future recommendation requires a separate approved step; future execution routing requires a higher, separate approval and is not implied by a recommendation.

## Source Boundary

The current source ledger records zero verified GitHub sources, ten
`verification_blocked` leads, and five `ambiguous_source` leads. Architecture
recommendations therefore remain local design mappings, not third-party
compatibility, performance, or licensing claims.
