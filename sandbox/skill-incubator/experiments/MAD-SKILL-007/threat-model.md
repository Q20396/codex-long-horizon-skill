# Threat Model

**Experiment:** `MAD-SKILL-007`
**Status:** `locked`

Assets: private notes, secrets, paths, links, vault configuration, and approval records. Boundaries: customer allowlist, local filesystem, future bridge, write-diff review. Actors: customer, reviewer, malicious note, future connector. Future flow: approved path -> read-only view -> review.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | private note/secret exposure or prompt injection | Critical | High | exact allowlist/secret exclusion | path review | GATE-PRIVACY |
| T02 | traversal, symlink, repo escape, unauthorized write | Critical | High | canonical containment/diff approval | path/write test | GATE-SCOPE |
| T03 | egress, connector dependency, supply chain | High | Medium | network/shell/MCP deny | egress record | GATE-LICENSE |
| T04 | background indexing, persistence, cost | High | Medium | no daemon/no index/budget | process record | GATE-OBSERVABILITY |
| T05 | approval bypass, rollback failure, false read-only claim | High | Medium | separate approval/rollback/direct evidence | gate record | GATE-HUMAN-CONTROL |
