# Experiment Gates

Every gate must pass before scoring. A failed gate cannot be offset by quality,
speed, token savings, or any total score.

- GATE-SOURCE: source identity, immutable commit, and pattern linkage are clear.
- GATE-LICENSE: repository, file, model, dataset, and asset licenses are known.
- GATE-SCOPE: reads, writes, permissions, and network scope are explicit.
- GATE-PRIVACY: no secret, unrelated private file, or unapproved client data.
- GATE-ISOLATION: use an isolated worktree, temporary directory, or container.
- GATE-ROLLBACK: a recovery method exists; high-risk rollback is tested.
- GATE-OBSERVABILITY: commands, changes, network, cost, and tests are recorded.
- GATE-HUMAN-CONTROL: each action has a separate customer approval.
- GATE-NO-REGRESSION: a no-skill baseline and regression set are defined.
- GATE-CLAIM-INTEGRITY: local evidence is distinct from marketing and papers.

Failure leaves an experiment `locked`, `rejected`, or `retained_in_sandbox`.
