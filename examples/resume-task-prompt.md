# Resume Task Prompt Example

```text
Use the long-horizon-engineering skill.

Resume the previous task safely:

- Read AGENTS.md, README.md, and any existing PROJECT_MEMORY.md, TASK_LOG.md,
  or WORKING_STATE.md.
- Re-check the current repository state before editing.
- Identify what was completed, what failed, what remains uncertain, and the next
  safest step.
- Do not blindly continue from old state if the repository has changed.
- Do not create or update memory, logs, state, or handoff files in sensitive
  repositories unless I explicitly approve.
```
