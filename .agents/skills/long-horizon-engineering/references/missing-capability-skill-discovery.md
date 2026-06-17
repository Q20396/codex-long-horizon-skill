# Missing Capability Skill Discovery

Use this protocol when a task appears to need a skill, workflow, or domain
methodology that is not available locally, or when repeated task evidence shows
the current skill has a capability gap.

This is a review-gated discovery and improvement process. It may use public
GitHub search as evidence, but it must not automatically copy, install, mutate,
publish, merge, or deploy skills.

## When To Use

Use this protocol when:

- No local skill clearly covers the task.
- The current skill is too generic for the requested domain.
- A task fails because the skill lacks a workflow, safety rule, validation step,
  or domain-specific structure.
- The user asks Codex to compare public skills before improving this package.
- A new skill or bounded update may be justified by evidence.

Do not use this protocol for simple one-off tasks, typo fixes, or ordinary code
changes where local repository inspection is enough.

## Approval Gate

Before searching public GitHub or reading external repositories, ask or confirm:

- Search goal
- Search terms
- Number of repositories to inspect, usually top 5 or top 10
- Ranking method, such as relevance, stars, recency, or known source
- Whether to inspect README files only or also skill code/scripts
- Whether license information should be checked
- Whether findings may be used to propose local skill improvements

Do not send private repository content, client files, source documents, logs, or
task data to public search providers.

## Public Source Review

For each candidate public repository, record:

- Repository URL
- Relevant files inspected
- License or unknown license status
- What capability it provides
- Trigger style
- Workflow structure
- Safety boundaries
- Templates, references, scripts, or tests
- Validation approach
- Risks or unclear claims
- What can be learned as a general pattern

Analyze ideas, not proprietary wording. Do not copy external code, prompts,
prose, assets, tests, or repo structure without explicit license review and user
approval.

## Capability Gap Decision

After reviewing local and public evidence, choose one:

- No change needed
- Update an existing reference
- Add a template
- Add trigger fixture coverage
- Add a small helper script
- Create a new skill
- More evidence needed

Prefer the smallest change that addresses the observed capability gap.

## Review-Gated Upgrade Flow

1. State the local capability gap.
2. Collect public-source evidence if the user approves.
3. Separate facts, assumptions, ideas, and risks.
4. Propose a bounded edit or new-skill brief.
5. Do not copy external code or prose.
6. Update trigger fixtures when trigger behavior changes.
7. Run package checks, doctor checks, trigger checks, description audit, compile
   checks if scripts changed, and `git diff --check`.
8. Commit on a branch and open or update a draft PR for review.
9. Do not merge or push to `main` without explicit instruction.

Use `references/skill-optimization-protocol.md`,
`references/external-search-protocol.md`,
`references/external-skill-adoption-safety-review.md`,
`templates/bounded-skill-edit.md`,
`templates/skill-validation-gate.md`, and
`templates/new-skill-brief.md` when useful.

Before recommending adoption of a public or third-party skill, review the
candidate with the external skill adoption safety protocol. If the user approves
a local clone or downloaded candidate folder, run
`scripts/audit_external_skill_candidate.py` and report any security, privacy,
licensing, or operational risks for customer decision.

## Do Not Add

- Automatic GitHub scraping without user approval
- Automatic skill mutation
- Automatic install or replacement of local skills
- Hard dependencies on external skill search tools
- Hidden benchmark runs
- Paid model/API calls by default
- License-unclear code or prose
- Private examples from client work

## Stop Conditions

Stop and ask when:

- The search would require private task data.
- A useful public source has unclear or restrictive licensing.
- The candidate pattern would weaken privacy, safety, validation, or review.
- The proposed improvement is broader than the user's approved scope.
- The change would create a new skill when a smaller reference/template update
  would be enough.
