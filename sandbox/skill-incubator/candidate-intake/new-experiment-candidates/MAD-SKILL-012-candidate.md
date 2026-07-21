# MAD-SKILL-012 Candidate: Engineering Traceability Pipeline

- status: `candidate_only`
- registered_experiment: `false`
- implementation_exists: `false`
- execution_authorized: `false`
- customer_decision: `not_approved`
- proposed_layers: `sandbox -> bundled-optional -> core-policy candidate`

The authoritative safety state is stored in: `candidate-intake/candidate-states/MAD-SKILL-012.json`. This Markdown file is explanatory only.

## Intended Scope

Model a stable-ID chain from specification to issue, decision, implementation,
test evidence, commit, PR narrative, changelog, release notes, and retrospective.
It must support bidirectional links, stale and orphan detection, decision
supersession, release-note provenance, and no automatic publication.

## Boundaries

Design only. No repository scan, issue tracker access, commit rewriting,
publication, release creation, or automatic linking is authorized.
