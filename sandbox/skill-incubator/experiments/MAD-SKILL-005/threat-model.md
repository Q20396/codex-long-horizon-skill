# Threat Model

**Experiment:** `MAD-SKILL-005`
**Status:** `locked`
**Restricted security boundary:** `true`

Assets: permissions, credentials, customer systems, audit records, budget, and containment rules. Boundaries: controller, hypothetical executor, isolated fixture, and customer decision. Actors: customer, reviewer, malicious task text, compromised dependency, hostile target. Future flow: approval -> control record -> bounded isolated action -> evidence.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | prompt injection, secrets, or credentials steer control | Critical | High | deny default/redacted synthetic fixtures | contract review | GATE-PRIVACY |
| T02 | traversal, symlink, repository escape, unauthorized writes | Critical | High | exact-path allowlist/no write grant | path evidence | GATE-SCOPE |
| T03 | egress, supply chain, unauthorized scan/exploit | Critical | Medium | offline defensive design/no security runtime | network record | GATE-HUMAN-CONTROL |
| T04 | loop persistence, background process, concurrency, cost amplification | Critical | Medium | no loop/current design; future cap four | process/budget record | GATE-OBSERVABILITY |
| T05 | benchmark leakage, approval bypass, rollback failure, false safety claim | Critical | Medium | isolated synthetic test/separate approval/recovery proof | gate evidence | GATE-CLAIM-INTEGRITY |
