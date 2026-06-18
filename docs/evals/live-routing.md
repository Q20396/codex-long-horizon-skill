# Optional Live Routing Evaluation

The deterministic routing contract in `tests/expected-triggers.json` is the
required regression check. It validates fixture quality and skill metadata
boundaries without calling a model.

Live Codex routing checks are optional because they depend on the installed CLI,
authentication, model behavior, and whether skill activation evidence is
observable.

## How To Run Manually

1. Create a temporary repository with no sensitive data.
2. Install or enable this plugin or copy the skills into `.agents/skills/`.
3. Pick 6-8 representative prompts from `tests/expected-triggers.json`.
4. Run each prompt in a fresh Codex session.
5. Record only observable evidence:
   - prompt ID
   - explicit or implicit invocation
   - visible selected skill, if shown
   - whether the response followed the expected skill workflow
   - inconclusive cases

Do not record hidden reasoning, credentials, private prompts, or sensitive
transcripts.

## Explicit vs Implicit

- Explicit: the prompt names `$long-horizon-engineering`,
  `$ai-video-production`, or says "Use the ... skill."
- Implicit: the prompt does not name a skill and relies on the description.

## Reporting

Use these statuses:

- `match`: observable skill evidence matched the fixture.
- `mismatch`: observable skill evidence contradicted the fixture.
- `inconclusive`: the workflow looked plausible but no activation evidence was
  visible.
- `not run`: CLI, authentication, or UI support was unavailable.

The tested CLI did not expose a stable machine-readable field proving skill
activation, so this repository does not include live routing in required CI.
