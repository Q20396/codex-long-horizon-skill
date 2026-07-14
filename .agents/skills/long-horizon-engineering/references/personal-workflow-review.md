# Personal Workflow Review Protocol

Use this optional protocol only when the user explicitly invokes
`long-horizon-engineering` or explicitly requests a personal workflow review,
and supplies non-sensitive material for the current review.

This is a read-only, proposal-only reflection workflow. It is not a
personal-memory system, user-profiling system, history scanner, or a way to
override current instructions.

## Core Contract

- Analyze only non-sensitive summaries, preferences, and examples the user
  explicitly provides for this review.
- Do not scan prior chats, raw prompts, conversation logs, email, cloud drives,
  browser history, shell history, hidden files, repositories, Git history,
  device data, or GPS data.
- Do not create, update, install, activate, or persist a rule, template, skill,
  or personal manual without separate approval for the exact target path.
- Do not claim that a saved file will be automatically loaded or remembered in
  later conversations. It can be used only when the user explicitly provides
  or loads it in a future task.
- A proposed rule cannot override system, developer, repository, safety, or
  current user instructions.
- Do not infer identity, personality, mental health, private relationships, or
  other sensitive traits. Describe possible operational gaps, not personal
  diagnoses.

## Allowed Input

Prefer short, user-supplied summaries such as:

- recurring non-sensitive task categories
- stated delivery preferences and constraints
- high-level outcomes, failures, and lessons
- repeated workflow steps the user wants to review
- anonymized aggregate counts or feedback

Do not accept or reproduce secrets, credentials, raw prompts, full
conversations, client data, legal evidence, financial account details, medical
information, identity documents, private correspondence, precise location, or
confidential source material.

If the supplied material may be sensitive, stop and ask whether a redacted
summary is sufficient before reading more.

## Review Flow

1. Confirm the allowed source material and the desired outcome.
2. Separate direct observations from evidence, hypotheses, and recommendations.
3. Identify a small number of repeated operational patterns or possible gaps.
4. Propose candidate rules or workflows with scope, evidence, benefits, risks,
   false-positive risk, and expiry or review conditions.
5. Ask the user to approve, reject, revise, or defer each candidate separately.
6. Make no persistent change unless the user later approves the exact path and
   content.

Use these labels consistently:

- **Observation:** directly stated in the supplied material.
- **Evidence:** a supplied, non-sensitive fact supporting the observation.
- **Hypothesis:** a tentative explanation that still needs confirmation.
- **Candidate rule:** a proposed reusable behavior, not an active instruction.
- **User decision:** approve, reject, revise, or defer.

Do not present a hypothesis as a fact or call a user behavior a cognitive blind
spot without evidence. Prefer wording such as "possible operational gap" or
"candidate improvement."

## Candidate Workflow And Skill Suggestions

Candidate workflows should remain small and concrete. For each one, record:

- the observed repetition and supporting evidence
- the intended trigger and non-trigger boundary
- the expected benefit and simpler alternative
- privacy, security, compatibility, and maintenance risks
- false-positive and false-negative risks
- validation and rollback or removal path

A candidate workflow is not permission to create a new skill, edit an existing
skill, install a skill, broaden triggers, or enable it automatically. Those are
separate, review-gated actions.

## Optional Personal Operating Manual

The default output is an in-conversation proposal, not a persistent file. When
the user explicitly requests a durable manual, use
`templates/PERSONAL_OPERATING_MANUAL_TEMPLATE.md` as a draft only after the
user approves the exact local target and confirms that the content is
non-sensitive.

Keep a personal operating manual private and outside a public repository. Do
not commit it, share it, or copy it into project memory, task logs, working
state, handoff files, or reusable skill templates. Every rule should have a
scope, source category, user decision, review date, and expiry or removal
condition.

## Stop Conditions

Stop and ask the user when:

- the requested source is not explicitly supplied or approved
- a task would require broad history, mailbox, cloud-drive, or device scanning
- the material appears sensitive or cannot be safely summarized
- persistence, installation, or activation has not received exact-path approval
- a proposed rule would conflict with higher-priority instructions or safety
  boundaries
