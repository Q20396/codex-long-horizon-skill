# Source Records

Each verified source has a directory containing the same seven metadata files:
source card, immutable pin, license review, security review, architecture notes,
extracted patterns, and claims to verify.

Entries with `verification_status: verification_blocked` remain only in
`../registry.json`; they have no immutable source baseline and therefore no
source directory. They cannot be installed, executed, or promoted.
