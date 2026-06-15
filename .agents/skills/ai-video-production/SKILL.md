---
name: ai-video-production
description: Use this skill for planning and producing AI-assisted videos, animated explainers, image-based storyboards, short-form social videos, and code-rendered video projects using Remotion-style, HyperFrames-style, or image-generation workflows.
---

# AI Video Production

Use this optional skill when a task involves planning or producing AI-assisted video, animation, image-based storyboards, thumbnails, social shorts, explainers, or code-rendered media.

This skill is documentation-first. It may guide scripts, storyboards, shot lists, asset manifests, preview plans, and render handoffs, but it must not automatically render, upload, publish, or post media.

When turning text into video, translate the meaning of the text into matching
visuals. Do not default to plain caption cards. If real footage or approved
assets are unavailable, use original abstract animation, motion graphics,
diagrams, symbolic scenes, interface mockups, kinetic typography, or other
safe generated visuals that express the idea.

When creating image or video files, generate them from explicit visual prompts
that describe the intended subject, style, motion, composition, aspect ratio,
and constraints. Record the prompt or prompt file in the asset manifest so the
result can be reviewed and reproduced.

Before generating images or video from text, analyze all provided text first.
Summarize the core message, key claims, emotional tone, narrative structure,
visual motifs, required facts, speculative boundaries, and unsafe or excluded
content. Use that summary to create the system-facing image or video prompts.
Do not generate media from isolated sentences without understanding the full
context.

## Workflow

1. Brief
2. Research boundaries
3. Script
4. Storyboard
5. Asset plan
6. Tool choice
7. Preview plan
8. Render handoff
9. Human approval gate

## Required Gate

Before final render, upload, publication, or external sharing, require explicit human approval. The handoff should show what will be rendered, what source assets are used, where outputs will be stored, and what command or tool action the human may run.

## Text-To-Visual Mapping

For each major script beat, plan a corresponding visual beat:

- First summarize the whole source text into a visual brief before writing
  prompts.
- Convert claims into diagrams, timelines, maps, charts, system layers, or
  before/after comparisons when appropriate.
- Convert abstract ideas into visual metaphors, animation, spatial layouts,
  icon motion, or cinematic symbolic scenes.
- Use captions as support, not as the whole video.
- If a scene is speculative, make the visual feel conceptual and avoid implying
  that it is documentary footage or confirmed evidence.
- Prefer generic placeholders when assets are missing or unapproved.
- For generated media, write a prompt for each image, video clip, animated
  scene, or reusable visual asset before producing the file.
- Keep prompts aligned with the approved script, storyboard, privacy
  boundaries, and licensing constraints.
- Do not use copyrighted, private, client, family, legal, medical, financial,
  identity, or confidential material without explicit approval.

## Privacy Rules

- Do not use private client, family, legal, medical, financial, identity, correspondence, or confidential business material without explicit approval.
- Prefer metadata, summaries, and user-provided descriptions before reading sensitive content.
- If sensitive source content is needed, ask first and explain why.
- Do not upload private assets to external services unless explicitly approved.
- Do not store sensitive content in reusable templates, logs, memory, storyboard, asset manifest, or handoff unless explicitly approved.
- Use placeholders and generic descriptions when approval is absent.

## Licensing Rules

- Do not copy external repository code.
- Do not copy large README sections or project prose.
- Learn general engineering patterns only.
- Check licenses before reusing code, assets, templates, music, fonts, voices, or model outputs.
- Remotion has special licensing considerations; verify current terms before using it in a commercial setting.

## Tool Choice Guide

- Choose a Remotion-style workflow for maintainable engineering, reusable React scene components, data-driven variants, batch rendering, precise frame timing, or long-lived video systems.
- Choose a HyperFrames-style workflow for fast agent-authored HTML/CSS/JS animation, browser preview, lint-before-render loops, and manual rendering from an inspectable `index.html`.
- Choose image generation for covers, thumbnails, storyboard frames, scene backgrounds, visual assets, style exploration, and image-to-video seed frames.

## Reference Files

- `references/remotion-patterns.md`
- `references/hyperframes-patterns.md`
- `references/imagegen-patterns.md`
- `references/video-production-pipeline.md`
- `references/privacy-media-policy.md`
- `references/licensing-notes.md`

## Templates

- `templates/VIDEO_BRIEF_TEMPLATE.md`
- `templates/STORYBOARD_TEMPLATE.md`
- `templates/SHOT_LIST_TEMPLATE.md`
- `templates/ASSET_MANIFEST_TEMPLATE.md`
- `templates/RENDER_HANDOFF_TEMPLATE.md`
