# K6 Knowledge Governance Static Implementation Map

Status: `REBASELINED_STATIC_CANDIDATE`

The local lifecycle statements and validation outcomes in this map are
pre-commit historical verification evidence. Current Git and pull-request
state is established only by repository and PR evidence; it is not inferred
from this map.

## Fixed inputs

```text
LHE base:
fd8f7f301c481a7542b5edfa18e3474b55b53048

K0-K5 design source:
/private/tmp/lhe-knowledge-governance-design-001/
sandbox/skill-incubator/architecture/
knowledge-governance-boundary-design.md

K0-K5 design SHA-256:
e0edd056afe951d75016c747554d73ee8b89818c99ca4a4da51f9ffba8d81693
```

The design document is an input to this isolated batch. It is not copied into
the candidate and is not modified by K6.

## Design-to-implementation mapping

| Design layer | K6 candidate implementation | Deliberately unimplemented boundary |
| --- | --- | --- |
| K0-K2 | Six-record Draft 2020-12 candidate Schema, descriptor validator, synthetic descriptor cases | No knowledge-file read, path resolution, provenance check, index, memory, or persistence |
| K3 | Closed Request, Authorization, and Receipt shapes; exact cross-record equality and timestamp checks; ordered first-match evaluation over synthetic JSON | No Authorization lookup, revocation service, section resolution, actual read, Receipt emission runtime, or storage |
| K4 | Closed Proposal and Human Disposition shapes; common readiness and ordered post-disposition checks | No preview renderer, filesystem writer, queue, scheduler, write Receipt, or host capability; `APPROVE` remains non-executable evidence |
| K5 | Synthetic static, capability-expansion, and future-runtime cases | No filesystem, renderer, network, host-enforcement, Hook, MCP, scheduler, or automatic-memory test |

## Candidate Schema placement

The candidate Schema lives at:

```text
sandbox/skill-incubator/knowledge-governance-k6/
knowledge-governance.schema.json
```

It is intentionally not registered in
`sandbox/skill-incubator/schemas/` or the existing formal release inventory.
That inventory is release evidence for the already published v0.6.0 line.
Registering K6 there would change stable release counts and is outside this
batch. K6 tests independently parse the candidate Schema, verify its six
closed definitions and internal references, and preserve the existing formal
inventory byte-for-byte.

The Schema's `x-k6-boundary` member is annotation only. It does not become an
instance field, authorization, or host policy.

The Schema is the sole normative source for record-local lexical and
closed-shape rules: unknown fields, ID grammar, relative-path grammar, fixed
timestamp format, the seven prohibited one-line Unicode code points, and the
shared declared sensitive-text/prohibited-heading patterns. The dependency-free
validator repeats only Schema-compatible admission prechecks as a necessary,
not sufficient, fail-closed boundary before relation evaluation; it does not
define an independent local contract or certify Schema acceptance. Draft
2020-12 remains the local-contract authority. The validator owns only
cross-record bindings, timestamp ordering, ordered first-match outcomes, and
other relationship semantics that Draft 2020-12 cannot express across separate
records. Regression tests cover both shared text rules and admission-precheck
parity, including an ASCII-versus-Unicode-case-mapping regression using
`API_KEY=SYNTHETIC`; the precheck uses ASCII-only case semantics and does not
Unicode-fold text into a prohibited ASCII marker. A cross-record validator
rejection is not described as a Schema failure.

K3 and K5 call the same ordered authorization-gate function. K5 does not
maintain a reduced Authorization evaluator: `UNKNOWN` sensitivity, evaluation
time ordering, Authorization expiry, Request expiry, revoked status, and a
future-dated revocation all retain the K3 first-match order.

## Validator boundary

`scripts/validate_knowledge_governance_contracts.py` accepts only an explicit
synthetic, fixture-only envelope through its public library API. Its optional
CLI first reads one caller-supplied JSON fixture path, then rejects a malformed
or non-synthetic/non-fixture-only envelope before contract validation, and
emits deterministic JSON to standard output. It has no
output-file option and imports no filesystem resolver, network, process,
authorization, renderer, writer, or persistence implementation.

The validator returns only:

```text
ACCEPT
REJECT
BLOCKED
NOT_AUTHORIZED
OUT_OF_SCOPE
```

Every result also discloses:

```text
runtime_execution: NOT_IMPLEMENTED
fixture_input_read: CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED
governed_target_io: NOT_IMPLEMENTED
network: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN
external_action: NONE
```

The CLI's file argument is an untrusted caller-supplied JSON input until its
parsed envelope has been validated. It does not claim a host-level guarantee
that an arbitrary caller path cannot be opened before that envelope check.
`governed_target_io` remains `NOT_IMPLEMENTED`, and host enforcement remains
`NOT_PROVEN`.

## Fixture boundary

Fixtures are JSON-only, synthetic, and marked:

```text
synthetic: true
fixture_only: true
```

They contain no real project content, account data, credentials, customer
identity, transaction, external URL, or absolute private path. Future-runtime
questions are represented only by the fixed states `OUT_OF_SCOPE`,
`NOT_EXECUTED`, and `NOT_PROVEN`.

## Non-goals and stop state

```text
runtime_execution: NOT_IMPLEMENTED
fixture_input_read: CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED
governed_target_io: NOT_IMPLEMENTED
authorization_lookup: NOT_IMPLEMENTED
preview_renderer: NOT_IMPLEMENTED
network: NOT_IMPLEMENTED
host_enforcement: NOT_PROVEN

obsidian: NOT_AUTHORIZED
automatic_memory: DISABLED
hook: NOT_AUTHORIZED
mcp: NOT_AUTHORIZED
scheduler: NOT_AUTHORIZED
persistence: NOT_AUTHORIZED

git_commit: PRE_COMMIT_HISTORICAL_EVIDENCE_ONLY
git_push: PRE_COMMIT_HISTORICAL_EVIDENCE_ONLY
pull_request: PRE_COMMIT_HISTORICAL_EVIDENCE_ONLY
release: NOT_PERFORMED
runtime_enablement: NOT_PERFORMED
```

The batch stops after local verification and a fixed-identity reviewer handoff.
No test result, Schema result, or static `ACCEPT` authorizes a later stage.

## Local verification record

```text
rebaseline_base: fd8f7f301c481a7542b5edfa18e3474b55b53048
targeted_k6_tests: PASS (13 passed, 0 skipped)
fixture_count: 50
schema_behavior: VERIFIED_WITH_ISOLATED_OFFLINE_DRAFT202012_VALIDATOR
reason: jsonschema 4.25.1 and its pinned dependencies were installed only in a temporary /private/tmp virtual environment from a fixed offline wheelhouse; no project or system installation and no validation-time network access occurred
draft202012_fixture_validation: PASS (50 fixture cases; 55 embedded records inspected)
full_local_unittest: PASS_WITH_OUTPUT_LIMITATION (process exit 0; the repository test harness did not emit a complete aggregate count to this terminal capture)
full_skill_validation: UNVERIFIED_IN_CURRENT_CANDIDATE_RECORD
formal_schema_lock_check: PASS (32 inventory entries: 9 fixture-validated, 23 syntax-only)
release_readiness_static_check: PASS_WITH_LIMITATION (v0.6.0 final --allow-existing-tag consistency mode; pre-tag-static is inapplicable to final release state; pre-commit candidate worktree state is historical evidence only)
schema_json_syntax: PASS
validator_python_compile: PASS (in-memory; no bytecode emitted)
validator_static_capability_check: VERIFIED_BY_TARGETED_TEST
synthetic_cli_validation: PASS (all 50 synthetic fixture cases)
git_diff_check: PASS (pre-commit candidate evidence)
changed_file_allowlist: PASS (11-file pre-commit candidate evidence)
pyc_pyo: NONE
file_sha256_manifest: CAPTURED_IN_REVIEWER_HANDOFF
independent_review: NOT_PERFORMED
```

Earlier reports of full-suite, formal-lock, release-readiness, compilation, or
skill-validation outcomes are not evidence for this changed candidate and are
deliberately not inherited here. They require a new reproducible run and a
current output record before they may be reported as PASS.
