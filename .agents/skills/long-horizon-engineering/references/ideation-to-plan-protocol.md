# Ideation To Plan Protocol

Use this protocol when the best implementation path is not obvious, when design
or product tradeoffs matter, or when the user asks for options before execution.

## Workflow

1. Restate the goal and constraints.
2. Generate multiple viable options.
3. Compare tradeoffs before selecting one.
4. Define explicit selection criteria.
5. Choose or ask the user to choose.
6. Convert the selected option into a small implementation plan.
7. Attach validation and rollback steps to each task.

## Option Shape

For each option, record:

- Summary
- Files or areas likely affected
- Benefits
- Costs
- Risks
- Validation needed
- When to choose it

## Selection Criteria

Use criteria such as:

- User value
- Safety and privacy impact
- Compatibility with existing architecture
- Testability
- Time to review
- Rollback simplicity
- Maintenance cost

## Stop Conditions

Pause if the options depend on unknown business rules, sensitive data,
unverified external facts, or high-impact behavior such as deployment,
auto-merge, security automation, or production execution.
