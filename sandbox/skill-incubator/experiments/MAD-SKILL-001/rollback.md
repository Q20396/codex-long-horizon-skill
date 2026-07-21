# Rollback Plan

**Experiment:** `MAD-SKILL-001`
**Status:** `locked`
**Rollback status:** `not_tested`

No implementation exists. A future approved build must record file changes, stop processes, close ports, remove approved dependencies, restore config, and document external-state reversal. It must compare customer tracked, staged, and untracked state. External state may not be fully reversible; that blocks promotion until evidence exists.
