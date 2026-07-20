# Repetition Policy

- Deterministic static checks run at least once.
- Low-randomness engineering tasks run at least three times.
- Routing, model selection, and generation tasks run at least five times.
- A reduced high-cost sample needs explicit customer approval.

Report total, successful, failed, blocked, and timed-out runs plus median,
mean, minimum, maximum, variance or dispersion, and confidence limitations.
Keep every failure, abort, timeout, and outlier explanation. Never rerun until a
good result appears and report only that final attempt.
