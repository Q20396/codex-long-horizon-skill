# Capability Families

The customer-provided list consolidates into nine capability families. Family
membership describes an engineering concern; it does not authorize a runtime,
source import, or automatic routing action.

## FAMILY-001: Skill Routing and Progressive Disclosure

Task classification, bounded recommendations, explicit-only versus
model-eligible use, risk disclosure, on-demand loading, and customer choice.
Mapped to MAD-SKILL-008.

## FAMILY-002: Specification and Traceability

Specification, issues, decisions, implementation, evidence, PR narratives,
changelog, release notes, and retrospectives. MAD-SKILL-006 and 011 cover
parts; MAD-SKILL-012 is the candidate gap.

## FAMILY-003: Capability Contract and Evidence Harness

Permissions, inputs, outputs, network, filesystem, costs, rollback, and real
output acceptance. Exit code zero alone is not success. Mapped to MAD-SKILL-002.

## FAMILY-004: Repository Understanding and Context

Bounded maps, relationships, context packs, incremental invalidation, and
handoff. MAD-SKILL-001, 003, 007, and 009 cover the safe planning layer; an
indexer remains a separate skill.

## FAMILY-005: Isolated Multi-Agent Control Plane

Serial planner, implementer, tester, and reviewer roles; isolated worktrees;
handoff; and a maximum proposed concurrency of four. Agent count is not a
quality metric. Mapped to MAD-SKILL-005.

## FAMILY-006: Browser and Visual QA

Routes, viewports, DOM and accessibility assertions, screenshot baselines,
visual differences, and final-state evidence. Real browser execution is not
included. MAD-SKILL-013 is the candidate gap.

## FAMILY-007: Media and Artifact Production

Plan, approval, provider, render, and validation must remain separate. Media,
PPTX, image, voice, and 3D runtimes are separate skills.

## FAMILY-008: Scheduled Automation Controller

Allowlists, dry runs, locks, timeouts, retry ceilings, circuit breakers,
budgets, notifications, cancellation, and evidence. No default long-lived
permission. MAD-SKILL-014 is the candidate gap.

## FAMILY-009: Restricted Domain Adapters

Legal, finance, security, communication, MCP, and real external services stay
outside the common engineering core and require dedicated approval.
