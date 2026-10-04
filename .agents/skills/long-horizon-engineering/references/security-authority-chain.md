# Security Authority and Verifiable Security Chain

Phase 1.25 is an experimental Python foundation, not a runtime integration,
host sandbox or authenticated audit service. Importing the module performs no
file, network, subprocess, environment mutation or background-thread effects.
No dependency is added. RSE and Local Compute execution paths remain unchanged.

## Trust and authority boundary

The trusted host bootstraps `ROOT_OWNER` and supplies current immutable
`SecurityAuthority` snapshots, scope relationships and bounded timestamps.
Runtime/model-originated data must never choose its own actor snapshot or call
the low-level storage API as an authorization entrypoint. This module does not
authenticate Python callers, cryptographically identify actors, resolve parent
identities or maintain an effective-authority database.

`authorize_management_change` is fail-closed for unknown actions, malformed,
revoked or expired authorities, scope mismatch and privilege escalation.
Root invariants cannot be disabled by any role, including Break Glass.

| Role | Management boundary |
| --- | --- |
| ROOT_OWNER | Installation scope; may grant admin/project/task/runtime, never mint another root through this API |
| INSTALLATION_ADMIN | Installation scope; may grant project/task, not root or another admin |
| PROJECT_AUTHORITY | Its project and descendants; may grant task authority only |
| TASK_AUTHORITY | Its project/task; no authority delegation |
| RUNTIME | Scoped evidence submission only; no policy, authorization, authority or Break Glass administration |

Child scope and expiry cannot exceed the grantor's. Installation/organization
policy changes use installation scope; project policy uses a project; task/run/
action policy changes require a task scope. The host supplies correct hierarchy
relationships; IDs are opaque, not inferred from filesystem paths.

## History is not effective state

`record_management_event` checks authority and the closed action/event pairing
before append. Policy supersession requires previous and replacement artifact
digests. Authorization and authority revocation append new events, never erase
old records. These events do not silently mutate an external policy or authority
store. The caller must supply the current revoked/expired snapshot on future
checks and apply any authorized policy change separately. An old unrevoked object
is not a revocation database. No actual permissions or runtime effects are enabled.

`record_receipt` records a digest of an RSE v1 receipt, not its raw target, reason
or evidence. It proves only that a caller submitted that digest; it does not
reconcile side effects, independently observe execution or certify receipt truth.

## Break Glass

`BreakGlassGrant` requires nonempty reason, installation/project/task scope,
explicit action/capability sets and exact target strings, issued time and expiry.
Maximum lifetime is 3,600 seconds. Only root/admin may record a grant; runtime
may record a validated use as evidence. It cannot grant or extend one.

`record_break_glass` records separate GRANTED, USED and EXPIRED events. Use requires
a recorded matching grant digest, an unexpired/nonrevoked grant and the exact
action/capability/target boundary. Pass actual `project_id`/`task_id` for a use
below a broader grant; both actor and grant must permit that scope, which is
preserved in the use record. Omitted scope defaults to the grant scope.
A recorded expiration prevents later backdated
use. No timer or worker is started: expiration is enforced on use and an authorized
caller explicitly records the expiry event. Pure `validate_break_glass` is only
a predicate and must not be used to perform an unrecorded override. There is no
RSE override adapter in this phase; root invariants remain immutable.

## Canonical records and verification

The sealed schema is `20396-security-chain/v1`. A record contains sequence,
timestamp, closed event kind/actor role, hashed chain/scope/actor/subject/event/
reason/evidence references, artifact/previous-artifact/authority digests,
`previous_hash` and `record_hash`. No raw target, command, prompt, secret, token,
credential, freeform reason or receipt is copied into the sealed record.
Drafts and supplied artifacts remain caller-owned sensitive inputs.

Canonicalization is UTF-8 JSON with sorted keys, compact separators, deterministic
set ordering and enum/dataclass conversion. Integral floats normalize to integers.
NaN, Infinity, unsupported types, oversized/deep structures and invalid timestamps
are rejected. This is the project's bounded Python format, not a claim of RFC 8785
or arbitrary cross-language canonical-number compatibility.

Genesis is 64 zeroes; sequence starts at 1. SHA-256 covers the complete canonical
record except its `record_hash`, including `previous_hash`. Verification checks
schema, identity, shape, bounds, contiguous sequence, duplicate event references,
links and record hashes. Modification, reordering, middle deletion and sequence
jumps fail verification. Failed verification blocks append; no automatic repair,
renumber, rehash, reset, delete or replace operation exists.

Digests are not encryption or anonymization: low-entropy inputs may be guessed,
and deterministic references reveal equality. Do not supply secrets unnecessarily
or publish sensitive chains. Diagnostics use fixed reason codes, not raw inputs.

## Storage and recovery

`InMemorySecurityChain(chain_id, installation_id)` is ephemeral.
`JsonlSecurityChain(chain_id, installation_id, path, create=True)` explicitly
creates a new file exclusively; reopening omits `create=True`. No default home
directory, hidden persistence, auto-creation on reopen or network service exists.
New POSIX files use mode 0600. Existing permissions are not silently changed.
The caller must choose an approved path inside a trusted directory and verify
its existing access controls. Filesystems/platforms can weaken permission/fsync
guarantees; no hostile-directory race or power-loss directory-entry guarantee is made.

Each JSONL append rereads and verifies the complete file, appends one canonical
line, flushes and fsyncs. Partial/malformed/noncanonical JSON, duplicate keys,
unexpected fields, nonregular files and corruption fail closed without repair.
An uncertain write/fsync latches that controller closed; inspect the existing file
before explicitly reopening. Do not blindly retry an event with a fresh ID.

An `RLock` serializes threads sharing **one controller object**. Separate objects
or processes must not write the same file concurrently. Multi-process safety is
not implemented. Limits are 10,000 records and 16,384 bytes per JSONL record;
this bounded foundation rereads history rather than adding indexes or rotation.

Before continuing across restarts, retain a trusted `(head_sequence, head_hash)`
separately from the chain. `verify_against(expected_sequence, expected_head)`
checks that historical prefix; valid extensions are accepted, rollback or changed
prefix is rejected. The host must invoke this check before append when continuity
matters; ordinary `verify()` checks internal consistency only.

Tamper-evident is **not tamper-proof or immutable**. A valid truncated prefix
passes ordinary verification. A completely rewritten, internally valid chain
cannot be distinguished without independently retained evidence. A colocated
head can be replaced alongside the chain. No signatures, trusted timestamps,
signed checkpoints, external anchors, consensus or cryptographic actor identity
are implemented. Stop on verification failure; preserve evidence and ask the
authorized operator to resolve it, never silently rebuild history.

## Minimal synthetic journey

Load `scripts/security_authority_chain.py` explicitly in a trusted Python host:

```python
chain = InMemorySecurityChain('synthetic-chain', 'synthetic-installation')
owner = SecurityAuthority('synthetic-owner', AuthorityRole.ROOT_OWNER,
                          'synthetic-installation')
record_management_event(chain, owner, ManagementAction.INSTALLATION_POLICY_CHANGE,
    EventType.POLICY_CREATED, event_id='policy-v1', now=1, artifact={'version': 1})
head = chain.head()
assert chain.verify().valid
assert chain.verify_against(*head).valid
```

`head()` returns `(sequence, hash)`; retain both separately from the chain file.
Tests: `python3 -m unittest discover -s tests -p 'test_security_authority_chain.py'`.
All validation uses synthetic data and explicit temporary files, not customer
policy changes, real execution, runtime credentials or installed host services.

## Excluded phases and compatibility

No Token Accountability (1.35), Critical Execution Trace (1.5), signed checkpoints
or external anchors (1.75), host observer, real runtime binding, Local Compute
integration, Paperclip adapter, dashboard, distributed ledger or blockchain.
RSE remains the separate Phase 1 kernel; receipt hashing does not modify its
execution decisions. Source packaging includes this reference and helper without
activating them or changing the published stable release.
