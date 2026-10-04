# Critical Execution Trace — Phase 1.5

## Purpose

Experimental library foundation for comparing declared and observed effects and
explaining critical parent/child patterns. It performs no actions on the targets.
The core package contains the script and this reference (54 core paths). It adds
no dependency, database, scheduler, provider integration or CLI runtime.

## Threat Model

An adapter can report an undeclared read, process, network request or other effect.
The library detects deterministic mismatches and bounded causal candidates in
supplied evidence. A compromised adapter can omit or falsify evidence. Validation
does not authenticate the adapter, prove byte-level data flow, or establish intent.

## Observation Boundary

Sources are closed: DECLARED, ADAPTER_OBSERVED and RECONCILIATION_OBSERVED.
Declared events and ATTEMPTED events are not observed effects. OBSERVED and
COMPLETED are adapter assertions, not host verification. PROCESS_EXIT may carry
an exit code; absent exit code remains unknown. Exit, decision and capability
events are retained as evidence but do not manufacture a side effect.

## Declared vs Observed

Immutable `DeclaredEffects` / `ObservedEffects` have ten categories: reads,
writes, creates, deletes, moves, processes, network_targets, secret_refs,
git_actions and external_actions. Comparisons are exact set differences after
canonicalization. Logical absolute POSIX paths use existing RSE normalization;
no filesystem or symlink resolution occurs. Network comparisons deliberately use
origins, not URL paths: this is not full RSE URL-policy enforcement. URLs with
credentials, query strings or fragments are rejected. Git commit and push differ.
Config/service/package/PR/release/deploy are typed external_actions; config and
service records do not imply network traffic.

`declared_from_action` maps each RSE action class explicitly and ignores
`expected_effect` prose. A declaration is intent, never authorization.
`compare_effects` requires identical contexts. Analysis compares by action, never
using one action's declaration to cover another action's observed effects.
An absent declaration is **unknown**, not an empty declaration: the report counts
`undeclared_baseline_action_count`. Supply an explicit empty declaration when the
authorized caller has established that no effects were declared.

## Trace Context

Trace/install/project/task/run/action, parent action, provider, optional model and
runtime identify immutable context. Optional scope is a prefix: run needs task,
task needs project. Rebinding any context field of an existing action is rejected.
Provider labels do not change detection rules. Context contains no prompt/output.

## Critical Event

Immutable records contain event ID, closed event type, context, source, finite
nonnegative timestamp, logical target, RSE data classification, optional
capability, status, evidence references, exit code and move destination. The
event vocabulary also retains policy/authorization/capability evidence without
creating a second authority engine. Move requires both source and destination.
The caller must supply opaque secret references, never secret values or payloads.

## Causality

Only a strict ancestor action establishes a causal candidate. Same-action order
and unrelated chronological order are insufficient. Parent cycles, self-parent,
scope mismatch, context rebind and backward earliest-action time are rejected
atomically. Out-of-order insertion is allowed. Detection separately checks each
participating event's timestamp. Missing parents never create imaginary events.
Parent links are adapter assertions, not delegation or authority grants.

## Trace Completeness

UNKNOWN is default. COMPLETE requires explicit nonempty `coverage_refs` supplied
by the caller and means **adapter-attested coverage only**. Missing parents force
PARTIAL. Coverage is not inferred from a closed process or a successful command.
No-findings wording always says SUPPLIED_OBSERVATIONS_ONLY and disclaims safety.
Check missing declaration count separately, including on COMPLETE traces.

Bounds: 128 events per trace, 128 input effects across categories per effects
record, 128 declarations, 32 ancestor edges, 16 evidence/coverage refs, 1024
characters per input text, 128 findings/divergences per analysis, timestamps up
to 2**53. Overflow raises rather than silently truncating. Risk search is bounded
by event count (at most cubic) and finding limit; no background work is started.

## Divergence Types

UNDECLARED_READ, UNDECLARED_WRITE, UNDECLARED_CREATE, UNDECLARED_DELETE,
UNDECLARED_MOVE, UNDECLARED_PROCESS, UNDECLARED_NETWORK,
UNDECLARED_SECRET_ACCESS, UNDECLARED_GIT_ACTION, UNDECLARED_EXTERNAL_ACTION.
Each carries its context, target, declared/observed digests and WARNING severity.
Absence of an expected effect is not reported as an extra effect.

`correlate_rse` validates receipt identity against the supplied ActionRequest.
Observed extra effects produce HIGH OBSERVED_EFFECT_CONTRADICTS_RSE_DECISION.
Policy-denial correlation additionally requires trusted caller attestation
`attempt_linked=True` that the event belongs to the denied attempt; action ID
alone cannot distinguish a historical effect from a retry. Default is unlinked.
Repeat-success denials, reconciliation and unknown outcomes do not accuse prior
effects. `RSECorrelation` preserves receipt policy/execution/reconciliation/final
states alongside divergences and the linkage flag; empty divergences do not mean
known success or absence of effects. It does not authenticate receipts or
replace RSE execution/reconciliation state. Its input must come from the trusted
RSE boundary; a forged matching receipt is not independently verifiable here.

## Risk Patterns

Six HIGH candidate patterns, with event IDs, action IDs, target, source data
classification, human-readable reason and evidence digest:

- SENSITIVE_READ_TO_EXTERNAL_NETWORK
- SECRET_ACCESS_TO_EXTERNAL_NETWORK
- SENSITIVE_READ_TO_PROCESS_TO_EXTERNAL_NETWORK
- SECRET_ACCESS_TO_PROCESS_TO_EXTERNAL_NETWORK
- UNDECLARED_NETWORK_AFTER_SENSITIVE_READ
- UNDECLARED_PROCESS_AFTER_SECRET_ACCESS

SENSITIVE, LOCAL_ONLY and SECRET file reads qualify; UNKNOWN is not silently
classified as sensitive. SECRET_ACCESS qualifies explicitly. External means
outside the caller's exact normalized internal/approved origin sets. Subdomains
are not inherited and no DNS is performed. Trusted sets must come from trusted
configuration, not the acting model. Undeclared patterns require that action's
explicit declaration. Declaring a network target does not negate RSE denial.
Current network patterns use NETWORK_REQUEST events only; other egress actions
remain visible to divergence comparison but are not broader exfiltration claims.

## Security Chain Integration

Three additions to the existing EventType enum: CRITICAL_TRACE_EVENT,
TRACE_DIVERGENCE and TRACE_RISK_FINDING. The record helpers reuse scoped
RSE_RECEIPT_RECORD management authority and existing chain validation/duplicate
protection. No schema or old event encoding is changed. Anchors store artifact
digests, not targets, secret refs or event payloads. An anchor does not prove
the caller observed real host activity. Full artifacts stay with the caller.
Existing chain limitations apply: tamper-evident, not tamper-proof; no signed
checkpoint or external trusted anchor. CET does not add a second ledger.

## Privacy

All sensitive artifacts suppress generated repr. No prompt, output, file body,
process environment or secret value field is provided. Opaque references can
still be sensitive; callers must not pass secrets disguised as references.
Do not indiscriminately serialize dataclasses: in-memory targets are available
for authorized operator inspection. Only the explicit record helpers redact
chain output to digests. Digests are commitments, not encryption.

## Adapter Trust Limitation

The library trusts supplied scope, classification, observations, causal links,
coverage refs, origins and current authority snapshots. Python callers can forge
inputs; this is validation of a contract, not a hostile-process security boundary.

## Current Enforcement

Synchronous input/structure validation, bounded deterministic comparisons and
candidate detection, plus scoped explicit evidence anchoring. Invalid structure
is rejected; no automatic execution blocking, alert delivery or network action.

## Non-Enforcement

No host sandbox, packet firewall, syscall interception, secret discovery, malware
classification, intent inference, live adapter, Paperclip integration, Local
Compute change, telemetry, background observer or production security guarantee.

## Future Host Observer

HOST_OBSERVED is intentionally absent. Independent host evidence requires a
separately authorized future design; no dormant implementation ships here.

## Public Claim Boundary

Phase 1.5 is an experimental trace foundation with synthetic tests. It is not
runtime activation, independent host coverage, signed evidence, malware detection
or prevention. No findings is not proof of safety. Merge is not release/deploy.

### Reproducing a risk commitment

`evidence_digest` binds the finding type, ordered connecting action path, digests
of **all supplied events on that path** (including intermediate actions), the
terminal action's declaration (or explicit absence), and normalized separate
internal/approved origin sets. Retain the trace events, declarations and trusted
origin configuration as caller-owned evidence to recompute the finding. Endpoint
IDs alone are not the full evidence. A changed bridge, declaration or origin
configuration changes the commitment or removes the finding. This is a digest
commitment, not signed or independently authenticated observation.

## Synthetic Operator Walkthrough

Run from the repository root with Python 3.9+. The following imports the shipped
module and uses synthetic in-memory evidence only; no file target is read and no
network request is made. The test suite executes this exact fenced example.

```python
import sys
sys.path.insert(0, '.agents/skills/long-horizon-engineering/scripts')
import critical_execution_trace as cet

def context(action, parent=None):
    return cet.TraceContext('demo', 'install', 'project', 'task', 'run',
                            action, parent, 'provider', None, 'adapter')

read = cet.CriticalEvent('read-1', cet.CriticalEventType.FILE_READ, context('read'),
    cet.ObservationSource.ADAPTER_OBSERVED, 1, '/synthetic/private.txt', cet.rse.DataClass.SENSITIVE)
network = cet.CriticalEvent('net-1', cet.CriticalEventType.NETWORK_REQUEST, context('net', 'read'),
    cet.ObservationSource.ADAPTER_OBSERVED, 2, 'https://outside.example', cet.rse.DataClass.UNKNOWN)
trace = cet.CriticalTrace('demo', 'install')
trace.append(read)
trace.append(network)
declarations = (cet.DeclaredEffects(read.context, reads=('/synthetic/private.txt',)),
                cet.DeclaredEffects(network.context))
report = cet.analyze_trace(trace, declarations, internal_network_origins=(), approved_network_origins=())
assert report.completeness == cet.TraceCompleteness.UNKNOWN
assert report.divergence_count == 1
assert report.risk_finding_count == 2
assert report.undeclared_baseline_action_count == 0
print('Declared read:', declarations[0].reads)
print('Observed:', [(e.event_type.value, e.target) for e in trace.events()])
print('Extra effect:', report.divergences[0].divergence_type.value)
for finding in report.risk_findings:
    print(finding.finding_type.value, finding.action_ids, finding.event_ids,
          finding.target, finding.data_classification.value, finding.reason)
print('Coverage:', report.completeness.value, report.no_findings_statement)
```

Interpretation: read was declared and observed. The child action declared no
effects but reported an external request. The explicit read → net parent link,
SENSITIVE classification and outside origin explain the two risk candidates.
UNKNOWN coverage remains UNKNOWN; neither the candidates nor the extra effect
prove that file contents were transferred or that the actor was malicious.
