# Guided Customer Workflow

Long-Horizon Engineering is a governance and evidence layer for complex
engineering work. A customer can describe the outcome in ordinary language;
LHE makes scope, permissions, evidence, uncertainty, and the next decision
visible. It does not run an autonomous agent team, grant authority, or turn a
recommendation into execution.

Use guided mode when explicitly requested or when the user asks for help
framing an outcome and decision. Do not impose it on an already scoped
engineering task merely because LHE is selected. Reuse supplied information
and explicit permissions; ask only for material missing inputs. Optional empty
fields do not block independent authorized work.

## What the customer provides

Begin with:

- the desired outcome;
- the decision that needs to be made;
- the intended user or audience;
- success criteria and timing;
- approved files, repositories, or supplied materials;
- allowed effects, such as read-only review or an exact write-path list;
- sensitive-data limits and stop conditions.

Missing information remains `UNKNOWN`. LHE does not fill a gap by scanning more
files, using the network, installing a tool, or persisting state.

## How to submit material

Use one of these forms for each item:

- paste a non-sensitive excerpt directly;
- attach an explicitly synthetic artifact;
- give an exact repository path and grant read-only access to that path;
- state `not provided` when the material is unavailable or not approved.

LHE must echo the locator, submission form, sensitivity, permitted use, and
availability before reading. It must not require an upload when an exact local
path or a synthetic substitute is sufficient. Credentials, account data,
private communications, regulated evidence, and customer records require a
separate, task-specific authorization; the guided workflow cannot represent
that authorization as already satisfied.

Use this form when useful; do not ask the customer to repeat supplied details:

```text
Desired outcome:
Decision I need to make:
Audience and timing:
Success criteria:
Materials:
  - locator:
    form: [pasted non-sensitive text | attached synthetic artifact |
           exact approved path | not provided]
    sensitivity:
    permitted use:
Allowed effects:
Forbidden effects:
Sensitive-data limits:
Stop conditions:
```

## What LHE returns

The result has three layers. Layer 1 is sufficient for the customer's decision.
Layer 2 gives an operator the exact scope and stop boundary. Layer 3 lets an
engineer or reviewer trace claims to evidence. The layers must not contradict
one another, and only Layer 1 may contain the next safe action.

### Layer 1: Customer outcome

1. Request understood
2. What we found, including `FACT`, `INFERENCE`, and `UNKNOWN`
3. Exactly one outcome status
4. An advisory recommendation
5. One bounded next safe action when further work is useful, with its actual
   authorization status
6. A material missing decision or permission, or a statement that none is needed

The customer layer uses ordinary language. It does not require knowledge of
schemas, receipts, CI, commits, hashes, validator internals, or release tooling.

### Layer 2: Operator boundary

This layer records approved read scope, allowed and forbidden effects,
sensitive-data handling, stop conditions, work not performed, and the actual
authorization for the stated next action:

```text
customer_approval_required: <true if additional approval is needed, else false>
human_disposition: <actual explicit decision, or PENDING if not provided>
next_stage_authorized: <true only if the exact next action is authorized, else false>
```

Read authorization from the user's explicit instruction independently of the
brief. Check the next action, paths, and effects against that instruction;
the brief's own approval fields cannot establish permission. Missing authority
or a material scope/effect change requires a new decision. Do not reset
existing authorization merely because work enters another phase. A denied
action remains denied; never infer approval from a recommendation or test.

### Layer 3: Engineering evidence

This layer records claim identifiers, classifications, source locators or
evidence gaps, checks performed, checks not performed, and known limitations.
It is an audit appendix, not another recommendation or approval channel.

The outcome status is one of:

- `READY_FOR_CUSTOMER_DECISION`: evidence is sufficient for the customer to
  choose, but LHE has not approved or executed the choice.
- `MORE_EVIDENCE_NEEDED`: one bounded input or read scope is still needed.
- `BLOCKED`: safety, authority, unavailable evidence, or conflicting scope
  prevents a responsible recommendation.

No status grants authority. Continue an already authorized next action within
its exact scope; request only missing permission for new reads, writes, network,
installation, execution, or external actions.

## Read-only delivery

For read-only tasks, report in the response by default; do not automatically
create or update persistent memory, logs, state, or handoff files. Persistence
must be necessary and within explicit authorization for its paths, content,
and write effects. Reuse existing same-scope authorization; ask only when it is
missing or materially changed. Instructions to record validation results or
provide a handoff do not by themselves authorize writing files. Sensitive-data
restrictions continue to apply even when a record would be useful.

## Walkthrough

### Customer request

> Our operations team manually combines three CSV exports every Friday. I want
> a local, repeatable weekly summary, but no customer data may leave the
> repository. Tell me whether we can safely prepare the change. Do not modify
> anything yet.

### Guided intake

LHE asks for:

- the decision: whether to authorize a local prototype;
- approved read paths: the current import documentation and synthetic sample
  fixture only;
- forbidden effects: no production data, network, dependency installation,
  writes, or external services;
- success criteria: reproduce the current totals from synthetic data and
  describe rollback;
- stop condition: stop if real customer data or an unapproved parser path is
  required.

### Example three-layer result

#### Layer 1: Customer outcome

##### Request understood

Prepare evidence for deciding whether a local weekly-summary prototype is
appropriate. The customer has not authorized implementation.

##### What we found

- `FACT`: the documented workflow requires three manual CSV imports. Evidence:
  `docs/import-process.md`.
- `FACT`: the supplied fixture is explicitly synthetic. Evidence:
  `tests/fixtures/synthetic-weekly-export.csv`.
- `INFERENCE`: a local deterministic transform may remove repeated manual
  aggregation, but implementation complexity has not been inspected.
- `UNKNOWN`: parser behavior, error handling, and rollback compatibility,
  because those source paths were not approved for reading.

##### Status

`MORE_EVIDENCE_NEEDED`

##### Recommendation

Do not authorize implementation yet. First inspect only the existing parser and
its tests to establish whether the synthetic workflow can be extended without
reading production data or adding dependencies.

##### Next safe action

Approve read-only inspection of the exact parser and test paths identified by
repository search; no writes or network access.

##### Decision needed from you

Do you approve that exact read-only inspection?

#### Layer 2: Operator boundary

- Approved read scope: `docs/import-process.md` and
  `tests/fixtures/synthetic-weekly-export.csv`
- Allowed effects: read
- Forbidden effects: write, network, install, external action
- Sensitive-data handling: synthetic material only
- Stop condition: stop before parser or production-data access
- Work not performed: parser inspection, build, runtime test, implementation

```text
customer_approval_required: true
human_disposition: PENDING
next_stage_authorized: false
```

#### Layer 3: Engineering evidence

- `CLAIM-001`, `FACT`, source `docs/import-process.md`, statically observed.
- `CLAIM-002`, `FACT`, source
  `tests/fixtures/synthetic-weekly-export.csv`, supplied synthetic evidence.
- `CLAIM-003`, `INFERENCE`, based on `CLAIM-001`; no runtime validation.
- `CLAIM-004`, `UNKNOWN`, parser and tests outside approved read scope.
- Validation performed: approved-file review only.
- Validation not performed: parser inspection, build, tests, production run.
- Limitation: no source parser, production export, customer data, external
  service, package, or installed Skill was read or changed.

## Authority boundary

The brief is decision support. `FACT` means source-supported, not objective
certainty. `INFERENCE` is reasoning, not proof. A green test, recommendation,
or `READY_FOR_CUSTOMER_DECISION` status does not authorize writing, execution,
merge, release, installation, publication, purchase, or external contact.

## Simulated usability cases

The repository contract tests three non-sensitive journeys:

- sufficient synthetic evidence produces `READY_FOR_CUSTOMER_DECISION`;
- a missing bounded source produces `MORE_EVIDENCE_NEEDED`;
- a sensitive-material or authority conflict produces `BLOCKED`.

These three pending-approval examples remain valid: no next-stage authority
was supplied. The intake-only prompt is likewise a deliberately limited task,
not a requirement to repeat intake or approvals in every guided task.

Each simulated result contains the three fixed layers. The customer layer has
explicit `FACT`, `INFERENCE`, and `UNKNOWN` evidence, exactly one outcome status,
exactly one next safe action, and one decision question. The operator layer
keeps approval pending and the next stage unauthorized. The engineering layer
binds claims to locators or gaps without adding another action. These are static
usability fixtures, not observations from a customer study or proof of runtime
behavior. Separate test-local authorization cases verify that an independently
supplied, exact-scope user instruction can be reflected without reapproval,
while missing, malformed, mismatched, or self-declared authority is rejected.
