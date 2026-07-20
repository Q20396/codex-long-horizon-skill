# Threat Model

**Experiment:** `MAD-SKILL-004`
**Status:** `locked`

Assets: source material, creative brief, media rights, customer identity, provider credentials, output location, and budget. Boundaries: planning document, asset manifest, future provider, external platform. Actors: customer, reviewer, provider, rights holder, malicious prompt. Future flow: approved brief -> plan -> separate approval -> future render.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | private material or prompt injection enters plan | High | Medium | approved public/synthetic inputs | source manifest | GATE-PRIVACY |
| T02 | path traversal, symlink, repo escape, unauthorized media write | High | Medium | exact output scope/write deny | path plan | GATE-SCOPE |
| T03 | provider egress, dependency compromise, supply chain | High | Medium | provider-neutral/offline planning | egress record | GATE-LICENSE |
| T04 | background render, cost amplification, external publish | Critical | Medium | separate render/publish approval and budget | approval record | GATE-HUMAN-CONTROL |
| T05 | benchmark leakage, rollback failure, misleading media claim | High | Medium | synthetic fixtures, output labels, recovery plan | evaluation evidence | GATE-CLAIM-INTEGRITY |
