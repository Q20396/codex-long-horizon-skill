# Capability Families

The customer-provided list consolidates into nine capability families. Family
membership describes an engineering concern; it does not authorize a runtime,
source import, or automatic routing action. The labels below distinguish a
current design mapping from partial coverage and future candidates. No mapping
is runtime-validated.

## FAMILY-001: Skill Routing and Progressive Disclosure

**Current design mapping:** MAD-SKILL-008 covers recommendation-only task
classification, risk disclosure, progressive disclosure, and customer choice.
**Partial coverage:** Skill creation remains a MAD-SKILL-011 evidence concern.

## FAMILY-002: Specification and Traceability

Specification, issues, decisions, implementation, evidence, PR narratives,
changelog, release notes, and retrospectives. **Partial coverage:**
MAD-SKILL-006 and 011 provide feedback and review-contract concepts only.
**Future candidate:** MAD-SKILL-012 owns stable IDs and release provenance.

## FAMILY-003: Capability Contract and Evidence Harness

Permissions, inputs, outputs, network, filesystem, costs, rollback, and real
output acceptance. Exit code zero alone is not success. **Current design
mapping:** MAD-SKILL-002 covers the common acceptance-contract boundary.
**Partial coverage:** individual terminal, CI, data, migration, and refactor
workflows are not implementations of that contract.

## FAMILY-004: Repository Understanding and Context

Bounded maps, relationships, context packs, incremental invalidation, and
handoff. **Partial coverage:** MAD-SKILL-001, 003, 007, and 009 cover distinct
planning constraints; none establishes a general indexer or knowledge runtime.
An indexer remains a separate skill.

## FAMILY-005: Isolated Multi-Agent Control Plane

Serial planner, implementer, tester, and reviewer roles; isolated worktrees;
handoff; and a maximum proposed concurrency of four. Agent count is not a
quality metric. **Partial coverage:** MAD-SKILL-005 covers governance and
containment, not an agent swarm, code-review runtime, or loop executor.

## FAMILY-006: Browser and Visual QA

Routes, viewports, DOM and accessibility assertions, screenshot baselines,
visual differences, and final-state evidence. Real browser execution is not
included. **Partial coverage:** MAD-SKILL-010 only supplies privacy and
demonstration boundaries. **Future candidate:** MAD-SKILL-013 owns browser and
visual QA planning; execution remains a separate skill.

## FAMILY-007: Media and Artifact Production

Plan, approval, provider, render, and validation must remain separate. Media,
PPTX, image, voice, and 3D runtimes are separate skills.

## FAMILY-008: Scheduled Automation Controller

Allowlists, dry runs, locks, timeouts, retry ceilings, circuit breakers,
budgets, notifications, cancellation, and evidence. No default long-lived
permission. **Future candidate:** MAD-SKILL-014 owns the scheduler safety
controller; MAD-SKILL-002 is only a partial contract overlap.

## FAMILY-009: Restricted Domain Adapters

Legal, finance, security, communication, MCP, and real external services stay
outside the common engineering core and require dedicated approval. They are
restricted-domain or separate-skill work, not router defaults.
