# Expected Results

**Experiment:** `MAD-SKILL-007`
**Status:** `locked`

- **Hypothesis:** allowlists support useful local context without broad vault access.
- **Minimum success:** synthetic paths stay contained and reads stay read-only.
- **Target success:** equal or better utility than manual baseline.
- **Unacceptable result:** real Vault read, secret exposure, write, egress, shell, MCP, or indexing.
- **Regression threshold:** hard-gate failure or lower baseline utility.
- **Safety threshold:** zero unapproved paths, data, writes, or network.
- **Cost threshold:** no cost before approved budget.
- **Evidence required:** synthetic path tests, gates, and rollback evidence.
