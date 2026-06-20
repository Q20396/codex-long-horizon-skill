# Usage and Trigger Review

Use this protocol when the user explicitly supplies local, aggregated skill
usage observations and asks for trigger or lifecycle recommendations.

This protocol is read-only with respect to current skill behavior. It may
explain evidence and propose changes, but it must not edit routing metadata,
trigger descriptions, trigger fixtures, lifecycle state, or skill files.

## Core Contract

Usage and trigger review is:

- Manual
- Local
- Aggregated
- Privacy-preserving
- Explicitly supplied by the user
- Read-only with respect to current skill behavior
- Proposal-only
- Non-telemetric
- Non-background
- Non-automatic

Required defaults:

- Proposal status: PROPOSAL_ONLY
- User decision: PENDING
- Changes applied: NO
- Trigger description modified: NO
- Trigger fixtures modified: NO
- Lifecycle state modified: NO
- Telemetry enabled: NO
- Background collection enabled: NO

The reviewer must not change the user-decision field to an approved value.
A recommendation is not approval.

## Conceptual Flow

1. RECEIVE USER-SUPPLIED AGGREGATE DATA
2. VALIDATE PRIVACY BOUNDARY
3. REVIEW TRIGGER EVIDENCE
4. CLASSIFY ROUTING ISSUE
5. FORM A PROPOSAL
6. IDENTIFY TEST-FIXTURE CHANGES
7. ASSESS SAFETY AND PRIVACY IMPACT
8. RECOMMEND ONE LIFECYCLE ACTION
9. WAIT FOR USER APPROVAL

## Prohibited Input Sources

Usage review may read only an explicit user-supplied aggregate artifact. It
must not scan or infer data from:

- Raw prompts
- Full conversations
- Codex logs
- Shell history
- Browser history
- Hidden files
- Home directories
- Repositories
- Git history
- Temporary directories
- Email
- Gmail
- Cloud drives
- Connected services
- Device information
- GPS or location
- Contacts
- User identities
- Client identities
- Account identifiers
- Credentials
- Tokens
- API keys
- Repository source contents
- Private absolute paths

When data sensitivity is uncertain:

- Do not persist it.
- Do not quote it in the review.
- Ask the user for a safer aggregate restatement.

## Permitted Aggregate Fields

Permitted aggregate fields may include:

- skill_name
- review_period
- explicit_invocation_count
- implicit_invocation_count
- correct_trigger_count
- false_positive_count
- missed_trigger_count
- too_heavy_count
- useful_task_count
- failed_task_count
- task_category_counts
- user_supplied_notes restricted to non-sensitive aggregate observations
- current_routing_mode
- recommendation

Do not require or encourage free-text fields that may capture raw prompts,
conversation excerpts, source code, paths, identities, or credentials.

## Recommendation Enum

Use exactly one of these lifecycle recommendations:

- KEEP
- OPTIMIZE
- NARROW_TRIGGER
- SPLIT
- FREEZE
- DEPRECATE

Do not add competing final recommendation values.

### KEEP

Current usage and trigger evidence is healthy. No behavior change is proposed.
May still recommend monitoring through future user-supplied aggregate reviews.

### OPTIMIZE

The skill is useful, but workflow cost, latency, validation burden, or
usability can improve without changing its fundamental scope. Requires a
separate improvement proposal.

### NARROW_TRIGGER

False positives, overbroad activation, or too-heavy feedback indicates the
skill should activate less often. May propose negative fixtures, clearer
exclusions, or explicit-only routing. Does not authorize changing the trigger.

### SPLIT

Evidence shows materially different task families, permission profiles, safety
boundaries, or execution costs should not share one skill. Requires a separate
architecture proposal.

### FREEZE

The skill should remain installed but receive no new capability work while
evidence is insufficient, usage is negligible, or risk or maintenance cost is
too high. Must be reversible. Does not disable or alter the skill
automatically. Requires explicit approval.

### DEPRECATE

The skill is obsolete, replaced, unsafe for continued use, or incompatible with
the supported product direction. Requires migration, compatibility, rollback,
and user-approval plans. Does not delete or disable the skill automatically.

## Routing-Evidence Decision Rules

### False Positives

Evidence:

- The skill activates when it should not.
- The task was too small, outside scope, or better served by another skill.

Normally propose one or more:

- Narrow trigger wording
- Add negative trigger fixtures
- Add explicit exclusions
- Require explicit invocation for higher-risk or heavier behavior
- Clarify overlap with another skill

Do not improve precision by weakening safety or privacy routing.

### Missed Triggers

Evidence:

- The skill should have activated but did not.

Normally propose one or more:

- Clarify positive trigger wording
- Add positive trigger fixtures
- Add synonyms or missing task categories
- Clarify explicit invocation examples

Do not broaden the trigger beyond the skill's real capability or permission
boundary.

### Too-Heavy Feedback

Evidence:

- The skill triggers correctly but applies excessive process, validation, state
  tracking, cost, or latency for the task.

Normally propose one or more:

- Narrow the implicit trigger threshold
- Introduce a smaller-task exclusion
- Recommend explicit-only invocation for expensive behavior
- Separate lightweight and heavy workflows
- Optimize workflow steps without weakening required validation

### Never Or Rarely Triggered

Evidence:

- Very low aggregate invocation count during a declared review period.

Normally:

- Treat low usage as evidence requiring context, not as automatic proof that
  the skill should be removed.
- Consider KEEP, FREEZE, trigger clarification, discoverability improvement, or
  SPLIT depending on product need.
- Do not automatically deprecate.

### High Missed-Trigger And High False-Positive Rates

Normally:

- Treat as routing ambiguity.
- Recommend manual routing review.
- Avoid blindly broadening or narrowing one phrase.
- Consider SPLIT when task families conflict.

### Safety Or Privacy Conflict

Safety and privacy boundaries override usage optimization.
Never weaken approval, network, privacy, filesystem, deployment, update, or mutation rules to improve activation counts.

## Trigger Fixture Model

Distinguish:

- Proposed trigger-description change
- Proposed positive fixture
- Proposed negative fixture
- Proposed explicit-invocation fixture
- Proposed boundary fixture
- Proposed no-skill fixture

Every fixture proposal must record:

- Fixture ID
- Prompt or privacy-safe abstract prompt
- Expected skill
- Expected trigger mode
- Reason
- Source aggregate signal
- Safety/privacy relevance
- Reviewer status

Static trigger fixtures validate declared routing expectations.
Static fixtures do not prove live Codex routing behavior.

`docs/evals/live-routing.md` remains advisory/non-required unless separately
approved. Live model routing must not become a hard deterministic CI gate
without a separate design and approval.

Fixture updates do not authorize editing `SKILL.md`.
Fixture updates require a separate implementation approval.

## Non-Actions

This protocol may recommend changes. It may not:

- Edit SKILL.md
- Edit trigger descriptions
- Edit routing metadata
- Freeze a skill
- Deprecate a skill
- Split a skill
- Apply fixture changes
- Record usage automatically
- Modify lifecycle state
- Install, update, merge, publish, or deploy anything
- Enable telemetry
- Scan logs
- Start a background job

## Review Artifact

Use `templates/TRIGGER_REVIEW_TEMPLATE.md` when a durable proposal would help.
Completing that template does not change triggers, fixtures, lifecycle state,
or installed skills.
