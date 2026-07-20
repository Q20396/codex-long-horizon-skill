# Threat Model

**Experiment:** `MAD-SKILL-010`
**Status:** `locked`

Assets: screen content, credentials, customer identity, external accounts, approvals, and action history. Boundaries: hypothetical recording, extraction, replay, external action. Actors: customer, reviewer, malicious page, future platform. Future flow: approval matrix -> preview-only outline -> review.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | private capture, secret exposure, prompt injection | Critical | High | no recording/synthetic only | capture-deny record | GATE-PRIVACY |
| T02 | traversal, symlink, repo escape, unauthorized write | High | Medium | no filesystem action/exact scope | path record | GATE-SCOPE |
| T03 | egress, platform dependency, supply chain | High | Medium | platform disabled/offline design | network record | GATE-LICENSE |
| T04 | background replay, cost, external send/payment/deletion | Critical | High | preview-only/all effects false | approval matrix | GATE-HUMAN-CONTROL |
| T05 | benchmark leakage, rollback failure, false safety claim | Critical | Medium | no execution/synthetic evidence/direct labels | gate evidence | GATE-CLAIM-INTEGRITY |
