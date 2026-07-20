# Rollback Plan

**Experiment:** `MAD-SKILL-005`
**Status:** `locked`
**Rollback status:** `not_tested`

No controller or executor exists. Future approved work must remove isolated files, stop processes, close ports, remove dependencies, restore configuration, and document any external-state reversal. It must prove customer workspace state is unchanged. Security effects may be irreversible; that blocks promotion.
