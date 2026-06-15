# Remotion-Style Patterns

Sources reviewed:

- https://github.com/remotion-dev/remotion
- https://www.remotion.dev/docs/composition
- https://www.remotion.dev/docs/cli/render
- https://github.com/remotion-dev/remotion/blob/main/LICENSE.md

These notes capture generalizable patterns only. Do not copy Remotion source code or examples into this repository.

## Video As Code

Remotion treats video as a programmatic artifact. The useful pattern is to make video output reproducible from source files, data, timing parameters, and assets. This makes video production closer to software delivery: versioned, testable, reviewable, and repeatable.

Use this pattern when the project needs:

- Reusable visual systems
- Many variants from shared data
- Precise timing and dimensions
- Reviewable code diffs
- Batch exports
- Integration with product, marketing, or reporting data

## Composition Registry

A Remotion-style project registers renderable compositions with stable IDs, dimensions, frame rates, durations, and default props. Treat the registry as the project's render catalog.

General pattern:

- `composition_id`: stable name used by preview and render tooling
- `width` and `height`: target output dimensions
- `fps`: timing resolution
- `duration_frames`: exact duration
- `default_props`: JSON-serializable inputs
- `schema`: optional validation layer for user-editable inputs

Keep composition IDs human-readable and platform-specific when needed, such as `vertical-short-1080x1920` or `product-demo-16x9`.

## Scene Components

Break a video into scene components instead of one large timeline. Scenes should own a clear slice of time and a small visual responsibility.

Useful component types:

- Title scene
- Problem or setup scene
- Data visualization scene
- Quote or caption scene
- Product UI scene
- Image montage scene
- Call-to-action scene
- End card

Reusable scene components should accept data and style tokens rather than hard-coded copy.

## Data-Driven Rendering

Data-driven video is the strongest Remotion-style pattern. Keep scripts, captions, chart data, asset paths, brand settings, and timing in structured files. The render code reads the structure and produces a deterministic output.

Recommended inputs:

- Script segments
- Scene list
- Caption timing
- Brand tokens
- Image and video asset manifest
- Render profile
- Localization or platform variants

Prefer JSON, YAML, or typed constants over unstructured prose for render parameters.

## Captions, Overlays, And Transitions

Treat captions and overlays as first-class timeline layers. Captions should be aligned to narration or scene timing and checked for readability on the target platform.

Transition guidance:

- Keep transitions purposeful and short.
- Use consistent transition families across a project.
- Avoid transitions that obscure captions or important product details.
- Record transition assumptions in the storyboard or shot list.

## Batch Rendering

Batch rendering works best when composition inputs are isolated from render logic. A campaign can render many videos by varying props, data files, locale, aspect ratio, or asset sets.

Use cases:

- Personalized summaries
- Product release variants
- Multi-language explainers
- Social platform aspect-ratio exports
- Data report videos

## Render Parameters

Document render parameters before handoff:

- Composition ID
- Entry point or project path
- Output path
- Width, height, fps, duration
- Props file or serialized props
- Codec/container assumptions
- Audio mix source
- Environment variables
- Expected render time or cost

Do not run final render automatically. Put the command or tool step in the handoff and wait for approval.

## Testing And Preview

Preview before render. For engineering-heavy videos, use quick still frames, short segment previews, or browser playback before spending time on a full export.

Suggested checks:

- Composition loads
- Props validate
- Missing assets fail early
- Key frames are readable
- Captions do not overlap important content
- Audio and visual timing align
- Final frame has no abrupt cut unless intentional

## Licensing Caution

Remotion is source-available with special licensing conditions, including company-license requirements for some organizations. Always check the current license before adopting Remotion itself. This skill only documents general patterns and should not be treated as legal advice.
