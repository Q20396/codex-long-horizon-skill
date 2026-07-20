# Threat Model

**Experiment:** `MAD-SKILL-009`
**Status:** `locked`

Assets: decision facts, customer input, author attribution, paths, and output claims. Boundaries: approved text input and local text diagram. Actors: customer, reviewer, malicious prompt, future renderer. Future flow: approved abstract structure -> text diagram -> review.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | private input, secret, or prompt injection | High | Medium | synthetic/approved input only | input review | GATE-PRIVACY |
| T02 | traversal, symlink, repo escape, unauthorized write | High | Low | exact path/write deny | path test | GATE-SCOPE |
| T03 | egress, dependency compromise, provider use | Medium | Low | offline/text-only default | egress record | GATE-LICENSE |
| T04 | persistent process, cost, benchmark leakage | Low | Low | no runtime/synthetic cases | process record | GATE-OBSERVABILITY |
| T05 | false attribution, approval bypass, rollback failure, false success | High | Medium | rejected source label/separate approval/direct evidence | review record | GATE-CLAIM-INTEGRITY |
