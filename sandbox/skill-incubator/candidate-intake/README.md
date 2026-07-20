# Capability Candidate Intake

This directory records customer-provided capability patterns and public-source
leads for architecture review. It is not a skill catalog, installer, runtime,
or permission grant.

## Scope

- All 40 customer-provided names are treated as capability patterns, not
  verified repositories or installable skills.
- Existing MAD-SKILL-001 through MAD-SKILL-011 remain the only registered
  experiments. This intake does not change their status or files.
- MAD-SKILL-012 through MAD-SKILL-014 are candidate-only designs. They are not
  registered experiments and have no implementation or execution authority.
- No source code, skill prose, credentials, customer material, private files,
  screenshots, or marketing metrics are imported here.

## Source Verification Boundary

The 2026-07-20 read-only lookup plan was limited to `api.github.com`. Every
requested API call returned HTTP 403, so no new source was verified and no
full commit SHA, license, or maintenance claim is asserted. Accordingly, no
new seven-file source card was created; those cards are reserved for sources
that pass immutable-commit verification.

See `capability-patterns.tsv`, `existing-experiment-map.tsv`, and
`deduplication-matrix.tsv` for the consolidation evidence. See
`source-candidates.json` for locked, non-executable public-source leads.
