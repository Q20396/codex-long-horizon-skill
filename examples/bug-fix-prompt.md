# Bug Fix Prompt Example

```text
Use the long-horizon-engineering skill.

Investigate this bug before editing:

- Reproduce the issue if possible.
- Identify the smallest likely code path.
- Add or run a targeted regression test.
- Make the smallest safe fix on a new branch.
- Run relevant existing tests.
- Open a draft pull request for review.

Do not update memory or task logs unless persistent tracking is appropriate and
the repository is not sensitive.
```
