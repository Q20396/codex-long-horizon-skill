# LHE Helper-Script Effect Manifest

`effect-manifest.json` is the machine-readable declaration for every installed
LHE helper script. CI requires exact coverage and compares selected static
surfaces to the declared network, write, delete, external-command and apply
requirements.

The manifest does not grant an effect. `explicit-only` means the script must
remain behind a separate approval decision; it never authorizes a connection.
Likewise, declared writes remain bounded by each script's own target and apply
guards. This is drift detection, not host-enforced isolation.
