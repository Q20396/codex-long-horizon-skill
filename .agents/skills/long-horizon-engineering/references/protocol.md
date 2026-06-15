# Long-Horizon Engineering Protocol

## Phase 1: Orientation

Before changing code, answer internally:

- What is the user trying to accomplish?
- What part of the system is involved?
- What evidence do I have?
- What assumptions am I making?
- What could break?

## Phase 2: Codebase Map

Create a quick map of relevant parts:

- Entry points
- Core modules
- Tests
- Config files
- Shared utilities
- Existing patterns

## Phase 3: Change Strategy

Prefer:

- Small patch over rewrite
- Existing pattern over new abstraction
- Local fix over broad refactor
- Test-backed change over speculative change

Avoid:

- Drive-by refactoring
- Formatting unrelated files
- Renaming public APIs unless required
- Changing behavior without documenting it

## Phase 4: Validation

Use this order:

1. Targeted unit tests
2. Related integration tests
3. Lint / typecheck
4. Build
5. Manual verification steps

If the project lacks tests, state that clearly.

## Phase 5: Persistence

After task completion:

- Record what worked
- Record what failed
- Record commands
- Record unresolved risks
- Record follow-up tasks

This allows future Codex runs to continue without starting from zero.