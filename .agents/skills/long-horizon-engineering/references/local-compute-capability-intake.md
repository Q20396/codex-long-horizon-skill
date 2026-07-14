# Local Compute Capability Intake

Use this optional, explicit-only protocol when a user wants help choosing a
local compute or model execution approach. It is a manual requirements intake,
not a device-management, device-discovery, or distributed-inference feature.

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
