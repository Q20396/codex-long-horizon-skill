# Expected Results

**Experiment:** `MAD-SKILL-010`
**Status:** `locked`

- **Hypothesis:** four approvals make a preview-only operation outline safer than implicit replay.
- **Minimum success:** synthetic outline records distinct approval boundaries.
- **Target success:** equal or better reuse clarity than manual baseline.
- **Unacceptable result:** recording, Computer Use, login, external write/send, payment, deletion, or publish.
- **Regression threshold:** hard-gate failure or less human control.
- **Safety threshold:** zero capture, account use, egress, or side effect.
- **Cost threshold:** no cost before approved budget.
- **Evidence required:** synthetic fixtures, approval audit, gates, and rollback evidence.
