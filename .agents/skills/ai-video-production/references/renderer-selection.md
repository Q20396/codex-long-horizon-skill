# Renderer Selection And Evidence

Use this optional protocol to choose a video production path before rendering.
It compares planning options; it does not install tools, run a renderer, call a
provider, generate media, upload assets, publish content, or consume credits.

## Start With The Deliverable

Record:

- intended format, duration, aspect ratio, and output variants
- whether the work is repeatable, data-driven, or a one-off concept
- required preview and review steps
- approved asset sources and licensing constraints
- privacy classification and whether external providers are allowed
- budget, timeline, and maintainability constraints

## Selection Criteria

Compare each candidate against:

- deterministic timing and reproducibility
- maintainability and source-code ownership
- preview and inspection workflow
- local versus external processing
- dependency, compute, cost, and quota implications
- accessibility, caption, audio, and export needs
- asset provenance, licensing, and privacy risk
- human approval point before final render or sharing

## Common Planning Paths

- **Remotion-style:** repeatable code-driven compositions, data visualizations,
  variants, and precise frame contracts.
- **HyperFrames-style:** inspectable HTML/CSS/JS compositions, rapid browser
  previews, and manual local rendering.
- **Provider-assisted generation:** only after explicit approval of the
  provider, inputs, cost, retention, and output use.
- **Placeholder-only:** the safest path when assets, rights, source facts, or
  rendering approval are incomplete.

These are planning categories, not endorsements of a particular product or
license. Verify current licensing and provider terms before use.

## Evidence Before Render

Before a human considers rendering, complete
`templates/RENDER_EVIDENCE_TEMPLATE.md` and ensure the existing render handoff
has a reviewed preview, approved assets, clear output location, and an explicit
approval owner.

## Stop Conditions

Stop and request clarification when:

- a renderer, provider, source asset, license, or cost is unknown
- private or client assets may leave the approved environment
- a request implies automatic render, upload, publication, or posting
- the output could misrepresent a speculative visual as real footage
- the approval owner or output destination is not defined

## Boundaries

Do not treat a selected renderer as approval to install it, execute it, or send
assets to it. Final rendering, external upload, publication, and paid provider
use require separate explicit human approval.
