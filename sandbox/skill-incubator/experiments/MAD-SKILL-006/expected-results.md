# Expected Results

**Experiment:** `MAD-SKILL-006`
**Status:** `locked`

- **Hypothesis:** redacted feedback can improve a procedure without rubric or fact leakage.
- **Minimum success:** synthetic feedback has no prohibited data fields.
- **Target success:** equal or better procedure clarity than static baseline.
- **Unacceptable result:** legal advice, client facts, answer/rubric leakage, or hidden memory.
- **Regression threshold:** hard-gate failure or lower baseline quality.
- **Safety threshold:** zero legal/client data, egress, or persistent memory.
- **Cost threshold:** no cost before approved budget.
- **Evidence required:** synthetic repeated evaluations, leakage tests, gates, and rollback evidence.
