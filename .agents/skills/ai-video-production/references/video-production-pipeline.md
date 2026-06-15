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

## Step 4: Script

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

## Step 5: Storyboard

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
- Motion or transition
- Narration
- On-screen text
- Asset IDs
- Approval notes

## Step 6: Asset Plan

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

## Step 7: Choose Tool Path

Use Remotion-style production for maintainable engineering, reusable components, data-driven videos, variants, and precise render contracts.

Use HyperFrames-style production for fast agent-authored HTML animation, previewable single-project compositions, lint-before-render loops, and manual local rendering.

Use ImageGen for covers, thumbnails, storyboard frames, scene backgrounds, visual assets, and image-to-video seed frames.

Hybrid paths are normal: for example, generate storyboard images, assemble a HyperFrames preview, then later migrate repeatable work to a Remotion-style system.

## Step 8: Preview

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

## Step 9: User Approval

Require approval before:

- Final render
- Upload to a third-party service
- External publication
- Use of sensitive source material
- Use of paid generation or paid render services

## Step 10: Render

The agent may prepare render commands or settings, but should not execute final render unless the user explicitly approves.

Render handoff should include:

- Tool path
- Preview location
- Command or UI steps
- Expected output path
- Inputs and assets
- Known issues
- License and privacy checklist

## Step 11: Export

Document export settings:

- Container and codec
- Resolution
- Frame rate
- Audio format
- Caption/subtitle output
- Thumbnail or cover
- Filename convention

## Step 12: Optional Publish Plan

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
