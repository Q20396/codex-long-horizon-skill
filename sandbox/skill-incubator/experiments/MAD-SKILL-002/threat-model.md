# Threat Model

**Experiment:** `MAD-SKILL-002`
**Status:** `locked`

Assets: customer files, permission contract, output evidence, secrets, and cost budget. Boundaries: contract, isolated fixture, future tool/provider, evaluator. Actors: customer, reviewer, malicious input, compromised dependency. Future flow: approved contract -> isolated synthetic run -> evidence.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | prompt injection or secret exposure | High | Medium | synthetic fixtures/redaction | fixture review | GATE-PRIVACY |
| T02 | traversal, symlink escape, repository escape, unauthorized write | Critical | Medium | canonical paths/write deny | path tests | GATE-SCOPE |
| T03 | egress, dependency compromise, supply chain | High | Medium | offline/pinned review | egress log | GATE-LICENSE |
| T04 | process residue, temp files, cost amplification | High | Medium | process inventory/budget | process and cost evidence | GATE-OBSERVABILITY |
| T05 | benchmark leakage, approval bypass, rollback failure, false success | High | Medium | blinded fixtures/separate approvals/direct evidence | gate record | GATE-HUMAN-CONTROL |
