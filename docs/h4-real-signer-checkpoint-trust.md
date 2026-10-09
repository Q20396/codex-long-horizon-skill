# H4 — Real signer + checkpoint trust

Delivery: `REPOSITORY_ONLY_EXPERIMENTAL`. The adapter in
`scripts/checkpoint_crypto.py` implements the existing injected
`CheckpointSigner` / `CheckpointVerifier` interfaces without changing the v1
schema, canonicalization, installed manifests, dependency locks or CI.
G06 and G07 are `PARTIALLY_IMPLEMENTED`; production signer identity is `UNKNOWN`
and production key custody is `NOT_VALIDATED`. Synthetic tests establish real
OpenSSH integration and an explicit policy boundary, not production enrollment.

## Explicit configuration

The trusted operator supplies an absolute executable path, an absolute signing
key handle/path, and a separately obtained public policy snapshot. There is no
default trusted signer, PATH backend selection, key discovery, SSH agent,
keychain, KMS, network signer, TOFU or enrollment from signature-carried keys.
Only Ed25519 is supported; existing ECDSA/RSA contract identifiers remain but
cannot fall back to this implementation. The signer inspects the explicit key's
public identity with `ssh-keygen -y -P ''` before signing and rejects unsupported
keys. It does not supply a passphrase or interactively unlock an encrypted key.

For repository Python use, the caller explicitly includes repository `scripts`
and `.agents/skills/long-horizon-engineering/scripts` on its module search path.
Then configure `OpenSSHBackend('/usr/bin/ssh-keygen')`,
`OpenSSHCheckpointSigner(backend, key_id, signing_key_path)` and
`OpenSSHCheckpointVerifier(backend, load_policy(public_json))`.
Pass these objects to existing `create_checkpoint`, `verify_checkpoint`,
`verify_checkpoint_sequence` and `verify_security_history` APIs. Calling import
alone performs no signing, subprocess, key/policy discovery or file creation.
This repository module is not added to any installed skill profile.

The operator must protect backend executable and key-path ancestry and bind its
actual executable identity during deployment preflight. This adapter does not
pin an OS binary digest or eliminate pathname replacement races on a hostile
host. It accepts a regular executable at the explicitly supplied absolute path;
the final executable and private-key components cannot be symlinks. Private key
handles must be regular, owned by the current user, at most 16 KiB, nonempty and
have no group/other permissions. Parent-directory trust remains an operator duty.

## Namespace and encoding

The signer signs exactly the bytes provided by the existing canonical payload
function. The fixed OpenSSH namespace is `20396-security-checkpoint/v1` and the
SSHSIG message hash is SHA512. Checkpoint trust never uses namespace `git` or Git
allowed-signers policy.

The opaque signature field contains **raw binary SSHSIG**, not armor, base64 text
or an additional JSON envelope. The parser requires magic `SSHSIG`, uint32
version 1, one canonical SSH Ed25519 public blob (32-byte key), the exact
namespace, an empty reserved field, `sha512`, and an inner `ssh-ed25519` signature
of exactly 64 bytes. All SSH strings have big-endian uint32 lengths. It rejects
truncation, invalid lengths, unknown version/hash/algorithm, trailing content and
wrong namespace. This format is exactly 198 bytes, below the unchanged 1024-byte
core limit; the unchanged core JSON serializer represents those bytes as hex.
OpenSSH armor is used only for bounded subprocess output and private temporary
verification files. Its normalized line width is 70 and it is decoded strictly.
Legacy Fake/raw tokens do not become real signatures.

## Public policy snapshot

`load_policy` takes explicit UTF-8 text or bytes, never a default file path. The
exact JSON schema is:

```json
{
  "schema_version": "20396-checkpoint-trust-policy/v1",
  "policy_version": "operator-snapshot-1",
  "keys": [{
    "key_id": "key-A",
    "principal": "operator-A",
    "public_key": "ssh-ed25519 <canonical-base64-public-blob>",
    "fingerprint": "SHA256:<unpadded-base64-SHA256-of-public-blob>",
    "purpose": "20396-security-checkpoint/v1",
    "status": "ACTIVE"
  }]
}
```

The placeholders above are explanatory, not a loadable or default trusted key.
Operator enrollment must independently establish the public key's intended
principal, fingerprint, key ID and purpose before supplying a snapshot. A
principal is a policy identity, not proof of a person or credential custody.
SSHSIG/core evidence carries no principal assertion to promote into policy.

Input is at most 32768 UTF-8 bytes and at most 32 keys. Empty keys explicitly
trusts nobody. Versions, key IDs and principals are 1–256 ASCII letters, digits,
underscores, dots or hyphens. Public keys contain exactly `ssh-ed25519`, one space
and canonical base64, without comments or options. Fingerprints are computed
locally from the canonical public blob and must match exactly. Purpose must
equal the fixed namespace, and status is exactly `ACTIVE` or `REVOKED`.
The parser rejects wrong types, unknown/duplicate fields at every nesting level,
unsupported schema, malformed keys, mismatched fingerprints, ambiguous key IDs,
principals and duplicate public keys (including aliases with different IDs).
Snapshots use frozen records and a tuple, copying parsed input. `PolicyError`
exposes only `POLICY_INVALID`; rejected or missing policy cannot establish trust.

The assessment's public policy reference is
`policy_version:SHA256(canonical snapshot JSON)`. It identifies explicit policy
content; it is not an authenticated enrollment receipt or durable anti-replay
ledger. The trusted operator remains responsible for policy origin and selection.

## Mathematics and trust

`assess(message_bytes, envelope)` returns an immutable sidecar containing
`cryptographic_validity` (`VALID`, `INVALID`, `NOT_ASSESSED`, `UNKNOWN`),
`signer_trust` (`TRUSTED`, `UNTRUSTED`, `UNKNOWN`), a bounded public reason code,
and the public policy reference (or `None` when policy is missing).

Mathematical verification uses `ssh-keygen -Y check-novalidate` with the
SSHSIG-carried public key. This key is never enrolled. A valid absent, revoked or
wrong-ID key can therefore yield `VALID + UNTRUSTED`. A valid signature without
policy yields `VALID + UNKNOWN`. Structurally invalid SSHSIG or a completed
OpenSSH incorrect-signature diagnostic yields `INVALID`. Unsupported envelope
algorithms yield `NOT_ASSESSED`; backend failures yield `UNKNOWN`.
Trust separately requires an ACTIVE record with exactly the envelope key ID and
SSHSIG public key. A trusted candidate also runs `ssh-keygen -Y verify` against
an explicit allowed-signers file containing only that key, policy principal and
namespace. Any backend refusal at this step yields `UNKNOWN`, not accepted trust.

Protocol `verify()` returns the existing typed VALID result only for real
mathematical validity plus trusted key/principal/purpose binding. Unknown,
revoked and mismatched-key signers retain `KEY_NOT_TRUSTED` denial. An invalid
signature may still name an independently trusted policy key; this does not
accept the checkpoint. Other failures remain sanitized adapter reasons.
The unchanged core only preserves `KEY_NOT_TRUSTED` specially and otherwise
maps adapter rejection to its existing `SIGNATURE_INVALID`; callers needing
the mathematics-versus-backend distinction must inspect the sidecar. A core
rejection is not by itself proof of mathematical invalidity.

Verification grants no authorization, effect execution, journal mutation,
retry eligibility, UNKNOWN clearing or reconciliation. Signing authenticates
the signed bytes, not unobserved effects, process authorship or complete history.

## Static lifecycle and failure boundary

Rotation uses different key IDs and a newly constructed verifier with an
explicit replacement policy snapshot. The unchanged core enforces increasing
sequence, previous-checkpoint linkage and its existing timestamp ordering.
Historical key A remains verifiable only if the selected policy explicitly
retains A as ACTIVE. Removing or marking A REVOKED denies it irrespective of a
caller-supplied old timestamp. This implementation does not prove when a
signature was generated. Supplying an older ACTIVE policy can restore acceptance:
policy version is configuration identity, not rollback prevention. No automatic
refresh, watcher, hot reload, custody operation or revocation service is supplied.

Darwin and Linux POSIX are the intended backend platforms; successful actual
capability tests are required for each. Other platforms return
`BACKEND_UNSUPPORTED`. Inputs are nonempty bytes at most 8192 bytes. The subprocess
has explicit argv, no shell, no inherited HOME, agent, askpass, display or
credential environment, no controlling terminal and a 5-second default timeout
(explicitly configurable up to 30 seconds). Combined stdout/stderr is bounded
while being read (8192 bytes default, maximum 65536), using nonblocking pipes.
Backend diagnostics, private bytes and signing handle paths are never included
in adapter results or exceptions. No backend success is inferred from a skip.

Timeout/output/failure paths kill the original process group even when its
leader already exited, and bound direct-child reap to one second. Private
temporary directories are 0700 and files 0600; all cleanup is attempted on both
success and error. Close, termination/reap or removal uncertainty produces
`CLEANUP_UNKNOWN` and an UNKNOWN assessment, overriding otherwise successful
verification. This is bounded local cleanup, not a guarantee against malicious
processes escaping their session, hostile kernels or power failure. A signing
failure raises a sanitized `BackendFailure`; the core keeps its existing
`SIGNER_FAILED` behavior and returns no checkpoint.

## Evidence and limits

`tests/test_checkpoint_crypto.py` requires `/usr/bin/ssh-keygen`; real cases fail
rather than skip when it is absent. Temporary synthetic Ed25519 keys test core
acceptance/history and a direct OpenSSH cross-check, unknown/self-carried key,
key-ID substitution, all canonical fields, strict encoding/version/namespace,
policy schema and identity ambiguity, static rotation/revocation, backend
absence/failure/timeout/output and cleanup uncertainty, encrypted/unsupported
keys, import inactivity and agent isolation. The direct cross-check uses the
same OpenSSH implementation and is not an independent cryptographic audit.

Local real integration: Darwin macOS 26.6.2 arm64, explicit `/usr/bin/ssh-keygen`,
198-byte SSHSIG; preflight correct/tampered payload and wrong namespace cases
passed. Companion `/usr/bin/ssh -V` reported OpenSSH_10.3p1 / LibreSSL 3.3.6;
this is package version provenance, not ssh-keygen's own version output.
Preflight ssh-keygen SHA256:
`0d8b8fb52762fa19431b40e8b75cd00b045f10bf206fd67f0598e09bfaad77d0`.
Linux real integration, final-candidate CI and independent reviews are separate
pending gates. Local formal remains `BLOCKED_MISSING_DEPENDENCIES`; schema
integration and controlled formal evidence must be reported separately.

H1–H3 durable-before-effect, failed-barrier denial, restart UNKNOWN, material
retry barrier, H2 lifecycle exclusion, reconciliation authority, observer
session/gap limits and H3 process-authorship `NOT_PROVEN` remain unchanged.
G03/G05 stay `PARTIALLY_IMPLEMENTED`. No exactly-once, cross-journal atomicity,
tamper-proof storage, independent anchor or production hardening claim is added.
H5–H9 are not started. Merge, tag, release, deployment and client activation
are outside this delivery; production hardening is `NOT_COMPLETE`.
