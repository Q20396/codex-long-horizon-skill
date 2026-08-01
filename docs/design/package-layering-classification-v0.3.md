# v0.3 Package Path Classification Review

Status: Proposed

This review applies the
[v0.3 package layering specification](package-layering-v0.3.md) to every path
in the version 1.0 package manifest. It does not move files, edit the manifest,
register a skill, or change an installation profile.

The machine-readable proposal is
`docs/design/package-layering-classification-v0.3.json`. The package manifest
remains the only authoritative path inventory.

## Result

| Result | Paths | Decision |
| --- | ---: | --- |
| Retain in `core` | 43 | All current core paths remain necessary for the safe engineering, recovery, validation, capability-discovery, or package-management contract. |
| `bundled-optional` inventory | 101 | This inventory contains 86 retained paths and 15 candidate extraction paths. |
| Retain in `bundled-optional` | 86 | These paths remain useful engineering extensions or safety boundary documents. |
| Candidate separate-skill extraction | 15 | These paths are a subset of the 101-path `bundled-optional` inventory; domain workflows should be reviewed as independently routed skills before any physical change. |
| Retain existing `separate-skill` | 28 | `ai-video-production` remains independently routed and governed. |

The 15 candidate extraction paths are a subset of the 101-path
`bundled-optional` inventory (`86 + 15 = 101`). The complete manifest inventory
remains `43 + 101 + 28 = 172`. All 172 manifest paths receive a deterministic
result: an exact override in the proposal or `retain-current-layer` through the
declared default action.

## Core Review

No core demotion is proposed. The 43 core paths cover:

- entry point and package manifest;
- approval, privacy, safety, capability, and stop boundaries;
- planning, debugging, migration, review, resume, and validation workflow;
- package, doctor, routing, safety, description, self-check, and updater tools;
- minimum handoff, rollback, risk, and verification templates.

Moving any of these paths now would weaken `core-only` or create a circular
dependency on optional content.

## Optional Review

Most optional content stays optional. In particular:

- Decision Map remains an optional planning layer.
- Voice and 3D sandbox documents remain optional safety boundaries; their
  presence does not install or authorize a provider.
- Skill discovery, lifecycle, and optimization material remains optional
  governance rather than a separate runtime.
- General evidence, data quality, API, UI/UX, TDD, and project-context material
  remains relevant to engineering work.

## Candidate Extractions

The proposal groups 15 paths into six candidate boundaries:

| Candidate boundary | Paths | Required follow-up |
| --- | ---: | --- |
| Finance domain | 4 | Confirm ownership by a dedicated investment-research skill and avoid duplicate contracts. |
| Disaster monitoring | 2 | Define data freshness, jurisdiction, alerting, and public-safety review. |
| Knowledge workspace | 4 | Define vault/notebook read, upload, exact-path write, and deletion boundaries. |
| Presentation | 3 | Define artifact generation, rendering, visual QA, and publication boundaries. |
| Content writing | 1 | Define explicit routing and prevent implicit activation for engineering work. |
| Personal workflow | 1 | Decide whether this belongs in a separate personal-operations product at all. |

`candidate-separate-skill-extraction` is not approval to create a skill. Each
candidate needs an independent architecture, trigger, permission, compatibility,
and rollback review.

## Deliberate Non-Moves

This review does not extract:

- `local-voice-tool-sandbox.md` or its approval card;
- `three-d-asset-provider-sandbox.md` or its approval card;
- external provider and app runtime boundary references;
- source-upload consent and secrets-scan checklists.

Those files constrain risky integrations without implementing them. They may
remain optional LHE safety documentation until a real separate skill owns the
same boundary and proves that removing the LHE copy does not create a gap.

## Compatibility

This proposal preserves:

- `legacy-full` as the default profile;
- `core-only` and `lhe-bundled` behavior;
- all current file locations;
- manifest schema version 1.0;
- legacy checker fallback;
- independent `ai-video-production` approval and lifecycle;
- current updater and installer behavior.

## Required Evidence Before Extraction

Each future extraction PR must provide:

1. a named owner skill and trigger contract;
2. proof that no core or selected-profile reference becomes broken;
3. clean-room install and package checks before and after extraction;
4. upgrade behavior for existing full installations;
5. rollback that restores the previous manifest and files;
6. documentation and release notes for changed installed content;
7. negative routing tests preventing LHE from claiming the extracted domain.

Physical moves should be grouped by one candidate boundary per PR. A candidate
may be rejected without changing the current package.

## Recommendation

The next implementation PR should not move all 15 files. It should first choose
one low-coupling boundary and prove the extraction workflow end to end.
Presentation is the best first experiment because it has no production runtime
inside LHE and already has a clear artifact boundary. Finance should wait until
ownership with the installed Public Equity Investing skill is explicitly
resolved.
