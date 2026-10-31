# Scoped Linux owned-child file observer — preparation only

Status: native NOT_RUN. Synthetic checks do not establish Linux runtime capability.
Baseline: 8333bb2f62df71dbc161d8465ccf9278963fecaa. DTrace diagnostics remain sealed.

## Selection

Three candidates were considered. macOS EndpointSecurity descendants client removes
root/TCC requirements for owned descendants, but still needs Apple's ES entitlement;
that entitlement is not presently established. Its open flags do not prove completed
reads. macOS eslogger requires root/FDA, lacks a source PID/directory allowlist and is
not a stable API. Neither satisfies the present permission/scope constraints.
Linux x86_64 ptrace observes the fixed owned helper's syscall entries and returns
without root, package installation or file-content collection, conditional on host
policy. Official support is not runtime verification. See the independent feasibility
report in the project evidence directory.

## Frozen minimal matrix

One new non-sensitive directory, one regular synthetic fixture and one absent leaf.
The fixed helper performs open/read-one-byte/close, open/write-one-byte/close, and an
absent-file open. Fourteen paired scoped events are required. Open flags mean intent;
positive read/write return counts confirm only returned/transferred byte counts, not
content identity, durability, user comprehension or exfiltration. Failed ENOENT open
is a negative case. Zero-byte operations cannot satisfy the positive matrix.

Missing events, malformed syscall records, unbound FD, unexpected path, unsupported
file operation, extra process/thread, changed mount namespace, identity change,
timeout, signal interruption or unresolved cleanup fail closed. Only one initial
pre-scope unmatched syscall exit may align the SIGSTOP startup; no startup coverage
is asserted. Exit status zero or an empty directory never substitutes for events.

## Identity and limits

Identity is PID plus /proc start ticks, original unreaped Popen and pidfd. Each stop
checks one thread and the same mount namespace. Tracked FD generations are bound by
owned /proc FD readlink/stat to the held fixture device/inode. Paths are fixed
absolute names with O_NOFOLLOW. No read/write buffers are copied; only bounded path
arguments for open are read. Observer stop wall/monotonic timestamps are not atomic
syscall execution timestamps. A cooperative, non-mutating mount/filesystem domain,
single waiter, no external reaper and no concurrent FD manipulation are required;
stop status alone is not proof of instantaneous identity.

Only the new fixed helper is supported. Arbitrary applications, shared FD tables,
file-backed mmap, vector/direct IO, clones, namespace changes and general descendants
are outside coverage and rejected where observed. This is not all-disk monitoring,
leak prevention, a production sensor or cloud-provider internal observation.

## Preparation and future execution

The four new files are the observer, its synthetic test, this document and the
single-use workflow. No product or original DTrace file is changed. The synthetic
tests use mocks/owned fixtures only; running the test file does not start ptrace.

Native entry is disabled by default. The authorization argument is a gate, not a
technical replay-proof permit; the project ledger supplies one-shot dispatch control.
Do not invoke it until a fresh exact-manifest authorization is granted.

Proposed future route: first push a signed four-file commit on
codex/linux-owned-observer-once-20261031 to the public
Q20396/codex-long-horizon-skill repository, without merge or PR. A single standard
Ubuntu 24.04 x64 job (five-minute cap) checks its parent baseline, four-file scope,
source hashes, Python 3.12.3, nonroot status, Yama 0/1 and Seccomp 0 before one run.
No install, sudo, artifact, cache or paid storage. Exact runtime availability remains
unverified; a changed runtime/policy stops rather than substituting an environment.
Before push, verify public/free standard-runner billing and that other workflows
cannot trigger. Zero cost is conditional on these preconditions, not guaranteed by
this local preparation. The workflow cannot be pushed under the present authority.

Observation software limit: eight seconds; native total target: thirty seconds,
including a five-second cleanup reserve. Blocking host operations and final report
write lack a hard upper bound. Own-child SIGKILL is permitted only through a bound
pidfd, or original unreaped Popen before pidfd acquisition; no process group or
arbitrary PID kill. EXITKILL and helper parent-death SIGKILL reduce orphan risk but
are not proof of cleanup. Unconfirmed exit/FD close remains UNKNOWN/NOT_PASS.

The future permit is consumed on first workflow trigger, even if preflight fails.
No rerun, second push, alternate mechanism or automatic retry. Scope and budget
changes require separate authorization. Existing permits stay consumed.

## Evidence

The native report is created exclusively in the new fixture directory, at most
16 KiB. CI emits a complete bounded JSON packet (32 KiB) with source/workflow hashes,
execution SHA, runner/run identity, synthetic checks, actual native events and report
length/SHA256, followed by an END marker. No artifact/cache upload is configured.
After a future run, read the CI log once, validate packet length/hash/END marker and
save it to the evidence domain. Missing/truncated logs or unmatched identity are
incomplete evidence, not PASS. CI logs do transmit the synthetic non-secret evidence;
that external action needs the future explicit run authorization.

Only an actual successful bounded run plus independent evidence review can establish
selected-matrix acceptance. No native acceptance or project completion is claimed.
