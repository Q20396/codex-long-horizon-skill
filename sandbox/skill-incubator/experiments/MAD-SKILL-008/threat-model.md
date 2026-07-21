# Threat Model

**Experiment:** `MAD-SKILL-008`
**Status:** `locked`

Assets: triggers, instructions, permission boundaries, customer task text, and context budget. Boundaries: router recommendation, loaded instruction, future executor. Actors: customer, reviewer, malicious prompt, future model. Future flow: task text -> recommendation -> separate approval.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | prompt injection/secret text changes routing | High | Medium | explicit criteria/no secret ingestion | fixture review | GATE-PRIVACY |
| T02 | traversal, symlink, repository escape, unauthorized load/write | High | Medium | path allowlist/read boundary | path tests | GATE-SCOPE |
| T03 | egress, dependency compromise, supply chain | Medium | Low | offline/no dependency default | egress record | GATE-LICENSE |
| T04 | persistent index, cost amplification, benchmark leakage | Medium | Medium | no index/fixed synthetic set | cost/fixture record | GATE-OBSERVABILITY |
| T05 | approval bypass, rollback failure, misleading routing claim | High | Medium | recommend-only/separate approval/direct evidence | gate record | GATE-HUMAN-CONTROL |
