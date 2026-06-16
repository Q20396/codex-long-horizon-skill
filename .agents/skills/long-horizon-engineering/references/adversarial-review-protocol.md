# Adversarial Review Protocol

Use this optional protocol when the user asks Codex to stress-test a plan,
architecture, product decision, migration, PR, launch plan, or technical claim
before implementation.

The goal is constructive pressure-testing. Be direct and skeptical, but keep the
review useful, evidence-backed, and easy to act on.

## When To Use

- The user says "grill me", "stress test this", "challenge this plan", or
  "play devil's advocate".
- A plan affects architecture, data, APIs, cost, rollout, safety, security,
  customer experience, or release timing.
- The work would be expensive to reverse.
- The user asks for risks before implementation.

## Workflow

1. Restate the plan or claim in one sentence.
2. Inspect available repository evidence before asking about facts that can be
   discovered locally.
3. Identify the highest-impact unresolved assumption.
4. Ask one focused question at a time unless the user requests a full written
   review.
5. For each challenge, explain why it matters and give a recommended default.
6. Track confirmed decisions, assumptions, risks, evidence, and unresolved
   branches.
7. End with a compact summary and the next safest step.

## What To Challenge

- Goal and success criteria
- User workflows and failure modes
- Scope boundaries and deferred work
- Data shape, migrations, and compatibility
- API contracts, auth, permissions, and rate limits
- Rollout, rollback, observability, and ownership
- Testing, verification, and manual review evidence
- Privacy, compliance, and sensitive-data exposure

## Evidence Rules

- Separate facts from assumptions.
- Cite file paths, tests, logs, command output, or user-provided context when
  evidence changes the recommendation.
- Do not invent constraints or hidden requirements.
- If evidence is missing, label the point as an assumption or open question.

## Output Shapes

For an interactive review:

```markdown
Question:

Why it matters:

Recommended default:

Evidence:
```

For a written review:

```markdown
## Confirmed Decisions

## Strongest Risks

## Unsupported Assumptions

## Evidence Checked

## Open Questions

## Next Safest Step
```

## Safety

Do not use adversarial review to pressure the user into unsafe work, to remove
legal or technical caveats, or to make claims more certain than the evidence
allows. If private, legal, financial, medical, identity, family, or client data
would be needed, ask before reading it and use the minimum necessary detail.
