# Project Instructions for Codex

When a task involves multi-step engineering work, use the `long-horizon-engineering` skill.

## General Expectations

- Prefer small, verifiable changes.
- Read existing files before editing.
- Follow existing project style.
- Do not introduce dependencies unless necessary.
- Run relevant tests whenever possible.
- Update task logs after non-trivial tasks.
- Update project memory when discovering durable project facts.

## Safety

Ask before:

- deleting files
- changing auth/payment/security logic
- running destructive commands
- modifying production config
- changing database migrations
- upgrading major dependencies

Never expose secrets.