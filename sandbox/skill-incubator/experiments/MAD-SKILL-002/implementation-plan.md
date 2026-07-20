# Future-Only Implementation Plan

**Experiment:** `MAD-SKILL-002`
**Status:** `locked`

| Phase | Preconditions/input | Output | Allowed/prohibited | Network/writes | Approval | Done/stop |
| --- | --- | --- | --- | --- | --- | --- |
| 0 Design only | proposal | contract | Markdown/no adapter | offline/sandbox docs | current only | stop on missing field |
| 1 Static prototype | approved contract | static fixture | local text/no host | offline/isolated | design approval | stop on ambiguity |
| 2 Isolated build | approved fixture | harness | approved local/no provider | offline/temp | build approval | stop on dependency |
| 3 Synthetic fixtures | harness | outputs | synthetic/no client data | offline/temp | fixture approval | stop on sensitive data |
| 4 Baseline comparison | outputs | evidence | evaluator/no promotion | offline/evidence | evaluation approval | stop on regression |
| 5 Adversarial evaluation | evidence | abuse record | static/no real tool | offline/temp | adversarial approval | stop on gate failure |
| 6 Rollback verification | artifact | recovery evidence | approved local | offline/cleanup | rollback approval | stop on residue |
| 7 Customer promotion review | evidence | decision | review/no automatic action | offline/no mutation | explicit approval | stay locked without it |

No phase is authorized or executed by this file.
