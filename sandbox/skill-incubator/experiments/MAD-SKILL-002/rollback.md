# Rollback Plan

**Experiment:** `MAD-SKILL-002`
**Status:** `locked`
**Rollback status:** `not_tested`

No harness exists. A future build must remove isolated files, stop processes, close ports, remove approved dependencies, restore configuration, and record external-state handling. Customer workspace tracked, staged, and untracked state must compare unchanged. Non-reversible external state blocks promotion.
