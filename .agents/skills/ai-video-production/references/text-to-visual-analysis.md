# Text To Visual Analysis

Use this protocol when turning supplied text into a visual explanation plan for
diagrams, explanatory graphics, storyboard sequences, image-prompt concepts, or
text-only recommendations.

This protocol is analysis and planning only. It must not generate images or video,
call an image or video model, upload media, publish media, spend credits, or
send sensitive material to an external provider.

## Core Contract

Required defaults:

- Analysis status: PROPOSAL_ONLY
- User decision: PENDING
- Media generated: NO
- Media uploaded: NO
- Media published: NO
- External provider invoked: NO
- Credits or quota consumed: NO

Later media generation requires a separate explicit user approval with the exact
selected items, provider or tool confirmation, privacy review, cost or quota awareness,
and a separate execution step.

## Workflow

### 1. Confirm Source Scope

Identify the supplied text, allowed source material, excluded source material,
audience, platform, format, privacy restrictions, and licensing restrictions.

Do not access private documents, folders, screenshots, connected services, or
external sources unless the user explicitly supplies or approves them.

### 2. Analyze The Complete Text

Read the complete supplied text before proposing visuals. Summarize:

- central idea
- source meaning that must be preserved
- key claims
- audience
- learning objective
- emotional tone
- structure or narrative arc
- domain or industry context
- unsupported facts that must not be invented
- speculative or uncertain content
- privacy or licensing constraints

Do not generate prompts from isolated sentences when the output is meant to
represent the whole source.

### 3. Extract Cognitive Anchors

Identify the concepts most worth remembering:

- core thesis
- key concept
- process step
- structure or framework
- cause and effect
- comparison or tradeoff
- timeline or evolution
- system layer
- decision point
- warning or constraint

Use a small set of high-value anchors. Do not visualize every paragraph by default.

### 4. Select Visualization Candidates

For each candidate, record:

- source anchor
- audience
- visual objective
- expected learning value
- why a visual helps
- why it may not need a visual
- accuracy constraints
- privacy and licensing constraints

Recommend text-only treatment when the idea is already clear, too nuanced for a
safe visual, unsupported by evidence, or too sensitive to visualize.

### 5. Distinguish Output Types

Separate proposed outputs into:

- diagrams for structure, process, systems, timelines, and relationships
- explanatory graphics for memorable concepts, comparisons, and summaries
- storyboard sequences for timed video beats
- image-prompt concepts for generated stills or seed frames
- text-only sections that should remain prose or narration

Do not blur these categories. A storyboard beat may reference a diagram or image
prompt, but it should still state its role clearly.

### 6. Draft Prompt And Handoff Cards

For visual candidates that pass review, draft cards with:

- card ID
- output type
- source anchor
- rationale
- audience
- visual objective
- expected learning value
- subject
- composition
- style
- motion if relevant
- aspect ratio
- text policy
- negative constraints
- privacy notes
- licensing notes
- approval status

If a visual is speculative, label it conceptual and avoid documentary or
evidence-like wording.

## Approval Gate

Stop at the analysis plan unless the user explicitly approves generation.

Before any later generation or render, confirm:

- exact selected cards
- provider or tool
- cost or quota impact
- source material approval
- privacy review
- output destination
- whether upload or publication is allowed

## Safety Notes

Do not store secrets, API keys, private client data, legal evidence, family
information, medical information, financial account details, identity
documents, private correspondence, confidential source content, private
absolute paths, raw prompts from private sessions, or copyrighted source
material in reusable examples or public artifacts.

Use generic placeholders when examples are needed.
