# Local Case Evidence Provider

Status: sandbox-only, explicit-only, declared-disabled interface.

This is a clean-room contract for a future local provider. It contains no
Dropbox, Gmail, Outlook, Hotmail, or Google Drive implementation, no OAuth
client, no account access, no background process, and no encryption code. It
does not authorize installation or a connector run.

## Synthetic Pilot Boundary

The repository pilot is a fixture-only contract exercise. Its adapter identity
is `synthetic-local-read-only-adapter`; it reads only synthetic JSON fixtures
already in this repository. It performs no network request, account connection,
credential lookup, decryption, persistence, connector emulation, or customer
data processing. A green pilot proves only that the static contracts and
customer outcome shape agree.

The synthetic run record uses `connector_type: synthetic-mailbox` and records a
future target such as Gmail or Google Drive separately. This prevents a fixture
from claiming that a real provider was connected or validated.

The pilot record, both checkpoints, and the customer outcome are recursively
closed against unknown fields. Runtime aliases, automatic-approval fields, and
other undeclared nested structures fail static validation. Type failures return
`FIELD_TYPE_INVALID` and stop semantic traversal of the malformed branch.

## Purpose

The future provider may download an explicitly approved, read-only source
subset into a locally encrypted case store, build a source/version/hash/locator
ledger, extract provenance-bound observations, and retain an incremental
cursor. LHE Core receives only redacted, structured evidence references and
never raw customer material.

If the active model or host sends prompt content to a remote service, raw
customer material must not be placed in its context. Sensitive extraction must
use an independently reviewed local deterministic parser or local model.

## State Machine

`DISCONNECTED -> APPROVAL_PENDING -> CONNECTED_ONE_RUN -> ENUMERATING ->
FETCHING_APPROVED -> LOCAL_VERIFYING -> INDEXED -> CHECKPOINTED -> DISCONNECTED`

Failures enter `BLOCKED` or `QUARANTINED`. Stale cursors, prompt injection,
active content, unexpected scopes, provider errors, hash mismatches, legal-hold
uncertainty, and retention conflicts fail closed. There is no automatic
reconnection or background synchronization.

## Evidence And Storage

The local ledger binds each item to connector type, provider object ID, provider
version, immutable content hash, source locator, source and retrieval times,
extraction method/version, and resulting FACT/INFERENCE/UNKNOWN claims.

Raw snapshots are disabled by default. A future implementation may retain a raw
snapshot only in the encrypted local case store after explicit file-level and
retention approval. Repositories, prompts, logs, summaries, model memory,
telemetry, and remote stores must not contain raw or sensitive content.

Case encryption requires a per-case data-encryption key wrapped by an OS
credential-store key. Tokens and refresh credentials remain in OS credential
storage and never appear in repository files, prompts, receipts, logs, or
summaries.

## Incremental Reconnection

The encrypted local index remains useful after connectors are disconnected. A
fresh delta requires a new per-connector, per-run approval and reconnection.
Provider cursors are hints, not authority. An expired or invalid cursor triggers
a bounded metadata rescan and content-hash deduplication, not silent acceptance
or an unbounded raw-content rescan.

## Retention, Deletion, Export, And Legal Hold

Retention, deletion, raw snapshot preservation, and export are separate
customer decisions. An export requires an explicit destination, redaction
review, encrypted package, and manifest. A legal hold or preservation duty
requires counsel direction; LHE and the provider must not decide it.

Audit records are append-only and tamper-evident through hash chaining or a
locally protected MAC key. They are operational evidence, not a claim of
forensic authenticity, admissibility, or independent legal certification.

## Static Limits

The schema and synthetic fixtures can verify the enumerated structural
boundaries, supported schema-keyword closure, and fail-closed reason codes.
They cannot detect arbitrary prose claims or prove encryption, Keychain isolation,
connector API behavior, malware containment, deletion, legal compliance,
runtime permissions, host isolation, or customer authorization.
