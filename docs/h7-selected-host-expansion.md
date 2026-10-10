# H7 selected host expansion: registered-PID PROCESS_EXIT

## Delivery and authority

REPOSITORY_ONLY_EXPERIMENTAL. Design Authority selected macOS kqueue
EVFILT_PROC / NOTE_EXIT on base
`b4e48f458a3070b489a1728e113e0e01390689c4` (2026-10-10).
This is not installed client capability, a daemon, global process discovery,
or full H7/platform coverage. G12 records only this selected increment.
H5/H6 FULL ACCEPTANCE and PRODUCTION HARDENING remain NOT_COMPLETE.
G03 remains PARTIALLY_IMPLEMENTED. H8–H9 are not started.

## Interface and evidence boundary

`scripts/host_observer_macos_exit.py` is an explicit repository entry point;
its caller supplies the existing skill scripts import path for `host_observer`.
Import does not start observation. `MacOSExitObserver(session_id)` validates
Darwin capabilities and opens one queue. `register(pid, action_id_ref=None)`
accepts an exact integer PID in 1..2^31-1 (not bool), an optional bounded
opaque reference, and at most 128 cumulative distinct registrations.
Registration uses NOTE_EXIT / EV_ONESHOT and is recorded only after native
registration succeeds. A consumed PID cannot be registered again in that
collector. The trusted caller must select and control the target; no PID scan
or target authorization is provided by this module.

`wait_for_exit(timeout)` accepts a finite 0..30 seconds and reads at most one
event. Only a native `select.kevent` with EVFILT_PROC, a registered PID and
NOTE_EXIT, without EV_ERROR, produces an observation. Wrong PID/filter/flag
produces none; invalid type/native error closes the collector and fails.
Sequence increments only on valid delivery, each registration at most once.
`close()` is idempotent and latches closed before cleanup. An ambiguous close
reports RESOURCE_STATE_UNKNOWN, never blindly retries a potentially reused
descriptor. Closed operations are rejected. Native exception text is suppressed.

The output reuses HostObservation: PROCESS_EXIT, PARTIAL, effect_digest=None,
the supplied action reference, short-session `ref:pid-N`, fresh observation ID
and independent `macos-kqueue-proc-exit` / `ref:macos-kqueue-evfilt-proc-note-exit`
source. It contains no exit code, argv, environment, file content or capability.
It proves only that the native mechanism reported the registered PID exiting.
PROCESS SUCCESS / AUTHORSHIP / ALL EFFECTS: NOT_PROVEN.
PID reuse and the trusted cooperative host remain limitations; PID is not a
durable process image identity. This is not an atomic/global snapshot.

None means NOT_OBSERVED / UNKNOWN, never proof of liveness, non-exit or no
effect. waitpid is used solely for controlled-test cleanup, not evidence.
No polling or synthetic fallback supplies observations.

## Ingestion and restart

The collector does not write CET, chain or journal. The trusted caller feeds
the existing HostObservationIngestor, producing HOST_OBSERVED CET and Security
Chain records. Shared-chain ingestion must use the existing owner/session
contract; a single collector does not establish global exclusive collection.
Known, absent and unresolved action references remain CORRELATED,
UNCORRELATED and UNRESOLVED_LINK respectively; correlation grants no authority.

Restart uses a fresh interpreter and new session with an explicit gap. Old
session reuse and observation replay are rejected. Lost native registrations
are not recovered or reconstructed. Sticky ingestion failure remains sticky;
no action UNKNOWN is cleared and no reconciliation authority is introduced.
H1 durability, material barriers, H2 ownership, target observation limits,
signer trust, anchor GET-only recovery and binding v2/legacy fences are unchanged.
No journal migration/reset, downgrade support or mixed-writer support is added.

## Reproducible qualification

Run from the isolated repository with its existing Python, without dependencies:

```sh
python3 -B -m unittest discover -s tests -p test_host_observer_macos_exit.py -v
python3 -B -m unittest discover -s tests -p test_cross_process_coordination.py -v
python3 -B -m unittest discover -s tests -p test_host_observer_macos.py -v
```

Native tests pipe-block the child, register before releasing it, require actual
NOTE_EXIT and ingest into CET/chain. Three successive children cover all three
correlation states; only one child is alive at a time. A native-event-dropping
wrapper proves cleanup/reaping does not fabricate observation. The handoff test
holds ownership, rejects a competing controller without changing chain bytes,
kills the first controller after its child is reaped, rejects old session and
replay in a fresh interpreter, and collects a new native event with explicit gap.

Portable doubles separately test invalid input/type/PID/filter/flags, EV_ERROR,
registration budget, sequence/replay, chain/trace failure, sanitized errors and
ambiguous close. Doubles do not prove native delivery. Linux explicitly skips
Darwin tests as NOT_RUN_PLATFORM_RESTRICTED; CI success is not native acceptance.

Test budgets: at most two controllers plus one controlled child per scenario,
child wait 3 seconds, kill/reap additional 3 seconds, interpreter communication
at most 10 seconds, supervised case budget 30 seconds. Timeout/failure is not
PASS. These bounds do not assert OS hard-real-time guarantees.

Initial base RED: eight selected EXIT tests failed because the collector was
absent. An additional huge-integer timeout RED exposed OverflowError; bounded
range validation precedes float finiteness conversion to reject it consistently.
Final test/CI counts and exact-SHA independent review belong to the delivery
report, not an unbound claim here. Local formal remains
BLOCKED_MISSING_DEPENDENCIES. No exactly-once, complete continuity, universal
filesystem support, tamper resistance, hostile-host isolation or new power-loss
guarantee is claimed.
