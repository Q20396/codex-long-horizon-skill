# Continuous Improvement Protocol

Use this protocol for periodic improvement of the long-horizon-engineering
skill itself.

The goal is to learn from related Codex, agent, and Agent Skills projects
without copying external code or weakening safety boundaries.

When reviewing public frontier-agent capabilities, including Fable-style public
descriptions, use `public-agent-capability-review.md` to classify source
reliability and translate capability themes into small, reviewable changes.

## Safe Loop

Run this loop at most weekly unless the user asks otherwise:

1. Check related public projects, skill catalogs, release notes, and recent PRs.
2. Record only non-sensitive observations and links.
3. Separate facts from assumptions.
4. Identify small reusable patterns, not code to copy.
5. Decide whether any pattern improves this skill.
6. Make the smallest local change.
7. Run package checks.
8. Open a draft PR for user review.

Do not modify `main` directly. Do not auto-merge. Do not copy external code
without checking the license and preserving attribution where required.

## Suggested Watchlist

Treat this list as a starting point, not a dependency:

- OpenAI Codex documentation and release notes
- Anthropic Claude Code documentation, release notes, and public agent guidance
- Agent Skills / `SKILL.md` ecosystem projects
- High-signal coding-agent tools that expose durable state, review, testing,
  worktree isolation, or approval gates
- Long-horizon software engineering benchmark projects
- This repository's own issues, PR feedback, and task history

## GitHub Scan Helper

Use `scripts/github_skill_scan.py` when a GitHub-based scan is useful. It uses
the GitHub CLI to search public repositories and inspect repository metadata and
file-tree signals.

Example:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/github_skill_scan.py --dry-run --limit 3
```

The script is an evidence collector. It does not decide what to change, does not
copy source code, and does not merge anything. Codex should review the report,
separate facts from assumptions, and only adapt small reusable patterns.

## Evidence Table

Use this shape when evaluating an upstream idea:

```markdown
| Source | Observed fact | Reusable pattern | Risk | Decision |
| --- | --- | --- | --- | --- |
| URL or repo | What was directly observed | Small idea to adapt | What could go wrong | Adopt / skip / revisit |
```

## Adoption Rules

Adopt only changes that are:

- Small and easy to review
- Evidence-backed
- Useful for long-horizon engineering work
- Safe for public repositories
- Compatible with optional memory/log/state behavior
- Free of private data and copied implementation code

Skip changes that introduce:

- Heavy orchestration
- Autonomous deployment
- Self-modifying behavior without review
- Mandatory memory or logs
- Hidden network calls
- Vendor-specific lock-in unless documented as optional
- Adoption of unverified claims as facts
- Copied code, leaked internals, or license-unclear implementation details

## Weekly Automation Boundary

A weekly automation may inspect public sources and open a draft PR, but it must
not:

- Push to `main`
- Merge PRs
- Store secrets or private data
- Create or update memory/log/state files in sensitive repositories without
  explicit user approval
- Apply large rewrites without evidence

The user remains the reviewer and final decision maker.
