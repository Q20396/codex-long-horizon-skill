# Capability Boundaries

Use this guide to decide how far Codex may go when a task asks for powerful
agent behavior such as orchestration, deployment, self-improvement, auto-merge,
production execution, or security automation.

The principle is simple: capability does not imply permission. Prefer
review-gated, reversible workflows over autonomous high-impact actions.

## Boundary Levels

| Level | Meaning | Examples |
| --- | --- | --- |
| Allowed | Safe to do inside the current repository when relevant. | Read files, inspect code, run local tests, make scoped edits on a branch. |
| Ask first | Allowed only after explicit user confirmation. | Broad external scans, destructive commands, dependency upgrades, production config changes. |
| Draft PR only | Codex may propose and package the change, but must not merge or deploy it. | Skill self-improvement, large refactors, security-sensitive fixes. |
| Plan only | Codex may prepare a plan, checklist, dry-run, or rollback path, but not execute. | Production deployment, data migration, incident response actions. |
| Forbidden by default | Do not do unless the user gives a narrow, explicit, authorized request. | Production execution, auto-merge, broad mailbox or drive scanning. |
| Forbidden | Do not perform. | Credential exposure, unapproved exploit automation, attacks on public or third-party targets. |

## Capability Decisions

### Sub-Agent Orchestration

Status: allowed when useful, but lightweight.

Codex may use sub-agents or parallel investigation when the work is independent,
bounded, and easy to summarize. Good uses include codebase mapping, test
triage, documentation review, and comparing isolated modules.

Do not use sub-agents for heavy autonomous orchestration, recursive delegation,
or work that requires frequent shared context. The main agent remains
responsible for decisions, edits, validation, and final summary.

### Autonomous Deploy

Status: plan only by default.

Codex may prepare deployment plans, preflight checks, dry-run commands, rollback
plans, and release notes. Do not deploy to production or production-like
environments unless the user explicitly confirms the target, command, timing,
rollback path, and acceptable risk.

### Self-Improvement Loop

Status: draft PR only.

Codex may inspect public sources, record evidence, make small skill
improvements, run checks, and open a draft PR. It must not auto-merge, push
directly to `main`, use leaked code, or create hidden background modification
loops.

### Auto-Merge

Status: forbidden by default.

Codex should not merge its own PRs by default. It may explain merge readiness or
prepare a merge checklist, but human review remains the normal gate. Auto-merge
requires an explicit user request, a clean working tree, passing required
checks, and a clear statement that the user accepts the risk.

### Production Execution

Status: plan only by default.

Codex may inspect configuration, identify deployment risk, propose commands, and
prepare rollback steps. It must ask before running commands that affect
production services, production data, billing, authentication, user permissions,
or infrastructure.

### Security Exploit Automation

Status: defensive only.

Codex may perform authorized defensive security work such as threat modeling,
dependency review, static analysis, configuration review, and safe reproduction
of a bug inside an approved local or test environment.

Do not automate exploitation, credential theft, persistence, evasion,
exfiltration, destructive testing, or scanning of public or third-party targets
without clear authorization and safe scope. Prefer explaining risk and
defensive remediation.

## Confirmation Checklist

Before crossing from normal engineering into high-impact action, confirm:

- Who authorized the action
- Exact target repository, service, environment, or data scope
- Exact command or workflow to run
- Whether the action is reversible
- Rollback plan
- Expected blast radius
- What evidence supports proceeding
- What checks passed

If any answer is unclear, pause and ask.

## Public Skill Defaults

For a reusable public skill, default to:

- Branch and draft PR over direct `main` changes
- Review-gated self-improvement
- Optional memory/log/state files
- No autonomous deployment
- No auto-merge
- No production execution without explicit confirmation
- No offensive security automation
- No hidden background monitoring

These defaults make the skill safer to share across unknown repositories and
teams.
