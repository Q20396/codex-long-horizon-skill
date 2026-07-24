# Renderer Runtime Sandbox Protocol

Use this protocol only after a video plan has selected a renderer category and
the user explicitly asks to assess, preview, or render with a runtime. It is a
proposal and approval protocol, not an installer, renderer, provider client,
or execution command.

## Boundary

Keep the planning skill separate from execution:

- planning: brief, storyboard, assets, renderer fit, preview criteria, and
  render handoff
- local runtime: dependency inspection, project preparation, local preview,
  and local render
- external provider: provider selection, asset transfer, paid generation,
  retention, and output retrieval

Neither a selected renderer nor an approved video plan authorizes a runtime.

## Required Approval Sequence

Record each decision in
`templates/RENDER_RUNTIME_APPROVAL_CARD.md`. The user may approve a later
stage only after the earlier one is understood.

1. **Environment inspection**: identify only the requested local runtime and
   its version or absence. Do not install, start services, inspect unrelated
   directories, or read private media.
2. **Dependency installation**: state each package, source, version, disk
   impact, network requirement, and script hook. This is a separate approval.
3. **Preview**: state the exact project path, permitted inputs, output path,
   browser or renderer process, and expected temporary artifacts. A preview
   is not final rendering approval.
4. **Final render**: state the renderer, output location, resolution, frame
   rate, duration, compute/cost expectation, and validation evidence.
5. **External processing or sharing**: state provider, uploaded asset scope,
   account/session requirement, data retention, pricing/quota, retrieval
   location, and publication destination. Each external transfer or publish
   action needs its own approval.

## Safe Defaults

- Start with placeholders, synthetic assets, or user-provided non-sensitive
  samples.
- Use a dedicated temporary project and output path where practical.
- Keep source assets, generated media, credentials, and account/session data
  out of logs, templates, and review bundles.
- Prefer an inspectable local preview before a final render.
- Stop if licensing, asset provenance, privacy classification, output
  destination, compute cost, or provider retention is unknown.

## Runtime Categories

### Local Code Renderer

Remotion-style, HTML/CSS/JS, FFmpeg, browser automation, Node, Docker, and
similar runtimes may require installation, local file reads, child processes,
GPU/CPU consumption, temporary output, and dependency scripts. None is
assumed present, safe, private, or compatible. Record the exact requested
capability rather than approving a broad tool category.

### External Media Provider

Cloud rendering, generation, transcription, voice, asset libraries, and
hosted previews can transfer data outside the machine or consume paid quota.
They require an explicit provider and data-transfer approval. Do not silently
fall back from a local renderer to an external provider.

## Stop Conditions

Stop and return to the render handoff when:

- the user has approved planning but not the runtime stage
- a required dependency, installation source, or project path is unclear
- private, client, licensed, biometric, voice, or regulated material may be
  processed outside the approved boundary
- a request would upload, publish, post, or spend funds without separate
  approval
- the requested process cannot be limited to the agreed renderer, inputs, and
  output location

## Evidence Before Completion

After an approved preview or render, record the runtime version, approved
inputs, output path, settings, validation result, known limitations, and the
owner responsible for output removal. Do not claim deterministic output when
the runtime, provider, assets, fonts, browser, or hardware are not pinned.
