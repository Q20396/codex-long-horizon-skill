# Video Production Pipeline

## Inputs And Outputs

Input may be an article, idea, document summary, topic, URL, product note, dataset summary, or user-provided brief.

Output should be a production package:

- Video brief
- Script
- Storyboard
- Shot list
- Asset manifest
- Preview plan
- Render handoff
- Approval checklist

## Step 1: Clarify Audience And Platform

Capture:

- Target audience
- Platform: TikTok, YouTube Shorts, YouTube, LinkedIn, website, product demo, presentation
- Aspect ratio and duration
- Tone
- Call to action
- Accessibility needs
- Brand constraints
- Source boundaries

## Step 2: Choose Format

Common formats:

- Vertical short
- Horizontal explainer
- Carousel-to-video
- Presentation video
- Product demo
- Data story
- Animated storyboard
- Thumbnail and cover package

## Step 3: Set Research Boundaries

Define what may be read, summarized, quoted, or transformed. For sensitive sources, ask before reading. Prefer user summaries or metadata when possible.

Record:

- Approved sources
- Excluded sources
- Citation needs
- Privacy restrictions
- Claims requiring fact check

## Step 4: Analyze Source Text

Before writing image or video prompts, read all provided text and produce a
short visual brief. Do not generate media from isolated sentences unless the
user explicitly asks for a single-line prompt.

Capture:

- Core message
- Central idea of client-provided text
- Relevant industry or domain context
- Target audience expectations
- Industry vocabulary and claims that need checking
- Common visual language for the industry
- Key claims or facts
- Reasonable inferences
- Speculative or fictional elements
- Emotional tone
- Narrative arc
- Visual motifs
- Credible industry metaphors or systems
- Characters, objects, places, systems, or symbols
- Required exclusions, privacy limits, and licensing constraints
- What the generated media should make the viewer understand

Use this analysis as the basis for script beats, storyboard scenes, visual
prompts, and asset plans.

For client-provided text, summarize rather than copy. Keep proprietary wording,
client names, private documents, screenshots, contracts, legal evidence,
financial details, family information, and confidential research out of public
or reusable prompts unless the user explicitly approves the exact content.

## Step 5: Script

Write a script that fits the platform and duration.

Include:

- Hook
- Core beats
- Narration
- On-screen text
- Caption plan
- Timing estimate
- Call to action

Keep narration and visual text separate. Social video text should be short enough to read on mobile.

## Step 6: Storyboard

Turn the script into scenes or shots.

For text-to-video tasks, each scene should translate the text's meaning into a
matching visual idea. Avoid making the whole video a sequence of plain text
cards unless the user explicitly asks for that style. When footage is not
available, use safe original animation, abstract motion graphics, diagrams,
maps, system layers, icon motion, interface mockups, or symbolic cinematic
scenes.

Each storyboard row should include:

- Scene number
- Time range
- Text beat or idea being visualized
- Visual description
- Visual generation prompt or prompt file when media will be generated
- Motion or transition
- Narration
- On-screen text
- Asset IDs
- Approval notes

## Step 7: Asset Plan

Plan assets before generation or render.

Asset sources:

- User-provided public assets
- User-approved private assets
- Generated images
- Generated or recorded voiceover
- Licensed stock assets
- Original abstract animation
- Original motion graphics
- Original diagrams
- Generic interface mockups
- Product screenshots
- Placeholder assets

Track every asset in the manifest.

For generated image or video assets, write the prompt before creating the
file. The prompt should include subject, scene, style, motion if applicable,
composition, aspect ratio, duration for video, negative constraints, privacy
constraints, and licensing notes. Store the prompt text or a prompt file path in
the asset manifest.

## Step 8: Choose Tool Path

Before choosing a path, compare reproducibility, preview workflow, privacy,
licensing, cost, and the human approval gate with
`references/renderer-selection.md`. Tool selection is planning only and does
not authorize installation, provider use, rendering, upload, or publication.

Use Remotion-style production for maintainable engineering, reusable components, data-driven videos, variants, and precise render contracts.

Use HyperFrames-style production for fast agent-authored HTML animation, previewable single-project compositions, lint-before-render loops, and manual local rendering.

Use ImageGen for covers, thumbnails, storyboard frames, scene backgrounds, visual assets, and image-to-video seed frames.

Hybrid paths are normal: for example, generate storyboard images, assemble a HyperFrames preview, then later migrate repeatable work to a Remotion-style system.

## Step 9: Preview

Preview before render.

Preview checks:

- Story clarity
- Visuals match the script meaning
- Captions support the visuals instead of replacing them
- Timing
- Readability
- Caption placement
- Asset correctness
- Audio pacing
- Brand fit
- Sensitive-content redaction
- Missing license or source notes

## Step 10: User Approval

Require approval before:

- Final render
- Upload to a third-party service
- External publication
- Use of sensitive source material
- Use of paid generation or paid render services

## Step 11: Render

The agent may prepare render commands or settings, but should not execute final render unless the user explicitly approves.

Render handoff should include:

- Tool path
- Preview location
- Command or UI steps
- Expected output path
- Inputs and assets
- Known issues
- License and privacy checklist

Complete `templates/RENDER_EVIDENCE_TEMPLATE.md` before asking for final-render
approval.

## Step 12: Export

Document export settings:

- Container and codec
- Resolution
- Frame rate
- Audio format
- Caption/subtitle output
- Thumbnail or cover
- Filename convention

## Step 13: Optional Publish Plan

Prepare a plan, not an automatic post:

- Platform
- Title
- Description
- Hashtags or tags
- Thumbnail
- Alt text
- Captions
- Schedule
- Approval owner
