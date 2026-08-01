# Video Skill Integration Catalog

This catalog is an original capability map for `ai-video-production`. It does
not install, load, execute, import, or endorse an external repository. A name
in this file is a planning reference only; it is never a trigger for a local
scan, provider call, dependency installation, asset upload, render, or post.

## Core, Documentation-Only Capabilities

These capabilities belong to this skill's planning surface. Their outputs are
draft artifacts and each remains human-approved before an external effect.

| Capability | Draft output | Required review boundary |
| --- | --- | --- |
| `video-understand` | timestamped content and risk map | It is a clip/editing clue, not copyright, factual, or identity determination. |
| `video-clip-pipeline` | context-preserving candidate groups | Record pre-roll and post-roll; reject decontextualised quote-only clips. |
| `video-edit` | EDL, trim rationale, sequence, format plan | A plan cannot modify media or add effects automatically. |
| `video-caption-generator` | VTT/SRT-style caption draft and low-confidence list | Human spot-check names, technical terms, and numbers. |
| `video-translate` | timed parallel subtitle draft and glossary | Human language/brand review is required. |
| `short-form-pipeline` | platform delivery packet | Publication authority is always human-only. |
| `storyboard-and-prompt-plan` | shot prompts and prompt-to-scene map | Prompts are drafts; no provider call or media generation. |
| `motion-render-plan` | renderer-neutral composition and preview handoff | A renderer selection is not installation or render authority. |

## Named External Candidates: Disposition

Each disposition concerns integration into this skill, not the quality or
popularity of the project. Re-check the exact commit, licence, dependencies,
and current terms before a future adapter proposal.

| Candidate | What can be adopted now | Disposition | Why it is not embedded |
| --- | --- | --- | --- |
| HyperFrames | inspectable HTML/CSS composition and preview-first pattern | `ADAPT_PATTERN_ONLY` | Its runtime needs Node, FFmpeg, browser automation, local reads, child processes, and output writes. |
| Remotion | reusable, data-driven composition and render-contract pattern | `ADAPT_PATTERN_ONLY` | It is a Node/React renderer with a separate commercial-eligibility licence check. |
| Video Use | transcript-to-EDL / review-before-edit sequence | `ADAPT_PATTERN_ONLY` | Its documented setup asks for FFmpeg, a cloned repo, an optional transcription key, and writes outputs beside source footage. |
| VideoCut | Chinese spoken-word editing requirements | `NEEDS_MANUAL_SECURITY_REVIEW` | Exact upstream identity, licence, install behavior, and runtime effects must be verified before it becomes an adapter. |
| Seedance 2 skill | storyboard prompt structure only | `ADAPT_PATTERN_ONLY` | A third-party prompt skill is not the Seedance renderer and cannot authorize generation, account use, or paid credits. |
| Gen Media | none | `UNVERIFIED_NAME` | The name does not yet identify one canonical open-source project, licence, or data boundary. It stays outside the catalog. |

## Default-Disabled Adapter Contract

A future adapter for any candidate must be a separately reviewed package with:

- immutable source identity and licence/provenance record
- declared dependencies, installation scripts, processes, network, accounts,
  credentials, input paths, output paths, temporary files, cost, and retention
- one-run, least-privilege approval card; no background watch, sync, memory,
  telemetry, or automatic update
- local-only mode described separately from every external transfer; no cloud
  fallback when the local path is unavailable
- synthetic fixtures for EDL, captions, translations, and render handoffs
- output state `DRAFT_FOR_HUMAN_REVIEW`; no automatic rendering, upload, or
  publication

Do not add a provider, MCP server, API key, package dependency, renderer,
source-media access, or publication integration to the core skill merely
because a keyword matches this catalog.
