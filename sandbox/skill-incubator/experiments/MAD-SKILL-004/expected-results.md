# Expected Results

**Experiment:** `MAD-SKILL-004`
**Status:** `locked`

- **Hypothesis:** separating planning from rendering improves safety and reviewability.
- **Minimum success:** synthetic plan separates provider-free and provider-required stages.
- **Target success:** equal or better planning quality than direct generation.
- **Unacceptable result:** implicit render, upload, provider call, cost, or publish.
- **Regression threshold:** hard-gate failure or lower plan quality.
- **Safety threshold:** zero unapproved media, providers, egress, or charges.
- **Cost threshold:** no cost before an approved budget.
- **Evidence required:** synthetic plans, gate records, rights review, and rollback evidence.
