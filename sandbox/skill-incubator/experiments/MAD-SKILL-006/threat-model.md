# Threat Model

**Experiment:** `MAD-SKILL-006`
**Status:** `locked`
**Domain:** restricted legal

Assets: client facts, legal evidence, rubric, answers, identities, and procedure rules. Boundaries: synthetic fixture, evaluator, learner proposal, customer decision. Actors: customer, evaluator, model, malicious prompt. Future flow: synthetic case -> redacted signal -> proposal -> review.

| ID | Scenario | Impact | Likelihood | Mitigation | Evidence | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | legal/client data, secret exposure, prompt injection | Critical | High | synthetic fixtures/no client data | fixture audit | GATE-PRIVACY |
| T02 | traversal, symlink, repo escape, unauthorized write | High | Medium | isolation/write deny | path evidence | GATE-SCOPE |
| T03 | egress, dependency compromise, supply chain | High | Medium | offline/no dependencies | egress record | GATE-LICENSE |
| T04 | persistent feedback memory, cost amplification, benchmark leakage | Critical | Medium | no memory/rubric-blind fixtures/budget | storage/eval record | GATE-OBSERVABILITY |
| T05 | approval bypass, rollback failure, misleading legal claim | Critical | Medium | separate review/no advice/direct evidence | gate record | GATE-CLAIM-INTEGRITY |
