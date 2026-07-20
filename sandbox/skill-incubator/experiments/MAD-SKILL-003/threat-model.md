# Threat Model

**Experiment:** `MAD-SKILL-003`
**Status:** `locked`

Assets: authorized source boundaries, rights assertions, citations, customer files, secrets, and candidate outputs. Boundaries: customer manifest, isolated processing area, reviewer. Actors: customer, rights holder, reviewer, malicious document, provider. Future flow: approved source manifest -> bounded index -> review.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | private/secret source exposure or prompt injection | Critical | Medium | exact-source approval and redaction | rights/source manifest | GATE-PRIVACY |
| T02 | traversal, symlink, repository escape, unauthorized write | High | Medium | canonical exact paths and write deny | path tests | GATE-SCOPE |
| T03 | egress, parser dependency compromise, supply-chain leak | High | Medium | offline/no parser default | dependency/egress record | GATE-LICENSE |
| T04 | persistent corpus, cost amplification, benchmark leakage | High | Medium | no retention/synthetic fixtures/budget | storage/cost evidence | GATE-OBSERVABILITY |
| T05 | approval bypass, rollback failure, misleading provenance claim | High | Medium | separate rights approvals/recovery/direct citations | review record | GATE-CLAIM-INTEGRITY |
