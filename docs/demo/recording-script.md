# Demo Recording Script

Target length: 20-30 seconds.

Do not record private repositories, secrets, usernames, tokens, private paths,
or client content.

## Setup

Use a disposable demo repository and reset the terminal before recording:

```bash
clear
git status --short
```

## Narrative

1. Add the marketplace:

   ```bash
   codex plugin marketplace add Q20396/codex-long-horizon-skill --ref main
   ```

2. Install or enable the plugin in Codex.
3. Select `long-horizon-engineering`.
4. Run one realistic prompt:

   ```text
   Use the long-horizon-engineering skill.
   Investigate this failing test, identify root cause, make the smallest safe
   fix, run validation, and summarize the draft PR handoff.
   ```

5. Show the plan.
6. Show validation evidence.
7. Show the draft PR handoff.

## Visible Moments

- Marketplace command or plugin UI.
- Skill name visible.
- Short plan.
- Validation command output.
- Final handoff summary.

## Cleanup

```bash
git status --short
```

Delete temporary repositories and confirm no private files were staged or
committed.
