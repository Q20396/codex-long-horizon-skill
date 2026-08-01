---
name: long-horizon-engineering
description: Use for long-running software engineering and local static capability discovery. It may suggest descriptor-only legal-evidence, document-governance, or public-equity packs; keywords never authorize, install, load, or execute them. Do not use for simple edits, legal or financial advice, media, or automatic external actions.
version: 0.6.0-dev
repo: https://github.com/Q20396/codex-long-horizon-skill
skill_id: long-horizon-engineering
update_channel: candidate
---

# Long-Horizon Engineering

Use this skill as a local governance and evidence kernel for non-trivial
software engineering and bounded capability discovery. It makes scope,
permissions, evidence, uncertainty, and the customer's next safe decision
visible. It does not provide legal or financial advice, hold customer records,
connect accounts, install domain packs, or execute external actions.

## Example Prompts

- Use the long-horizon-engineering skill. Explore the repository, plan the
  migration, implement it incrementally, run validation, and open a draft PR.
- Use the long-horizon-engineering skill. Debug this failing integration test
  across modules, identify root cause before editing, and verify the smallest
  safe fix.
- Use the long-horizon-engineering skill. Resume the interrupted refactor by
  reading prior state, checking current code, and reporting the next safest
  step before changing files.
- Use the long-horizon-engineering skill in guided customer mode. Help me turn
  a plain-language engineering outcome into an evidence-backed recommendation.
  Start with intake only, make permissions and limits visible, and end with one
  next safe action for my decision.

## Guided Customer Workflow

Use this prompt-native workflow when a customer needs a clear outcome but does
not want to manage engineering process details. It is a thin presentation layer
over the existing Understand, Explore, Plan, Validate, and Human Gate workflow;
it does not create a new lifecycle, runtime, router, or approval authority.

Start with a short intake. Ask only for information needed to establish:

- the desired outcome and the decision the customer needs to make;
- who will use the result and any deadline or as-of time;
- exact files, repositories, or supplied materials that may be read;
- whether any writes, network access, installation, or external action are
  allowed;
- sensitive-data constraints, success criteria, and stop conditions.

Accept material in one of three explicit forms: a pasted non-sensitive excerpt,
an attached synthetic artifact, or an exact approved repository path. The
customer may also state `not provided`; keep the resulting gap `UNKNOWN`.
Before reading, echo each material locator, submission form, sensitivity,
permitted use, and whether it is available. Do not require an upload when an
exact local path or a synthetic substitute is sufficient.

Offer this compact intake form:

```text
Desired outcome:
Decision I need to make:
Audience and timing:
Success criteria:
Materials: [pasted non-sensitive text | attached synthetic artifact |
            exact approved path | not provided]
Allowed effects:
Forbidden effects:
Sensitive-data limits:
Stop conditions:
```

Do not inspect additional material while intake is incomplete. Default to
read-only analysis, no persistence, no network, no installation, and no
external action. If the request contains credentials, account data, private
communications, regulated evidence, or other sensitive material, stop. Never
upload, paste, sync, transmit, summarize, or place that material in model
memory. Ask for a non-sensitive substitute or propose a separately installed,
default-disabled local provider that keeps raw material encrypted and local.

Classify each material conclusion as `FACT`, `INFERENCE`, or `UNKNOWN`, with a
locatable evidence reference or an explicit evidence gap. Then return three
layers as one Customer Outcome Brief, in this order. The first layer must stand
alone for a non-engineering customer; do not require the customer to understand
schemas, receipts, CI, commits, hashes, or validator internals.

### Layer 1: Customer outcome

1. **Request understood** - the outcome and decision in plain language.
2. **What we found** - at least one concise `FACT`, `INFERENCE`, and `UNKNOWN`.
3. **Status** - exactly one of `READY_FOR_CUSTOMER_DECISION`,
   `MORE_EVIDENCE_NEEDED`, or `BLOCKED`.
4. **Recommendation** - advisory reasoning, not a decision on the customer's
   behalf.
5. **Next safe action** - exactly one bounded action, including the one approval
   or input it requires. It is a proposal, not execution permission.
6. **Decision needed from you** - a direct question the customer can answer.

### Layer 2: Operator boundary

Record the approved read scope, allowed and forbidden effects, sensitive-data
handling, stop conditions, work not performed, and the fixed approval boundary:

```text
customer_approval_required: true
human_disposition: PENDING
next_stage_authorized: false
```

### Layer 3: Engineering evidence

List claim identifiers, source locators or explicit gaps, verification status,
validation performed, validation not performed, and known limitations. This
layer supports audit and review; it must not introduce a second recommendation,
another next action, or any approval claim.

Use `READY_FOR_CUSTOMER_DECISION` only when the stated evidence and limitations
are sufficient for the customer to choose. Use `MORE_EVIDENCE_NEEDED` when one
specific additional input or read scope can close the material gap. Use
`BLOCKED` when safety, authority, unavailable evidence, or contradictory scope
prevents a responsible recommendation. Never translate any status into a write,
execution, merge, release, publication, purchase, or other external action.

For example, a customer may ask whether a local report can replace manual CSV
work while forbidding production data, writes, and network access. If only
documentation and a synthetic fixture are approved, report the verified manual
steps as `FACT`, implementation complexity as `UNKNOWN`, return
`MORE_EVIDENCE_NEEDED`, and propose one next safe action: approval to inspect
the exact parser and test paths read-only. Ask the customer that one decision
in Layer 1, record the unchanged approval boundary in Layer 2, and keep test
and source detail in Layer 3.

When repository documentation is available,
`docs/customer-guided-workflow.md` provides a longer walkthrough. It is
explanatory, not a required installed dependency; the instructions above are
the installed Skill contract.

## Local Capability Discovery

Use the packaged `catalog/local-capability-catalog.json` only to recognize
customer language and present a capability suggestion. A keyword match:

- does not select or execute a domain pack;
- does not prove that a pack or provider is installed, callable, or safe;
- does not grant read, write, network, account, upload, persistence,
  installation, execution, publication, or external-action effects;
- must report descriptor-only or unavailable status; and
- must end with one explicit next safe action for the customer.

The catalog includes descriptor-only cards for Australian legal-evidence
organization, family and office document governance, and Australian/US
public-equity research. Their implementation descriptors live in the repository
sandbox and contain no host-visible `SKILL.md`. They remain `sandbox-only`,
`explicit-only`, `installed: false`, `callable: false`, and `executable: false`.

If more than one card matches, ask for clarification. If no card matches, say
the capability is not declared. Never fetch or auto-load uninstalled code.
Only a separately installed, locally accessible skill can become callable, and
installation, provider access, and each high-impact effect require separate
approval.

The declared Local Case Evidence Provider and its synthetic pilot are
non-callable interface evidence. The pilot is `fixture-only`: it cannot connect
an account, use credentials, access the network, persist data, provide
encryption, or verify runtime feasibility. Never describe passing synthetic
tests as connector, encryption, credential-isolation, or host-enforcement
evidence.

## When To Use

Use this skill when the task involves one or more of:

- unfamiliar repository exploration
- multi-file implementation
- complex debugging or failing tests
- migrations, refactors, API changes, or schema changes
- CI, build-system, dependency, or performance work
- security-sensitive engineering review within authorized scope
- code review response or merge-readiness checks
- interrupted work that needs safe resumption
- validation-heavy engineering handoff
- local static discovery of a declared high-stakes capability card, where the
  output is a suggestion and no customer material is read

Do not use this skill implicitly for simple typos, one-line edits,
conversational answers, generic writing, video/storyboard planning, legal or
financial advice, disaster monitoring, or unrelated data analysis. A precise
catalog keyword may invoke discovery mode only; it must not invoke the domain
workflow. If the user explicitly invokes this skill for a safe unusual
workflow, follow the explicit request while preserving the safety boundaries
below.

## Failure Recovery

If work is interrupted, tests fail unexpectedly, requirements conflict, or the
repository changes underneath the task, stop and re-establish state before
editing. Re-read relevant instructions, inspect current files, separate facts
from assumptions, and continue only after the next safe step is clear.

Do not make behavioral changes based only on assumptions. Verify important
claims with repository files, tests, logs, command output, official docs, or
user-provided context before editing.

## Core Workflow

### 1. Understand

Restate the request in concrete engineering terms:

- goal
- constraints
- expected deliverable
- known files or modules
- unknowns and assumptions
- safety or privacy risks

### 2. Explore

Inspect relevant files before editing. Look for:

- existing patterns and ownership boundaries
- tests, build scripts, package managers, CI, and lint/typecheck commands
- related modules, schemas, APIs, migrations, and error logs
- prior task state if resuming work
- repository-specific instructions such as `AGENTS.md`

For large unfamiliar repositories, optionally consult
`references/repomix-codebase-context.md` <!-- profile-optional-reference -->;
generated context is a map, not a replacement for reading files you will edit.

For an approval-gated structural map assembled from explicitly allowed paths,
consult `references/safe-project-context-map.md` <!-- profile-optional-reference -->.
It is not a repository-wide scan, graph
database, background index, or permission to read sensitive files.

### 3. Plan

Produce a short implementation plan when the work is non-trivial. Include:

- files likely to change
- validation commands
- risk areas
- important assumptions and supporting evidence
- rollback or containment strategy
- user confirmation needed before high-risk steps

For substantial work, also state the Definition of Done, in-scope and
out-of-scope paths, acceptance criteria and evidence, stop conditions, and the
rollback path. A plan is a proposal, not permission to edit, run high-impact
commands, or promote a result.

When the user explicitly requests a single resumable goal-delivery record, use
the bundled-optional `templates/GOAL_DRIVEN_DELIVERY_CONTRACT.md` <!-- profile-optional-reference -->.
It is an explicit-only thin layer over the
existing Planner/Builder/Evaluator, implementation-plan, working-state, and
verification-evidence contracts. Do not create or persist an instance without
approval for its exact file path, and do not treat it as execution, promotion,
or next-stage authority.

For complex implementation plans, use `templates/implementation-plan.md` when a
written plan would reduce risk.

For long-running work with many possible next steps, use
`references/decision-map-and-frontier.md` <!-- profile-optional-reference -->
to create an optional planning-only
Decision Map. The computed Frontier can recommend the next executable work, but
it is not execution permission, approval, or a replacement for checkpoints.

### 4. Execute

Make the smallest coherent change that solves the task. Preserve local style,
avoid unrelated refactors, and do not introduce dependencies unless they are
needed and aligned with the project.

### 5. Validate

Run the narrowest relevant checks first, then broader checks when warranted.
Record commands and outcomes. For validation-heavy work, use
`templates/verification-evidence.md` when the reviewer needs a concise evidence
record.

For substantial work, distinguish execution evidence from the evaluator
conclusion. A passing command is evidence, not by itself proof that every
acceptance criterion was met. Map important requirements to direct evidence and
state any remaining gaps.

### 6. Debug

When validation fails, read the error, form a hypothesis, make a targeted fix,
and rerun the relevant check. Avoid blind edits.

### 7. Summarize

End with:

- what changed
- why it changed
- validation run and results
- known risks or limitations
- next safest step

For substantial work, include handoff-quality details: evidence used, decisions
made, what was not changed, reviewer focus, rollback notes, and remaining
uncertainty.

## Resumable State

`docs/PROJECT_MEMORY.md`, `docs/TASK_LOG.md`, `docs/WORKING_STATE.md`, and
handoff reports are optional. Use them only when persistent tracking is
appropriate, useful for resumption, and the repository is not sensitive.

Do not create or update persistent memory, logs, state, or handoff files in
sensitive repositories unless the user explicitly approves. When resuming work,
read existing memory/log/state files if present, then re-check the current
repository before editing. Compare the recorded branch, commit, working diff,
and last verification result with current state before relying on old notes.

`append_project_memory.py` is preview-only by default. It never chooses a
target implicitly: a write requires an explicit project root, an explicit
target below that root, `--apply`, and `--confirm`. Do not use it for client,
legal, family, financial, identity, account, or other sensitive material. Its
pattern checks are a fail-closed guardrail, not proof that content is safe.

Use:

- `references/resume-protocol.md` for interrupted-work recovery
- `references/planner-builder-evaluator-loop.md` for role-based planning,
  execution, evidence review, and human disposition on substantial tasks
- `references/decision-log.md` for fact, assumption, decision, evidence, risk,
  and follow-up tracking
- `templates/WORKING_STATE_TEMPLATE.md` or
  `templates/HANDOFF_REPORT_TEMPLATE.md` only when a persistent record is safe
  and useful

## Core References

Load only the references that match the task:

- `references/protocol.md` for the baseline long-horizon workflow
- `references/safety-policy.md` for safety rules
- `references/client-privacy.md` for client or confidential data
- `references/capability-boundaries.md` for high-impact agent behavior
- `references/stop-conditions.md` for when to pause
- `references/validation-matrix.md` for choosing verification
- `references/systematic-debugging-protocol.md` for root-cause debugging
- `references/large-migration-playbook.md` for broad migrations
- `references/code-review-response-protocol.md` for reviewer or CI feedback
- `references/security-review-protocol.md` for defensive security review
- `references/ship-readiness-protocol.md` for merge/release readiness
- `references/decision-map-and-frontier.md` <!-- profile-optional-reference -->
  when the user asks what to do next, how to sequence a long-running task, or
  how to identify the next safe PR
- `references/external-search-protocol.md` <!-- profile-optional-reference -->
  when current public technical facts are necessary
- `references/safe-project-context-map.md` <!-- profile-optional-reference -->
  for a bounded map of an unfamiliar repository before broad engineering work
- `references/approved-tool-contract-card.md` before a selected external tool
  is proposed for a permissioned action
- `references/local-voice-tool-sandbox.md` <!-- profile-optional-reference -->
  before proposing a local voice, speech, voice-cloning, or voice-enabled MCP
  tool, including a voice-companion workflow. It is a default-disabled design
  contract; naming a companion does not authorize microphone access, network
  access, memory, voice cloning, voice imitation, or a runtime.
- `references/three-d-asset-provider-sandbox.md` <!-- profile-optional-reference -->
  before proposing an external 3D asset provider, hosted 3D-generation
  service, or 3D asset MCP tool
- `references/ui-design-skill-adapter.md` <!-- profile-optional-reference -->
  when coordinating Hallmark or a similar downstream UI or design skill; it
  defines authority, file-write, external-source, design-token, and validation
  boundaries

The `profile-optional-reference` marker means the named resource may be
described by the core entrypoint but is loadable only when the selected profile
contains it. Inspect `package-manifest.json` before relying on such a resource.

When this skill coordinates a downstream design or UI specialist, LHE safety,
privacy, authority, file-scope, validation, and delivery rules take precedence.
The downstream skill defaults to read-only audit. Creating or changing global
styles, design tokens, design-system files, project state, external assets, or
URL access requires an exact file-level plan and user approval before execution.
Visual review does not replace build, typecheck, test, browser, or accessibility
validation.

## Explicit-Only Extensions

Some bundled references support adjacent or experimental workflows, but they do
not broaden implicit activation. Use them only when the user explicitly invokes
this skill or explicitly requests that workflow. Do not select this skill
implicitly for those domains merely because a reference exists.

See `references/explicit-only-extensions.md` <!-- profile-optional-reference -->
for the index covering writing, research, notebook, presentation, financial,
jurisdiction, disaster monitoring, external skill discovery, skill lifecycle,
SkillOpt-style optimization, local compute capability intake, and other
optional workflows.

For explicitly authorized work with an Obsidian vault, Markdown note, JSON
Canvas, or Obsidian Base, use `references/obsidian-knowledge-workflow.md` <!-- profile-optional-reference -->.
Default to a proposal and exact-path
approval; do not scan, index, sync, or write to a vault automatically.

AI video briefs, storyboards, shot lists, visual prompts, asset manifests, and
render handoffs belong to the `ai-video-production` skill unless the task is
engineering work on a video codebase, such as debugging a multi-file Remotion
rendering bug or migrating a rendering repository.

## Role Boundaries

Planner, Builder, and Evaluator are serial working roles, not autonomous
sub-agents, permission tiers, or a self-approving loop. The Planner proposes a
bounded task contract, the Builder performs only approved work, and the
Evaluator reviews evidence and reports findings. The Evaluator does not edit,
approve its own proposal, or authorize push, merge, deployment, publication, or
other high-impact actions. Human approval remains required for those actions.

## Routing And Promotion Governance

When route selection or skill promotion needs a reviewable structured decision,
use `references/skill-routing-and-promotion-contract.md`. Its fixed precedence
separates selection, ambiguity, authority, package disposition, and promotion
eligibility. A selected or eligible result is not installation, execution,
promotion, merge, release, or deployment authorization. The contract is static
and defined by a Draft 2020-12 schema plus dependency-free contract tests; it
is not a runtime router or host-enforced isolation. A formal Draft 2020-12
engine result must be reported separately when that engine is unavailable.

## Safe Update / Self-Check Protocol

When the user asks to check for updates, update skills, upgrade skills, or
compare installed skills with GitHub, first ask for explicit permission to
access:

`https://github.com/Q20396/codex-long-horizon-skill`

Explain that this first permission is only for checking updates and temporarily
downloading or cloning the repository. During the check phase, do not install,
replace, delete, or modify installed skills.

After permission, compare installed local skills with the GitHub version.

Installed local paths depend on the installation mode:

- project-level: `.agents/skills/<skill_id>` below the approved project root;
- Codex user-level: `~/.codex/skills/<skill_id>`.

The legacy `~/.agents/skills` layout is not the assumed Codex user-level
target. Do not infer an installed path: ask for, or inspect only with approval,
the exact target before comparing or updating it.

Remote repo paths:

- `.agents/skills/long-horizon-engineering`
- `.agents/skills/ai-video-production`

Summarize:

1. local version
2. remote version
3. changed files
4. added files
5. removed files
6. important instruction changes
7. risk level
8. upgrade recommendation
9. comparison-only statement: no backup or replacement was created
10. the separate `update_installed_skill.py` path required for an approved
    replacement plan

Ask for explicit second approval before applying any update. The comparison
script cannot apply an update. Use `update_installed_skill.py` for the
separately approved backup-first replacement flow; it must replace only the
selected approved skill folder, validate `SKILL.md`, reject duplicated nested
paths, report exact files changed, and provide rollback instructions.

Never silently update. Never update all skills unless the user explicitly
approves all skills. Prefer check-only mode unless the user clearly asks to
apply an update.

## Safety Rules

Never expose secrets, print API keys, commit credentials, or copy private
content into reusable logs. Treat client, private, legal, financial, family,
medical, identity, business, and confidential research data as sensitive by
default.

Do not auto-merge. Do not store secrets, API keys, private client data, legal
evidence, family information, financial account details, identity documents,
private correspondence, or confidential documents in memory, logs, state files,
handoff files, commits, public PRs, or examples.

Before reading sensitive materials, tell the user why access is needed, which
files or folders would be read, whether metadata is enough, whether content
would be quoted, summarized, or recorded, and how sensitive content will be
minimized or omitted. Wait for explicit approval before reading sensitive
content.

Ask for confirmation before:

- reading, modifying, staging, committing, pushing, or summarizing sensitive
  client or confidential materials
- deleting files or running destructive commands
- using sub-agents for broad or high-impact work
- enabling auto-merge, deployment, or production-affecting commands
- scanning local folders outside the repository
- scanning connected cloud drives, document stores, Gmail, or mailboxes
- using device location, GPS, or precise location data
- modifying auth, payment, security, database migration, production config, or
  major dependency behavior
- uploading source material to external providers or tools

If uncertain whether a file or action is sensitive, stop and ask.

## Final Reporting Contract

For substantial tasks, report:

### Summary

Briefly describe the outcome.

### Changes

List changed files and their purpose.

### Verification

List commands run and results. Say clearly if a command was unavailable or not
run.

### Risks / Notes

Mention unresolved concerns, safety boundaries, and review focus.

### Next Step

Give one recommended next step when useful.
