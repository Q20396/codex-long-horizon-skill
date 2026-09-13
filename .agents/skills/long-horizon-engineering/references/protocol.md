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

Before adding an implementation, make a bounded search: confirm the need, then
consider relevant repository helpers, the standard library, native capabilities,
and already installed dependencies before new code. This is a search order, not
a ranking of acceptable solutions. Stop when an option meets the actual contract;
do not inspect every category ritualistically. Check normal, error and boundary
behavior, platform compatibility, and relevant security or performance needs.
A shorter or native alternative is not equivalent merely because its happy path
works. Reuse must not introduce inappropriate coupling.

For a new dependency, abstraction or in-repository technical coordination layer,
briefly identify the current requirement it serves and why a simpler existing
option is insufficient.
Use an existing task plan or handoff only when that artifact is already required
or approved; otherwise explain the rationale in the task response. Do not create
a separate record merely for this check. This grants no agent or external
coordination authority.
Preserve necessary complexity: validation, tests, error and parent exit-code
propagation, authorization, evidence, persistent-state verification and recovery
must not be removed merely to reduce code. Missing equivalence evidence means
retain the safeguard or investigate, not assume it is redundant.

## Phase 4: Validation

Use this order:

1. Targeted unit tests
2. Related integration tests
3. Lint / typecheck
4. Build
5. Manual verification steps

If the project lacks tests, state that clearly.

When a change adds substantial abstraction, dependency or duplicated machinery,
or a reviewer identifies a concrete complexity concern, a separate bounded
complexity pass may help. It is optional, not a gate for every small patch, and
does not replace correctness or security review. Limit it to the affected area.
For each proposed simplification, use the same artifact-or-response rule above
to describe the location, suspected excess, alternative, behavioral differences
or unknowns, and checks needed to establish
equivalence. Apply only within existing authorization and revalidate affected
behavior. Fewer lines or tokens alone are not evidence of improvement.

## Phase 5: Persistence

After task completion:

- Record what worked
- Record what failed
- Record commands
- Record unresolved risks
- Record follow-up tasks

This allows future Codex runs to continue without starting from zero.
