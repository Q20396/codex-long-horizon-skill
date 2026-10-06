# LHE Helper-Script Effect Manifest

`effect-manifest.json` is the machine-readable declaration for every installed
LHE helper script. CI requires exact coverage and compares selected static
surfaces to the declared network, write, delete, external-command and apply
requirements.

The manifest does not grant an effect. `explicit-only` means the script must
remain behind a separate approval decision; it never authorizes a connection.
Likewise, declared writes remain bounded by each script's own target and apply
guards. This is drift detection, not host-enforced isolation.

The Local Compute Beta modules are APIs, not apply-flag CLIs. Imports have no
effects. Effects arise only through explicit calls: the deployment journal writes
to its selected path, and approved subprocess/worker adapters may have their own
effects. Caller-provided consent is not proof of human approval or sandboxing.
The manifest conservatively includes adapter effects; it does not imply that
providers or remote transports ship with this package.

The Phase 2A runtime binding is also an explicitly constructed API, not an
apply-flag CLI. Its filesystem and local Git operations require RSE authority.
The conservative network declaration covers possible internal effects of trusted
allowlisted children; no network adapter ships in Phase 2A and child network containment is
not implemented. Importing or installing the module activates nothing.

The separate Phase 2B remote binding is likewise an explicitly constructed,
inactive API. Approved digests, RSE policy/authorization and explicitly registered
capabilities precede its HTTPS request, single-ref Git update or PR create.
Git pack preparation uses hardened local Git and an owned temporary input file;
Git network helpers are not used. The host supplies any transport credentials;
the module does not discover credentials. Its remote DELETE method is a bounded
HTTP operation, not a local delete or a Git-ref deletion API. This declaration
does not authorize an endpoint or imply exactly-once, crash durability, network
containment, independent host observation or a production deployment.

The Phase 2C agent bridge is an inactive API. Pure `prepare()` freezes and
normalizes proposal data without executing effects. The manifest conservatively
declares effects delegated through the existing Phase 2A/2B bindings, plus
same-process reservations, the existing journal and digest-only chain evidence.
It adds no runtime effect route or direct adapter invocation. The trusted host
must supply independently saved prepared/payload commitments, construct the
bindings, register capabilities and obtain current scoped authorization before
execution. Installation, import and preparation grant no capability or authority.
Model/provider identity and effect declarations do not authorize effects. Trusted
child effects remain uncontained; no host interception or crash persistence is
implied by this declaration.

The Phase 3B macOS backend is an explicitly constructed, session-scoped API.
It creates one kqueue descriptor and registers caller-supplied PIDs for a single
NOTE_EXEC each. It launches no child and reads no command line, environment or
process metadata. Its effects are native registration and bounded in-memory
session state; `close()` releases the descriptor. Only returned matching native
events produce HostObservation values, and the existing ingestor owns CET/chain
publication. Import and installation activate nothing. Coverage is PARTIAL;
observation grants no authority, enforcement or automatic reconciliation.
