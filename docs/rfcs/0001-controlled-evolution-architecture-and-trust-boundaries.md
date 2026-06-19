# RFC-0001: Controlled Evolution Architecture and Trust Boundaries

## Status

- Status: PROPOSED
- Implementation: NOT STARTED
- Runtime behavior added by this RFC: NO
- User approval required for implementation: YES
- Candidate self-application: FORBIDDEN
- Automatic stable promotion: FORBIDDEN
- Labs implementation included: NO

RFC-0001 is not v0.2 PR-02. v0.2 PR-02 remains reserved for
read-only installed-skill self-check.

RFC-0001 defines architecture only. RFC-0001 does not complete v0.3.0.
Implementation requires separate approval and separate pull requests.

## Purpose

This RFC defines a controlled evolution architecture for the
long-horizon-engineering skill package. It describes how the project may later
support self-correction, evidence-based self-improvement, candidate
self-iteration, baseline-versus-candidate evaluation, human-reviewed stable
promotion, and Stable/Labs separation without creating an unrestricted
autonomous mutation loop.

The intended flow is:

1. Observe.
2. Record privacy-preserving evidence.
3. Classify failure.
4. Confirm recurrence.
5. Propose a reproducible eval.
6. Propose a bounded candidate.
7. Evaluate baseline and candidate independently.
8. Apply security, privacy, correctness, and trust-root gates.
9. Produce a promotion recommendation.
10. Wait for human approval.
11. Promote, reject, mark inconclusive, or roll back.

## Non-Goals

This RFC does not implement:

- v0.2 PR-02 read-only installed-skill self-check
- trace collection
- telemetry
- log scanning
- repair execution
- candidate mutation execution
- baseline/candidate execution
- promotion execution
- network behavior
- external code retrieval
- hooks
- background jobs
- new dependencies
- update/apply behavior
- plugin behavior
- marketplace behavior
- release behavior
- Labs implementation

## Current Stable Guarantees

The current stable package already provides:

- a review-gated self-check policy
- proposal-only self-improvement templates
- dry-run default installed-skill update behavior
- backup-first update behavior when explicitly applied
- local safety audit tooling
- package validation tooling
- doctor checks
- trigger fixture tests
- release-readiness tooling
- explicit safety, privacy, network, update, and capability-boundary guidance

Current behavior remains unchanged by this RFC.

## Terminology

- Stable: the conservative skill package intended for ordinary installation.
- Labs: a future experimental environment for candidate evaluation and canary
  work. Labs is not implemented by this RFC.
- Candidate: a proposed skill or workflow change under review.
- Baseline: the currently approved skill state used for comparison.
- Trace: a future privacy-preserving evidence record.
- Trust root: paths and rules that candidates cannot modify or weaken.
- Protected eval: a holdout, security, or privacy evaluation outside candidate
  control.
- Human approval: an explicit user or maintainer decision recorded outside the
  candidate's control.

## Product Invariants

- A candidate may not approve itself.
- Proposal permission is not write permission.
- Write permission is not approval.
- Approval is not stable promotion.
- Stable promotion always requires an explicit human decision.
- Prompt instructions alone are not a sufficient enforcement boundary.
- Exact commit SHA is the reproducible comparison identity.
- An inconclusive evaluation is not a pass.
- One successful demonstration is never sufficient for promotion.
- The currently executing skill version may not replace itself during the same
  run.
- Tests, safety rules, privacy rules, and approval gates must not be weakened
  to make a candidate pass.

## Three-Loop Architecture

The architecture has three independent loops. These loops must never be
collapsed into one unrestricted autonomous loop.

1. Inner Repair Loop: repairs the current authorized customer task using current
   validation evidence.
2. Outer Improvement Loop: converts recurring redacted failures into
   proposal-only eval and candidate artifacts.
3. Promotion Loop: compares an explicitly approved candidate against the
   baseline in isolated, reproducible conditions.

Stable may eventually observe, collect explicitly enabled local redacted
evidence, classify failures, aggregate non-sensitive failure patterns, propose
evals, propose candidate improvements, build explicitly approved isolated
candidate worktrees, compare baseline and candidate, and recommend promotion,
rejection, or inconclusive status.

Stable may not approve itself, automatically apply a candidate to Stable, merge
itself, release itself, deploy itself, modify protected evals, modify promotion
policy, modify rollback policy, modify its immutable trust root, broaden its
own write permissions, grant itself network access, change stable branch
protection, or obtain stable-main push credentials.

## Inner Repair State Machine

Purpose: repair the current authorized customer task using current validation
evidence. The repair loop must not modify the long-horizon-engineering skill
itself.

States:

- UNDERSTAND
- PLAN
- IMPLEMENT
- VALIDATE
- CLASSIFY_FAILURE
- REPAIR
- COMPLETED
- ESCALATED
- BLOCKED
- ROLLED_BACK

Initial budgets:

- Maximum repair rounds: 4
- Maximum identical-failure rounds: 2
- Maximum changed files: 15
- Maximum unapproved dependencies: 0
- Maximum unapproved scope expansions: 0

| Source | Destination | Guard | Required evidence | Illegal conditions | Retry behavior | Stop conditions | Rollback behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UNDERSTAND | PLAN | Goal, constraints, unknowns, and risks are understood. | Request summary, repo instructions, relevant files inspected. | Jumping directly to COMPLETED. | Re-read instructions if context is stale. | Sensitive scope unclear; user approval needed. | No changes yet. |
| PLAN | IMPLEMENT | Approved scope and validation path are known. | File plan, risk notes, validation commands. | Jumping directly to COMPLETED. | Revise plan once if evidence contradicts it. | Plan requires unapproved scope expansion. | No changes yet. |
| IMPLEMENT | VALIDATE | Changes remain within authorized scope. | Diff summary, changed file count, current HEAD. | Jumping directly to COMPLETED. | Keep changes small enough to revert. | Changed file budget exceeded; security or privacy gate. | Revert only the attempted repair change. |
| VALIDATE | COMPLETED | Required checks passed and evidence belongs to current repository HEAD. | Test output, command status, evidence commit. | Completing with pending approval, stale evidence, failed checks, or unrun required checks. | Not applicable. | Any unresolved blocker. | Not needed. |
| VALIDATE | CLASSIFY_FAILURE | A required check failed or could not run. | Failing command, exit status, logs, failure reason code. | Ignoring failures or reporting PASS for checks not run. | One classification per observed failure. | Failure cannot be interpreted safely. | Preserve current state until next decision. |
| CLASSIFY_FAILURE | REPAIR | Failure is repairable, within budget, and inside authorized scope. | Failure code, hypothesis, repair plan. | Repair after budget exhaustion; repair that weakens tests. | Rerun only relevant checks after each repair. | Repeated identical failure reaches budget. | Revert attempted repair if it worsens evidence. |
| REPAIR | VALIDATE | Targeted repair is complete. | Diff summary, repair count, changed paths. | New dependency or scope expansion without approval. | Up to four repair rounds total. | No measurable progress. | Revert repair if validation regresses. |
| CLASSIFY_FAILURE | ESCALATED | Failure is not safely repairable by the agent. | Failure code, evidence, reason for escalation. | Continuing to mutate without a safe path. | None. | Permission, privacy, security, or repeated failure gate. | Restore pre-repair state when needed. |
| Any non-terminal state | BLOCKED | Required input or approval is missing. | Missing decision, missing permission, blocked command. | Guessing past the blocker. | Resume only after approval or new evidence. | User decision unavailable. | Preserve or revert to last safe state. |
| Any changed state | ROLLED_BACK | Rollback is required or approved. | Prior commit or diff, rollback reason. | Deleting unrelated work. | Verify rollback once. | Rollback artifact unavailable. | Return to last known safe state. |

COMPLETED requires:

- Required checks were actually run.
- Evidence is bound to current repository HEAD.
- Required checks passed.
- No unresolved blocker exists.
- No required approval remains pending.
- No security regression exists.
- No privacy regression exists.
- Authorized scope was not exceeded.
- Unrun checks are reported as NOT RUN.
- Claimed status matches verified status.

## Outer Improvement State Machine

Purpose: convert recurring privacy-preserving failures into proposal-only eval
and candidate artifacts.

States:

- TRACE_AVAILABLE
- REDACTED
- CLASSIFIED
- CLUSTERED
- RECURRENCE_CONFIRMED
- EVAL_PROPOSED
- HYPOTHESIS_PROPOSED
- CANDIDATE_PROPOSED
- AWAITING_REVIEW
- REJECTED
- APPROVED_FOR_EVALUATION

| Source | Destination | Guard | Required evidence | Illegal conditions | Retry behavior | Stop conditions |
| --- | --- | --- | --- | --- | --- | --- |
| TRACE_AVAILABLE | REDACTED | Trace collection was explicitly enabled. | Trace metadata, sensitivity assessment. | Persisting raw prompts or sensitive content. | Retry redaction only with stricter minimization. | Redaction confidence is low. |
| REDACTED | CLASSIFIED | Redaction completed before persistence. | Redacted trace, redaction decision. | Unredacted trace enters classification. | Reclassify if enum migration exists. | Sensitive residue found. |
| CLASSIFIED | CLUSTERED | Canonical failure codes exist. | Failure reason codes, evidence IDs. | Duplicate synonymous codes without migration mapping. | Re-cluster after code correction. | Insufficient evidence. |
| CLUSTERED | RECURRENCE_CONFIRMED | Multiple related failures exist. | Cluster references, recurrence count. | Treating one example as recurrence. | Wait for more samples. | Recurrence is not supported. |
| RECURRENCE_CONFIRMED | EVAL_PROPOSED | A reproducible eval can be proposed. | Failure cluster, fixture idea, success and failure criteria. | Proposal without evidence references. | Revise proposal after review. | Eval would require sensitive content. |
| EVAL_PROPOSED | HYPOTHESIS_PROPOSED | Eval proposal is coherent and still proposal-only. | Eval proposal, expected behavior. | Self-approving the eval. | Human may request revisions. | User rejects eval direction. |
| HYPOTHESIS_PROPOSED | CANDIDATE_PROPOSED | Candidate can target a bounded behavior change. | Hypothesis, exact requested mutation paths, risk analysis. | Candidate without rollback plan. | Candidate can be narrowed. | Mutation scope is unsafe. |
| CANDIDATE_PROPOSED | AWAITING_REVIEW | Candidate is fully documented. | Candidate contract fields, validation plan. | Applying candidate before review. | Revise only as proposal. | Required approval missing. |
| AWAITING_REVIEW | REJECTED | Human or gate rejects proposal. | Rejection reason. | Retrying automatically as approval. | New evidence may start a new proposal. | Proposal is unsafe. |
| AWAITING_REVIEW | APPROVED_FOR_EVALUATION | Human approves evaluation only. | Approval record, candidate ID. | Treating evaluation approval as stable promotion. | Proceed to Promotion Loop only. | Approval does not cover requested paths. |

Rules:

- Redaction must occur before persistence.
- Unredacted traces cannot enter classification, clustering, or candidate
  generation.
- Low-confidence sensitive content must not be persisted.
- Candidates must cite evidence IDs, failure codes, a reproducible eval
  proposal, exact requested mutation paths, risks, validation, and rollback.
- The system may propose but may not approve its own eval or candidate.

## Promotion State Machine

Purpose: compare an explicitly approved candidate with the current baseline.

States:

- CANDIDATE_APPROVED
- BASELINE_PINNED
- CANDIDATE_PINNED
- WORKTREES_CREATED
- CONFIGURATION_VERIFIED
- DEVELOPMENT_EVAL_COMPLETE
- PROTECTED_EVAL_COMPLETE
- COMPARISON_COMPLETE
- GATES_PASSED
- GATES_FAILED
- INCONCLUSIVE
- AWAITING_HUMAN_DECISION
- PROMOTED
- REJECTED
- ROLLED_BACK

| Source | Destination | Guard | Required evidence | Illegal conditions | Retry behavior | Stop conditions | Rollback behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CANDIDATE_APPROVED | BASELINE_PINNED | Evaluation approval is explicit. | Approval record, baseline exact commit SHA. | Branch name used as identity. | Resolve tag to SHA if supplied. | Baseline cannot be pinned. | No mutation yet. |
| BASELINE_PINNED | CANDIDATE_PINNED | Candidate source is exact. | Candidate exact commit SHA. | Tag without resolved SHA. | Re-resolve moved tag and report. | Candidate source is mutable. | No mutation yet. |
| CANDIDATE_PINNED | WORKTREES_CREATED | Source identities are pinned. | Baseline SHA, candidate SHA, worktree paths. | Shared mutable worktree. | Recreate isolated worktrees once. | Filesystem permission failure. | Delete experimental worktree only. |
| WORKTREES_CREATED | CONFIGURATION_VERIFIED | Worktrees are isolated. | Task-set hash, model config, tool policy, network policy, budgets. | Different configs or budgets. | Correct config before eval starts. | Config cannot be made identical. | Remove worktrees. |
| CONFIGURATION_VERIFIED | DEVELOPMENT_EVAL_COMPLETE | Development eval suite is frozen. | Eval output, required-test execution. | Editing eval after observing result. | Re-run declared flaky cases. | Required check skipped. | Preserve report. |
| DEVELOPMENT_EVAL_COMPLETE | PROTECTED_EVAL_COMPLETE | Development eval does not hit hard stop. | Holdout, security, and privacy eval output. | Candidate modifies protected eval. | Re-run only per policy. | Protected eval skipped. | Reject or roll back. |
| PROTECTED_EVAL_COMPLETE | COMPARISON_COMPLETE | Both suites completed. | Comparison artifact, metrics, missing-data report. | Omitting failed checks. | Recompute with same inputs. | Missing required data. | Preserve artifact. |
| COMPARISON_COMPLETE | GATES_PASSED | Every hard gate passes. | Gate report. | False-success case, trust-root modification, or privacy regression. | None. | Any hard gate fails. | Not applicable. |
| COMPARISON_COMPLETE | GATES_FAILED | One or more hard gates fail. | Gate failures. | Reclassifying failures to bypass gates. | None. | Hard gate failure. | Reject candidate. |
| COMPARISON_COMPLETE | INCONCLUSIVE | Data is flaky or incomplete. | Flakiness or missing-data report. | Treating INCONCLUSIVE as pass. | Repeat only under declared policy. | Confidence remains insufficient. | No promotion. |
| GATES_PASSED | AWAITING_HUMAN_DECISION | Gate report is complete. | Human decision request. | GATES_PASSED treated as PROMOTED. | Wait. | Human decision missing. | No promotion. |
| AWAITING_HUMAN_DECISION | PROMOTED | Human explicitly approves stable promotion. | Approval record. | Automatic stable promotion. | None. | Approval denied. | Rollback plan must exist. |
| AWAITING_HUMAN_DECISION | REJECTED | Human rejects or defers. | Decision record. | Retrying as approval. | New proposal required. | None. | Discard candidate. |
| PROMOTED | ROLLED_BACK | Rollback trigger fires. | Rollback trigger, prior SHA, verification result. | Candidate edits rollback logic. | Verify rollback once. | Missing rollback artifact. | Restore prior stable SHA. |

Promotion requires:

- Exact baseline commit SHA.
- Exact candidate commit SHA.
- Identical task set and task-set hash.
- Identical starting repository state.
- Identical model and configuration.
- Identical tool permissions.
- Identical network policy.
- Identical time, token, and cost budgets.
- Completed development evaluations.
- Completed protected evaluations.
- Unchanged trust-root hashes.
- All hard gates passed.
- Explicit human stable-promotion approval.

Rules:

- INCONCLUSIVE is not a pass.
- GATES_PASSED is not PROMOTED.
- The currently executing version cannot replace itself in the same run.
- Stable promotion cannot be automatic.

## Exact SHA Identity

Exact commit SHA is the reproducible comparison identity.

A tag is a human-readable input only. Every tag must resolve to an exact SHA.
Record both requested tag and resolved SHA. Detect and report moved tags.
A tag without its resolved SHA is insufficient.

The following are invalid reproducible comparison identities:

- main
- master
- latest
- branch names
- moving aliases

## Trace and Redaction Contract

This RFC defines a conceptual contract only. It does not implement schemas.

Required trace fields:

- schema_version
- trace_id
- task_id
- skill_name
- skill_version
- skill_commit
- repository_base_commit
- repository_head_commit
- evidence_commit
- task_category
- trigger_mode
- phase_transitions
- required_tests
- tests_actually_run
- files_changed_count
- repair_rounds
- claimed_status
- verified_status
- failure_reason_codes
- approval_state
- rollback_state
- cost_summary
- latency_summary

Redaction before persistence is mandatory.

When sensitivity is uncertain, do not persist the content.

Trace persistence prohibits these fields by default:

- raw prompts
- full conversations
- identities
- emails
- credentials
- tokens
- API keys
- customer source contents
- customer database contents
- client names
- internal URLs
- account identifiers
- private absolute paths
- browser history
- shell history
- Codex logs
- hidden-file contents
- precise device location
- GPS location

## Failure Taxonomy

Use one canonical enum. Do not create duplicate synonymous reason codes unless
an explicit alias and migration mapping is defined.

| Reason code | Meaning | Required evidence | Severity | Repairability | Blocks completion | Clustering | Eval proposal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WRONG_TRIGGER | Skill activated for the wrong task. | Trigger text summary and selected skill. | Medium | Repairable by trigger change. | Sometimes | Yes | Yes |
| MISSED_TRIGGER | Skill failed to activate when appropriate. | Task summary and missing skill evidence. | Medium | Repairable by trigger change. | Sometimes | Yes | Yes |
| INSUFFICIENT_DISCOVERY | Work proceeded before enough exploration. | Timeline of inspected files and edits. | High | Repairable by re-exploration. | Yes when material | Yes | Yes |
| UNSUPPORTED_ASSUMPTION | A decision lacked evidence. | Claim and missing evidence link. | High | Repairable by verification. | Yes when material | Yes | Yes |
| INCORRECT_PLAN | Plan contradicted requirements or repo facts. | Plan text and conflicting evidence. | Medium | Repairable by replanning. | Sometimes | Yes | Yes |
| SCOPE_EXPANSION | Work exceeded approved scope. | Changed paths and approval scope. | High | Repairable by rollback or approval. | Yes | Yes | Yes |
| REQUIRED_TEST_SKIPPED | A required check was not run. | Required tests and actual commands. | High | Repairable by running check. | Yes | Yes | Yes |
| WRONG_TEST_SELECTED | Validation did not match risk. | Test choice and required validation matrix. | Medium | Repairable by correct test. | Sometimes | Yes | Yes |
| TEST_FAILURE_UNRESOLVED | A failing test remained unresolved. | Test output and final status. | High | Repairable when root cause is known. | Yes | Yes | Yes |
| FALSE_SUCCESS | Success was claimed despite contradictory evidence. | Final claim and failing evidence. | Critical | Repairable only by correction and revalidation. | Yes | Yes | Yes |
| STALE_EVIDENCE | Evidence did not match current state. | Evidence commit and current HEAD. | High | Repairable by rerun. | Yes when material | Yes | Yes |
| STALE_CHECKPOINT | Resumed state was obsolete. | Checkpoint and current repo diff. | Medium | Repairable by resync. | Sometimes | Yes | Yes |
| REPEATED_FAILURE | Same failure repeated past budget. | Repair history and failure code. | Medium | Not locally repairable after budget. | Yes | Yes | Yes |
| NO_MEASURABLE_PROGRESS | Repairs did not improve evidence. | Before/after validation results. | Medium | Sometimes | Yes after retries | Yes | Yes |
| TOOL_FAILURE | Tool failed or was unavailable. | Tool command and error. | Medium | Sometimes | Sometimes | Yes | No unless recurrent |
| DEPENDENCY_FAILURE | Dependency install or runtime failed. | Dependency logs. | High | Sometimes | Yes if required | Yes | Yes |
| NETWORK_UNAPPROVED | Network was needed or attempted without approval. | Command, tool, or policy evidence. | Critical | Not bypassable. | Yes | Yes | Yes |
| PERMISSION_FAILURE | Required permission was missing. | Error output and permission boundary. | Medium | Requires user action. | Yes | Yes | No |
| SECURITY_GATE | Security rule blocked progress. | Finding or policy evidence. | Critical | Not bypassable. | Yes | Yes | Yes |
| PRIVACY_GATE | Privacy rule blocked progress. | Sensitive category and policy evidence. | Critical | Not bypassable. | Yes | Yes | Yes |
| USER_APPROVAL_REQUIRED | A user decision is required. | Missing approval record. | Low | Requires user action. | Yes | No | No |
| EXTERNAL_SOURCE_UNTRUSTED | External source failed trust review. | Source ledger and audit finding. | High | Repairable by excluding source. | Yes for adoption | Yes | Yes |
| LICENSE_UNKNOWN | License was not verified. | Missing license/provenance. | High | Repairable by review. | Yes for copying/adoption | Yes | Yes |
| MUTATION_UNAPPROVED | Mutation was attempted without approval. | Diff/action and approval state. | Critical | Not bypassable. | Yes | Yes | Yes |
| ROLLBACK_REQUIRED | Rollback is required. | Regression or boundary violation. | High | Repairable by rollback. | Yes | Yes | Yes |

## Eval Proposal Contract

Required fields:

- schema_version
- eval_id
- source_failure_codes
- evidence_references
- fixture_reference
- immutable_starting_commit
- allowed_tools
- denied_tools
- network_policy
- execution_budgets
- required_checks
- success_criteria
- failure_criteria
- false_success_criteria
- security_criteria
- privacy_criteria
- expected_artifacts
- cleanup_behavior
- provenance
- reviewer_status
- proposal_status
- user_decision
- approved_for_protected_suite
- changes_applied

Required defaults:

- Proposal status: PROPOSAL_ONLY
- User decision: PENDING
- Approved for protected suite: NO
- Changes applied: NO

## Candidate Contract

Required fields:

- schema_version
- candidate_id
- baseline_version
- baseline_commit
- evidence_references
- failure_cluster_references
- eval_references
- hypothesis
- proposed_paths
- proposed_behavior_changes
- mutation_budget
- trigger_impact
- security_impact
- privacy_impact
- network_impact
- dependency_impact
- expected_improvement
- expected_cost
- rollback_plan
- candidate_status
- user_decision
- changes_applied
- stable_promotion_approved
- evaluation_result
- promotion_recommendation
- provenance

Required defaults:

- Candidate status: PROPOSAL_ONLY
- User decision: PENDING
- Changes applied: NO
- Stable promotion approved: NO

## Baseline/Candidate Comparison Contract

Required fields:

- schema_version
- baseline_commit
- candidate_commit
- requested_baseline_tag
- resolved_baseline_sha
- requested_candidate_tag
- resolved_candidate_sha
- task_set_hash
- model_configuration
- tool_policy
- network_policy
- time_budget
- token_budget
- cost_budget
- verified_success_rate
- false_success_rate
- regression_count
- security_regression_count
- privacy_regression_count
- repair_round_average
- human_takeover_rate
- trigger_precision
- trigger_recall
- required_test_execution_rate
- cost
- latency
- statistical_confidence
- sample_size
- repeated_run_count
- missing_data
- rollback_requirement
- conclusion
- promotion_recommendation
- provenance
- approval_state

## Completion Gate

A customer task may enter COMPLETED only when:

- Required checks were actually run.
- Evidence is bound to current repository HEAD.
- Required checks passed.
- No unresolved blocker exists.
- No required approval remains pending.
- No security regression exists.
- No privacy regression exists.
- Authorized scope was not exceeded.
- Required artifacts exist.
- Failed checks are reported.
- Skipped checks are reported.
- Checks not run are reported as NOT RUN.
- Claimed status matches verified status.

## Default-Deny Mutation Manifest

This is a conceptual, versioned contract. It is not implemented by this RFC.

Required behavior:

- Default action: DENY
- Default exact-path write allowlist: EMPTY
- Candidate-specific approval: REQUIRED
- Exact repository-relative paths: REQUIRED
- Mixed-trust directory wildcards: FORBIDDEN
- Additional paths require new approval
- Candidate cannot modify its own mutation manifest
- Candidate cannot approve its own paths

Approval must bind:

- candidate ID
- baseline SHA
- exact paths
- approved operation
- approval record
- approval timestamp
- validity or expiry

Concepts:

1. PROPOSABLE: a candidate may produce a review artifact suggesting a diff.
   Proposal permission does not grant write permission, application permission,
   or promotion permission.
2. CANDIDATE-WRITABLE AFTER EXPLICIT APPROVAL: only exact repository-relative
   paths explicitly listed in the approved candidate mutation manifest. The
   default list is empty. No mixed-trust directory wildcard is allowed.
3. REVIEW-ONLY: a candidate may propose changes, but Stable may not
   automatically apply them.
4. IMMUTABLE TO CANDIDATES: candidates may not modify these paths or the
   enforcement that protects them.

The following broad paths are not freely candidate-mutable:

- .agents/skills/long-horizon-engineering/SKILL.md
- .agents/skills/long-horizon-engineering/references/**
- .agents/skills/long-horizon-engineering/templates/**
- .agents/skills/long-horizon-engineering/scripts/**

## Existing Safety-Critical Paths

The repository currently has no canonical RFC index, no root schemas/
directory, no root policies/ directory, no root promotion/ directory, no root
rollback/ directory, and no CODEOWNERS file.

Current exact path classifications:

| Path | Classification | Reason |
| --- | --- | --- |
| .agents/skills/long-horizon-engineering/SKILL.md | REVIEW-ONLY | Mixed workflow and safety instructions; a candidate may propose a diff but Stable must not automatically apply it. |
| .agents/skills/long-horizon-engineering/references/self-check-policy.md | IMMUTABLE TO CANDIDATES | Defines proposal-only behavior, network approval, reproducible comparison, privacy, and anti-mutation boundaries. |
| .agents/skills/long-horizon-engineering/references/capability-boundaries.md | IMMUTABLE TO CANDIDATES | Defines high-impact action boundaries, auto-merge, deployment, production execution, and self-improvement limits. |
| .agents/skills/long-horizon-engineering/references/safety-policy.md | IMMUTABLE TO CANDIDATES | Defines safety and privacy boundaries for sensitive work. |
| .agents/skills/long-horizon-engineering/references/client-privacy.md | IMMUTABLE TO CANDIDATES | Defines protected data categories and private-data handling. |
| .agents/skills/long-horizon-engineering/references/stop-conditions.md | IMMUTABLE TO CANDIDATES | Defines conditions that must pause or block work. |
| .agents/skills/long-horizon-engineering/references/external-source-scan.md | REVIEW-ONLY | Defines external source review guidance; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/references/external-skill-adoption-safety-review.md | REVIEW-ONLY | Defines external skill adoption review; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/references/external-tool-provider-protocol.md | REVIEW-ONLY | Defines approval-gated external tool use; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/references/skill-lifecycle-management.md | REVIEW-ONLY | Defines freeze, restore, and lifecycle decisions; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/references/skill-optimization-protocol.md | REVIEW-ONLY | Defines bounded skill-improvement workflow; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/references/skillopt-training-layer.md | REVIEW-ONLY | Defines optional candidate scoring and rejection rules; candidate changes require human review. |
| .agents/skills/long-horizon-engineering/templates/skill-validation-gate.md | REVIEW-ONLY | Template for validation and deployment readiness; not a runtime enforcement file. |
| .agents/skills/long-horizon-engineering/templates/bounded-skill-edit.md | REVIEW-ONLY | Template for bounded skill edit proposals; not a runtime enforcement file. |
| .agents/skills/long-horizon-engineering/scripts/update_installed_skill.py | REVIEW-ONLY | Controls installed-skill update behavior and backup-first application. |
| .agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py | REVIEW-ONLY | Performs safety audit checks that should not be silently weakened. |
| .agents/skills/long-horizon-engineering/scripts/audit_external_skill_candidate.py | REVIEW-ONLY | Performs external candidate safety review. |
| .github/workflows/check-skill.yml | REVIEW-ONLY | CI workflow changes require human review and must not be candidate-applied automatically. |
| .codex-plugin/plugin.json | REVIEW-ONLY | Plugin manifest controls package identity and distribution. |
| .agents/plugins/marketplace.json | REVIEW-ONLY | Marketplace manifest controls install source and availability. |
| scripts/check_release_readiness.py | REVIEW-ONLY | Release-readiness checks must not be candidate-applied automatically. |
| scripts/validate_plugin_package.py | REVIEW-ONLY | Plugin package validation must not be candidate-applied automatically. |

The exact requested paths
.agents/skills/long-horizon-engineering/references/skill-validation-gate.md and
.agents/skills/long-horizon-engineering/references/bounded-skill-edit.md are
not present. Their existing equivalents are
.agents/skills/long-horizon-engineering/templates/skill-validation-gate.md and
.agents/skills/long-horizon-engineering/templates/bounded-skill-edit.md.

A candidate may propose a human-reviewed change to review-only files where
appropriate, but it may not automatically apply, approve, or promote such a
change.

## Immutable Trust Root

Future protected path classes should include:

- policies/evolution/**
- promotion/**
- rollback/**
- evals/holdout/**
- evals/security/**
- evals/privacy/**
- candidate comparison implementation
- mutation-manifest enforcement implementation
- audit-integrity implementation
- release workflows
- CODEOWNERS
- branch-protection configuration
- credential configuration
- stable signing logic
- stable promotion thresholds

Future enforcement must combine:

- read-only filesystem mounts
- filesystem permissions
- isolated worktrees
- exact-path allowlists
- trust-root hash verification
- independent evaluator identity
- separate credentials
- branch protection
- protected CI environments
- trust-root diff rejection

Prompt rules alone are insufficient enforcement.

## Anti-Cheating Controls

Success is forbidden through:

- deleting tests
- adding skip markers
- weakening assertions
- replacing meaningful tests with trivial mocks
- suppressing exit codes
- hiding exceptions
- turning errors into warnings
- changing expected output to fit broken behavior
- reducing validation or coverage
- reusing stale evidence
- claiming PASS for checks not run
- editing promotion thresholds
- editing protected evals
- editing comparison logic
- editing mutation enforcement
- omitting failed checks
- reclassifying failures to bypass gates

## Evidence-Grounded Code Research

Future external code research must use this source order:

1. Authorized current repository.
2. Existing dependencies.
3. Official documentation.
4. Official examples.
5. Upstream repositories.
6. Trusted open-source implementations pinned to exact SHAs.
7. Broader public code only when necessary.

Before any external query, redact customer names, client names, private
repository names, private class names, private function names, private file
paths, internal domains, database names, log identifiers, account identifiers,
credentials, tokens, API keys, and customer source excerpts.

Required source ledger fields:

- schema_version
- source_id
- repository
- repository_url
- exact_commit_sha
- file
- license
- retrieved_at
- source_type
- copied_code
- adopted_pattern
- attribution_requirement
- security_notes
- privacy_notes
- provenance_verified
- review_status

External sources must be pinned to exact commit SHAs, license-reviewed,
provenance-recorded, quarantined, statically inspected, not executed before
sandbox approval, and not installed automatically into the customer repository.

Do not copy external code unless license, provenance, scope, attribution,
security review, and required human approval permit it.

Prefer independently implementing learned patterns. GitHub Stars are discovery
metadata only.

## Metrics and Promotion Gates

Initial hard gates:

- Security regressions: 0
- Privacy regressions: 0
- False-success cases: 0
- Trust-root modifications: 0
- Test-weakening cases: 0
- Unauthorized dependencies: 0
- Unauthorized network actions: 0
- Required-test execution rate: 100%
- Holdout verified-success rate: no decrease
- Resume success rate: no decrease
- At least one declared target metric improves.
- Cost and latency remain within approved budgets.

Candidate metrics may include verified success rate, false success rate,
regression count, repair round average, human takeover rate, trigger precision,
trigger recall, required-test execution rate, cost, latency, and missing data.

## Statistical and Inconclusive Results

- Minimum sample size must be declared before evaluation.
- Evaluation configuration must be frozen before observing results.
- Repeated-run count must be declared for nondeterministic tasks.
- Pass/fail oscillation is INCONCLUSIVE.
- Missing required data is INCONCLUSIVE.
- A tie does not automatically promote.
- One successful run is insufficient.
- INCONCLUSIVE never becomes GATES_PASSED.
- Human approval is still required after gates pass.
- Promotion may not proceed when a protected evaluation was skipped.
- Promotion may not proceed when required evidence is stale.
- Promotion may not proceed when task-set identity differs.

Rollback triggers include security regression, privacy regression, false
success, trust-root modification, unapproved network access, unapproved
dependency, holdout regression, resume regression, audit-integrity failure,
human rejection, canary regression, and missing rollback artifact.

## Stable and Labs Boundary

Stable may eventually:

- collect explicitly enabled local redacted evidence
- classify failures
- aggregate non-sensitive failure patterns
- generate proposal-only evals
- generate proposal-only candidates
- build user-approved isolated candidate worktrees
- compare baseline and candidate
- recommend promotion
- recommend rejection
- recommend INCONCLUSIVE
- produce human-readable review artifacts
- produce machine-readable review artifacts

Stable may not:

- apply a candidate to Stable automatically
- approve itself
- merge itself
- release itself
- deploy itself
- modify protected evals
- modify promotion policy
- modify rollback policy
- modify the immutable trust root
- hold stable-main push credentials
- modify stable branch protection

Labs may eventually:

- apply candidates in isolated experimental worktrees
- run bounded automated repair
- create experimental commits
- run candidate evaluations
- promote passing candidates to labs/canary
- roll back labs/canary automatically

Labs may not:

- automatically merge into Stable
- hold stable-main push credentials
- modify stable branch protection
- modify stable promotion policy
- modify stable rollback policy
- execute unreviewed external code outside a sandbox

Synchronization rules:

- Stable -> Labs: controlled synchronization allowed.
- Labs -> Stable: human-reviewed promotion PR only.
- Automatic reverse synchronization: FORBIDDEN.

## Threat Model

| Threat | Asset | Failure or attack path | Prevention | Detection | Recovery | Residual risk | Target version |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Candidate modifies evaluator. | Evaluation integrity. | Candidate edits comparison implementation. | Immutable evaluator path. | Trust-root diff rejection. | Reject candidate. | CI misconfiguration. | v0.5.0 |
| Candidate modifies holdout tests. | Promotion quality. | Candidate changes protected evals. | Immutable protected eval paths. | Hash verification. | Restore protected eval SHA. | Weak holdout design. | v0.5.0 |
| Candidate weakens safety policy. | User safety. | Policy edit removes a gate. | Immutable safety policies. | Policy diff gate. | Reject candidate. | Ambiguous wording. | v0.3.0 |
| Candidate weakens privacy policy. | User privacy. | Policy edit permits sensitive logging. | Immutable privacy policies. | Privacy contract tests. | Reject candidate. | User-approved disclosure. | v0.3.0 |
| Candidate weakens tests. | Correctness. | Delete or relax tests. | Anti-cheating gates. | Test-weakening audit. | Reject candidate. | Subtle weakening. | v0.4.0 |
| Candidate uses stale evidence. | Decision quality. | Evidence commit differs from HEAD. | Evidence commit binding. | SHA mismatch. | Re-run evidence. | External drift. | v0.3.0 |
| Customer information leaks through external search. | Privacy. | Raw private terms sent online. | Query redaction. | Source/query ledger review. | Stop and report. | User-approved disclosure. | v0.3.0 |
| Malicious external code executes. | Local system. | Downloaded code runs. | Quarantine and sandbox approval. | Static inspection. | Remove quarantine and reject. | Sandbox escape. | v0.5.0 |
| A compromised dependency is introduced. | Supply chain. | Candidate adds package. | Dependency approval gate. | Dependency diff audit. | Remove dependency. | Trusted dependency compromise. | v0.4.0 |
| Candidate expands writable scope. | Repository boundary. | Candidate requests broad path. | Exact-path allowlists. | Changed-path audit. | Reject or roll back. | Tool bug. | v0.5.0 |
| Candidate gains stable push credentials. | Stable branch. | Shared credentials. | Separate credentials. | Credential audit. | Revoke credentials. | Host compromise. | v0.5.0 |
| Candidate merges without approval. | Stable integrity. | Automation merges PR. | Branch protection. | Merge audit. | Revert merge. | Admin override. | v0.5.0 |
| Candidate releases without approval. | Release integrity. | Release workflow runs. | Protected release workflow. | Release audit. | Yank or supersede release. | Registry delay. | v0.5.0 |
| Candidate deploys without approval. | Production systems. | Deployment command runs. | Deployment forbidden by default. | Deployment logs. | Roll back deployment. | External side effect. | v0.5.0 |
| Candidate falsifies audit records. | Audit trail. | Logs are edited. | Append-only or hashed artifacts. | Integrity check. | Reject and restore. | Local deletion. | v0.5.0 |
| Candidate deletes rollback artifacts. | Recovery. | Candidate removes backups. | Rollback path outside candidate control. | Artifact check. | Restore from protected source. | Missing remote. | v0.5.0 |
| Repair loop runs indefinitely. | Time and cost. | No retry budget. | Repair budgets. | Repeated failure detection. | Escalate or block. | Long single run. | v0.4.0 |
| Candidate recursively creates uncontrolled agents. | Control boundary. | Agent spawning loops. | Explicit approval and budget. | Tool/action audit. | Stop and reject. | Delegated tool bug. | v0.4.0 |
| Candidate broadens routing to inflate usage. | Trigger precision. | Over-broad description. | Trigger fixtures. | False-positive tests. | Revert routing change. | Uncovered prompt types. | v0.3.0 |
| Candidate overfits development evals. | Generalization. | Candidate tuned to visible cases. | Protected holdout evals. | Dev/holdout gap. | Reject candidate. | Holdout leakage. | v0.5.0 |
| Candidate accesses hidden network channels. | Privacy and supply chain. | Script or connector network path. | Network policy. | Network audit. | Block and reject. | Platform channel. | v0.5.0 |
| Candidate reads unrelated local files. | Local privacy. | Broad filesystem scan. | Path scope and mounts. | Access audit. | Stop and report. | Tool visibility. | v0.4.0 |
| Candidate modifies its own mutation manifest. | Mutation boundary. | Candidate changes allowlist. | Manifest immutable to candidates. | Trust-root diff. | Reject candidate. | Enforcement bug. | v0.5.0 |
| Candidate changes comparison logic. | Evaluation integrity. | Comparison code edited. | Immutable comparison implementation. | Hash verification. | Reject candidate. | Evaluator bug. | v0.5.0 |
| Candidate changes promotion thresholds. | Promotion integrity. | Gate values relaxed. | Immutable thresholds. | Threshold diff audit. | Reject candidate. | Policy ambiguity. | v0.5.0 |
| Candidate hides failed checks. | Review integrity. | Failed checks omitted. | Required artifact list. | Report completeness audit. | Mark false success. | Human misses issue. | v0.4.0 |
| Candidate reclassifies failures to avoid gates. | Gate integrity. | Critical failure renamed. | Canonical enum. | Failure-code audit. | Reclassify and reject. | Ambiguous case. | v0.3.0 |
| Tag movement changes the compared source. | Reproducibility. | Tag points to new commit. | Record requested tag and resolved SHA. | Moved-tag detection. | Re-pin exact SHA. | Deleted object. | v0.3.0 |
| Baseline and candidate use different model configurations. | Eval fairness. | Config mismatch. | Configuration verification. | Comparison contract check. | Re-run with identical config. | Provider nondeterminism. | v0.5.0 |
| Baseline and candidate receive different budgets. | Eval fairness. | Time/token/cost mismatch. | Budget freeze. | Comparison contract check. | Re-run with identical budgets. | Runtime variance. | v0.5.0 |

## Rollback Model

Rollback must be defined for:

- Inner repair loop
- Candidate worktree
- Labs canary
- Stable release

Rollback artifacts must record:

- previous exact commit SHA
- candidate exact commit SHA
- diff summary
- evaluation report
- promotion decision
- rollback trigger
- rollback timestamp
- verification result
- artifact hashes where applicable

A candidate must not be able to delete or rewrite rollback artifacts.
Rollback logic must remain outside candidate control.

## Compatibility

This RFC is additive and documentation-only. It does not change installed skill
behavior, update behavior, plugin behavior, marketplace behavior, CI behavior,
release behavior, or runtime execution.

Root tests remain the canonical location for repository-level contract checks.
The RFC is placed under docs/rfcs/ because docs/ is the repository's existing
documentation root and no canonical RFC index currently exists.

## Version Roadmap

v0.2.0: Self-Check and Review-Gated Improvement.

Includes read-only self-check policy, proposal-only findings, separate
update/apply behavior, external skill audit protocol, privacy-preserving usage
review, and installed-skill self-check in reserved v0.2 PR-02.

Does not include self-correction runtime, trace runtime, candidate mutation, or
stable promotion automation.

v0.3.0: Evidence and Evaluation Foundation.

Definition of Done:

- versioned trace contract
- deterministic redaction contract
- failure taxonomy
- eval-case contract
- candidate contract
- baseline/candidate comparison contract
- local-only default
- privacy contract tests
- trust-root definition
- default-deny mutation contract
- no candidate self-application
- no automatic stable promotion

v0.4.0: Bounded Self-Correction.

Definition of Done:

- inner repair state machine
- repair budgets
- identical-failure detection
- no-progress stop
- required-test enforcement
- evidence bound to repository HEAD
- false-success detection
- anti-test-weakening controls
- escalation
- rollback
- no skill self-modification
- behavioral repair evaluations

v0.5.0: Review-Gated Candidate Self-Iteration.

Definition of Done:

- isolated candidate worktrees
- baseline and candidate pinned by exact SHA
- exact-path mutation manifests
- default-deny enforcement
- protected holdout evals
- protected security evals
- protected privacy evals
- independent comparison artifacts
- hard promotion gates
- source ledger for external code research
- human decision required
- no automatic stable merge
- no automatic stable release
- no automatic stable deployment

## Explicitly Deferred Work

- automatic stable promotion
- automatic stable merge
- automatic stable release
- automatic production deployment
- stable-main push credentials for the agent
- runtime replacement of the currently executing skill
- autonomous modification of trust-root policies
- autonomous modification of holdout evals
- autonomous modification of security evals
- autonomous modification of privacy evals
- autonomous modification of promotion thresholds
- autonomous branch-protection changes
- automatic external-code execution
- automatic dependency installation
- automatic Gmail access
- automatic cloud-drive access
- automatic GPS access
- automatic private-account access
- automatic telemetry
- automatic customer profiling
- Labs canary implementation
- multi-agent autonomous swarms
- recursive uncontrolled self-spawning
- self-generated approval

## Open Questions

- Which exact files should become externally enforced policies in v0.3.0?
- Should future schemas live under root schemas/ or docs-only examples first?
- What minimum sample size should be required for each eval class?
- Which evaluator identity and credential separation model is practical for
  this repository?
- Should Labs live in this repository or in a separate experimental package?

## Acceptance Criteria

- RFC status declares PROPOSED.
- Implementation status declares NOT STARTED.
- Runtime behavior added by this RFC is NO.
- User approval is required for implementation.
- Candidate self-application is FORBIDDEN.
- Automatic stable promotion is FORBIDDEN.
- Labs implementation included is NO.
- RFC-0001 is not v0.2 PR-02.
- v0.2 PR-02 remains reserved for read-only installed-skill self-check.
- Exact commit SHA is the reproducible comparison identity.
- Tags must resolve to and record exact SHAs.
- Mutable refs are rejected as reproducible comparison identities.
- Redaction before persistence is mandatory.
- Raw prompts, full conversations, and customer source contents are prohibited
  from traces by default.
- False-success gate equals 0.
- Required-test execution gate equals 100%.
- Default mutation action is DENY.
- Default exact-path write allowlist is EMPTY.
- Mixed-trust directory wildcards are FORBIDDEN.
- Mutation manifest cannot be candidate-modified.
- Safety-critical paths are not freely candidate-mutable.
- Trust-root modification is forbidden.
- Test weakening is forbidden.
- Protected eval modification is forbidden.
- INCONCLUSIVE is not a pass.
- GATES_PASSED still needs human approval.
- Stable -> Labs synchronization is controlled.
- Labs -> Stable requires a human-reviewed promotion PR.
- Automatic stable merge, release, and deployment are forbidden.
- Labs is not implemented.
