# Code Review Response Protocol

Use this protocol when responding to human, automated, GitHub, CI, or external
review feedback on a branch or pull request.

## Core Rule

Reviewer feedback is evidence to evaluate, not an order to apply blindly.
Understand it, verify it against the repository, then respond with the smallest
safe change or a reasoned question.

## Workflow

1. Read all review comments before editing.
2. Group comments by blocking, important, minor, question, or out-of-scope.
3. Restate unclear feedback in technical terms or ask for clarification.
4. Verify each suggestion against current code, tests, constraints, and prior
   user decisions.
5. Implement one logical item at a time.
6. Run the smallest relevant validation after each meaningful fix.
7. Reply with what changed, where, and what was verified.
8. Push back only with concrete evidence when a suggestion is incorrect,
   unsafe, stale, or out of scope.

## Response Patterns

- Fixed: name the change and validation.
- Clarification needed: ask a specific question before editing.
- Not applying: explain the repo-specific evidence or safety reason.
- Deferred: explain why it is out of scope and where it should be tracked.

## Stop Conditions

Stop and ask the user when:

- review items conflict with each other
- feedback requests a scope expansion
- feedback touches sensitive, legal, financial, medical, identity, or client
  data
- the requested fix could break compatibility or public behavior
- the reviewer appears to be missing important repository context

## Safety

Do not paste private review material, raw client evidence, secrets, or
confidential source content into reusable logs or public summaries. Use links,
file paths, and short technical descriptions when possible.
