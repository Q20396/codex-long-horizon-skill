# Signed Checkpoints — Phase 1.75

## Purpose

Inactive, experimental stdlib contracts for host-supplied signature verification
and externally retained checkpoint evidence. Core package: 56 paths. No keys,
network adapter, background task, database or runtime activation is included.

## Threat Model

A writer can rebuild or shorten an internally valid Security Chain. A verifier
holding an older trusted signed checkpoint can detect a different hash at the
checkpointed sequence, or a chain too short to contain it. A compromised signer,
verifier or caller can defeat this contract; Python objects are not a sandbox.

## Why Hash Chain Alone Is Insufficient

An attacker can recompute every hash after changing an old record. Internal
linkage then passes, but the checkpointed prefix hash differs. With no separately
retained evidence, replacing both chain and checkpoints remains undetectable.

## Checkpoint Model

`SignedCheckpoint` is an immutable **candidate artifact**. Its class name or
constructor does not certify a signature. Call `verify_checkpoint` with trusted
host verification before treating it as signed. `create_checkpoint` always
verifies signer output before returning; failure emits no signed result.

Schema: `20396-security-checkpoint/v1`. Fields: schema_version, checkpoint_id,
chain_id_ref, installation_ref, sequence, chain_head_hash, created_at, key_id,
algorithm, previous_checkpoint_hash, signature. Chain/installation refs use the
existing SHA-256 identity references. IDs are opaque ASCII references, not secrets.
Signatures are bytes internally, lowercase hex in JSON; 1–1024 bytes.
Times are finite nonnegative values through 2**53, normalized to float.
Sequence is an integer from 1 through the existing chain bound (10000).
Empty chains are rejected. No checkpoint file persistence is provided.

## Canonical Payload

UTF-8 JSON, sorted keys, compact separators, `allow_nan=False`. Every field except
signature is signed, including schema, key and algorithm. Complete-artifact
SHA-256 includes the signature; that hash identifies a checkpoint but is NOT a
signature. JSON reading rejects duplicate/unknown fields, bad signature hex,
unsupported values and artifacts over 8192 bytes. Input object key order is
irrelevant. Explicit serialization exposes caller-owned references; repr hides
artifact fields, and diagnostics use fixed reasons rather than adapter exceptions.

## Signer / Verifier Boundary

`CheckpointSigner.sign(bytes) -> SignatureEnvelope` and
`CheckpointVerifier.verify(bytes, envelope) -> SignatureVerification` are trusted
host contracts. A valid result must explicitly return `valid=True`, `reason=VALID`
and the exact key/algorithm actually used. Truthy booleans, dictionaries, missing
metadata, exceptions and mismatches fail closed. Unknown keys return
KEY_NOT_TRUSTED. No private keys, certificates, environment, keychain, HSM, KMS,
key URL discovery or trust-on-first-use are read by this module.

## Signature Algorithm Boundary

Closed identifiers: ED25519, ECDSA_P256_SHA256, RSA_PSS_SHA256. These are contracts,
not included implementations. The host must pin an approved implementation and
algorithm parameters (including signature encoding and RSA-PSS salt/MGF policy)
to its key resolution; it must not reinterpret algorithms or infer them from
length. Envelope metadata and signed metadata must agree.

## Key Identity

Key ID is inside the signed payload and identifies host verification material,
not ownership. The trusted verifier decides which keys are trusted. Key rotation
can use a different trusted key on a later, strictly higher-sequence checkpoint.
No rotation service, certificate hierarchy, revocation service or global trust
store is included. Host policy controls old-key verification and compromised-key
handling, not the caller-supplied timestamp alone.

## Checkpoint Continuity

First predecessor is GENESIS_CHECKPOINT_HASH (`0` repeated 64 times), distinct in
name from the chain genesis and not a trust root. Successors commit to the full
prior checkpoint hash. Sequences strictly increase; times cannot decrease.
Same-sequence checkpoints, including same-head rotation, are rejected for
simplicity. `verify_checkpoint_sequence` checks 1–1024 artifacts, unique IDs,
all signatures, same identity, linkage and ordering from genesis. Creation checks
its supplied predecessor against the current chain. Full ID replay detection
requires retained history; creation alone cannot discover omitted old IDs.

Deleting a middle checkpoint or reordering breaks continuity. Deleting the newest
checkpoint can leave a valid old history: retain the newest trusted anchor and
compare it against the presented latest checkpoint. A caller selecting only an
older anchor cannot prove freshness. This is checkpoint continuity, not blockchain.

## Chain Verification

Creation derives sequence/hash from a single structurally verified records
snapshot of the existing Security Chain object; raw arbitrary head tuples are
not accepted. `verify_chain_against_checkpoint` verifies identity/signature and
the exact record at checkpoint.sequence. Later valid records are allowed.
File-backed chains remain subject to their existing trusted-controller/storage
limits; explicit calls may read that caller-selected chain, never key files.

## Tail-Truncation Detection

Checkpoint at 100, chain ends at 80: CHECKPOINT_AHEAD_OF_CHAIN. Given the retained
checkpoint, a valid shorter prefix is not silently accepted.

## Whole-Chain Replacement Detection

Different internally valid chain with same identity and a different hash at 100:
CHAIN_DIVERGENCE. Rebuilding hashes after historical mutation produces the same
failure. The trusted checkpoint must predate the replacement and survive it.

## External Anchor Contract

`ExternalAnchor` includes anchor_id, checkpoint_hash, checkpoint_sequence,
chain_id_ref, installation_ref, anchored_at, opaque location_ref and optional
receipt_ref. Location/receipt fields reject URLs, query credentials and control
characters; store a safe opaque reference. Equality checks bind hash, sequence,
both identities and time ordering. Caller time is not a trusted timestamp.

`AnchorPublisher.publish(anchor_request_id, checkpoint)` returns an anchor artifact.
The host adapter MUST use stable request identity, reject conflicting reuse and
retain a request-to-anchor mapping for reconciliation. It MUST enforce its real
external-action permissions in addition to this module's management gate. The
module calls it once; there is no scheduler or automatic retry. This phase ships
no actual provider, adapter or anchor store. Tests use synthetic adapters only:
TEST DOUBLE ONLY, NOT EXTERNAL TRUST.

Only trusted current ROOT_OWNER or INSTALLATION_ADMIN snapshots may create or
publish installation-wide checkpoints. Existing authority validation covers
scope, expiry and revocation; CHECKPOINT_CREATE and ANCHOR_PUBLISH are the only
management additions. Runtime/project/task roles cannot self-certify. Low-level
artifact constructors are data APIs, not signing/publication authority.

## Anchor Unknown Outcome

Publisher exception or unusable response returns ANCHOR_OUTCOME_UNKNOWN: external
publication may have occurred. The checkpoint can remain valid independently.
Retain checkpoint and original request ID; never blindly publish under a new ID.
No automatic retry occurs. A host needing durable recovery must persist those
inputs itself; there is no hidden durable queue or restart-safe deduplication here.

## Anchor Readback

`reconcile_anchor` verifies the checkpoint before asking `AnchorReader.read` with
the same request ID. Matching artifact: READBACK_VERIFIED. Missing artifact:
NOT_FOUND, not proof that publication never occurred (eventual consistency may
apply). Reader error: ANCHOR_OUTCOME_UNKNOWN. Mismatch: ANCHOR_MISMATCH. Neither
path republishes. PUBLISHER_ATTESTED and READBACK_VERIFIED do not prove independent
retention; a dishonest or same-failure-domain adapter can report either.

## Trust Layers

1. CHAIN_ONLY: structural hash linkage, not authenticated history.
2. SIGNED_CHECKPOINT: trusted host verifier accepted a prefix commitment.
3. SIGNED_AND_ANCHORED: matching **trusted independently obtained** anchor was
   supplied to `verify_security_history`. This is conditional on caller evidence,
   not a measured property of storage. Do not pass a local copy or publisher-only
   receipt as independent evidence.

The report separates chain_valid, signature_valid, prefix_valid, continuity_valid
and anchor_valid; None means not assessed. The high-level single-checkpoint helper
does not verify complete checkpoint continuity; call verify_checkpoint_sequence
with the retained history separately. `verify_checkpoint_against_anchor` only
checks artifact equality, not signature authenticity. Use the high-level helper
when both are required. A failed comparison never yields a trusted combined level.

## Key Compromise Limitation

A stolen trusted signing key may produce valid forged checkpoints. This phase
does not solve custody, host integrity, trusted time, remote availability,
independent witness honesty or non-repudiation under compromise. Independently
retained older evidence may expose conflicts but cannot recover compromised trust.

## No Home-Grown Crypto

No signature mathematics or HMAC-as-signature. Unit FakeSigner/FakeVerifier use
exact-message lookup and arbitrary test tokens: NOT CRYPTOGRAPHIC SECURITY. Tests
prove contract logic, not a real algorithm or provider integration. Real crypto
and external retention require separately validated host integrations.

## Current Enforcement

Bounded input validation, canonicalization, host-verifier result checking, prefix
and continuity comparison, conservative authority checks and one-shot adapter
calls. No new ledger or self-anchoring events; security-chain/v1 stays unchanged.

## Non-Enforcement

No malware/intent detection, key custody, PKI, network transport, real anchor
publication, HSM/KMS, runtime binding, host observer or automatic execution block.
RSE, Token Accountability, CET and Local Compute behavior is unchanged. No
Paperclip dependency. No environment changes or operational I/O during import.

## Operator Journey

With host-provided `chain`, `actor`, `signer`, `verifier`:

```python
cp = create_checkpoint(chain, actor, signer, verifier, checkpoint_id='cp-1',
    now=trusted_clock_value, algorithm=SignatureAlgorithm.ED25519, key_id='host-key-1')
# cp.sequence, cp.chain_head_hash, cp.key_id and cp.previous_checkpoint_hash
# answer what was signed. Do not print serialized artifacts indiscriminately.
report = verify_security_history(chain, cp, verifier)
# report.signature_valid and report.prefix_valid must both be True.
outcome = publish_anchor(cp, verifier, actor, publisher, anchor_request_id='req-1',
    chain_id=known_chain_id, installation_id=known_installation_id, now=trusted_clock_value)
# If ANCHOR_OUTCOME_UNKNOWN: retain cp + req-1, use reconcile_anchor, never retry automatically.
# Verify independent retention separately before supplying an external_anchor to
# verify_security_history. Matching publisher receipt alone is not that evidence.
```

For local reproducible synthetic examples (no real signing/publication):
`python3 -m unittest tests.test_signed_checkpoints -v`.

## Public Claim Boundary

20396 includes an experimental signed-checkpoint contract that can bind a verified
Security Chain prefix to trusted external signature verification and independently
retained anchor evidence. It is tamper-evident under those assumptions, never
tamper-proof, immutable forever or production PKI. Merge does not activate runtime
bindings, create keys or publish anchors.
