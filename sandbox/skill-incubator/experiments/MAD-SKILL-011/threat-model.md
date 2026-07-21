# Threat Model

**Experiment:** `MAD-SKILL-011`
**Status:** `locked`

Assets: Skill instructions, trigger contracts, permission contracts, fixtures, review records, and customer decisions. Boundaries: candidate description, approved paths, evaluator, future target repository. Actors: customer, reviewer, malicious prompt, future builder. Future flow: approved candidate -> review package -> customer decision.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | secret/private data or prompt injection in candidate | High | Medium | synthetic/redacted inputs | input review | GATE-PRIVACY |
| T02 | traversal, symlink, repo escape, unauthorized target write | Critical | Medium | exact-path approval/write deny | path record | GATE-SCOPE |
| T03 | egress, dependency compromise, supply chain | Medium | Low | offline/no dependency default | egress record | GATE-LICENSE |
| T04 | persistent evaluator, cost amplification, fixture leakage | High | Medium | no daemon/synthetic fixtures/budget | process/fixture record | GATE-OBSERVABILITY |
| T05 | approval bypass, rollback failure, misleading readiness claim | High | Medium | separate approvals/baseline/direct evidence | gate record | GATE-HUMAN-CONTROL |
