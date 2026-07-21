# Baseline Protocol

Compare every candidate against the same task without the candidate Skill. Fix
or record the repository commit, fixtures, prompt, model and version, reasoning
level, tools, permissions, network, dependency and runtime versions, operating
system, token and time budgets, retry policy, concurrency, evaluator, rubric,
seed when applicable, timestamp, and audit ID.

Baseline and candidate must use identical inputs, model, tool permissions, time
budget, network conditions, retries, and acceptance criteria. The candidate
pattern is the only intended variable. If fairness cannot be established, mark
the result `inconclusive`, never `improvement`.
