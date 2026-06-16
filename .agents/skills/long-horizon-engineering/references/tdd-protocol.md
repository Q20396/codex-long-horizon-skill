# TDD Protocol

Use this optional protocol when test-first development would reduce risk:
features with clear behavior, bug fixes that need regression coverage, shared
library changes, API behavior changes, and refactors where public behavior must
stay stable.

Do not force TDD on documentation-only changes, exploratory spikes, generated
assets, or repositories without a usable test rig unless the user agrees to add
one.

## Workflow

1. Identify the behavior to prove.
2. Inspect existing test conventions and commands.
3. Break the work into small testable increments.
4. Write or update the narrowest failing test.
5. Run it and confirm it fails for the expected reason.
6. Implement the smallest change that makes the test pass.
7. Run the relevant suite, then broader checks when risk justifies it.
8. Refactor only while tests remain green.
9. Record test evidence before claiming completion.

## Test-First Planning

For each increment, define:

- Behavior
- Test file
- Test name
- Input or fixture
- Expected result
- Failure mode covered
- Command to run

Start with the simplest meaningful behavior, then add boundaries, errors,
integration points, and regressions.

## Regression Bug Fixes

For a bug, prefer this sequence:

1. Reproduce the issue or identify the missing coverage.
2. Add a failing regression test.
3. Confirm the test fails for the bug, not for setup noise.
4. Fix the implementation.
5. Re-run the regression test and relevant suite.
6. Record the before/after evidence.

If the bug cannot be reproduced locally, say so and use the best available
evidence. Do not pretend a regression test proved behavior it did not exercise.

## Quality Checks

- Tests should assert behavior, not implementation details, unless the
  implementation detail is the public contract.
- Keep one behavior per test where practical.
- Prefer existing fixtures, helpers, and naming conventions.
- Avoid broad snapshots unless they are the established local pattern.
- Do not add brittle sleeps or network-dependent tests without clear reason.

## Stop Conditions

Pause and ask when:

- No test command or framework can be identified.
- Adding a test rig is larger than the requested task.
- The failing test would need private production data.
- The expected behavior is ambiguous.
- The user explicitly chooses a non-TDD path after risks are explained.
