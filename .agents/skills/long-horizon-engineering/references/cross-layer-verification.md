# Cross-Layer Verification — Experimental

`cross_layer_verification.py` contains only three public types:
`VerificationInput`, `VerificationFinding`, and `CrossLayerVerifier`.
`CrossLayerVerifier.verify(input)` returns an immutable tuple of factual findings.

```text
MODE: READ_ONLY
ACTION SCOPE: ONE_ACTION
LAYERS: DECLARED, AUTHORIZED, ADAPTER_OBSERVED, HOST_OBSERVED, TARGET_REALITY
RESULTS: MATCH, MISSING, EXTRA, DIVERGED, UNKNOWN, NOT_OBSERVED
FINDINGS PERSISTED: NO
FINDINGS CHAINED: NO
NEW LEDGER: NO
AUTHORIZATION MUTATION: NO
RECONCILIATION MUTATION: NO
ENFORCEMENT: NO
```

The four fixed directional comparisons are DECLARED → AUTHORIZED,
AUTHORIZED → ADAPTER_OBSERVED, ADAPTER_OBSERVED → HOST_OBSERVED, and
HOST_OBSERVED → TARGET_REALITY. There is no configurable pair API, executor,
observer control, persistence hook, Security Chain write or CET emission.

## Trusted normalization boundary

The caller supplies normalized evidence already produced by existing layers.
The verifier authenticates no source, inspects no target and establishes no
coverage. A caller-supplied `VERIFIED`, coverage label, or reference is an
attestation, not independent proof. Model data must never populate trusted
authorization, coverage or reality inputs. Python immutability is an ordinary
API contract, not isolation from hostile Python code.

Each layer accepts at most 128 descriptors of this shape:

```python
(semantic_class, material_ref_or_None, action_ref_or_None,
 evidence_refs, correlation_status)
```

Only inert lists/tuples are accepted and copied to tuples. References follow the
existing host grammar: `ref:` plus 1–128 opaque identifier characters, or a
`sha256:` digest. Each descriptor has at most 16 evidence refs; a finding has at
most 32. Refs must already be opaque and safe to disclose. The verifier is not
a secret detector or a redactor. It rejects paths, URLs, arbitrary maps and raw
source objects with a fixed error code.

Use existing bounded material identities where their semantics agree, such as
the bridge's prepared material identity after checking the exact authorized
payload commitment. A source record/artifact digest proves the identity of that
record; it is not automatically an effect identity shared across layers. Do not
compare source-record digests as material identities. A host target hash and an
adapter target cannot be equated without an existing trusted identity mapping.
For multi-part effects such as FILE_MOVE, a material ref must cover both endpoints
and any other material component required by the existing contract. An opaque
ref must name the same material slot in both layers. This is local normalization,
not a new global identity system.

Normalize sources according to their existing contracts:

| Input | Required source |
| --- | --- |
| DECLARED | Agent/model declared effect evidence, e.g. prepared `declared_effects`; untrusted proposal evidence only |
| AUTHORIZED | Trusted RSE authorization/effect commitments for this exact action, current policy decision and approved payload; a proposal or broad grant alone is insufficient |
| ADAPTER_OBSERVED | Existing adapter/CET `ADAPTER_OBSERVED` evidence with comparable material identity; generic success strings are insufficient |
| HOST_OBSERVED | Existing trusted HostObservation/ingestor evidence and explicit correlation; neither authorization, reality nor kernel truth |
| TARGET_REALITY | Existing trusted independent reconciliation/readback establishing this comparable material effect; neither adapter success, HTTP status nor NOTE_EXEC alone |

Preserve the original source when normalizing. Do not synthesize adapter evidence
from host evidence or authorize a declaration by copying it. A target-reality
ref may only be populated from actual independent verification, not by copying
the expected or observed effect. Existing tests exercise synthetic CET/RSE/host
contracts and real temporary-file readback; they do not prove production source
authentication or universal material comparability.

`None` means unavailable source, including an omitted collection. An explicit
empty collection means that source was supplied with no represented effects.
Only `CORRELATED` descriptors whose explicit action ref equals `action_id` can
participate. `CORRELATED` without an explicit action ref is rejected as
contradictory input. `UNCORRELATED` and `UNRESOLVED_LINK` remain unassigned, and
known other-action evidence is excluded. No time, list-order or text-similarity join
exists. Unassigned evidence can make an absence conclusion unresolved; it never
becomes a current-action MATCH or EXTRA.

## Coverage and comparison

Coverage uses `SCOPED_COMPLETE`, `PARTIAL`, or `UNKNOWN`. Supplied declaration and
authorization collections describe the complete bounded sets represented by
those sources for this action; use `None` if that cannot be established. Adapter
and host coverage attest only their existing observation scope and must cover
the semantic effects being compared before absence supports MISSING or EXTRA.
Do not promote aggregate counts, a successful call or a quiet observer into
complete coverage. Narrower or unsupported scopes must use UNKNOWN/PARTIAL.

Current macOS NOTE_EXEC coverage stays PARTIAL. Its PROCESS_EXEC is distinct from
PROCESS_START; a PID target ref does not establish the executed program image or
payload identity. If no comparable material identity is available, normalize
material as `None` and obtain UNKNOWN. The verifier creates no observation.

`host_gap=True` marks a sequence gap or degraded host evidence, including a
previous gap still affecting a session. It makes host coverage UNKNOWN for
absence in either direction. Positive unambiguous evidence can still MATCH;
an absent observation cannot become MISSING. PARTIAL absence is NOT_OBSERVED;
UNKNOWN coverage yields UNKNOWN. Likewise, partial/unavailable evidence in
source A cannot prove that an unmatched B effect is EXTRA.

Unique material identities in the same class MATCH, including proven positive
matches under partial coverage or a host gap. After exact matches, DIVERGED
requires uniquely established material correspondence: a single complete
comparable identity on each side, complete scoped coverage on both sides, and
no gap or unresolved alternative that could hide an exact counterpart.
Uncertain leftover pairing yields UNKNOWN. Multiple candidates, repeated
identities or any incomplete identity in that class yield
UNKNOWN instead of arbitrary pairing. Distinct classes follow directional set
semantics and never DIVERGE merely because their classes differ. Unsupported
semantics yield UNKNOWN. These are bounded factual comparisons, not claims of
intent, causality, maliciousness, severity or confidence.

Reality status is only VERIFIED/UNKNOWN. UNKNOWN dominates the entire reality
comparison, even with no host effects. VERIFIED requires trusted independent
evidence but does not attest exhaustive reality coverage. Thus absent reality
evidence remains UNKNOWN; this API supplies no complete reality coverage claim.
Consequently different host/reality leftovers also remain UNKNOWN; VERIFIED
alone does not prove a unique pairing.

Findings include action, both layers, semantic class, material ref, result,
reason, evidence refs and coverage. `compared_effect_ref` shows the counterpart
for MATCH/DIVERGED. For EXTRA/its uncertainty, `coverage_status` reports A's
coverage (the absence source); otherwise it reports B's coverage. Unavailable
sources or unresolved reality produce a pair-level UNKNOWN with no invented
effect ref. Results sort by fixed pair order, class, material ref, result,
counterpart ref and evidence refs. Input order never creates identity.
If both scoped sets are empty but an unresolved link is present, a pair-level
UNKNOWN reports the correlation gap without assigning that event to the action.

No finding authorizes, executes, enforces, retries or automatically reconciles
an action. Findings are not persisted or chained. Phase 5 is not implemented.
