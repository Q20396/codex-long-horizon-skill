# Project Instructions for Codex

When a task involves multi-step engineering work, use the `long-horizon-engineering` skill.

## General Expectations

- Prefer small, verifiable changes.
- Read existing files before editing.
- Follow existing project style.
- Do not introduce dependencies unless necessary.
- Run relevant tests whenever possible.
- Update task logs after non-trivial tasks when appropriate and safe.
- Update project memory when discovering durable, non-sensitive project facts.
- Do not create or update memory/log files in sensitive repositories unless the user explicitly approves.

## Safety

Ask before:

- deleting files
- changing auth/payment/security logic
- running destructive commands
- modifying production config
- changing database migrations
- upgrading major dependencies

Never expose secrets.
