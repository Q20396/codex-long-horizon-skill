---
name: long-horizon-engineering
description: Use for long-running software engineering and local static capability discovery. It may suggest descriptor-only legal-evidence, document-governance, or public-equity packs; keywords never authorize, install, load, or execute them. Do not use for simple edits, legal or financial advice, media, or automatic external actions.
version: 0.7.0
repo: https://github.com/Q20396/codex-long-horizon-skill
skill_id: long-horizon-engineering
update_channel: stable
---

# Long-Horizon Engineering

Use this skill as a local governance and evidence kernel for non-trivial
software engineering and bounded capability discovery. It makes scope,
permissions, evidence, uncertainty, and the customer's next safe decision
visible. It does not provide legal or financial advice, hold customer records,
connect accounts, install domain packs, or execute external actions.

## Authorization Continuity

Reuse explicit, still-valid authorization from the current conversation when
the action, target, scope and effects are unchanged. Continue necessary approved
investigation, implementation, validation, repair, review and closeout without
asking for approve at each phase. A phase change, interruption, resume or
context compaction does not reset authority.

Read the applicable instructions and existing project state before resuming,
then reconcile them with the current request and actual repository. Plans,
suggestions, test results, installation, historical records and status labels
do not independently grant permission or restore consumed one-shot permits.

Ask only for missing authority or a material change to scope, target or effects.
Missing necessary evidence, an explicit failure-stop rule or an exhausted
budget/attempt limit pauses the affected action; continue independent work
that remains authorized. Do not retry under another job, identity or environment
to bypass a stop condition. Secrets and separately controlled external effects
retain their boundaries.

Throughout this skill and its references, an instruction to obtain approval
means first check whether the exact action is already covered; reuse it if so.
It never means widening a bounded or one-shot grant. If a reference explicitly
requires a later decision on a newly frozen object, or the user's grant reserves
that decision, honor it. One complete grant can cover several specified stages;
comparison permission alone does not authorize installation or replacement.

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

Use this prompt-native workflow when the user explicitly requests guided mode
or help framing an outcome and decision. Do not impose it on an already scoped
engineering task merely because LHE is selected. It is a thin presentation layer
over the existing Understand, Explore, Plan, Validate, and Human Gate workflow;
it does not create a new lifecycle, runtime, router, or approval authority.

Reuse the outcome, materials, constraints, and explicit permissions already
provided. Ask only for missing information that materially affects the task:

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

Offer this compact intake form only when useful; do not require the user to
repeat information already supplied:

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

If an intake gap affects safety, scope, or correctness, pause only the affected
action. Continue independent authorized work; optional missing fields do not
make an otherwise sufficient intake incomplete. Default to
read-only analysis, no persistence, no network, no installation, and no
external action. If the request contains credentials, account data, private
communications, regulated evidence, or other sensitive material, pause the
affected data handling and continue independent authorized work. Never
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
5. **Next safe action** - one bounded action when further work is useful; state
   whether it is already authorized or requires a specific missing input or
   permission. A recommendation itself grants no execution permission.
6. **Decision needed from you** - ask only for a material missing decision or
   permission; otherwise state that no additional decision is needed.

### Layer 2: Operator boundary

Record the approved read scope, allowed and forbidden effects, sensitive-data
handling, stop conditions, work not performed, and the actual approval boundary.
Populate these fields from explicit authorization for the stated next action,
not from the template, a plan, or a passing check:

```text
customer_approval_required: <true if additional approval is needed, else false>
human_disposition: <actual explicit decision, or PENDING if not provided>
next_stage_authorized: <true only if the exact next action is authorized, else false>
```

Do not reset existing authorization merely because work enters another phase.
Ask again only for missing authority or a material change to scope or effects.

### Layer 3: Engineering evidence

List claim identifiers, source locators or explicit gaps, verification status,
validation performed, validation not performed, and known limitations. This
layer supports audit and review; it must not introduce a second recommendation,
another next action, or any new grant of approval.

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
installation, provider access, and each high-impact effect must be covered by
explicit authorization. One grant may cover the specified effects together;
a catalog match cannot supply missing authority.

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

## Local Compute Orchestration (Beta, opt-in)

客户名称统一为 **本地算力辅助（Beta）**；20396客户版本标Beta，机器标识/frontmatter/接口及本节旧锚点不改。20396自有装配/升级成功后默认展示可选启用/授权offer；显式--local-assist才调用准备入口，平台市场无通用hook。setup在本地终端分别询问启用和元数据读取；拒绝零探测。固定Darwin资产59项清单已只读核验，安全解包/离线模型注册/同次卸载回滚/自有服务句柄生命周期有合成覆盖，没有安装运行实际包。NVIDIA/AMD/Apple Silicon/Mac Studio端到端、任务质量及节省均未验证。

The default v0.7.0 package includes `scripts/local_compute_deployment.py` and
`scripts/local_compute_pool.py`. They are the single implementation source,
available relative to this installed SKILL.md; no repository clone is needed.
Use the existing Python runtime and explicitly add this Skill's `scripts`
directory to the invoking process's import path to import
`local_compute_deployment` and `local_compute_pool`. Do not install Python or
dependencies automatically if the runtime is unavailable.

Normal workflow remains OPENAI_ONLY. Do not import or invoke these APIs unless
local compute is relevant and requested. Installation/import does not authorize
hardware inspection, provider installation, model download, inference, network
access or a node pool. `collect_probe(node_id, consent, reader)` requires explicit
node inspection consent and a caller-supplied read-only reader. The opt-in local_model_assist.py supplies partial metadata readers and a
loopback Ollama worker and a fixed Darwin owned-file installation recipe. Pause the affected
local-compute action if a qualified adapter or fact is unavailable; continue other authorized work. Hardware
inspection, download/install, storage, inference, network and costs must each
be covered, but may be authorized together once for the same fixed scope.
Installation does not prove qualified local routing or measured cloud savings.

Use the installed `scripts/local_model_assist.py status` or `prepare` explicit entry for new/upgrade planning; these have no hardware, network or install effects. No plugin install/upgrade hook is registered by this candidate. Do not probe this developer's computer, install a runtime or run inference merely because implementation is requested. Customer hardware absence does not block code/mock work.

`deployment-plan` is effect-free. `deploy-files` requires separately bound lifecycle consent, a budget and probe authority before native platform/resource checks or effects. It downloads only pinned runtime/config/layers, installs the exact reviewed runtime tree and private legacy Ollama model manifest/blob layout, and leaves all runtime/task results UNVALIDATED. Runtime staging may follow only the one observed GitHub release-assets HTTPS edge; other redirects fail closed. Never execute these actions on the developer's computer under implementation-only authority.

Ownership facts now use the existing DurableJournal (<=256 entries, whole file <=1MiB), not another ledger. Fresh restore authority, root identity, version/pins, every file/link/hash and remaining budget must be checked. A legacy record cannot adopt customer resources; UNKNOWN/pending and consumed reservations are never reset. Same-pin upgrade reuse downloads nothing; different pins use a new private root and retain the original. Uninstall first marks owned state UNKNOWN, then records remaining files only after success.

`serve-session` exposes restored owned service start and original-handle stop in a bounded foreground session, with separately bound start/stop authority, private HOME/TMP/MODELS, loopback and NO_CLOUD. Persist POSSIBLY_ACTIVE before launching; direct reaping records descendant UNKNOWN, never idle. `uninstall` requires fresh delete/save authority and reliable host idle confirmation; previous activity/legacy UNKNOWN also requires confirm-idle scope. This is a cooperative-host assertion, not independent process evidence; never infer it from the record or direct exit. No PID adoption or permanent daemon is installed.

The original public fixed-format `qualify` smoke check remains qualified=false. With separately authorized input/criteria files, native probe and native inference, the exact-JSON qualification bridge can write a private short-lived schema2 record only for those input bytes, criteria, version/model and data scope. Injected/synthetic clients never mint native qualification. `assist` checks scope before reading and actual input hash before dispatch; a new answer must still satisfy the criteria before release. No class-wide competence follows from one case. Archive verification, installation, runtime start and token savings remain separate acceptance states.

Codex can explicitly invoke the CLI tool; its default model is unchanged. Normalized local usage is returned, missing counts UNKNOWN. Automatic desktop-wide routing, complete hosted-token acquisition, generic human/natural-language grading and permanent service supervision are not implemented; actual customer/native/Codex and same-quality cloud comparisons remain untested. Do not describe those gaps as merely missing developer hardware or create false qualification to bypass them.

Before `probe`, obtain the exact node/field/disk-scope consent; missing AMD/Windows/available-resource facts remain UNKNOWN. Before `assist`, a trusted host must supply the current qualified Node record, exact runtime/model/task/data binding and explicit result-return permission. Do not mint Node booleans from a nonempty reference. This is a cooperative-host assertion boundary, not identity authentication. LOCAL_ONLY output may only be released to a local caller; the CLI return-to-cloud path requires separate scope and binds the input path. Never inject cloud_worker on local failure.

Use existing deployment/pool/token-accountability modules, not duplicate cores. Runtime metadata/known install declarations are not real health or task qualification. Explicit project-owned install/update handoff runs prepare only, retaining -I isolation and leaving a completed skill installation intact on feature failure. Lifecycle staging/cleanup must retain exact consent, immutable pins, ownership and UNKNOWN; staging is not installation. No Codex default/provider configuration is changed. Caller must serialize device use and retain UNKNOWN state; one-shot CLI is not durable anti-replay or cross-process GPU reservation. Token comparison remains scoped and requires complete same-task/same-cloud-model quality evidence; absent counts are UNKNOWN, all return/retry/review calls count and negative benefit is reported.


These are synthetic-tested Beta foundations, not production-ready deployment.
Workers and evidence are trusted caller inputs, not a remote authentication or
sandbox guarantee. LOCAL_ONLY inputs and derived outputs cannot use cloud
fallback. Real provider/model/multi-node validation is NOT_RUN; cloud savings
are UNMEASURED. Distributed inference and model sharding are not implemented.

## Failure Recovery

If work is interrupted, tests fail unexpectedly, requirements conflict, or the
repository changes underneath the task, pause affected edits and re-establish
state. Continue independent authorized work while resolving the affected part. Re-read relevant instructions, inspect current files, separate facts
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
- any missing authorization before high-risk steps; do not ask again when covered

For substantial work, also state the Definition of Done, in-scope and
out-of-scope paths, acceptance criteria and evidence, stop conditions, and the
rollback path. A plan is a proposal, not permission to edit, run high-impact
commands, or promote a result.

When the user explicitly requests a single resumable goal-delivery record, use
the bundled-optional `templates/GOAL_DRIVEN_DELIVERY_CONTRACT.md` <!-- profile-optional-reference -->.
It is an explicit-only thin layer over the
existing Planner/Builder/Evaluator, implementation-plan, working-state, and
verification-evidence contracts. Do not create or persist an instance without
existing or new explicit authorization for its exact file path, and do not
treat the record itself as execution, promotion,
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
and rerun the relevant check only within the active attempt/budget and
failure-stop rules. Do not repeat a consumed one-shot run. Avoid blind edits.

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

For read-only tasks, report in the response by default; do not automatically
create or update persistent memory, logs, state, or handoff files. Persistence
must be necessary and within explicit authorization for its paths, content,
and write effects. Reuse existing same-scope authorization; ask only when it is
missing or materially changed. Instructions to record validation results or
provide a handoff do not by themselves authorize writing files.

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
other high-impact actions. Explicit human authorization remains required;
reuse a valid same-scope grant rather than requesting it again.

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
compare installed skills with GitHub, first check for existing explicit
authorization to access the following source; ask only if missing:

`https://github.com/Q20396/codex-long-horizon-skill`

If the grant covers comparison only, keep it limited to checking updates and
necessary temporary retrieval; do not install, replace, delete or modify
installed skills. A grant that also covers an exact backup-first replacement
may continue after its specified checks pass; no phase-based reapproval.

After permission, compare installed local skills with the GitHub version.

Installed local paths depend on the installation mode:

- project-level: `.agents/skills/<skill_id>` below the approved project root;
- Codex user-level: `~/.codex/skills/<skill_id>`.

The legacy `~/.agents/skills` layout is not the assumed Codex user-level
target. Do not infer an installed path: use an already specified target or
inspect only within existing authorization; ask for the exact missing target
before comparing or updating it.

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

Before applying an update, verify that explicit authorization covers the
selected immutable version, exact destination, backup/rollback and replacement
effects. Ask for that missing scope only; do not demand a second approval
when the existing grant already covers it. The comparison script cannot apply
an update. Use `update_installed_skill.py` for the approved backup-first flow;
it must replace only the selected approved skill folder, validate `SKILL.md`,
reject duplicated nested
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

When sensitive read authority is missing or materially changed, tell the user
why access is needed, which
files or folders would be read, whether metadata is enough, whether content
would be quoted, summarized, or recorded, and how sensitive content will be
minimized or omitted. Obtain the missing explicit authorization before reading;
do not re-request an existing same-scope sensitive-read grant. Do not widen it.

Check existing authority before the following actions; obtain confirmation only
for missing or materially changed scope, target or effects:

- reading, modifying, staging, committing, pushing, or summarizing sensitive
  client or confidential materials
- deleting files or running destructive commands
- using sub-agents for broad or high-impact work
- deployment or production-affecting commands; require approval for the exact effects
- scanning local folders outside the repository
- scanning connected cloud drives, document stores, Gmail, or mailboxes
- using device location, GPS, or precise location data
- modifying auth, payment, security, database migration, production config, or
  major dependency behavior
- uploading source material to external providers or tools

If sensitivity or authority remains materially uncertain after checking
existing context, pause that action and ask one focused question. Continue
independent authorized work; do not access secrets to resolve the uncertainty.

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


### 客户续行向导（Beta，本地候选）

自有安装/升级成功的 `local_assist_offer` 提供准确 `prepare_argv`；执行准备命令后，`guide.wizard_argv` 给出当前已安装入口。它不是市场自动弹窗，也不会在安装时扫描设备。先阅读权限，再在客户自己的终端启动：

```text
python3 -I -B <已安装Skill绝对路径>/scripts/local_model_assist.py wizard --wizard-phase plan --disk-root <获准磁盘目录绝对路径> --install-root <20396专用私有安装根绝对路径>
```

`plan` 先确认启用、再单独确认读取硬件元数据；拒绝不探测、不生成部署权限。推荐不足时跳过，保留20396和Codex原功能。向导沿用同一推荐模型，展示精确下载/磁盘预算和已有配置限制；另行明确同意后，才保存有限、私有、绑定该根/模型的授权记录，并返回下一阶段的完整参数数组。有效且同范围的旧授权可复用，过期/变更不能静默继承。不要自行省略或重建返回的参数。

`deploy` 只在客户执行返回命令后复用原部署器：固定版本下载、核验和文件安装；相同pin自有安装通过原journal重核后零下载复用。未知、冲突或失败停止，不覆盖客户配置，不将文件安装标为模型验证通过。已有客户Ollama仅按原inspect接口核查，不接管或停止；向导不覆盖它的模型/运行时。

`session` 使用返回的准确命令，并补客户授权的 `--input-file <绝对路径>` 和 `--quality-case-file <预期JSON标准绝对路径>`。这是精确输入验证，不是通用评分。向导对服务启动、输入/标准读取、验证推理及结果回到Codex分别说明和取得同意，不要求客户手造JSON，不由记录推定当前权限。只有原生验证通过才产生短期精确资格；合成测试永不生成真实资格。

启动前拒绝已占用的本地端口；启动后最多3轮只读版本/模型就绪检查（最多6次GET），仅连接拒绝可在原期限内继续，不重试推理。端口检查和原句柄存活是合作宿主观察，不是原子端口归属证明。人工同意均在服务启动前完成。

服务会话保持前台且有界（`--session-seconds`≤300并满足原共享预算）；显示的完整 `assist` 参数数组供客户在获准Codex会话的执行工具中明确调用。向导不会启动Codex、改默认模型或自动转云。必须在服务会话仍活跃、资格及授权仍有效时调用；会话结束不能继续使用过期命令。输出返回Codex可能进入其云端上下文，拒绝回传就不发此调用。完成或失败后仅清理原句柄，后代仍UNKNOWN，不据此自动卸载。预算不足或身份变化停止，不自行延长。

恢复入口为同一向导的 `--wizard-phase recovery`，复用已有根、lifecycle和budget参数；先重新核查原记录及自有文件。未知/部分失败不自动修复或删除，仅提供核查交接。已知且重新核验的自有安装，客户独立确认闲置并明确批准卸载后，才生成准确的原 `uninstall` 命令及有限权限；仍由客户明确执行，不覆盖或接管其他资源。

拒绝、条件不足及待补任务参数均给固定状态/下一阶段，不代表验收通过。失败退出后先核原journal的PENDING/UNKNOWN；不重试未知操作、不删除未知资源。恢复仍需当前有效权限及文件核验，曾启动资源还须可靠闲置确认。当前仅支持既定macOS配方；Windows/AMD等不因此完成。真实模型部署、推理、Codex会话与token节省仍未验证。
