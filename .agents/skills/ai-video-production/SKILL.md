---
name: ai-video-production
description: Use for AI-assisted video or animation planning: video briefs, scripts, storyboards, shot lists, visual prompts, asset manifests, preview plans, and render handoffs. Do not use for general repository engineering or automatic rendering, uploading, publishing, or posting.
version: 0.2.1
repo: https://github.com/Q20396/codex-long-horizon-skill
skill_id: ai-video-production
update_channel: stable
---

# AI Video Production

Use this optional skill when a task involves planning or producing AI-assisted video, animation, image-based storyboards, thumbnails, social shorts, explainers, or code-rendered media.

This skill is documentation-first. It may guide scripts, storyboards, shot lists, asset manifests, preview plans, and render handoffs, but it must not automatically render, upload, publish, or post media.

## Routing Boundaries

- "Design a storyboard and shot list" -> use `ai-video-production`.
- "Create a render handoff and visual asset plan" -> use `ai-video-production`.
- "Debug a multi-file Remotion rendering bug" -> use
  `long-horizon-engineering`.
- "Migrate a video-rendering codebase" -> use `long-horizon-engineering`.
- Explicit invocation takes precedence when the requested workflow is safe and
  applicable.

Do not use this skill for general software engineering, repository migrations,
backend debugging, CI repair, or production deployment unless the user is
specifically asking for video planning artifacts.

## Example Prompts

- Use the ai-video-production skill. Create a 60-second vertical video brief,
  script outline, storyboard, shot list, asset manifest, and render handoff
  using placeholder assets only.
- Use the ai-video-production skill. Turn this article into visual prompts and
  a storyboard, but do not render or upload anything.
- Use the ai-video-production skill. Analyze this supplied text, identify which
  concepts deserve diagrams or a storyboard, and prepare visual prompts without
  generating media.
- Use the ai-video-production skill. Build a design system for this short-form
  explainer and require human approval before render.

## Validation Guidance

Before claiming a video plan is ready, verify that the brief, script,
storyboard, shot list, asset manifest, render handoff, privacy notes, licensing
notes, and human approval gate are present. For rendered projects, preview and
inspect outputs before publication.

## Failure Recovery Strategy

If assets are missing, source text is unclear, private material appears, or a
render step is not approved, stop and produce a handoff with what is known,
what remains blocked, and the next safe approval-gated action.

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

For projects that need a consistent visual system, consult
`references/design-system-for-video.md`. Use `templates/DESIGN.md` and
`templates/visual-style-tokens.md` before generating prompts when visual
consistency matters. Do not clone protected brand systems unless the user owns
rights or explicitly asks for internal/inspirational analysis.

For client-provided text, identify the central idea first, then place it in the
relevant industry context before generating visuals. Summarize the audience,
industry vocabulary, common visual language, credible metaphors, and claims
that need fact-checking. Use the industry-aware summary to create image and
video prompts. Do not copy private client wording into reusable prompts, logs,
or public examples unless explicitly approved.

For knowledge articles, method notes, scripts, reports, or abstract
explanations, consult `references/text-to-visual-analysis.md`. Preserve source
meaning, extract cognitive anchors, decide which ideas genuinely benefit from
visualization, distinguish diagrams, explanatory graphics, storyboards, image
prompt concepts, and text-only sections, then stop at a proposal until the user
approves generation.

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

## Safe Update / Self-Check Protocol

When the user asks to check for updates, update skills, upgrade skills, or
compare installed skills with GitHub, first ask for explicit permission to
access:

`https://github.com/Q20396/codex-long-horizon-skill`

Explain that this first permission is only for checking updates and temporarily
downloading or cloning the repository. During the check phase, do not install,
replace, delete, or modify installed skills.

After permission, compare installed local skills with the GitHub version.

Installed local paths:

- `~/.agents/skills/long-horizon-engineering`
- `~/.agents/skills/ai-video-production`

Remote repo paths:

- `.agents/skills/long-horizon-engineering`
- `.agents/skills/ai-video-production`

Summarize:

1. local version
2. remote version
3. changed files
4. added files
5. removed files
6. important instruction changes
7. risk level
8. upgrade recommendation
9. backup path that would be used
10. rollback plan

Ask for explicit second approval before applying any update. If applying an
update, create a timestamped backup first, replace only the selected approved
skill folder, validate that `SKILL.md` exists, validate that the folder is not
empty, validate there is no duplicated nested path such as
`.agents/skills/.agents/skills`, report exact files changed, and print the
rollback command. If anything fails, restore from backup where possible.

Never silently update. Never update all skills unless the user explicitly
approves all skills. Prefer check-only mode unless the user clearly asks to
apply an update.

## Text-To-Visual Mapping

For each major script beat, plan a corresponding visual beat:

- First summarize the whole source text into a visual brief before writing
  prompts.
- For client text, extract the central idea and relevant industry context before
  choosing visual metaphors, style, or generated assets.
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
- Use licensing fields and approval checklists for production handoff only; do
  not provide definitive copyright, rights-clearance, or legal conclusions.

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

For a documented comparison of renderer fit, privacy, licensing, previews,
cost, and approval gates, use `references/renderer-selection.md` and complete
`templates/RENDER_EVIDENCE_TEMPLATE.md` before requesting final-render
approval. Selecting a tool does not authorize installation, rendering, provider
use, upload, publication, or spending.

## Manual Media Skill Upgrade Scan

When asked to check related video or image skills, Codex may run
`scripts/scan_top_media_skills.py` to inspect the top public GitHub repositories
for video/image generation skill signals. The scan should self-check code and
workflow signals, suggest possible optimizations, explain upgrade impact, and
produce customer upgrade options only. Do not copy external code, prompts,
templates, or media. Do not auto-upgrade. The user must manually choose whether
to click a PR, request an original change, copy reviewed material, or skip.

## Reference Files

- `references/remotion-patterns.md`
- `references/hyperframes-patterns.md`
- `references/imagegen-patterns.md`
- `references/video-production-pipeline.md`
- `references/privacy-media-policy.md`
- `references/licensing-notes.md`
- `references/design-system-for-video.md`
- `references/text-to-visual-analysis.md`
- `references/renderer-selection.md`

## Templates

- `templates/VIDEO_BRIEF_TEMPLATE.md`
- `templates/DESIGN.md`
- `templates/visual-style-tokens.md`
- `templates/brand-system-for-video.md`
- `templates/TEXT_TO_VISUAL_ANALYSIS_TEMPLATE.md`
- `templates/STORYBOARD_TEMPLATE.md`
- `templates/SHOT_LIST_TEMPLATE.md`
- `templates/ASSET_MANIFEST_TEMPLATE.md`
- `templates/RENDER_HANDOFF_TEMPLATE.md`
- `templates/RENDER_EVIDENCE_TEMPLATE.md`

## Scripts

- `scripts/scan_top_media_skills.py`
