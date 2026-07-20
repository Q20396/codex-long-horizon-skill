# Promotion Policy

Promotion requires a separately approved, reproducible experiment, safety and
privacy review, license review, rollback plan, and evidence that the candidate
improves a stated benchmark. No experiment can promote itself.

An experiment result recommendation is not customer approval, merge approval,
or release approval. Codex may set only `recommended_status`; it must never set
an approved status automatically. Each transition needs a new customer decision
record containing evidence, risks, unverified items, regression results, cost,
rollback, target layer, installation impact, and version impact.

Scores do not override failed gates. A result scoring 85 or above can only be a
`candidate_optional` recommendation. Core consideration additionally requires
two real projects, two task types, passing regressions, no critical unknowns,
maintainable ownership, an independent PR, and explicit customer approval.

The Incubator does not auto-install, auto-update, auto-merge, or mutate skills.
