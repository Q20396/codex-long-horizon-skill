# Demo Recording Guide

This directory describes demo assets to record later. Do not commit generated
GIFs, videos, or screenshots unless they are intentionally reviewed.

## Suggested GIF Workflow

1. Install the skills into a small demo repository.
2. Start Codex.
3. Run a copy-paste prompt from `prompts/`.
4. Capture Codex exploring, planning, validating, and summarizing.
5. Keep the GIF short: show the workflow shape, not every command.

## Suggested Terminal Recording Workflow

Suggested tools include terminal screen recording, asciinema-style recorders, or
your operating system's built-in recorder. No specific commercial tool is
required.

Record:

1. Clone or open the repository.
2. Copy `.agents/skills` into a demo project.
3. Run `check_skill_package.py --installed`.
4. Ask Codex to perform a small safe task.
5. Show validation output and the draft PR handoff.

## Screenshots To Capture

- README skill catalog.
- Copy-paste prompt library.
- Codex implementation plan.
- Validation evidence.
- Draft PR summary.

## Recording Checklist

- Use a disposable demo repository.
- Remove secrets, tokens, usernames, private paths, and private client content.
- Keep terminal font readable.
- Show commands that viewers can copy.
- Do not include generated credentials or private logs.

## Recommended Demo Narrative

1. Install the skill.
2. Start Codex.
3. Run a copy-paste prompt.
4. Inspect the plan.
5. Generate changes.
6. Validate the result.
7. Open a draft PR.

## Cleanup Instructions

- Delete temporary demo repositories.
- Remove generated local branches if they are not needed.
- Confirm no private files were staged or committed.
- Re-run validation before publishing demo assets.
