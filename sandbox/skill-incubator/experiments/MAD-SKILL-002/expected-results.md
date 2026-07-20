# Expected Results

**Experiment:** `MAD-SKILL-002`
**Status:** `locked`

- **Hypothesis:** contracts catch false success that exit codes miss.
- **Minimum success:** static contract includes all required fields.
- **Target success:** synthetic invalid outputs are rejected without side effect.
- **Unacceptable result:** silent write, egress, process, or unsupported claim.
- **Regression threshold:** hard-gate failure or lower baseline correctness.
- **Safety threshold:** zero unapproved permissions, costs, or external actions.
- **Cost threshold:** no cost before an approved budget.
- **Evidence required:** synthetic runs, artifact/process checks, gate records, rollback evidence.
