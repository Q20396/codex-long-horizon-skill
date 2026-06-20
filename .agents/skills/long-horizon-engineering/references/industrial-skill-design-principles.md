# Industrial Skill Design Principles

Use this reference when designing, reviewing, or refactoring Codex skills in
this repository.

Industrial-grade skills are not better because they are longer. They are better
when they trigger correctly, execute a clear workflow, use controlled
permissions, produce verifiable results, and improve through evidence.

Borrow architecture ideas, not external implementation. Useful public patterns
should be translated into this repository's own safety model instead of copied,
reinstalled, or treated as runtime dependencies.

## Required Contract

Start with the user problem before tool selection. A skill should prove that it
solves a real workflow problem before it adds tools, scripts, references, or
automation language.

Record clear goals and non-goals. Keep product responsibility narrow enough
that a reviewer can tell what the skill owns, what it delegates to another
skill, and what it refuses to do.

Require evidence before capability expansion. GitHub Stars, popularity, and
novelty are not evidence of safety, quality, compatibility, or justified
capability expansion.

Use privacy by default. Sensitive or private data should not be read, copied,
logged, summarized, committed, uploaded, or used for evaluation unless the user
explicitly approves the specific scope.

Plan compatibility and rollback before promoting a skill change. A reviewer
should be able to reject, revert, freeze, or narrow the change without damaging
the rest of the package.

Definition of Done:

- goals and non-goals are explicit
- trigger cases cover positive, negative, boundary, and explicit-only examples
- false-positive and false-negative risks are named
- minimum tools and permissions are documented
- policy guidance is separated from executable behavior
- deterministic contract and package validation exist
- static routing fixtures are distinguished from live routing
- privacy and approval gates are preserved
- compatibility and rollback notes are present

## Principle 1: Clear Trigger Boundary

Define when the skill should activate and when it should stay silent.

Record:

- positive trigger examples
- negative trigger examples
- borderline examples
- explicit-only cases
- overlap with sibling skills
- false-positive analysis
- false-negative analysis

Do not broaden trigger text merely to make a skill seem more capable. Broad
trigger wording increases false positives and makes the user pay process cost
for tasks that do not need the skill.

## Principle 2: Minimal Tool Boundary

Give the skill only the minimum tools and permissions needed for the task.

Prefer:

- read-only exploration before mutation
- explicit path staging instead of broad staging
- network access only after user approval
- local validation before remote actions
- human approval before install, update, render, publish, deploy, push, merge, or release

The clearer the tool boundary, the lower the chance of accidental triggering,
privacy exposure, or dangerous operation.

Use explicit-only routing for expensive, destructive, privacy-sensitive,
credential-bearing, production-facing, experimental, or broadly autonomous
capabilities. Explicit-only invocation does not bypass approval and does not
grant permission to read, write, install, upload, publish, deploy, push, merge,
or release.

## Principle 3: Progressive Disclosure

Keep `SKILL.md` concise. It should contain trigger conditions, the core
workflow, required gates, and safety boundaries.

Move long material into supporting folders:

- `references/` for long protocols and background guidance
- `templates/` for reusable review, plan, and handoff structure
- `scripts/` for stable helper commands
- `assets/` for reusable static assets, if needed later

Agents should load supporting files only when the task calls for them. This
saves context and reduces information overload.

Maintain separation of policy and executable behavior. A reference may propose
safe process, review criteria, or approval gates; scripts and commands should
only implement behavior that is explicitly approved and validated.

## Principle 4: Match Workflow Depth To Task

Use lighter process for simple tasks and heavier process for risky or complex
tasks.

Light tasks may need:

- quick file inspection
- one narrow edit
- one targeted validation command

Heavy tasks may need:

- codebase mapping
- written plan
- risk review
- staged implementation
- multiple validation layers
- rollback notes
- draft pull request review

This is workflow-depth matching, not permission to bypass safety or choose
unapproved external tools.

## Principle 5: Test The Skill Contract

At minimum, test:

- whether the skill package can be installed or validated
- whether positive prompts trigger the intended skill
- whether negative prompts do not trigger the skill
- whether required references, templates, and scripts exist
- whether the resulting workflow is safer or clearer than not using the skill

Static trigger fixtures are a regression proxy. They record declared routing
expectations but do not prove live model routing.

Use deterministic contract tests for policy defaults, required files, and
template fields. Use package validation to confirm the installed skill package
has the expected structure.

## Principle 6: Close The Evaluation Loop

Prepare test cases, cover multiple scenarios, and record results. When a skill
fails, classify the failure:

- trigger failure
- workflow failure
- permission-boundary failure
- privacy or safety failure
- validation failure
- stability or repeatability failure
- output-quality failure

Then make the smallest targeted improvement:

- revise the description
- clarify the workflow
- add a fixture
- add a template
- add or improve a helper script
- strengthen validation
- narrow or split the skill

Do not weaken safety, privacy, approval, or validation rules to improve a score.

## Principle 7: RFC-0001 Mutation Boundary

Skill evolution must preserve the controlled-evolution trust boundary:

- Default mutation action: DENY
- Default exact-path write allowlist: EMPTY
- Exact-path approval required
- Mixed-trust directory wildcards forbidden
- Proposal is not write permission
- Write permission is not approval
- Approval is not promotion

Do not describe `SKILL.md`, `references/**`, `templates/**`, or `scripts/**` as
freely candidate-mutable. Any candidate change still needs exact-path approval,
review, validation, and promotion.

## Principle 8: Router, Not Worker

A router skill helps the user decide which existing skill, protocol, or prompt
style fits the task. It should not perform the downstream work by itself.

A router may:

- classify the task
- ask one or two clarifying questions when routing is ambiguous
- recommend the smallest fitting skill or protocol
- explain why a heavier workflow is or is not needed
- point to a local reference or an approved external route catalog

A router must not:

- bypass the selected skill's safety rules
- install external skills
- invoke newly installed external skills automatically
- mutate files as part of route selection
- broaden triggers just to make a skill appear more capable

When a router recommends an external route, treat that recommendation as
proposal-only until the user approves review, download, install, and use as
separate actions.

## Principle 9: Invocation Permission Layers

Separate how a skill is discovered from what the skill is allowed to do.

Use these layers when designing or reviewing a skill:

- Human-invoked: the user explicitly names the skill, route, or workflow.
- Model-selected: the agent may choose the installed skill when the trigger
  clearly matches.
- Review-only: the skill or candidate can be inspected but not installed,
  executed, or used for mutation.
- Install-approved: the user approved installation of a specific reviewed
  subset into a specific target.
- Use-approved: the user approved invoking an installed skill for a specific
  task.
- High-impact-approved: the user separately approved actions such as network
  access, sensitive-file reads, push, merge, publish, deploy, render, release,
  or production execution.

If a platform supports routing metadata that keeps non-selected skill
descriptions out of the active context, use it conservatively. If the platform
does not support that metadata, document the activation boundary in `SKILL.md`
and keep long details in `references/`.

## Principle 10: Shared Design Vocabulary

Large skill packages need shared language so separate skills feel like one
system instead of unrelated prompts.

Maintain a small vocabulary for recurring concepts such as:

- trigger boundary
- explicit-only extension
- review-only
- proposal-only
- approval gate
- route catalog
- exact reviewed commit
- persistent state
- handoff
- validation evidence
- rollback plan

Use shared terms consistently across `SKILL.md`, `references/`, `templates/`,
tests, README sections, and PR descriptions. Shared vocabulary should describe
non-sensitive workflow concepts only. Do not use it to store client facts,
private task details, raw prompts, legal evidence, family information, account
data, credentials, or confidential source material.

## Review Checklist

Before accepting a skill change, ask:

- Is the trigger boundary sharper?
- Are unnecessary tools or permissions avoided?
- Would a router help the user choose a skill without doing the work itself?
- Is the invocation layer clear: human-invoked, model-selected, review-only,
  install-approved, use-approved, or high-impact-approved?
- Are shared design terms used consistently?
- Is `SKILL.md` still concise?
- Are long details in `references/`, `templates/`, `scripts`, or `assets`?
- Does the workflow depth match the task risk?
- Are positive, negative, and boundary fixtures updated when needed?
- Does validation prove the package still works?
- Is there a clear rollback or rejection path?

The goal is an industrial skill: correctly triggered, process-driven,
permission-controlled, verifiable, and continuously improved by review.
