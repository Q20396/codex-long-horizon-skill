# Large Migration Prompt Example

```text
Use the long-horizon-engineering skill.

Plan this migration before editing:

- Map public APIs, schemas, config, tests, and risky modules.
- Break the migration into small phases.
- Preserve backward compatibility where practical.
- Use feature flags or compatibility layers only if they reduce risk.
- Run narrow tests first, then broader tests.
- Record completed and remaining phases in the PR summary.
- Ask before changing public APIs, schemas, production config, auth, payments,
  or data behavior.

Implement only the first safe phase on a new branch and open a draft pull
request for review.
```
