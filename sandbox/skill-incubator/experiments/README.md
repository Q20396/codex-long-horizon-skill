# Locked Experiments

This directory contains governance templates only. It contains no experiment
implementation, copied third-party code, dependencies, provider configuration,
or runtime setup.

All experiments begin as `locked`. A status transition is manual and needs a
new customer decision record. A proposal, score, evaluator conclusion, or
Codex-generated text is not customer authorization.

Lifecycle: `locked`, `proposed`, `approved_for_design`,
`approved_for_isolated_build`, `testing`, `rejected`,
`retained_in_sandbox`, `candidate_optional`, `approved_optional`,
`candidate_core`, `approved_core`, `deprecated`.

Templates describe an experiment before any build can be considered. They must
not be used to claim that an experiment ran, passed, or was promoted.
