# Decision Map And Frontier

Use a Decision Map when a long-running engineering effort has many possible
next steps and the user needs a deterministic answer to "what should happen
next?" It is a planning layer only. It does not execute work, grant write
permission, approve changes, replace checkpoints, or bypass review.

## Purpose

The Decision Map records the current planning state for a bounded engineering
effort:

- Destination: the high-level outcome.
- Decisions: resolved architectural or product choices.
- Unknowns: questions that still require investigation.
- Out of Scope: explicit exclusions.
- Work Items: proposed units of work.
- Dependencies: relationships between work items.
- Frontier: computed work that is currently executable.

The Frontier MUST be generated from the map. Do not manually invent, edit, or
promote Frontier entries. A Frontier item is a recommendation to consider next;
it is not approval to implement it.

## Boundary

Planning is not execution.
Frontier is not permission.
Recommendation is not approval.
Decision Map is optional.
Existing checkpoint, resume, authority, rollback, validation, and independent
review protocols remain valid.

Do not use a Decision Map to:

- write files without approval
- modify Git state
- open, merge, or close pull requests
- install dependencies or plugins
- read external systems
- expand task scope
- override a stop condition

## Data Model

A map contains:

- `metadata`: schema version and timestamps.
- `destination`: the desired outcome and success criteria.
- `decisions`: resolved decisions with evidence.
- `unknowns`: unresolved questions or investigation needs.
- `out_of_scope`: work explicitly excluded from this effort.
- `work_items`: actionable planning units with status.
- `dependencies`: directed edges from a work item to its prerequisites.
- `frontier`: a generated list of currently executable work item IDs.

Work item statuses:

- `pending`: not started and potentially executable.
- `in_progress`: started but not complete.
- `blocked`: waiting on an unresolved blocker.
- `completed`: done.
- `cancelled`: no longer part of the plan.
- `out_of_scope`: explicitly excluded.

## Frontier Algorithm

The Frontier is the stable, sorted list of work items where:

- status is `pending`
- the item is not blocked
- every dependency is `completed`
- the item is not marked out of scope

The algorithm MUST reject:

- duplicate work item IDs
- dependencies that reference unknown IDs
- dependency cycles
- manually supplied Frontier values that differ from the computed result
- malformed statuses

Stable ordering is by the order of `work_items` in the Decision Map. This keeps
review diffs predictable and avoids model guessing.

## Lifecycle

1. Define the destination and non-goals.
2. Record known decisions and unknowns.
3. Add work items with explicit IDs.
4. Add dependency edges.
5. Compute the Frontier.
6. Review the Frontier against current authority and checkpoint state.
7. Select the next task only after normal human approval and LHE checkpoint
   rules.

## Migration Notes

Existing projects do not need a Decision Map. Add one only when it reduces
planning ambiguity. Do not migrate checkpoint logs, task logs, or review bundles
into a Decision Map unless the user explicitly asks for that exact artifact.

## Future Extension Points

Optional adapters may later project the Decision Map into GitHub Issues, Linear,
or Jira. Those systems are not canonical. The local Decision Map remains the
source of truth unless a future reviewed protocol changes that boundary.
