# Risk Assessment

**Experiment:** `MAD-SKILL-002`
**Status:** `locked`

| Area | Inherent | Design-only | Implementation/execution/promotion | Residual |
| --- | --- | --- | --- | --- |
| Data sensitivity/privacy | High | Low | High for host input/output | Medium |
| Permission scope/writes | High | Low | Critical for host writes | Medium |
| Network/dependencies/services/cost | High | Low | High for external tools | Medium |
| Irreversible actions/rollback | High | Low | High for side effects | Medium |
| Legal/regulatory/maintenance | Medium | Low | Medium | Medium |
| Cross-platform uncertainty | High | Low | High for shells/hosts | High |

Design-only status does not reduce execution or promotion risk.
