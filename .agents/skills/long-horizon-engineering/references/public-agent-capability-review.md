# Public Agent Capability Review

Use this guide when improving this skill from public descriptions of frontier
coding agents, including Claude Code, Fable-style long-horizon agents, Codex,
and related research.

The goal is to learn safely from public capability patterns, not to copy
external code, private leaks, vendor-specific internals, or unverified claims.

## Source Reliability

Rank sources before adopting an idea:

1. Official product documentation or release notes
2. Peer-reviewed or preprint research with reproducible claims
3. Reputable technical reporting with named sources
4. Community reports, demos, benchmarks, or social posts
5. Rumors, leaked code, unverifiable screenshots, or marketing claims

Only official documentation and reproducible research should drive behavior
changes directly. Treat media reports and community claims as signals to
investigate, not as proof.

If a capability is attributed to a public model or product but no official
source confirms it, mark it as unverified.

## Capability Areas To Review

When comparing public agent systems, look for reusable patterns in:

- Long-running task execution and resumption
- Whole-codebase exploration before edits
- Context compaction and state handoff
- Permission boundaries and user confirmation gates
- Parallel research or delegated review, when available
- Validation, self-testing, and regression checks
- Visual or screenshot-assisted UI review
- Pull request, CI, and human handoff workflows
- Memory hygiene and stale-state handling
- External-source access and privacy controls

Do not adopt heavy orchestration, autonomous deployment, hidden background
monitoring, self-modifying behavior, or mandatory persistent logs.

## Evidence Table

Use this shape when reviewing a public capability:

```markdown
| Source | Reliability | Observed capability | Reusable pattern | Risk | Decision |
| --- | --- | --- | --- | --- | --- |
| URL or citation | Official / research / media / community / unverified | What was directly observed | Small safe pattern to adapt | What could go wrong | Adopt / skip / monitor |
```

## Adoption Rules

Adopt a pattern only when it is:

- Small and reviewable
- Useful for long-horizon engineering
- Compatible with user confirmation gates
- Compatible with optional memory/log/state behavior
- Safe for public repositories
- Free of copied implementation code
- Supported by evidence stronger than rumor

Prefer improving instructions, templates, and checklists before adding scripts.
Add scripts only when the behavior is deterministic, local, safe, and easy to
review.

## Capability Gap Checklist

Before proposing a change, ask:

- Does the current skill already cover this behavior?
- Is the gap about planning, execution, validation, safety, or handoff?
- Can the improvement be expressed as a small reference note or checklist?
- Does it require new tools, network access, credentials, or background tasks?
- Could it cause Codex to overreach or skip user confirmation?
- What test or package check will verify the change?

## Fable-Style Claim Handling

Public descriptions of Fable-style agents may emphasize long autonomous coding
runs, large migrations, self-testing, visual review, memory, and enterprise
handoff. Treat these as capability themes, not implementation instructions.

Safe translations for this skill:

- Long autonomous runs -> resumable working state and stop conditions
- Large migrations -> phased migration playbook with user confirmation
- Self-testing -> validation matrix and recorded test outcomes
- Visual review -> optional screenshot or UI inspection when tools are present
- Persistent memory -> optional, non-sensitive memory with safety warnings
- Enterprise handoff -> concise handoff report for substantial work

Unsafe translations to avoid:

- Running indefinitely without review
- Auto-merging or deploying
- Copying external code or leaked internals
- Mandatory memory/log creation
- Broad personal data scanning
- Treating media claims as verified facts

## Review-Gated Improvement Loop

For skill improvements based on public agent capabilities:

1. Gather public sources.
2. Classify source reliability.
3. Separate facts, assumptions, and unverified claims.
4. Identify one or two small reusable patterns.
5. Update only the smallest relevant files.
6. Run the package checker and helper `--help` commands.
7. Open a draft PR for human review.

Do not push directly to `main`, auto-merge, or create persistent reports in
sensitive repositories unless the user explicitly approves.
