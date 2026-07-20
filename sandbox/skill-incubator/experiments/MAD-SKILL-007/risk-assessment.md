# Risk Assessment

**Experiment:** `MAD-SKILL-007`
**Status:** `locked`

| Area | Inherent | Design-only | Implementation/execution/promotion | Residual |
| --- | --- | --- | --- | --- |
| Data sensitivity/privacy | Critical | Low | Critical for personal vaults | High |
| Permission scope/writes | Critical | Low | Critical for local paths | High |
| Network/dependencies/services/cost | High | Low | High for connectors | Medium |
| Irreversible actions/rollback | High | Low | High for note changes | Medium |
| Legal/regulatory/maintenance | High | Low | High for sensitive notes | High |
| Cross-platform uncertainty | High | Low | High for path semantics | High |

Document-only work does not reduce actual local-data risk.
