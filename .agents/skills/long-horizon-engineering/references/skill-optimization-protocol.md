# Skill Optimization Protocol

Use this protocol when improving this skill package or another Codex skill
based on observed behavior.

This is a lightweight, manual, review-gated method inspired by text-space skill
optimization. It does not train models, call model APIs, run autonomous update
loops, or create deployable generated skill snapshots by default.

## When To Use

Use this protocol when:

- A skill change is based on failed or weak prior behavior.
- Trigger behavior changes.
- A new reference, template, script, or safety rule changes how Codex acts.
- A reviewer asks for evidence that a skill edit improves behavior.
- The user asks for self-check, self-improvement, or skill update analysis.

Do not use this protocol for tiny typo fixes unless the typo changes meaning.

## Core Loop

1. Define the behavior gap.
2. Collect rollout evidence from examples, task transcripts, tests, or review
   comments.
3. Separate facts, assumptions, and hypotheses.
4. Propose bounded skill edits.
5. Validate the candidate against relevant examples and checks.
6. Accept only changes supported by evidence.
7. Record rejected or risky edits when useful.
8. Open a draft PR for human review.

## Rollout Evidence

Rollout evidence means observed behavior, not vibes.

Acceptable evidence includes:

- Expected trigger fixture results.
- Package checks and doctor output.
- Prior Codex task transcripts, if non-sensitive and approved.
- Reviewer comments.
- User-reported failure examples.
- Reproduced behavior in a target repository.
- Documentation or source files directly inspected.

Do not store secrets, API keys, private client data, legal evidence, family
information, medical information, financial account details, identity documents,
private correspondence, or confidential source content in rollout records.

## Bounded Edits

Keep skill edits small enough to review.

Prefer:

- Add one narrow rule.
- Replace one misleading paragraph.
- Delete obsolete or harmful wording.
- Add one trigger example.
- Add one validation check.

Avoid:

- Rewriting the whole skill.
- Adding broad orchestration.
- Making optional memory/log/state behavior mandatory.
- Adding hidden network calls.
- Adding dependencies for a documentation-only improvement.
- Copying external code or prose.

## Validation Gate

Before claiming a skill improvement, run the checks that match the change.

Common gates:

- `python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py`
- `python3 .agents/skills/long-horizon-engineering/scripts/doctor.py`
- `python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py`
- `python3 .agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py`
- `git diff --check`

Accept the change only when:

- The behavior gap is clear.
- The edit is bounded.
- Required checks pass or skipped checks are explained.
- Privacy and safety boundaries remain intact.
- The reviewer can understand why the change is useful.

If validation is weak, keep the PR draft and label the change experimental.

## Rejected Edits

When a proposed edit is rejected, record the reason if it may prevent repeated
mistakes.

Useful rejection reasons:

- Fails trigger checks.
- Broadens the skill too much.
- Weakens privacy or approval gates.
- Adds dependency or network behavior without need.
- Conflicts with current repository conventions.
- Is based on an unsupported assumption.
- Copies external code or prose.

## Source Of Truth

For this repository, the reviewed Git branch and PR are the source of truth.
Do not create a generated `best_skill.md` as a deployment artifact unless the
user explicitly asks for that release model.

## Optional Templates

Use these templates only when they help review:

- `templates/skill-rollout-log.md`
- `templates/bounded-skill-edit.md`
- `templates/skill-validation-gate.md`
- `templates/rejected-skill-edit-log.md`

