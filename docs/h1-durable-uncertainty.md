# H1: bounded process-restart uncertainty

Experimental, opt-in, standard-library execution journal. This is not a new
authority, Security Chain, daemon, retry engine, or state machine. Existing
in-memory interfaces remain unchanged. Live and durable journals share one pure
RSE transition validator; invalid transitions are rejected in both. H2 cross-process
coordination is not implemented.

## Trusted host setup

The host supplies an explicit absolute path with no symlink components, a trusted
storage identity, current authorization, approved payload commitments, adapters,
and a separately owned Security Chain. The parent directory and its lifecycle must
be trusted. File permissions must exclude group/other access; hardlinks and symlinks
are rejected. Never accept a model-selected path or storage identity.

`rse.DurableSecurityJournal(path, storage_id=identity, create=True)` is ONLY for
genuinely new storage, established by the trusted host. It exclusively creates a
0600 file, writes a version/identity header, synchronizes it and its parent directory.
Never use create as an error-recovery fallback. A missing or empty file on recovery
is `DURABLE_STATE_UNTRUSTED`, not proof of non-execution.

Reopen with `rse.DurableSecurityJournal(path, storage_id=identity)` and pass this
same journal to the existing bindings. Reconstruct the Bridge normally. Supply
fresh trusted policy, authorization, context and previously approved payload
commitments; the journal does not restore authority or retain raw payloads.

## Ordering and records

The existing RSE path verifies policy, authorization and capability before writing
AUTHORIZED and ATTEMPTED. Payload prebinding remains in the existing bindings.
Every append completes write plus `os.fsync` before returning; only then can the
adapter run. A partial write or sync failure latches the journal instance closed.
No automatic repair or retry is performed.

Records contain sequence/hash continuity, existing JournalEntry fields, hashed
authorization reference, attempt sequence (the PROPOSED record sequence), and the
Bridge's existing material identity/payload digest when using that path. Raw
payloads, prompts, completions, credentials and caller identities are not stored.
Bounds are 16 MiB and 16384 total records including the header. Exhaustion fails
closed, without rotation or destructive compaction.

Recovery validates canonical encoding, identities, hashes, sequence, existing RSE
transitions and confirmed-success evidence references before returning a journal.
AUTHORIZED, ATTEMPTED and unresolved outcomes remain retry barriers. A different
proposal/action ID cannot bypass a recognized pending Bridge material identity.
Unknown equivalence is not invented. The Bridge restores an eligible original
action's pending reservation only for explicit reconciliation.

## Operator recovery

1. Establish that the previous trusted controller has terminated. Do not run two
   controllers against the same file. This implementation does not arbitrate owners.
2. Reopen the original storage with its original identity. Do not create a fresh
   file, discard history, or replace UNKNOWN with NOT_EXECUTED.
3. On `DURABLE_STATE_UNTRUSTED` or `JOURNAL_OR_BOUNDARY_FAILURE`, stop execution.
   Preserve evidence; do not edit, truncate or automatically repair the journal.
4. For pending actions, re-supply trusted original payload/context commitments and
   current authority, and use the existing explicit Bridge reconciliation path.
   Missing local evidence or ambiguous remote readback remains UNKNOWN. Model text
   or adapter success strings are not independent target reality.
5. Only trusted existing reconciliation results can resolve uncertainty. A
   RECONCILED_NOT_APPLIED outcome still requires full current authorization before
   any later execution. There is no automatic network reconciliation or retry.

## Evidence limits

- Single trusted controller, process termination and restart only. File replacement
  or content changes observed by a live journal fail closed. This is not atomic
  cross-process ownership; undetected concurrent writers are outside the supported
  model. No distributed deduplication or exactly-once effects are claimed.
- Partial final records and broken continuity are detected. Removing a complete
  suffix that leaves a valid prefix, restoring an old valid file, or replacing all
  storage cannot in general be detected without independent trusted history.
  Retaining ATTEMPTED but losing its outcome conservatively restores UNKNOWN.
  The host must preserve the trusted storage lifecycle; a valid header alone does
  not prove that previous effects never occurred.
- Local hashes detect corruption, not malicious rewrites. No tamper-proof or
  malicious-administrator protection is claimed.
- `fsync` and directory synchronization are required operations, not a verified
  universal power-loss guarantee. Platform/filesystem guarantees must be separately
  validated. Local testing: Darwin arm64, Python 3.9.6, temporary synthetic storage;
  filesystem power-loss behavior is unverified.
- The execution journal and Security Chain are separate. There is no cross-journal
  atomic transaction. A durable adapter outcome is not proof that all subsequent
  Security Chain / CET appends completed. Existing detected evidence failures still
  request reconciliation; a crash between journals may leave incomplete chain
  evidence. A valid journal does not establish independent target reality.
- Local formal validation remains BETA when the approved target environment is
  unavailable. No dependency substitution, framework, or H2 work is included.

Tests in `tests/test_durable_uncertainty.py` use synthetic storage and effects,
including `os._exit` in a child and a fresh interpreter that must block retry.
No real external accounts or destructive host tests are required.
