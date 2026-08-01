# Presentation Separate-Skill Extraction Contract

Status: Candidate only

> **Supersession.** This is a v0.3 historical candidate record. The approved
> v0.4 Local Governance Upgrade changes the package default to
> `local-governance-core`; it does not create, register, or authorize this
> presentation capability.

This contract evaluates the presentation boundary identified by the v0.3
package path classification. It does not create or register a skill, move
files, edit the package manifest, change an installation profile, add a
runtime, or authorize execution.

The machine-readable contract is
`docs/design/presentation-separate-skill-extraction-v0.3.json`.

## Decision

Presentation authoring is a valid separate capability boundary, but its final
owner is unresolved. The platform may already provide an installed presentation
capability. That capability MUST be evaluated before this repository creates a
second skill with overlapping triggers, artifact ownership, or runtime
responsibilities.

Evaluate ownership in this order:

1. an installed platform presentation capability;
2. a repository-owned separate skill, only if a material gap remains;
3. a narrow compatibility bridge, only when two owners cannot be avoided.

This proposal does not install, invoke, configure, or modify any platform
capability.

## Candidate Source Boundary

The candidate consists of exactly three current `bundled-optional` paths:

- `references/presentation-delivery-protocol.md`
- `templates/deck-outline.md`
- `templates/slide-qa-checklist.md`

Their full repository-relative paths and content digests are recorded in the
machine-readable contract. All three remain in their current locations.

## Responsibility Split

The future presentation owner would be responsible for:

- deck and slide artifact planning;
- PPTX generation or editing when approved tooling is available;
- rendering and visual slide QA;
- speaker notes tied to a deck;
- artifact-specific compatibility and export validation.

LHE remains responsible for:

- software-engineering planning and execution;
- checkpoints, evidence, rollback, and validation;
- coordinating a presentation deliverable inside a larger engineering task;
- preserving approval and capability boundaries across handoffs.

Planning a presentation does not authorize artifact writes. Generating a binary
deck does not authorize external asset retrieval. Creating a deck does not
authorize upload, publication, account access, or distribution.

## Routing

Presentation-only requests should route to the approved presentation owner.
Code review, architecture analysis, implementation plans, ordinary Markdown
reports, and AI-video work must not be captured by this boundary.

When one request contains both engineering and presentation work, the work is
split into explicit branches. LHE may coordinate the engineering branch, but it
does not inherit the presentation owner's write, tool, account, or publication
permissions. Ambiguous requests require clarification.

## Compatibility

This candidate preserves:

- `legacy-full` as the default profile;
- current `core-only` and `lhe-bundled` behavior;
- all current paths and manifest entries;
- existing package and doctor checks;
- existing updater and installer behavior;
- the current explicit-only presentation reference in LHE.

No migration is required. Existing installations remain valid.

## Implementation Gate

A later implementation PR must provide:

1. an approved owner with a unique trigger contract;
2. negative routing tests showing LHE does not claim presentation-only work;
3. clean-room package checks with and without the extracted capability;
4. temporary-directory upgrade and rollback evidence;
5. proof that selected profiles have no broken references;
6. release notes for any change to installed content.

The implementation must stop if ownership overlaps an installed presentation
capability, if a selected profile would contain a broken reference, or if the
change introduces a provider, account, network, upload, publication, or other
runtime side effect.

## Rollback

This proposal is rolled back by reverting this document, its machine-readable
contract, and its tests.

For a future physical extraction, rollback must restore the previous manifest,
the three source paths, and LHE routing references, then re-run package, doctor,
routing, clean-room install, and upgrade checks. Rolling back LHE must never
silently delete a separately installed presentation capability.

## Deliberate Non-Goals

This contract does not:

- create a new `SKILL.md`;
- choose a final owner;
- move or duplicate presentation files;
- modify LHE routing;
- modify package or doctor checks;
- install or call a presentation tool;
- generate a deck;
- access external assets or accounts;
- upload, publish, or distribute an artifact;
- change any v0.3 profile or default.
