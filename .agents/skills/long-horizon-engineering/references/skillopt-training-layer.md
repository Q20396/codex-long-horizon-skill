# SkillOpt-Inspired Training Layer

Use this optional protocol when the user wants a more automated skill
improvement loop inspired by SkillOpt-style text optimization.

This layer is for training and evaluating candidate skill edits. It must not
mutate production skills, merge PRs, push to `main`, or send sensitive customer
data to external providers.

## Core Idea

Treat the skill as an optimizable text artifact:

1. Collect non-sensitive task outcomes, rollout notes, trigger misses, review
   comments, or benchmark failures.
2. Generate one or more bounded candidate edits.
3. Score the candidate against a non-sensitive task set and safety checks.
4. Reject edits that regress validation, weaken privacy, or expand authority.
5. Recommend the best candidate for human review.

The deployed skill changes only after review and approval.

## Inputs

Use only approved, non-sensitive inputs:

- Current skill text
- Candidate patch or candidate skill file
- Non-sensitive benchmark cases
- Trigger fixtures
- Safety audit output
- Redacted rollout logs
- Reviewer comments that contain no private source content

Do not include secrets, API keys, legal evidence, family information, medical
details, financial account data, identity documents, private client data,
confidential source content, or exact private repository snippets.

## Optional Optimizer Model

An external optimizer model may be used only when the user explicitly approves:

- Provider or tool to use
- Exact skill text or redacted excerpt to send
- Non-sensitive evidence to send
- Purpose of the optimization
- Whether results may be stored in a report

Prefer local generation first. If external optimization is approved, send only
generic skill text, abstracted failure modes, and non-sensitive benchmark cases.
Do not send customer repositories, private logs, private prompts, credentials,
client documents, or legal/financial/medical/family materials.

## Candidate Edit Rules

Candidate edits should be small and reversible:

- Add, delete, or replace a narrow section.
- Preserve YAML front matter and skill name.
- Preserve privacy and approval gates.
- Avoid changing unrelated skills.
- Avoid broad rewrites unless a narrow patch cannot fix the failure mode.
- Include expected improvement, regression risk, and rollback plan.

## Scoring

Use `scripts/score_skill_candidate.py` for local static scoring against
`tests/skill-eval-cases.json` or an approved custom fixture.

Static scoring is not a complete behavioral benchmark. It is a first gate that
checks whether candidate text preserves required protocols and avoids forbidden
phrases. Follow it with package checks, trigger fixtures, safety audit, and any
task-specific validation.

Recommended checks:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/score_skill_candidate.py
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
python3 .agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py
python3 .agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py
git diff --check
```

## Acceptance Gate

Recommend a candidate only when:

- Candidate score is not lower than baseline.
- No required safety case fails.
- No privacy or authority boundary regresses.
- Package checks pass.
- Trigger checks pass.
- Human review is still required before deployment.

Reject the candidate when:

- It improves one benchmark while weakening safety.
- It requires sensitive data to evaluate.
- It needs unapproved external model calls.
- It broadens uploads, account access, publishing, deployment, or merge powers.
- It removes manual approval gates.

## Output

Use `templates/skill-training-report.md` when a written report would help.
Include baseline score, candidate score, failed cases, safety notes, rejected
edits, recommended action, and customer approval status.

The report should support a decision. It is not permission to auto-merge.
