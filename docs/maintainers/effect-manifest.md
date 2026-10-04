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
allowlisted children; no network adapter ships and child network containment is
not implemented. Importing or installing the module activates nothing.
