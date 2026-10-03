# Interruption and Recovery Walkthrough

**ILLUSTRATIVE WALKTHROUGH — not an executed run, benchmark, screenshot or reliability claim.**

This fictional example shows what to inspect in a long task. It does not prove
automatic continuation, host wake-up, crash recovery or cross-model reliability.

## Example: resume a migration

Goal: replace an old parser API in a disposable, non-sensitive demo repository
while preserving accepted input/output behavior.

| Point in the task | Evidence to inspect | What can be concluded |
| --- | --- | --- |
| Plan | Approved file scope and acceptance cases | A plan exists, not completed work |
| Before interruption | Changed paths, exact commit/diff and recorded test command/results | Only the checks actually run support verified progress |
| Resume | Current branch, commit, staged/unstaged diff compared with the prior handoff | Old evidence may be stale; drift needs a revised bounded plan |
| Continue | Remaining approved change plus current regression checks | Work may progress; missing acceptance evidence stays open |
| Handoff | Acceptance criteria mapped to current evidence and named gaps | Human disposition, not automatic merge/release authority |

For example, a fictional handoff records 12 of 19 required items verified.
Resume at item 13 only after checking that the first 12 and their evidence still
apply to the current repository. Otherwise reconcile drift first. These counts
are illustrative, not recorded test results.

Illustrative unfinished state:

```text
Completed work: parser adapter edited.
Verified: only the targeted compatibility cases that actually ran.
Remaining: integration cases and final scope review.
Unknown: whether the current branch still matches the handoff.
Next: inspect current state before editing or repeating tests.
```

Illustrative final state **only if the required checks have actually been run**:

```text
Each required criterion: linked to its current command/result and reviewed diff.
Unverified: list any missing evidence; do not mark those criteria complete.
Human decision: accept or request a bounded correction.
Remote actions: Draft PR only if authorized, then audit the agreed objective.
Merge/release: separate actions; never inferred from passing tests.
```

These are reporting templates, not fabricated test outputs. Replace them with
actual evidence in a real run; a pass label without evidence is insufficient.
See the [resume example](../../examples/resume-work/) and
[resume protocol](../../.agents/skills/long-horizon-engineering/references/resume-protocol.md).

## Recording a real demo later

No recorded demo is supplied here. A future recording should show the original
request, approved plan, real interruption, current-state recovery, continuation,
and acceptance evidence. Use a disposable repository and non-sensitive synthetic
code. Record exact commands and results, including failures and missing proof.

Installation, persistent state, branch operations, PR creation and publication
each need applicable approval. Do not imply a demo plan authorizes them.
Do not include credentials, private paths, personal identifiers or client content.
Keep the terminal legible and label any edited or omitted portion.

Use existing recording tools and the [current installation checks](../../README.md#installation-status),
not legacy recording commands. Review generated assets before approved publication.
Remove temporary resources only with exact-target authorization; do not delete
branches by default.
