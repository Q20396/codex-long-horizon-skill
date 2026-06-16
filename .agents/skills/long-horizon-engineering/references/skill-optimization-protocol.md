# Skill Optimization Protocol

Use this protocol when improving a Codex skill based on observed task outcomes,
trigger failures, reviewer feedback, or repeated workflow problems.

This is a lightweight SkillOpt-inspired methodology. It treats a skill as an
optimizable text artifact, but it does not include the Microsoft SkillOpt
runtime, optimizer, benchmark harness, or any hard dependency.

## Core Principle

Skill improvement must be evidence-backed, bounded, validation-gated, and
reviewed by a human before deployment.

Do not automatically mutate production skills.

## When To Use

Use this protocol when:

- A skill repeatedly triggers too often, too rarely, or in the wrong situations.
- A task outcome shows the skill missed an important workflow, safety rule, or
  validation step.
- Reviewer feedback identifies a recurring instruction problem.
- The user asks to compare candidate skill changes or select a deployable skill
  version.
- A skill update needs rollout evidence, reflection, and validation before
  merge.

Do not use this protocol for ordinary app code changes unless the task is about
improving a skill package.

## Lightweight Optimization Loop

1. Collect rollout, trajectory, or task outcome evidence.
2. Inspect successes, failures, and near misses.
3. Identify recurring failure modes.
4. Propose one bounded skill edit at a time.
5. Define expected improvement and regression risk.
6. Validate against trigger fixtures, package checks, doctor checks, description
   audits, and any task-specific evidence.
7. Reject edits that do not improve outcomes or that create unacceptable risk.
8. Select the best deployable skill candidate only after validation passes.
9. Record the best-skill or deployable-skill decision.
10. Open a reviewable PR or handoff. Do not auto-merge.

Use `templates/skill-rollout-log.md`,
`templates/skill-reflection-report.md`,
`templates/bounded-skill-edit.md`,
`templates/skill-validation-gate.md`, and
`templates/rejected-skill-edit-log.md` when a written record would help.

## Artifact Expectations

### Rollout Log

Record task/request, skill version or commit, expected behavior, actual
behavior, task trajectory or outcome, result, failure mode, evidence,
checked_at, and notes.

### Reflection Report

Summarize successes, failures, recurring patterns, likely root causes, proposed
improvements, risks, and what not to change.

### Bounded Skill Edit

Keep each proposed edit small. Name the target file, edit type, reason, exact
change summary, expected improvement, regression risk, validation plan, and
rollback plan.

### Validation Gate

Before calling a skill improvement complete, record checks run, trigger fixture
impact, package/doctor impact, description audit impact, acceptance criteria,
rejection criteria, and final decision.

### Rejected Edit Log

When an edit is not adopted, record the rejected edit, negative feedback,
reason, evidence, lesson learned, and how to avoid repeating it.

## Best-Skill / Deployable-Skill Selection

When multiple candidate skill changes exist, compare them by:

- Evidence quality
- Improvement against the target failure mode
- Trigger precision
- Safety impact
- Regression risk
- Documentation clarity
- Validation results
- Ease of rollback

The deployable skill candidate is the smallest candidate that improves the
observed failure mode while passing validation and preserving safety.

## Validation Commands

For this repository, prefer:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
python3 .agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py
git diff --check
```

Add task-specific validation when the skill change affects scripts, install
flow, CI, examples, or another skill.

## Safety Rules

- Do not run hidden optimizer jobs.
- Do not make paid model or API calls by default.
- Do not send private repositories, client data, legal evidence, family
  information, medical information, financial records, identity documents,
  credentials, or confidential source content to external services.
- Do not copy external code or prose.
- Do not replace human PR review.
- Do not auto-merge, auto-push to `main`, or deploy unvalidated skill changes.
- Do not treat synthetic benchmark wins as sufficient without task evidence.

## Stop Conditions

Stop and ask when:

- Evidence contains sensitive data that cannot be safely summarized.
- A proposed edit would broaden tool access, uploads, publishing, or production
  execution.
- Validation results conflict.
- A candidate skill change improves one trigger while weakening a safety rule.
- The user asks for automatic mutation, hidden benchmarking, or unreviewed
  deployment.
