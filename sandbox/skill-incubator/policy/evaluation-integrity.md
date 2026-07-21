# Evaluation Integrity

Do not place hidden rubrics, answers, task IDs, answer-bearing filenames, or
evaluator feedback inside a candidate Skill. Candidates must not read result
directories, private validation fixtures, holdouts, or user private data.

Fixture levels are `public-development`, `private-validation`, `holdout`,
`regression`, and `adversarial`. Every fixture records its ID, category, source,
license, sensitivity, expected and prohibited behavior, evaluator, visibility,
and mutation policy.

All failures, aborts, timeouts, and inconclusive runs are retained. Do not
selectively report successes, manually repair a result and call it automated,
or claim a paper or marketing result as a local result.
