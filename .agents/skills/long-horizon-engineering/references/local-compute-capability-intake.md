# Local Compute Capability Intake

Use this optional, explicit-only protocol when a user wants help choosing a
local compute or model execution approach. It is a manual requirements intake,
not an automatic device-discovery or distributed-inference feature.

## Local Compute Orchestration (Beta)

**Maturity: BETA.** Partial packaged implementation, not production-ready.
Real provider installation, model deployment/tuning and multi-device execution
have not been validated. The full zero-touch setup flow is not implemented.

The v0.7.0 candidate includes APIs at `scripts/local_compute_pool.py`
and `scripts/local_compute_deployment.py` relative to the installed Skill root.
These are the single implementation source. They are explicitly invoked Python APIs,
not automatically activated hooks, a daemon, a network scanner, or a cluster
manager. Packaging does not activate them; existing workflow semantics do not change.

`TaskPool` accepts independent node records, exact node/model/config worker
bindings, an authorized node set and concurrency ceilings. Qualification belongs
to a node/provider/model/config/task tuple, not a task class globally. A trusted
caller supplies evidence and consent; constructing an object or importing JSON
does not prove human authorization or authenticate a remote host.

The caller and adapters must run within the task's approved data boundary.
LOCAL_ONLY inputs and outputs must never be uploaded to cloud Main. Cloud
fallback requires permission for both input and output. A node being local does
not grant it access to every project's data. Worker results remain candidates,
not final verified conclusions.

Deployment effects are separately authorized, exact-target operations with
conservative resource reservations. Model selection operates only on supplied
approved candidates; it does not discover or download a model catalog. A smoke
test is not task qualification. Unknown outcomes require actual-state
reconciliation before any retry. Provider-specific installation, model identity,
endpoint binding, measured resource enforcement and recovery must be verified at
the integration boundary, not inferred from synthetic adapter success.

Migration creates an untrusted replacement node with hints only: consent,
runtime validation and qualifications must be obtained afresh. Never transfer
credentials or treat combined device memory as one machine's memory.

Distributed topology decisions are candidates only. No model sharding or
distributed runtime is supplied. Real node deployment, cross-node transport and
distributed experiments require separate exact authorization, including hosts,
ports, authentication, data scope, resource ceilings and rollback.

Synthetic tests exercise orchestration logic only; no real local-model quality,
multi-device throughput or cloud-usage saving is established by them.

### Target architecture, not the current end-to-end implementation

20396's intended sequence is consent, read-only probe, capability/value
evaluation, deployment plan, bounded authorization, provider/model selection,
installation/download, tuning, runtime validation, task qualification, then
local/hybrid execution. Customers retain control of inspection, installation,
storage/download budgets, network/privacy scope and material model/provider
changes. Selection and tuning may be automated only within those approved
limits; this complete flow is not implemented in the current Beta.

Task-level aggregation comes first: independent workers produce candidate
results for policy-permitted verification and synthesis. Different devices and
models retain separate qualifications. Distributed execution remains future
work requiring insufficient single-node and task-pool capability, material
model benefit, compatible nodes/interconnect/runtime, and explicit topology
authorization. No memory-summing or automatic cluster claim is implied.

## Ask Only For User-Supplied Information

Request only information the user chooses to provide, such as:

- intended workload and success criteria
- local-only, offline, or external-provider constraints
- approximate hardware class, operating system, and available budget
- acceptable latency, throughput, and output-quality tradeoffs
- retention, privacy, and licensing constraints

Use `templates/COMPUTE_CAPABILITY_INTAKE.md` for a structured record when
appropriate.

## Prohibited Behavior

Do not:

- discover devices on a local network
- inspect hardware, processes, ports, or installed models without approval
- start services, download models, join a cluster, or distribute workloads
- access credentials, provider accounts, or API keys
- claim a configuration is compatible without current evidence
- treat a capability recommendation as permission to install or run anything

## Recommendation Format

Separate:

- confirmed user-provided facts
- assumptions that need verification
- feasible options and their tradeoffs
- privacy, cost, reliability, and operational risks
- the next manual verification step

Do not use popularity, benchmark headlines, or model context-window claims as
the sole basis for a recommendation. Cite current primary documentation when
external technical facts materially affect a decision.

## Safety

Keep recommendations proposal-only. Any network discovery, model download,
hardware inspection, provider use, or service start requires separate explicit
approval with a bounded scope.
