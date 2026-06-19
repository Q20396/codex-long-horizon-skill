# HyperFrames-Style Patterns

Sources reviewed:

- https://github.com/heygen-com/hyperframes
- https://github.com/coleam00/hyperframes-ai-video-generation

These notes capture generalizable workflow and architecture patterns only. Do not copy HyperFrames source code, templates, or README text into this repository.

## HTML-Native Composition

A HyperFrames-style workflow defines video in regular web files: HTML, CSS, JavaScript, and local assets. The strongest pattern is that the composition can be opened and inspected like a web page before it becomes a video.

This is useful when:

- Agents can author simple HTML more reliably than a full video framework.
- The team wants direct browser preview.
- The animation can be expressed as DOM, CSS, canvas, SVG, WebGL, or embedded media.
- The final render should come from the same local source files as the preview.

## Agent-Friendly Authoring

HTML-native video gives an agent a small, visible artifact to edit:

- `index.html` for structure and timing metadata
- `styles.css` for layout and visual design
- `script.js` for animation timelines and interaction-free playback
- `assets/` for images, audio, fonts, and video snippets
- `manifest.json` or similar for source tracking

Prefer clear IDs, semantic sections, and simple timeline anchors so both humans and agents can reason about the file.

## Previewable `index.html`

The preview is part of the production contract. A reviewer should be able to open the composition locally, seek or replay it, and inspect whether the story, layout, and timing work before render.

Preview checks:

- Correct aspect ratio and safe areas
- No missing assets
- Text readable at target resolution
- Animations complete before scene cuts
- Captions remain visible
- Audio starts and ends as expected

## Composition Metadata

For an HTML-native handoff, record the fields that make the browser preview and
render refer to the same artifact:

- local project path
- `index.html` path
- composition ID or stage ID
- width and height
- duration
- fps or frame-stepping assumption
- asset root
- audio tracks
- animation adapter or timeline mechanism
- lint or inspect result
- preview URL or local preview command

Prefer explicit timing metadata or data attributes over hidden timing embedded
only in prose. The agent may describe a render command, but final render remains approval-gated.

## Deterministic Rendering

A deterministic render pipeline should seek exact frames, capture the browser state, and encode with stable settings. The general pattern is:

1. Source files define the composition.
2. A preview validates the composition.
3. A linter or inspector checks structure and asset references.
4. The renderer captures frames from a headless browser.
5. Video encoding produces the export.

Avoid randomness unless the seed is explicit and recorded.

## Lint Before Render

Linting is a cheap gate before expensive rendering. A HyperFrames-style workflow should fail early on:

- Missing composition metadata
- Invalid dimensions or duration
- Missing audio, image, font, or video assets
- Timeline gaps that were not intentional
- Unsupported remote dependencies
- Non-seekable or wall-clock-only animation that cannot be frame-sampled
- Oversized assets
- Broken animation adapters

## Manual Render Gate

The reviewed HyperFrames AI workflow uses automation to research, draft, generate audio, edit HTML, lint, and open a preview, while keeping final render manual. Preserve that separation.

The agent may prepare:

- Preview URL
- Expected output path
- Render command
- Asset manifest
- Known issues
- Approval checklist

Do not silently install runtime requirements, run package-manager scripts, or
render the final MP4 without approval. If Node, FFmpeg, browser automation, or Docker is required, state that in the handoff.

The human decides whether to render.

## Animation Layers

HyperFrames-style projects can combine familiar web animation layers:

- CSS transitions and keyframes for simple movement
- GSAP-style timelines for sequenced animation
- Lottie for vector animation assets
- Three.js for 3D scenes
- Canvas or SVG for charts and custom visuals
- Web Animations API or adapter-based timelines for frame seeking

Keep each animation layer deterministic and seekable.

## When This May Be Easier Than Remotion

Prefer HyperFrames-style authoring when the project is a short, one-off, or agent-generated video and the primary need is an inspectable HTML artifact. It is often easier for agents to modify copy, layout, colors, animation anchors, and asset references in a single browser-previewable project than to reason through a larger React render system.

Prefer Remotion-style authoring when the project needs a durable component system, many data-driven variants, typed props, package-level tests, or deeper engineering integration.
