# 20396

## v0.8.0 source release contract — 本地算力辅助（Beta）

The source contract targets v0.8.0. Publication, signed-tag identity and isolated
marketplace resolution remain separate gates; this branch does not establish
that customers can already install that release. Latest actually published
stable remains v0.7.0 until those gates complete. Do not run a v0.8.0 install
command before verifying its published immutable tag and exact source.

The v0.8.0 source includes the #191 helper and model catalog, plus the explicit
20396 installer/updater offer. `--local-assist` invokes preparation only.
Marketplace installation is not a proven automatic setup hook, and Skill
installation does not switch Codex models. Real macOS deployment, inference
and Codex sessions remain NOT_RUN; token savings are UNVERIFIED. Other
platform capabilities are not expanded by this release contract.

After publication verification only, use the immutable version selector:
`codex plugin marketplace add Q20396/codex-long-horizon-skill --ref v0.8.0`.
The source marketplace policy is `AVAILABLE`; it is not publication evidence.

After publication verification, register the reviewed v0.8.0 tag explicitly;
a registration pinned to v0.7.0 does not automatically advance. Preserve customer
configuration and review the exact updater target and retained backup before
any separately authorized replacement. On conflicts or UNKNOWN, stop. Rollback
requires current ownership/identity and permission checks; never move old tags
or overwrite an active model/customer configuration.

**客户版本：20396（Beta）。** 机器使用的 skill 名称与路径保持 `long-horizon-engineering` 不变。

**Long-Horizon Engineering for Codex · 让长任务接得上、结果查得到。**

20396 是一个 Codex skill，适合代码迁移、大型重构、复杂排错和多步骤 PR。
它帮助你保留目标、已核验的进度、证据和剩余工作；中断后先核对现状，再继续已授权任务。
它不是自动唤醒服务，安装后也不会自行扫描设备或启动监控。

[快速开始](#customer-quick-start) · [安装与版本](#installation-status) ·
[本地模型能力](#local-compute-orchestration-beta) · [隐私访问说明](#privacy-observation-scope)

## Customer Quick Start

已安装后，在 Codex 中粘贴并替换下面的路径和目标：

```text
使用 long-horizon-engineering skill（20396）。
目标：修复 <具体问题>，并用相关检查验证结果。
范围：<项目绝对路径>，仅使用非秘密源码和合成数据。
允许：读取该项目、必要的局部修改、离线检查，以及在项目内保存进度和证据。
禁止：联网、安装依赖、提交、推送、合并和部署。
在这些边界内连续完成排查、修复和验证；不要因阶段切换重复要求 approve。
遇到缺少必要材料、新的外部影响或明确停止条件时，只暂停受影响的动作。
```

首次使用时，把**项目路径、目标、允许动作和禁止动作**一次说清。
如果你已明确授权相同范围，20396 会直接继续；计划、测试通过或安装成功本身不会新增权限。
只想先看方案，可说 **“Start with intake only”**；只想只读检查，可明确禁止写入和执行。
尚未安装请先看[安装与版本](#installation-status)，无需先运行实验模块。

<details>
<summary>Read-only English example / 只读示例</summary>

```text
Use the long-horizon-engineering skill.
My desired outcome is: migrate <module> from <old API> to <new API>.
The material I can provide is: <exact approved repository path>.
Inspect that approved repository read-only, define acceptance checks,
and propose the smallest plan. Do not edit or make external calls.
```

Expect a plain-language customer outcome and evidence-backed checks.
[客户提示词](prompts/customer-guided-decision.md) · [使用示例](docs/customer-guided-workflow.md)

</details>

两项可选方向：授权后评估本地模型是否适合你的任务；在已接入的观察范围内报告事件和证据。
下面分别说明已实现接口、已有验证和仍需补齐的部分，不能把产品目标当作已经部署的能力。

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

**本地算力辅助（Beta）**：当前本地候选增加已打包的显式适配入口；不是安装/升级后自动部署模型的完整功能。以下英文标题及锚点保留兼容。

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

### 授权、检测与实际安装

| 环节 | 当前实现与证据 |
|---|---|
| 设备信息读取 | `collect_probe(node_id, consent, reader)` 先检查已授权节点，再调用接入方提供的只读 reader。允许字段包括系统/架构、CPU/SoC、内存、加速器/显存、剩余磁盘、运行器版本和已有模型；应只读取客户本次批准的必要字段，不读取文件正文或设备序列号。reader 本身受信，字段过滤不保证它没有额外读取。 |
| GPU 与兼容性判断 | 已实现按提供的资源、候选配置和资格证据做有限判断。新增授权后调用的部分 Linux/NVIDIA 与 Apple 元数据 reader，AMD 与 Windows 完整探测尚缺；没有真实 provider/model 安装配方，不能承诺自动识别所有 GPU。 |
| 下载和安装 | 已有精确 effect/命令绑定、预算和恢复接口；真实下载源、模型/许可、安装路径、下载量、峰值磁盘、网络与费用须在授权中明确。接口存在不等于真实安装完成。 |
| 运行和任务路由 | 已增加 Ollama 回环 worker、精确版本/模型digest检查及显式工具CLI，复用既有池与token账。仅mock HTTP合成验证；真实推理、客户硬件资格和端到端部署未验证，桌面默认模型不变。 |

一次授权若已包含上述具体范围和效果，可以连续执行，不因检测→安装→验证的阶段切换再问 approve。
缺 reader、配方或资格证据时暂停受影响动作；不代装依赖或自行扩大网络、存储、费用权限。
符合条件的任务改由本地模型处理后，**可能减少云端 token 使用，实际收益需验证**。
本版本没有实测节省比例，也不保证安装模型本身就减少使用量。

截至2026-11-03：已有客户引导、准确隔离CLI、部分平台reader、Ollama worker及用量适配，尚未发布。自有安装/升级默认展示可选启用及授权入口；固定Darwin文件部署、原账本所有权保存/恢复、受控启动与卸载已有代码和合成覆盖。实际发行包仅下载核验及只读检查，没有安装执行。质量资格桥仅支持客户明确标准的精确JSON输入/输出，未作真实推理或Codex会话验证。NVIDIA、AMD、Apple Silicon（含Mac Studio）端到端未实测，正常流程仍为 OPENAI_ONLY，**节省效果未验证**。
本候选仅允许将日志摘要、差异分类等有外部资格记录的任务交给本地辅助服务；本地失败默认停止，不未经授权静默切换云端。LOCAL_ONLY 原始输入及派生输出均不得自动回传云端。
Codex CLI 的本地 provider 是另一种显式会话选择，不代表安装本 skill 后当前 Codex 桌面模型会自动被替换。

### 显式客户入口（本地候选，未发布）

20396自有装配器与升级器在成功安装/升级后默认输出 `local_assist_offer`（Beta名称、准确安装路径命令及授权说明），不默认启用。显式 `--local-assist` 才自动调用已安装的准备入口。可选 `--local-assist-model` 仅选择既有目录中的模型。它不是平台市场自动钩子，不授权硬件探测、下载或推理；准备失败保留已完成的20396安装。其他安装方式可由客户明确调用：

```text
python3 -I -B <已安装Skill绝对路径>/scripts/local_model_assist.py status
python3 -I -B <已安装Skill绝对路径>/scripts/local_model_assist.py prepare --model-id qwen3.5:4b
python3 -I -B <已安装Skill绝对路径>/scripts/local_model_assist.py setup --disk-root <客户批准的绝对路径>
python3 -I -B <已安装Skill绝对路径>/scripts/local_model_assist.py deployment-plan --install-root <客户私有安装根绝对路径>
```

`status`、`prepare`和`deployment-plan`均无硬件/网络/安装效果。`setup`要求客户本机终端，先询问是否启用，再单独询问元数据读取权限；拒绝时不调用reader。同意后才检查并推荐，不把同意读取变成下载或推理授权。`prepare --existing-state <获准状态JSON>`仅评估复用声明，不凭此产生资格或授权。版本/配方变化、授权过期须更新对应范围同意；pending UNKNOWN不自动重试。

`probe`需本机授权文件和明确磁盘根；仅在客户实际同意后调用。Linux/NVIDIA及Apple字段解析有合成覆盖；Apple可用量是free+speculative保守瞬时快照，不是保留的VRAM；AMD/Windows完整reader不足保持UNKNOWN。外部探测命令只支持现有POSIX有界管道；缺工具不安装，原句柄清理不明即停止。

`assist`经Codex现有执行工具显式调用CLI，必须有当前运行时/模型pin、已验证Node/任务资格记录、精确数据文件范围授权及明确`--return-to-cloud`许可；默认不读输入、不推理。该显式命令是实际可执行接线代码，当前只用mock验证，无真实Codex模型会话证据。LOCAL_ONLY结果只能由声明本地输出边界的Python caller处理，不能经该CLI stdout回传云端。授权/资格文件是受信host提供的声明，不是加密认证或自动资格生成；不得为通过而手工伪填probed/runtime_validated。

HTTP仅限127.0.0.1、禁环境代理和重定向、版本/digest初末核查；持有服务的客户还必须确认本地模型及NO_CLOUD等配置。该声明和API快照不能证明系统网络隔离。客户端异常会锁为UNKNOWN；失败没有cloud_worker，不静默转云，不承诺取消服务端推理已经完成。当前caller须串行控制同一设备并复用UNKNOWN状态；一次CLI一个任务，不提供跨进程容量预留或技术防重放。

`-I` 保留隔离模式；入口只绑定已安装脚本的准确目录，不依赖当前目录或PYTHONPATH。两种临时安装布局均测试上述准确命令，不用测试进程注入搜索路径代替。

生命周期只操作明确授权、独占创建且身份仍匹配的材料。固定Ollama v0.40.13 Darwin包长度186689993B、SHA256及59项归档清单已只读核验，展开量608745773B。代码手动解包固定文件/目录/安全相对链接，保留许可证，不使用extractall。没有在本机安装或启动实际程序；版本与签名信任不由包结构或哈希代证。

`deploy-files`接通 `PinnedStage` 的下载→运行时文件安装→固定模型文件注册，要求准确 `--install-root`、`--lifecycle-consent-file`、`--budget-file`及另行读取授权 `--grant-file`；启动前核客户Darwin≥14、架构与资源。不凭计划输出授权。下载含runtime及所选模型的全部config/layers；预算同时计暂存、展开、模型副本、既有占用和journal，阶段不重置。仅为已核runtime开放GitHub到release-assets.githubusercontent.com的一次HTTPS跳转，其他未审重定向拒绝；未真实下载模型。各文件结果标UNVALIDATED，不启动服务或产生任务资格。

受信host可在同一控制器内调用 `OwnedOllamaService`，持有另行绑定的start-service/stop-service授权，核文件收据后执行准确自有 `ollama serve`，使用私有HOME/TMP/模型根、127.0.0.1及进程级NO_CLOUD，不改全局配置。`stop`只清理原句柄，后代仍UNKNOWN；直接进程退出不能证明所有runner已闲置，不可据此自动卸载。模型注册使用现有固定manifest/blob布局，不另造运行时。

未知部分下载及所有权不自动重试/接管/删除。所有权快照存入现有DurableJournal，不增账本，最多256项、整个journal≤1MiB；只含固定相对文件名、身份/摘要、版本pin和活动状态，不存正文、密码或PID。恢复须新鲜有效的restore授权、准确私有根及逐原件核验，保留原预算消耗和PENDING，记录存在不构成修改/删除权限。旧账本无快照时不接管原资源。

`ownership-status`及`upgrade-check`接受与部署相同的根、模型、lifecycle授权和预算参数，核验相同pin的自建材料。`deploy-files`遇既有账本时必须有restore/save授权，完整核验后零下载复用；不同pin要求新独占根，保留旧安装，不原地覆盖客户版本。`uninstall`还要求明确卸载/save权限和可靠的本次 `--idle-confirmed`；曾启动或活动未知时另须confirm-idle范围。这是可信host提供的当前闲置声明，不是账本或直接进程退出证明，无法可靠确认时禁止执行。

删除前先将原账本owned快照标UNKNOWN，成功后保存剩余树；失败/崩溃不留下可盲用的旧有效清单。身份、摘要、目录、关闭状态变化均拒绝，预算和UNKNOWN不清零。仅删除20396创建并重新核验的资源，客户原有Ollama、模型、自定义配置不接管；旧记录或未知资源保留。

`serve-session`在恢复核验后，读取另行绑定的 `--service-consent-file`，通过 `--session-seconds`（≤300且满足剩余共享预算）启动受控前台会话；到时或Control+C只清理原句柄，不跨命令采用数字PID。启动前持久记录POSSIBLY_ACTIVE，退出仅记DIRECT_EXIT_DESCENDANTS_UNKNOWN，后代未知不伪装成闲置。不是常驻后台服务，也不修改系统服务或Codex默认配置。源码改变、活动不明或原预算不足时失败停止。

`inspect-runtime`可在inspect-runtime许可下只读核客户已有Ollama版本和模型digest，不收养或修改该服务，仍要求任务资格。原 `qualify`公开格式样例始终qualified=false。新增 `--quality-case-file`、`--qualification-output`路径后，须先绑定输入与评分标准文件的qualify权限、再读取正文；原生probe与原生推理按客户明确的预期JSON完全匹配时，才在私有位置独占写入短期精确输入资格记录。合成/注入客户端不生成真实Node；这不是一般任务类别胜任证明，也不是人工评分或任意自然语言质量评估器。

新记录绑定输入SHA、标准SHA、模型/版本、数据范围及到期；`assist`在读正文前核范围，读后核实际SHA，派发再次核验，实际新答案也必须符合原标准才释放，不能拿同路径的新正文或随机新答案复用资格。接口可由Codex执行工具显式调用，stdout现在包含原账本规范化usage；缺失计数保留UNKNOWN。完整OpenAI宿主用量采集、通用自动路由、常驻服务及各平台原生验证未实现或未实测，不宣称节省；没有开发者硬件不妨碍代码与夹具工作。


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




See the [implementation report and claim evidence](LOCAL_COMPUTE_ORCHESTRATION_IMPLEMENTATION_REPORT.md)
for synthetic coverage, adapter requirements and remaining work.

## Privacy Observation Scope

面向使用云端 AI 的客户，目标是说明“哪些获准对象有访问或操作证据”。
**当前还不是安装后自动运行的全盘隐私监控服务。** 观察器运行在客户明确授权、实际接入的主机上，
不在云端模型供应商内部；不能看到其内部处理，也不能保证资料不外泄。

| 已有机制 | 可以报告什么 | 不能据此推断什么 |
|---|---|---|
| 受信 host 事件接入 | 明确来源、会话、序号、时间、事件类型、动作/目标引用、可选摘要及覆盖状态；需接入真实传感器。 | caller 提供的数据不自动成为独立的系统访问证据。 |
| macOS 明确注册的 PID | one-shot `NOTE_EXEC`，以及仓库内[选定 `NOTE_EXIT` 扩展](docs/h7-selected-host-expansion.md)。已有合成与选定原生验证，范围以各报告为准。 | 进程执行/退出不证明读取了某个私密文件，不涵盖全部后代、命令内容或全部副作用。 |
| [指定本地文件核对](docs/h3-independent-target-reality.md) | 在获准根目录、身份和大小限制内核对指定普通文件的元数据/摘要；这是主动读取，须事先授权。 | 核对结果不证明此前哪个进程访问了文件，也不是私密目录访问历史。 |
| 跨层比较与[只读中文展示](docs/h9-bounded-operator-findings.md) | 转述已提供的结果、原因、覆盖范围和证据引用，提醒负责人核查。 | 展示/观察本身不能阻止读取、上传或泄漏，也不授予自动重试权限。 |

只有观察来源实际提供并可靠绑定某个文件的访问事件，才可报告该范围内的“被触碰”；
当前进程事件不能替代该文件证据。Linux 已选测试的外部观察记录是验证证据，未装成客户常驻监控器。
无事件仍可能是未覆盖或未知；观察到访问也不等于上传或泄漏。

接入前应明确设备、进程、目录、事件、时限和报告去向。默认以不含个人信息的对象引用、
动作类别及必要摘要报告，路径按授权脱敏；不为演示采集私密正文、口令或凭据。
现有受控执行接口只会拒绝经其接线的未授权请求，不构成系统级访问拦截或云端防泄漏。

## Experimental Foundations

<details>
<summary>实验模块、开发者接口与证据边界</summary>

### Runtime Safety Envelope — Experimental Foundation

20396 includes an experimental vendor-independent [Runtime Safety Envelope
foundation](.agents/skills/long-horizon-engineering/references/runtime-safety-envelope.md)
that separates AI action proposals from policy, authorization, capabilities,
side-effect reconciliation and security receipts. Phase 1 tests exercise the
Python kernel using fake adapters. The separately constructed Phase 2A local
binding below is opt-in; nothing is activated by installation or import.
No host sandbox, kernel security, packet firewall or provider-internal security
guarantee is implied. This is source-branch functionality, not a v0.7.0 release claim.

### Security Authority and Verifiable Security Chain — Experimental

The [Phase 1.25 foundation](.agents/skills/long-horizon-engineering/references/security-authority-chain.md)
adds scoped management checks, bounded Break Glass records and deterministic
SHA-256 linked history for policy, authorization, authority and RSE receipt digests.
Tests use synthetic data, in-memory storage and explicitly selected temporary
JSONL files. Phase 1.25 itself adds no runtime binding or Paperclip dependency.
The chain is **tamper-evident, not tamper-proof**: without a separately retained
trusted head, valid tail truncation or whole-chain replacement cannot be detected.
Actor authentication is a trusted-host responsibility; the separate Phase 1.75
checkpoint contract below accepts host-supplied verification and anchor evidence.
This is source-branch functionality, not a published-release or deployment claim.

### Token Accountability — Experimental Foundation

The [Phase 1.35 foundation](.agents/skills/long-horizon-engineering/references/token-accountability.md)
represents model usage by project/task/run, checks nested budget contracts and
identifies deterministic anomalies such as unattributed, post-completion or
unreconciled-retry usage. Provider-unreported metrics remain UNKNOWN; reported
and estimated costs are separate. An anomaly is not evidence of theft or intent.
No real provider/runtime binding, live quota enforcement or background monitoring
is implemented. This is source-branch functionality, not a deployment claim.

### Signed Checkpoints — Experimental Foundation

20396 includes an experimental signed-checkpoint contract that can bind a verified
Security Chain prefix to trusted external signature verification and independently
retained anchor evidence supplied by a trusted host integration. It detects
rollback or replacement only when that trusted evidence survives independently.
The module does not manage private keys or contact an anchor service. Real crypto,
key custody and external publication remain host responsibilities; synthetic tests
do not establish those properties. See [signed checkpoint boundaries](.agents/skills/long-horizon-engineering/references/signed-checkpoints.md).

### Critical Execution Trace — Experimental Foundation

The [Phase 1.5 foundation](.agents/skills/long-horizon-engineering/references/critical-execution-trace.md)
compares declared effects with caller-supplied adapter observations, validates
parent/child traces and reports bounded deterministic causal risk candidates.
It can anchor evidence digests in the existing Security Chain. Adapter observations
are not independent host evidence; even COMPLETE means caller-attested coverage.
No host/kernel/syscall observer, malware or intent classification, background
monitoring or automatic enforcement is implemented by this trace foundation.
This is source-branch functionality, not a published-release or deployment claim.

### Trusted Local Runtime Binding — Experimental / Same Process

The opt-in [Phase 2A binding](.agents/skills/long-horizon-engineering/references/runtime-binding.md)
routes bounded regular-file operations, explicitly allowlisted processes and local
Git exact staging/commit through existing RSE governance. Payload digests must be
bound before authorization; a Git commit additionally binds the exact staged tree,
parent and message, rejecting changed tree/parent before commit. Adapters report their own observed boundaries to CET
and seal evidence digests, not raw file contents or process output, in the chain.

This is **not an OS sandbox, host observer or network containment**. Allowlisting
a process does not reveal or constrain all its internal effects. Unsupported safe
filesystem primitives fail closed; no universal race-free guarantee is made.
UNKNOWN outcomes block blind retries within the same process, not across crashes.
Phase 2A has no network, Git push, GitHub, deployment, installation, secret-store,
Paperclip, Codex-hook or Local Compute adapter. Nothing registers or executes on
import. These are source-branch capabilities, not published-release claims.

### Bounded Remote Effect Binding — Experimental / Same Process

The separate opt-in [Phase 2B binding](.agents/skills/long-horizon-engineering/references/remote-runtime-binding.md)
adds bounded HTTPS requests, exact single-branch fast-forward Git updates and
GitHub-compatible PR creation through existing RSE authority. Destination,
payload and old/new Git state are committed before authorization. Credentials
are supplied by trusted host transport code, not discovered or included in model
payloads. Redirects are disabled and TLS verification remains enabled.

UNKNOWN blocks blind mutation retries in the same journal process; bounded
readback may remain inconclusive. This is **not exactly-once, crash-durable
execution, a secret manager, a network sandbox or independent host observation**.
No PR merge/update, release/deploy, package installation, SSH, Paperclip,
Codex runtime hook or Local Compute integration is added. Installing/importing
the module activates nothing; no real external account mutation is used in tests.

### Agent Runtime Integration — Experimental Foundation

20396 can translate bounded agent action proposals into existing governed
ActionRequest and Phase 2A/2B payload contracts, then route explicitly authorized
actions through the existing RSE-controlled execution path.

Agent/model output remains untrusted proposal data. The bridge does not let a
model self-authorize, self-grant capabilities, directly invoke effect adapters,
or bypass an unresolved UNKNOWN mutation by issuing a cosmetically new proposal.

Duplicate-effect suppression is same-process and same-bridge only; this is not
crash-durable agent orchestration, a Host Observer, OS sandbox, or proprietary
Codex interception layer.

### Host Observation — Experimental Evidence Foundation

20396 can ingest bounded observations from an explicitly trusted host evidence
source and represent them separately from model declarations, adapter observations
and reconciliation evidence.

The foundation defines evidence provenance, ordering, scoped coverage and explicit
action correlation. Missing host evidence does not prove an effect did not occur.

### Real Host Observation — Experimental macOS Slice

An experimental macOS backend uses kqueue EVFILT_PROC / NOTE_EXEC for explicitly
registered processes. PROCESS_EXEC means the registered PID executed a new program
image; coverage is PARTIAL. It does not represent fork/new-PID creation, application
success or complete process lifecycle coverage.

The native event becomes an existing HostObservation, then HOST_OBSERVED CET and
bounded Security Chain evidence through the existing ingestor. Registration is
one-shot, the wait is finite and the caller closes the session. No command line or
environment is collected. No daemon, global process monitor, enforcement layer,
polling fallback, kernel-truth guarantee or automatic reconciliation is included.

### Cross-Layer Verification — Experimental

20396 can deterministically compare bounded evidence across model declarations,
RSE authorization, adapter observations, host observations and trusted
target-reality evidence for one action at a time.

The verifier produces MATCH, MISSING, EXTRA, DIVERGED, UNKNOWN and NOT_OBSERVED.
It is read-only: findings are not persisted or written back to the Security Chain,
and verification does not authorize, execute, enforce or automatically reconcile
anything. See the [normalization and coverage contract](.agents/skills/long-horizon-engineering/references/cross-layer-verification.md).


</details>

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

Updates are explicit and comparison-first. Backup-first replacement needs
authority for the exact version, target and effects; reuse an existing approval
that already covers them, otherwise obtain it before replacement. No automatic background update or mutable-ref upgrade.
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
