# 20396

**Long-Horizon Engineering for Codex**

**Long tasks survive the chat.**

Resume the work. Verify the evidence.

A Codex skill for migrations, large refactors, difficult debugging and multi-step
PRs. It keeps **goal, verified progress, evidence, required remaining work and
authority** explicit, so resumption starts with what can actually be verified.

Long-running coding tasks can lose their goal, repeat checked work, mistake
progress for completion, or resume from stale state. 20396 provides instructions
for avoiding these failures—not an autonomous runtime or a reliability guarantee.
Recovery needs approved persisted state and a fresh repository check; 20396 cannot
wake Codex or guarantee crash recovery.

> **New — [Local Compute Orchestration (Beta)](#local-compute-orchestration-beta)**
>
> 20396 includes executable foundations for routing bounded work to qualified
> local-model workers and coordinating independently qualified device identities
> for task-level execution. Current validation uses injected workers, not real
> models or networked devices; provider deployment remains partial.
> Validated local execution may reduce OpenAI/Codex cloud-model usage.

[Try it](#customer-quick-start) · [Published release](#installation-status) ·
[Recovery walkthrough](#from-interruption-to-verified-results)

## Customer Quick Start

### Runtime Safety Envelope — Experimental Foundation

20396 includes an experimental vendor-independent [Runtime Safety Envelope
foundation](.agents/skills/long-horizon-engineering/references/runtime-safety-envelope.md)
that separates AI action proposals from policy, authorization, capabilities,
side-effect reconciliation and security receipts. Phase 1 tests exercise the
Python kernel using fake adapters; no real runtime binding is included or activated.
No host sandbox, kernel security, packet firewall or provider-internal security
guarantee is implied. This is source-branch functionality, not a v0.7.0 release claim.

### Security Authority and Verifiable Security Chain — Experimental

The [Phase 1.25 foundation](.agents/skills/long-horizon-engineering/references/security-authority-chain.md)
adds scoped management checks, bounded Break Glass records and deterministic
SHA-256 linked history for policy, authorization, authority and RSE receipt digests.
Tests use synthetic data, in-memory storage and explicitly selected temporary
JSONL files. No real runtime binding or Paperclip dependency is added.
The chain is **tamper-evident, not tamper-proof**: without a separately retained
trusted head, valid tail truncation or whole-chain replacement cannot be detected.
Actor authentication, signed checkpoints and external anchors are not implemented.
This is source-branch functionality, not a published-release or deployment claim.

### Token Accountability — Experimental Foundation

The [Phase 1.35 foundation](.agents/skills/long-horizon-engineering/references/token-accountability.md)
represents model usage by project/task/run, checks nested budget contracts and
identifies deterministic anomalies such as unattributed, post-completion or
unreconciled-retry usage. Provider-unreported metrics remain UNKNOWN; reported
and estimated costs are separate. An anomaly is not evidence of theft or intent.
No real provider/runtime binding, live quota enforcement or background monitoring
is implemented. This is source-branch functionality, not a deployment claim.

### Critical Execution Trace — Experimental Foundation

The [Phase 1.5 foundation](.agents/skills/long-horizon-engineering/references/critical-execution-trace.md)
compares declared effects with caller-supplied adapter observations, validates
parent/child traces and reports bounded deterministic causal risk candidates.
It can anchor evidence digests in the existing Security Chain. Adapter observations
are not independent host evidence; even COMPLETE means caller-attested coverage.
No host/kernel/syscall observer, malware or intent classification, real runtime
binding, background monitoring or automatic enforcement is implemented.
This is source-branch functionality, not a published-release or deployment claim.

**Already installed?** Start with a non-sensitive repository and a bounded task:

```text
Use the long-horizon-engineering skill.
My desired outcome is: migrate <module> from <old API> to <new API>.
The material I can provide is: <exact approved repository path>.
Inspect that approved repository read-only, define acceptance checks,
and propose the smallest plan. Do not edit or make external calls.
```

Expect a plain-language customer outcome, the proposed scope and permissions,
and the checks that would demonstrate success. Then authorize only the work
you want performed. A plan or a passing check is not approval to push or merge.
After approval, ask Codex to continue required authorized work against those
criteria; changed scope or effects need a new decision, unchanged authority does not.

For guided decision support, say “Start with intake only” using the [customer prompt](prompts/customer-guided-decision.md)
and [walkthrough](docs/customer-guided-workflow.md). New installation needs the
version and target checks below; reading the [examples](examples/) needs no installation.

## Installation Status

**Latest published stable: [v0.7.0](https://github.com/Q20396/codex-long-horizon-skill/releases/tag/v0.7.0)**,
verified 2026-10-03. After approving installation and completing the
[verification checklist below](#install-verify-update), register its marketplace:

```bash
codex plugin marketplace add Q20396/codex-long-horizon-skill --ref v0.7.0
```

Registration is **not plugin installation**. With a compatible CLI, install
`codex-long-horizon-skill@codex-long-horizon-skills` through its plugin interface,
then verify discovery and loading. Check `codex plugin --help`; no installation
is performed by reading this page.

**Version boundary:** v0.7.0 is the published stable release and includes
Local Compute Orchestration (Beta). Beta does not mean production-ready local
model deployment: real provider/model and hardware validation remain incomplete.
The historical v0.6.0 package does not include this capability. Publication is
not customer installation verification; do not substitute mutable `main`.
The marketplace metadata is `AVAILABLE`; registration and installation remain
separate verified steps.

## When to use 20396

Use it for multi-session work, dependent milestones, staged migration/refactor
checks, or costly interruption/recovery. Skip it for a typo, a few obvious lines,
or when ordinary Codex already supplies enough structure.

20396 adds a reusable scope, recovery and evidence checklist—not exclusive Codex
capabilities, automatic memory, or proof of unattended reliability.

## Three tasks to try

Start with read-only planning; approve implementation separately.

**Migration**
```text
Use long-horizon-engineering. Plan migrating <module> to <new API> in this
approved repository. Identify compatibility risks and acceptance tests.
Do not edit or make external calls yet.
```

**Large refactor**
```text
Use long-horizon-engineering. Plan a behavior-preserving refactor of <area>.
Inspect the approved files, propose small steps and regression checks,
and identify what evidence would establish completion. No edits yet.
```

**Interrupted bug investigation**
```text
Use long-horizon-engineering. Resume <bug> using the approved repository and
existing non-sensitive handoff. Re-check branch, diff and prior test evidence.
Report what is verified, stale or still unknown, then propose the next step.
Do not repeat verified work without a reason or change files yet.
```

More examples: [migration](examples/repository-migration/),
[refactor](examples/large-refactor/), [bug investigation](examples/bug-investigation/),
[resume](examples/resume-work/), and the [prompt library](prompts/).

## How it works

1. Fix the objective and acceptance criteria.
2. Work in bounded, authorized steps.
3. Verify claims against actual evidence.
4. Track required work still missing—not every possible improvement.
5. On resumption, reconcile saved state with the current repository.
6. Finish only when required acceptance evidence is complete.

## From interruption to verified results

**Illustrative walkthrough—not a recorded execution or benchmark.**

A fictional API migration has **12 of 19 required items verified** when a session
ends. In a new session, provide the approved handoff. Re-check its objective,
branch, commit, diff and evidence: if the first 12 remain valid, continue with
item 13; if not, correct the affected assumptions before continuing.

Required tests → current validation evidence → Draft PR **if authorized** →
completion audit against the agreed objective. Missing evidence stays open;
a Draft PR is not a merge, release or proof of all possible delivery work.

See the [walkthrough and recording plan](docs/demo/README.md) and
[resume protocol](.agents/skills/long-horizon-engineering/references/resume-protocol.md).

## Safety Model

20396's instructions require bounded scope, least privilege, explicit authority,
and evidence-linked claims. Do not place secrets, credentials, customer-sensitive
information, legal evidence, family information, financial account details,
identity documents, confidential content or private correspondence in reusable
prompts, state, logs, commits, examples or public reports. Do not upload such
material. Sensitive repositories default to plan-only until exact access and
actions are approved; use explicit-path staging.

The package does not add a background service or telemetry collector.
This is not a guarantee about the Codex host, model provider or connected tools.
Plans, recommendations and green checks do not authorize external effects.
See [safety policy](.agents/skills/long-horizon-engineering/references/safety-policy.md),
[client privacy](.agents/skills/long-horizon-engineering/references/client-privacy.md)
and [security reporting](SECURITY.md).

## Early project — real workloads wanted

Report interrupted migrations, repeated work or missing completion evidence in
[Issues](https://github.com/Q20396/codex-long-horizon-skill/issues): include a public-safe
minimal reproduction, expected/observed behavior and recovery result. No production
reliability or adoption claim is implied. See [contributing](CONTRIBUTING.md),
[first contribution](docs/first-contribution.md) and [conduct](CODE_OF_CONDUCT.md).

## Optional domain capabilities

Engineering remains the primary workflow. Optional descriptors and references
also cover [public-equity research](.agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.md),
legal-evidence organization and document governance; see the
[capability catalog](.agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json).
Descriptors suggest bounded work; they are not installed domain skills.

The public-equity reference specifies source provenance, facts vs. assumptions,
dated valuation inputs, counterevidence and explicit evidence gaps. These are
review instructions, not proven investment performance or a tax/reconciliation
service. Professional decisions remain with the human.

None of these references authorize accounts, trading, filing, publishing or
contacting others; they are not autonomous financial or legal agents.
The Local Case Evidence Provider pilot is fixture-only, with no network,
accounts, credentials, persistence or encryption.
AI video remains an **optional bundled sibling skill**, not 20396's primary identity.

## Local Compute Orchestration (Beta)

20396 includes an optional experimental local-compute orchestration layer as
[packaged Python APIs](.agents/skills/long-horizon-engineering/scripts/local_compute_pool.py)
in the published v0.7.0 default Skill inventory. It is not automatically
enabled. The published v0.6.0 does not contain this capability.

> **Beta:** Validation is synthetic/injected-worker based. Real provider
> installation, local-model deployment, hardware-specific tuning and
> multi-device execution have not been validated. This is not production-ready.

The current implementation provides node-specific qualification identity checks,
consent and privacy policy checks, bounded concurrent task-pool dispatch,
load-aware scheduling, migration hints with trust reset, and OpenAI fallback
through an injected callback when both input and output policy permit it.
`LOCAL_ONLY` data cannot use that cloud fallback path. Caller-supplied evidence
and worker adapters are trusted boundaries, not remote-host authentication or
operating-system isolation.

The intended local-model workloads are selected, low-risk first passes such as
diff classification, log analysis and test-failure summaries, with independently
verifiable results. These are use cases, not claims of model qualification.
Multiple nodes are independent workers for separate tasks, not pooled memory
or one larger machine. Different provider/model configurations have separate
qualification identities; replacement nodes require fresh consent, probe,
deployment authorization, runtime validation and task qualification.

Local compute complements OpenAI: fallback or stronger reasoning/final synthesis
may use OpenAI only where input and derived-output policy allow it. LOCAL_ONLY
summaries, patches and findings must instead remain within authorized local or
human verification, or stop.

The [deployment API](.agents/skills/long-horizon-engineering/scripts/local_compute_deployment.py) provides exact approved
effect handling, conservative budgets and POSIX journal recovery. Concrete
provider/model setup, measured auto-tuning and the full zero-touch flow are
**not fully implemented**, not merely awaiting hardware tests.

Distributed single-model inference across machines is **not implemented**;
topology planning can only recommend a candidate. There is no model sharding,
automatic LAN discovery or silent cluster creation.

Real single-node, multi-node, distributed, provider-install and model-tuning
validation are **NOT_RUN**. Cloud-usage reduction is **UNMEASURED**. Once a local
path is validated, suitable workloads **may reduce OpenAI/Codex cloud-model
usage**; no token savings or hardware compatibility is guaranteed.

See the [implementation report and claim evidence](LOCAL_COMPUTE_ORCHESTRATION_IMPLEMENTATION_REPORT.md)
for synthetic coverage, adapter requirements and remaining work.

## Design references

20396 is independently designed and maintained. External comparisons include
[GitHub Spec Kit](https://github.com/github/spec-kit) (spec-driven development),
[obra/superpowers](https://github.com/obra/superpowers) (engineering workflows),
[Matt Pocock's skills](https://github.com/mattpocock/skills) (task-focused skills),
[affaan-m/ECC](https://github.com/affaan-m/ECC) (agent configuration and workflows),
[Cloudflare security-audit-skill](https://github.com/cloudflare/security-audit-skill)
(security review), and [Multica's Karpathy-inspired guidelines](https://github.com/multica-ai/andrej-karpathy-skills)
(third-party minimal engineering practices—not an official Andrej Karpathy framework).

These are design references and review lenses, not product foundations, bundled
dependencies, endorsements or collaborations.

**Comparison, not accumulation:** compare an idea against the current workflow,
test when necessary, and adopt only demonstrated incremental value with applicable
approval. `NO_CHANGE` is a valid outcome—not every evaluation creates a feature.
The [independent review checklist](sandbox/skill-incubator/architecture/independent-lhe-upgrade-review-checklist.md)
is a proposal-only methodology reference, not execution authority.

## Documentation

[Install](INSTALL.md) · [Upgrade](UPGRADE_GUIDE.md) · [Changelog](CHANGELOG.md) ·
[Examples](examples/) · [Templates](templates/) · [Community skills](COMMUNITY_SKILLS.md) ·
[Skill entrypoint](.agents/skills/long-horizon-engineering/SKILL.md) ·
[Optional reference index](.agents/skills/long-horizon-engineering/references/explicit-only-extensions.md)

<details>
<summary>Skill catalog and package profiles</summary>

## Skill Catalog

<!-- skill-catalog:start -->
| Skill | Purpose | Best For |
| --- | --- | --- |
| [`ai-video-production`](.agents/skills/ai-video-production/SKILL.md) | Use for AI-assisted video or animation planning: video briefs, scripts, storyboards, shot lists, visual prompts, asset manifests, preview plans, and render handoffs. Do not use for general repository engineering or automatic rendering, uploading, publishing, or posting. | Video briefs, scripts, storyboards, visual prompts, asset manifests, and render handoffs. |
| [`long-horizon-engineering`](.agents/skills/long-horizon-engineering/SKILL.md) | Use for long-running software engineering and local static capability discovery. It may suggest descriptor-only legal-evidence, document-governance, or public-equity packs; keywords never authorize, install, load, or execute them. Do not use for simple edits, legal or financial advice, media, or automatic external actions. | Large refactors, migrations, debugging, PR workflows, resumable tasks, and validation-heavy engineering. |
<!-- skill-catalog:end -->

## Package Profiles

- `local-governance-core`: default and recommended minimal profile for
  high-sensitive work. It contains the engineering governance kernel, static
  capability catalog, and local work-packet template. The repository provides
  `scripts/assemble_skill_profile.py` to create a deterministic,
  caller-chosen core artifact for controlled distribution or inspection. The
  current marketplace plugin manifest still packages the repository skill
  directory, so this selection is not yet a claim that marketplace installation
  physically omits optional files. Do not treat the profile label as host
  isolation until the marketplace artifact layout is separately validated.
- `core-only`: compatibility alias for the same current core content.
- `lhe-bundled`: core plus bundled optional references and templates.
- `legacy-full`: explicit compatibility profile; includes bundled optional
  content and the separately packaged AI video skill.

Profiles describe package selection only. They do not prove host isolation,
activate a profile, install a domain pack, or grant permissions.

For a local, no-upload first result, use the
[Local Governance Work Packet](docs/local-governance-work-packet.md). It is a
copy-paste intake and review format, not a connector, database, or runtime.

</details>

<details>
<summary>Advanced workflow contracts and optional capabilities</summary>

## Role-Based Engineering Loop

For substantial engineering tasks, the long-horizon skill uses a lightweight
Planner -> Builder -> Evaluator -> Human Gate flow. The Planner defines scope,
completion criteria, evidence, and stop conditions; the Builder performs only
approved work; the Evaluator maps results to evidence and reports gaps; the
human decides whether to accept or request a bounded correction.

These are serial working roles, not autonomous sub-agents. They do not grant
new permissions or enable automatic edits, installs, pushes, merges, deploys,
or releases. Optional working state supports safe resumption only after current
branch, diff, and validation state have been re-checked.

## Industrial Skill Design Principles

Industrial skills should trigger accurately, run with least privilege, use
progressive disclosure, match workflow depth to task risk, and maintain an
evaluation loop. `SKILL.md` should stay concise; long protocols, templates,
scripts, and assets should live in their supporting folders.

For larger skill systems, this repository favors router patterns, invocation
permission layers, and shared design vocabulary while keeping external ideas
review-gated instead of copied or auto-installed.

Keywords: router patterns, invocation permission layers, shared design vocabulary.

## Optional Obsidian Knowledge Workflow

The long-horizon skill can create a proposal for an Obsidian-compatible
Markdown note, JSON Canvas, or Base when the user explicitly asks. It begins
with user-supplied content or a narrowly approved file, requires exact vault
paths and approved read scope before analysis, and keeps all vault changes
proposal-only until separately approved with an exact target path.

The bundled-optional [protocol](.agents/skills/long-horizon-engineering/references/obsidian-knowledge-workflow.md)
defines bounded read-only RETRIEVE / SURFACE / COLLIDE intents over approved
Markdown scopes. These are documentation contracts, not a retrieval runtime;
real retrieval quality, surfacing value and collision accuracy remain unvalidated.

It never scans a whole vault, indexes private notes, follows vault symlinks,
syncs cloud content, installs or invokes Obsidian CLI, or treats a vault as
automatic long-term memory. JSON Canvas artifacts can be checked locally with:

```bash
python3 .agents/skills/long-horizon-engineering/scripts/validate_json_canvas.py \
  path/to/approved.canvas
```

## Safe Project Maps And Render Evidence

For large or unfamiliar repositories, the long-horizon skill can prepare a
bounded project context map from explicitly approved repository paths. It is a
report-first planning aid, not a graph database, automatic repository scan, or
permission to inspect sensitive files. It does not read cloud drives, Obsidian
vaults, mailboxes, media, or folders outside the repository by default.

The video skill can document renderer selection and render evidence before a
human approves final rendering. It compares repeatability, preview workflow,
privacy, licensing, cost, assets, and output requirements, but does not install
tools, call providers, generate media, upload, publish, or spend credits.

Local compute planning remains manual and user-supplied. The skill does not
discover devices, scan networks, download models, start services, or form a
distributed compute cluster.

## Text To Visual Analysis

The `ai-video-production` skill can turn supplied text into visual plans before
generation. It analyzes the complete text first, selects only high-value
concepts for visualization, and produces diagram, storyboard, explanatory
graphic, image-prompt, or text-only recommendations. It does not generate,
upload, publish, or bill media automatically.

## Self-Check and Review-Gated Improvement

Self-check follows: Observe → Compare → Explain → Recommend → Wait for approval.
In this mode, self-check is read-only, and all findings remain proposal-only
until the user approves a separate action. Updating or applying a change is a
separate explicit action, not part of self-check.

## Time-Bounded Upgrade Audits

The optional `upgrade-audit-protocol.md` supports an explicitly requested,
time-bounded review of recent repository upgrades. It starts read-only, fixes
the audit window and baseline commit, and reports evidence, gaps, findings, and
test outcomes without creating audit files, branches, worktrees, or repairs.

Any network check, durable report, repair, or quarantined experiment needs a
separate user decision. The user-facing “mad-dog mode” label only exposes
locked experiment candidates; it never grants execution, installation, network,
push, merge, or release permission.

Even an opt-in experimental online comparison is stepwise: every network
request and every update action must show its scope, source/ref, risk,
validation, and rollback plan, then receive a fresh customer decision. Silence,
ambiguous consent, or a changed target stops the workflow.

A customer may use a weekly reminder to request a new decision, but the
reminder never accesses the network. Each week begins with no approval and
requires a fresh, source-scoped decision before any online comparison.

## Personal Workflow Review (Explicit Only)

The optional personal-workflow review protocol can turn only user-supplied,
non-sensitive task summaries into proposed reusable rules or repeated workflow
candidates. It separates observation, evidence, hypothesis, candidate rule,
and user decision so that a suggestion is never mistaken for a fact or an
active instruction.

It does not scan prior chats, raw prompts, email, cloud drives, browser or shell
history, repositories, hidden files, device data, or GPS. It does not infer
identity, personality, mental health, or private relationships. It does not
save a personal manual, create a skill, install anything, or enable a rule
automatically.

Any durable personal operating manual is private, user-controlled, outside a
public repository, and created only after exact-path approval. It is not loaded
automatically in future conversations and cannot override current user,
repository, safety, or higher-priority instructions.

## Approved External Tool Contracts

When a selected external CLI, MCP server, connected app, or provider would
need new permissions, use the optional Approved Tool Contract Card after
comparing candidates. It records the exact proposed action, input scope,
side-effect classes, lowest-risk preview, validation, fallback, and rollback.

The card is proposal-only: it does not authorize installation, execution,
network access, authentication, file writes, uploads, deployment, publishing,
or account actions. This package does not add a tool hub, automatic discovery,
automatic installation or updates, background services, telemetry, or model
routing.

## Optional Local Voice Tool Sandbox

For a user who explicitly asks to evaluate a local text-to-speech,
speech-to-text, voice-cloning, or voice-enabled MCP tool, the optional Local
Voice Tool Sandbox separates source review, installation, model download,
runtime start, MCP connection, input access, voice identity, output handling,
and cloud use into separate approval gates.

It does not install, configure, start, or connect any voice tool. By default,
it denies microphone and system-audio capture, arbitrary audio-path reads,
transcript history, voice cloning, personality rewriting, non-loopback
endpoints, cloud sync, and telemetry. Use the protocol and approval card only
for an explicitly requested, bounded review; local-first marketing is not a
security guarantee.

## Optional 3D Asset Provider Sandbox

For a user who explicitly asks to evaluate a hosted 3D asset provider,
3D-generation service, or 3D asset MCP tool, the optional 3D Asset Provider
Sandbox separates source review, skill acquisition, MCP configuration, account
connection, account-data access, reference upload, generation, final approval,
asset retrieval, project write, remote runtime, and sharing into separate
approval gates.

It does not install, configure, sign in, upload, generate, download, write,
or enable a remote runtime. By default, it denies account and credit access,
private reference transfer, automatic generation or credit spend, remote CDN
fallbacks, CSP/CORS changes, telemetry, and publication. The protocol stores
review-only public candidate commands without executing them; a public source,
installed skill, or prior approval never grants a later permission.

</details>

<details>
<summary>Verification, update boundaries and maintainer notes</summary>

## Install, Verify, Update

Before installation, verify the official marketplace identity and the public
Release/tag: v0.7.0's annotated tag object is
`4a3f94c0ae2d05848a3ce9accd6f38382bd08f1a`, and its peeled commit is
`69d8001d86bd40e11c3e95416d8a678102ce6504`. They are different Git objects.
Stop on missing or mismatched identity. Review the exact destination, selected
skill and backup/rollback before approved writes; never overwrite an existing
installation as a shortcut. Follow [INSTALL.md](INSTALL.md) and
[plugin verification](docs/plugin-install.md).
Project skills use `.agents/skills/<skill_id>`; user-level skills use
`~/.codex/skills/<skill_id>`. Verify installed files, discovery and loading separately.

Updates are manual, comparison-only first, and require separate approval for
backup-first replacement. No automatic background update or mutable-ref upgrade.
See [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md) for current release checks.

The legacy self-check is for the legacy/project-style `.agents/skills` layout;
use the `--target-skill-dir` updater flow for Codex user-level replacement.
For example, `--target-skill-dir ~/.codex/skills/long-horizon-engineering`
selects the installed skill directory; `--installed-root ~/.codex/skills`
selects the comparison root. Neither option grants permission to write.
Do not apply an update before reviewing the exact target, backup and rollback plan.

Validate this source package:

```bash
python3 scripts/generate_skill_catalog.py --check
python3 .agents/skills/long-horizon-engineering/scripts/check_skill_package.py
python3 .agents/skills/long-horizon-engineering/scripts/doctor.py
python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
```

Broader validation and contribution instructions are in
[CONTRIBUTING.md](CONTRIBUTING.md). Passing static checks is not runtime proof.

## Maintainer Notes

Regenerate the catalog with `python3 scripts/generate_skill_catalog.py` after
skill metadata changes; then rerun the checks above. Canonical trigger fixtures:
[tests/expected-triggers.json](tests/expected-triggers.json). Skill-local styles
live in each skill's `prompt-styles/`; [prompts/](prompts/) holds user task prompts.

</details>

## License

MIT. See [LICENSE](LICENSE).
