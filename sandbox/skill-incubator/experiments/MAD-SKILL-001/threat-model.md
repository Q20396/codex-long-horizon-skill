# Threat Model

**Experiment:** `MAD-SKILL-001`
**Status:** `locked`

Assets: source code, boundaries, allowlists, secrets, and approval records. Trust boundaries: approved paths, isolated worktree, generated artifact, and future model context. Actors: customer, reviewer, builder, malicious content, and a future provider. Future flow: approved paths -> bounded map -> evidence.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | prompt injection or secret exposure | High | Medium | allowlist and redaction review | input manifest | GATE-PRIVACY |
| T02 | path traversal, symlink, or repository escape | High | Medium | canonical containment | path tests | GATE-SCOPE |
| T03 | unauthorized write or persistent process | High | Low | read-only/no-daemon contract | diff/process record | GATE-HUMAN-CONTROL |
| T04 | egress, dependency compromise, supply chain | High | Low | offline/no dependency default | network record | GATE-SCOPE |
| T05 | cost amplification or benchmark leakage | Medium | Medium | fixed budget/synthetic fixtures | cost/fixture record | GATE-OBSERVABILITY |
| T06 | approval bypass, rollback failure, false success | High | Medium | separate approvals/recovery/direct evidence | decision/rollback record | GATE-CLAIM-INTEGRITY |
