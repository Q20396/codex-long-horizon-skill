# H2: bounded cross-process ownership

Experimental opt-in coordination for cooperating trusted controllers on one host.
This is not a daemon, lease, distributed lock, effect adapter, or new ledger.
H2 acceptance remains pending exact-SHA Linux CI and independent review. H3–H9
are not started. Architecture remains COMPLETE — EXPERIMENTAL; production
hardening remains NOT_COMPLETE.

## Host contract and entrypoints

The trusted host supplies a canonical absolute directory (resolve `/tmp` to
`/private/tmp` on Darwin), the durable journal path and storage ID, chain identity,
current authority, and payload commitments. Proposals cannot select ownership.
The directory must already exist, be owned by the effective deployment user, and
exclude group/other writes. Use a private 0700 directory. Protected files must be
immediate children, private regular files with one link on the same filesystem.
No symlink components, hardlink aliases, nested storage, or separate domain label
can choose a different lock for those files.

Acquire `rse.CrossProcessOwner(directory)` **before** opening either persistent
store. Pass the same live object as `owner=` to `DurableSecurityJournal`,
`JsonlSecurityChain`, `AgentRuntimeBridge`, and `HostObservationIngestor`.
Close the owner explicitly only after all work completes; context operations
reject premature close with `OWNERSHIP_BUSY`. Retain journal/chain objects for
that owner lifecycle; a successor must acquire ownership and construct fresh
objects to reload persisted state.

Coordinated execution and reconciliation use the Bridge. It checks the exact
journal/chain/owner combination and opens an action-specific scope around binding
validation, journal admission, the persistence barrier, adapter execution, outcome
recording, and chain/CET bookkeeping. Direct local/remote binding or RSE execution
with a coordinated journal outside that scope is denied before its adapter runs.
This restriction is deliberate: the existing binding APIs do not receive enough
information to establish ownership composition themselves. The scope matches the
actual bound action, not a global permissive flag; nested scopes are rejected.

Legacy in-memory and H1-only APIs retain their old guarantees. They do not provide
cross-controller coordination. The fixed `.h2-owner` marker makes reopening a
coordinated directory without `owner=` fail closed, including after clean close.
Never mix previously opened legacy writers with coordinated controllers.

## Lock and storage identity

The primitive is standard-library `fcntl.flock(LOCK_EX | LOCK_NB)` on one fixed
`.h2-owner` regular file per directory. Ownership is held until close/process
death, not just during append. Contention returns `OWNERSHIP_CONTENDED`; other
acquisition failures return fixed non-admission errors. There are no retries,
time leases, PID-liveness decisions, or lock deletion/recreation.

Each protected operation checks owner PID/liveness, directory identity, lock
identity, and all bound storage device/inode identities, link counts and modes.
Journal content is additionally checked against its loaded snapshot. Chain
append verifies the current canonical chain and sequence while holding the same
owner. Ownership does not authenticate historical records or prove an effect did
not happen. File-content rollback, complete store replacement after downtime,
malicious controllers, privileged interference, and external FD manipulation are
not defended. The trusted host must preserve the directory, lock and storage
lifecycles and never remove the lock, even when unlocked.

Darwin accepts local APFS after `fstatfs64` verifies both APFS and MNT_LOCAL.
The ctypes layout follows Apple's public 64-bit statfs ABI in
[XNU mount.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/mount.h).
Linux reads the kernel mount table and accepts only ext4, XFS, Btrfs, or tmpfs;
ambiguous escaped mount paths are rejected. Filesystem identification is an
admission restriction, not power-loss certification. Windows, NFS, SMB, FUSE,
overlay filesystems, and distributed hosts are unsupported and fail closed.

## Fork, exec, and controlled effects

Owner descriptors are non-inheritable across exec. A single at-fork callback
closes inherited descriptors in the child without issuing LOCK_UN, invalidating
all inherited owners. Weak registration does not retain dead owners. A fork
barrier covers construction before opening FDs through acquisition, avoiding an
unregistered-descriptor inheritance window. PID checks precede mutex access.

The supported process boundary is Python's `os.fork` with at-fork callbacks and
standard controlled subprocess exec with close-fds behavior. Raw foreign-library
fork/clone bypasses, deliberate descriptor duplication/passing, and hostile
controller code are outside this cooperative API contract. Do not pass owner FDs
to effects. Parent death may leave an effect child running; acquisition by a
successor does not clear its durable UNKNOWN barrier.

## Recovery and reconciliation

H1 write/fsync-before-effect ordering and fail-closed replay remain in force.
Crashes before the first PROPOSED record leave no admitted attempt. AUTHORIZED,
ATTEMPTED, or unresolved records remain uncertain, including a crash before the
adapter actually starts. Never infer NOT_APPLIED from death or elapsed time.
In coordinated mode, completed as well as unresolved Bridge material identities
block changing proposal/action IDs. The existing semantic material definition is
unchanged; arbitrary effect equivalence is not inferred.

Reconciliation uses the same owner and current policy/authorization. Insufficient
evidence stays UNKNOWN. After trusted RECONCILED_NOT_APPLIED, a subsequent attempt
requires a new authorization reference as well as the existing current authority,
expiry, payload and capability checks. Changing action IDs cannot reuse the
previous authorization for the same material. A changed reference is a trusted
host commitment, not authentication of a new human decision by Python.

The execution journal and Security Chain remain separate. Chain failure after an
effect is reported as uncertain, never success. There is no cross-log atomic
commit, exactly-once claim, or automatic repair/rotation.

## Observer handoff and remaining G03 gap

Coordinated ingestion requires an explicit new `session_id`, the same owner and
JSONL chain, and an installation-scoped authorized runtime/owner actor. Restricted
project/task-only actors cannot create this installation-scoped session claim.
The existing SECURITY_ALERT record format stores hashed session/observation
claims; these are coordination facts, not invented host sensor events or execution
receipts. A session claim is synchronized before ingestion. Reusing any recorded
session for that observer is rejected, even after a fresh interpreter starts.
Observation IDs are likewise consumed durably before CET publication; clearing
in-memory dedupe cannot authorize old IDs under a new session.

Every new session explicitly records `H2_OBSERVER_HANDOFF_GAP`. Its first event
reports SEQUENCE_GAP; coverage remains PARTIAL (or UNKNOWN when supplied as such),
never inferred continuous. Old owners, old sessions, mismatched owners, and
already-consumed observation IDs cannot write. A crash after a claim but before
CET/trace publication conservatively consumes the ID and may leave a gap.

G03 remains only partially addressed: no native registrations, trace contents,
original local evidence, prior sensor coverage, or continuous observation stream
are recovered. No durable observer service was introduced. Chain claim replay
depends on preserving the existing trusted chain; suffix rollback or whole-chain
replacement cannot establish fresh session eligibility. A bounded new-session
handoff is not a claim that the broader durable-observation gap is closed.

## Reproducible verification

`python3 -m unittest discover -s tests -p test_cross_process_coordination.py -v`
uses synthetic local effects and independent Python interpreters with pipe
synchronization, not sleep-based races or mock lock success. It covers real
Bridge/ingestion contention, unchanged contender storage, fork/exec and child
lifetimes, five abrupt crash windows and fresh recovery, ID changes, reconciliation,
chain sequencing, and observer handoff. Injected failure tests separately cover
fsync/acquisition errors. These injections are not crash evidence.

Local execution evidence: Darwin arm64/APFS, Python 3.9.6. Linux runtime/CI evidence
is pending and must be reported separately. Other platforms/storage are
NOT_RUN_PLATFORM_RESTRICTED. Formal locked-environment evidence must not be
substituted with local unlocked dependencies. Independent reviewer verdicts and
exact-final-SHA check-skill/formal-schema-gate CI remain delivery gates.
