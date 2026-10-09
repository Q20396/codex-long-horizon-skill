# H5 bounded GitHub anchor experiment

DELIVERY: REPOSITORY_ONLY_EXPERIMENTAL

REAL EXTERNAL PUBLICATION: NOT_VALIDATED  
INDEPENDENT RETENTION: NOT_VALIDATED  
REAL FRESHNESS: NOT_VALIDATED  
G08 / G09: PARTIALLY_IMPLEMENTED  
H5 FULL ACCEPTANCE: NOT_COMPLETE  
PRODUCTION HARDENING: NOT_COMPLETE

The root `scripts/checkpoint_anchor.py` is inactive on import and outside the
installed core. It supplies one fixed GitHub REST adapter, a private immutable
recovery capsule, one immutable version observation, and an actual GET reader.
It does not enroll keys, authorize action execution/retry, clear action UNKNOWN,
call reconciliation, modify RSE or publish an anchor by default.

## Explicit trusted inputs

The host supplies `GitHubTarget`: fixed `https://api.github.com`, numeric
repository ID, exact owner/name, branch and path prefix. Strict ASCII path
components reject dot segments, percent escapes, empty components and path
escape; at most eight final path components are traversed. The final path is
`<prefix>/<request_id>.json`.

`AnchorRequest` supplies stable request ID, exact canonical signed checkpoint
bytes, chain/install IDs, SHA256 checkpoint digest, sequence, key ID and immutable
public policy reference. Each operation validates canonical bytes, every binding
and H4 signature/trust through the explicit `OpenSSHCheckpointVerifier`. Its
actual `policy.reference` must equal the supplied reference. Historical capsules
are structurally validated without applying today's policy to unrelated old
requests. H4 policy anti-rollback remains NOT_IMPLEMENTED.

Write/read transports are separately required. `GitHubHTTPS` performs real HTTPS
I/O with verified TLS, no redirect/retry/proxy/netrc/environment credential lookup,
and optional explicitly supplied Authorization. Credentials travel through a
private worker pipe, never capsules or diagnostics. Injected transports must be
marked `SYNTHETIC_SERVICE`; only the exact bundled `GitHubHTTPS` implementation
may carry the `REAL_HTTPS_IO` label. A transport name/type still does not establish
an independent trust domain or authorization to use a real account.

## Ownership, persistence and duplicate admission

The host must provide an existing private 0700 local directory with protected
ancestry. `CrossProcessOwner` supplies the existing nonblocking cooperative flock
protocol, supporting its existing Darwin APFS and Linux local-filesystem matrix.
All capsule/observation files are immediate children on the same filesystem.
No new lock protocol, queue or append-only ledger is introduced.

One ownership lifetime covers bounded scan, duplicate comparison, exclusive
capsule creation, complete write, file fsync, directory fsync, reread and all
transport calls. Files use no-follow/exclusive opens, 0600 mode, regular/private
owner/single-link checks and descriptor/path identity binding before reads and
writes. Every persistence failure before transport yields zero transport calls.
Partial files are retained and fail closed; no repair/delete/rebuild restores
write eligibility. Ownership is released and descriptors are closed on return.

`OWNERSHIP_CONTENDED` and `OWNERSHIP_ACQUISITION_FAILED` are explicit zero-send
refusals with publication OUTCOME_UNKNOWN; neither authorizes automatic retry.
Synthetic concurrent tests on this macOS/APFS host observed ENOENT while the
existing owner opened its lock for creation, before flock admission. That is a
bounded platform diagnostic, not a general explanation for all filesystems.
After ownership becomes available, an existing capsule still permits only GET.

The immutable `<SHA256(request_id)>.capsule` holds request/checkpoint bytes and
nonsecret target/policy identity; its initial version is UNKNOWN by absence of
version evidence. At most one exclusive immutable `.observation` may bind the
capsule digest, request, checkpoint, target, commit, blob and evidence kind
(`PROVIDER_RECEIPT` or `ACTUAL_GET`). Observation durability uses the same file/
directory fsync and reread requirements. Orphan, corrupt, replaced, oversized or
ambiguous files fail closed. Initial capsules never change.

Once a capsule exists, every subsequent same-ID invocation is GET-only, even
after a crash before send. Different binding with the same ID is CONFLICT. A new
ID cannot bypass an existing capsule for the same checkpoint digest plus complete
configured target (origin/repository ID/name/branch/prefix); this deliberately
conservative rule also suppresses duplicates after a resolved observation.
The request-derived filename is excluded from that duplicate key. `read()` with
no capsule returns CAPSULE_MISSING/OUTCOME_UNKNOWN with zero creates; missing
local storage does not prove historical absence. Deleting/rolling back local
storage defeats local duplicate history; global duplicate protection is absent.

## Provider contract and independent GET

Official documentation inspected 2026-10-09:

- [Contents](https://docs.github.com/en/rest/repos/contents): PUT creates with
  message/base64 content/explicit branch; this adapter omits `sha`, which updates
  require. Only 201 confirms creation; 200 does not. Contents write permissions
  are broader than create-only permissions. Contents GET may follow symlinks.
- [Refs](https://docs.github.com/en/rest/git/refs): exact singular branch-ref GET
  returns commit identity; a branch is mutable.
- [Commits](https://docs.github.com/en/rest/git/commits) and
  [trees](https://docs.github.com/en/rest/git/trees): exact commit/tree GET binds
  the checkpoint path to a regular blob entry. Nonrecursive component traversal
  rejects truncated, oversized, duplicate or malformed entries and symlinks.
- [Blobs](https://docs.github.com/en/rest/git/blobs): exact blob GET supplies
  size/base64/SHA; the adapter verifies Git blob SHA1 and exact canonical bytes.
- [Repositories](https://docs.github.com/en/rest/repos/repos): every invocation's
  metadata GET checks numeric ID and exact full_name before publication/readback.

The fixed API version is `2026-03-10`. The sole create body contains message,
content and branch. No update/delete path or automatic retry exists. Response
path/blob/commit identities must match the configured request. Reader URLs are
constructed at the fixed origin; provider/caller URL fields are never followed.

The reader actually fetches repository identity, exact branch ref, exact commit,
bounded tree entries and exact blob bytes. A reliable 201 receipt may pin a
version but never marks READBACK_OBSERVED. Without a reliable receipt, a pin is
persisted only after all GET bytes/checkpoint/repository/path checks pass, before
returning accepted readback. A different commit/blob rejects even identical bytes.
Before the first reliable pin, replacement cannot be distinguished from the
unknown original version; no historical version is inferred. Same-provider reads
are bounded observations, not an atomic provider snapshot or independent retention.

## Conservative results and limits

`AnchorResult` separates send state, PUBLICATION_CONFIRMED_BY_PROVIDER,
READBACK_OBSERVED, independent retention and freshness. Sending may have happened
even when a timeout/error/bad receipt prevents confirmation. Unknown outcomes stay
OUTCOME_UNKNOWN, including 401/403/unavailable/malformed/overlimit responses. 404
or a missing tree entry yields NOT_OBSERVED, never proof of non-publication.
Identity/bytes/version mismatches return BINDING_MISMATCH while retaining existing
reliable publication evidence. Bounded diagnostics contain no response bodies,
backend stderr, key paths or credentials.

Freshness is UNKNOWN without trusted inputs. Optional trusted `(sequence,
chain_head_hash)` and clock/max-age judge FRESH_RELATIVE_TO_TRUSTED_INPUTS or STALE.
Freshness never follows caller timestamps, branch names or latest responses, and
does not grant write eligibility or assert globally newest history.

Bounds: 8192 checkpoint bytes, 16384 bytes per state file, 256 directory entries
plus the owner lock, 32768 response bytes, 256 entries per tree, eight path
components, 30 seconds maximum per transport request (default five). The real
HTTPS worker has an outer wall deadline covering DNS/import/socket operations,
65536 combined output bytes, bounded cleanup and process-group termination on
failure even after leader exit. A timeout cannot recall an already sent request.
Injected transports remain trusted synthetic test code; the host must preserve
their bounded-call contract. Filesystem fsync requests durability but these tests
do not establish hardware power-loss behavior or hostile-host isolation.

## Synthetic verification and remaining real gates

`tests/test_checkpoint_anchor.py` uses a localhost stored-byte HTTP service,
temporary synthetic Ed25519 keys, actual OpenSSH verification and fresh Python
interpreters. It covers one-create/GET recovery; receipt/readback separation;
checkpoint/target/path/blob/version mutations; stale/unknown freshness; dropped
reply; duplicate admission; real process kills in partial/durable/send/receipt/
observation windows; short writes/fsync/ownership/replacement failures; HTTP
diagnostics/limits; no import effects or ambient credentials; unchanged unresolved
RSE history; and bounded worker output/deadline/resource cleanup. Every injected
transport is SYNTHETIC_SERVICE. None of this validates real GitHub publication,
independent retention or actual freshness.

Real validation needs separate approval for the exact independent repository/
owner, account permission, retainer/trust domain, trusted expected-head/clock
source, retention duration, fees and cleanup operations. No merge, activation,
release or H6–H9 work is performed by this slice.
