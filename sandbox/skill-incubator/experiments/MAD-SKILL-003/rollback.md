# Rollback Plan

**Experiment:** `MAD-SKILL-003`
**Status:** `locked`
**Rollback status:** `not_tested`

No compiler exists. A future build must remove derived files, stop processes, close ports, remove dependencies, restore configuration, and delete only approved isolated output. It must verify customer workspace state is unchanged. Previously exposed or externally copied source text may not be fully reversible; that blocks promotion.
