# Trusted Local Runtime Binding — Phase 2A

Status: **EXPERIMENTAL / SAME_PROCESS**. Explicit trusted-host construction only.
Core packaging does not activate capabilities. Import does not register adapters,
run a process, change environment, access a network or start a daemon.

## Authority and payload lifecycle

The trusted controller creates an immutable `RuntimePayload`, computes its
canonical digest, and binds that digest to the action ID **before authorization**.
`RuntimeBinding.execute` checks this previously approved binding and action ID;
it cannot create approval by recomputing the incoming payload's digest.
Payload shape must match the action class. There is no arbitrary metadata bag.

The binding reuses `ActionRequest`, policy, authorization, `CapabilityBroker`,
`InMemorySecurityJournal` and `evaluate_and_execute`. Neither authorization without
a registered capability nor a capability without authorization permits execution.
Only the binding is the governed public execution route. Adapter objects are
trusted internal components: calling an adapter directly is outside the RSE
boundary, not an alternate authorized workflow.

## Filesystem boundary

The host explicitly supplies a trusted workspace root. There is no home, current
directory or repository discovery. Only regular files are supported. Directories,
FIFOs, sockets, devices and symlink involvement are rejected. No recursive deletion.
Reads and writes are capped at 8 MiB each, configurable downward only.

Containment combines component-aware paths with directory descriptors,
`O_NOFOLLOW` and file identity/type checks. Unsupported required primitives return
`PLATFORM_UNSUPPORTED`; there is no check-then-ordinary-open fallback. These controls
reduce TOCTOU risk but do not establish universal race-free containment against
hostile concurrent filesystem mutation on every platform or filesystem.

- CREATE requires an absent target and exclusive creation; it never overwrites.
- WRITE requires an existing regular file; it does not create a missing target.
- READ returns bounded bytes through the trusted local result, not the chain.
- DELETE removes one regular file, never a directory tree.
- MOVE stays within the same approved root and refuses an existing destination.

An operation whose write, close, fsync or namespace result may have taken effect
is UNKNOWN, not a clean failure. Read-only reconciliation may establish applied
or not applied from recorded evidence; ambiguity stays unknown.

## Process boundary

The trusted host supplies an absolute executable allowlist, a workspace root and
a bounded environment. No executable lookup through PATH. No shell command string,
shell interpreter, download/package/cloud/service tool authorization shortcut.
Execution uses an argv sequence with `shell=False` and contained cwd.
Ambient environment is not inherited; overrides are explicitly allowlisted.

The POSIX implementation requires directory descriptors, no-follow opens,
`fchdir`, descriptor inheritance and process-group termination. It uses a fixed
isolated Python launcher (`-I -S`) to enter the already-open directory and replace
itself with the pinned target via `execve`; it does not interpret user shell code.
This avoids resolving cwd again through a possibly replaced pathname. The
launcher is an internal trusted boundary, not an additional public capability.
Unsupported primitives fail closed; Windows support is not claimed.
The status handshake is bounded adapter evidence, not independent proof against
arbitrary host interference. Missing acknowledgements remain uncertain. The
launcher itself receives an empty environment; target environment is applied only
at `execve`. Target argv and environment are carried in local launcher arguments,
so do not put secrets in them or claim process-list secrecy.

Default timeout is 30 seconds; the maximum is 300 seconds. Stdout and stderr are
each capped at 1 MiB with truncation reported. Timeout after start is UNKNOWN even
after termination: the child may already have produced effects. Nonzero exit is
not proof of no effects. A start event means confirmed launch; an exit event means
confirmed exit, never presumed termination.

Once the launcher process has been created, status-read, selector or cleanup
errors remain UNKNOWN unless the handshake proves the target never started.
An empty event list alone is not evidence of no effect; retry remains blocked
even if a start event could not be recorded.

**Process allowlisting is not process containment.** Child-internal file, network,
credential or descendant activity is not independently observed. Tests use trusted
controlled fixtures, not arbitrary hostile binaries. Parent socket guards do not
prove child network containment. Trace coverage must retain this limitation.

## Local Git boundary

Only an explicitly supplied repository and Git executable are used. Staging
accepts exact paths: no `.`/`--all`/`-A`, globs or directory-wide staging. Commit is
a separately authorized action; staging does not authorize it. Messages are
bounded to 16 KiB. A known commit returns its SHA as evidence.

The trusted controller must capture the staged tree object ID and current parent
**before authorization**, and supply `expected_git_tree` and
`expected_git_parent` in the immutable payload alongside the message. Both fields
are covered by its canonical digest. Initial commits use the single parent
sentinel `UNBORN`. Execution never generates its own expected values.

After validating repository configuration and operation state, the adapter
re-reads HEAD and the staged tree as late as practical before commit. Changed
tree or parent is rejected with `GIT_TREE_BINDING_MISMATCH` or
`GIT_PARENT_BINDING_MISMATCH`, without invoking commit, restaging or resetting.
No staged changes is rejected with `GIT_NOTHING_TO_COMMIT`. Amend, merge commits,
and ambient merge/rebase/cherry-pick/revert/bisect or unmerged-index state are not
supported. Unsupported operation state returns `UNSUPPORTED_GIT_STATE`.
Object IDs are validated against the repository's recognized object format
(SHA-1 or SHA-256), not assumed to be 40 characters.

Success requires reading the resulting commit object and matching its exact
tree, parent list and message to the approved payload. A possible commit whose
result cannot be established remains UNKNOWN and cannot be retried blindly.
The binding's journal serializes calls within that controller. It does **not**
lock out external Git/index writers across authorization and execution; Git's
per-command locks do not close that interval or provide hostile multi-process
exclusion. Concurrent host mutation remains outside this bounded guarantee.

Hooks and signing are disabled. Unsafe filters/helper configuration fails closed;
promisor and remote upload/receive helper configuration is rejected before object
reads. Every Git subprocess uses an empty transport allowlist (including local
file transport), disables lazy fetch, and sets protocol denial. Lazy-fetch
environment support alone is not relied upon. A precheck launch/capture whose
effects are uncertain returns UNKNOWN and blocks retry, even before add/commit.
pager/editor, interactive credential helpers and aliases must not become alternate
execution routes. There is no reset, clean, fetch, pull, push or remote adapter.
An uncertain commit is reconciled using read-only evidence, never retried blindly.
Git staging and process effects have no deterministic reconciler in this phase;
their unresolved outcomes remain `STILL_UNKNOWN`.

## Evidence and recovery

RSE records ATTEMPTED before effects. Adapter-observed CET events describe confirmed
adapter boundaries, not authorization intent and not host-observed syscalls.
Declared/observed differences remain visible as divergences. The Security Chain
stores receipt/event/evidence digests, not raw payloads, file bytes, stdout, stderr
or commit messages. No provider token usage or checkpoint signature is fabricated.

Failure to seal evidence after a possible effect is a security-boundary failure
with UNKNOWN outcome and blocked retry. Inspect the receipt, operation evidence
and journal, then use read-only reconciliation. A new authorization does not erase
an unresolved old effect. Do not recreate an empty journal to bypass the block.
Retain the original binding as well as its journal: some reconciliation decisions
also depend on the binding's retained pre-effect evidence.

The generic journal is memory-only. Process death loses its retry/reconciliation
state; this phase does not offer crash-durable execution or exactly-once effects
across restarts. Recover outside automatic retry under a separate trusted procedure.

## Non-goals and public claims

No real network adapter, secret store, package install, service control, Git push,
GitHub write, PR/merge/release, deployment, Paperclip, Codex runtime hook, Local
Compute integration, kernel enforcement, OS sandbox, network containment or Host
Observer. Development-time PR creation is not a runtime capability.
Phase 2B and later require separate Design Authority approval.
