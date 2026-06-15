# Image Generation Patterns

Sources reviewed:

- https://developers.openai.com/api/docs/guides/image-generation
- Public patterns from open-source image-generation studios such as node/workflow UIs, prompt galleries, asset browsers, parameter panels, and local generation frontends.

These notes are general workflow guidance. Do not treat "ImageGen" as one repository or one product.

## Classify "ImageGen" References

When a request says "ImageGen", first classify the likely meaning:

- OpenAI image generation or API workflow
- Small DALL-E-style web app
- Local Stable Diffusion-style UI
- Node-based workflow studio
- Larger image/video generation studio
- Internal project with the same name

Ask or infer from context before assuming a provider.

## Prompt Schema

Use a structured prompt schema so outputs are reviewable and reproducible.

Suggested fields:

- `subject`: what must appear
- `purpose`: why the image is needed
- `audience`: who will see it
- `format`: cover, thumbnail, storyboard frame, background, icon, reference
- `style`: visual direction or preset
- `composition`: camera, layout, focal point, depth, crop
- `lighting`: mood, contrast, time of day
- `palette`: color constraints
- `text_policy`: no text, exact text, or editable text added later
- `negative_constraints`: what to avoid
- `aspect_ratio`: target platform shape
- `size`: requested pixel output when provider supports it
- `references`: approved input assets or descriptions
- `provenance`: model, provider, date, prompt version, seed if available

## Style Presets

Style presets reduce prompt drift across a campaign. Keep presets as reusable descriptions, not copied output.

Example preset categories:

- Product UI editorial
- Clean instructional diagram
- Cinematic macro object
- Warm documentary still
- Flat social carousel
- Minimal presentation background
- Hand-drawn storyboard frame
- Photoreal lifestyle scene

Presets should include typography handling, palette guidance, texture level, and realism level.

## Negative Constraints

Negative constraints help protect brand, privacy, and usability.

Common constraints:

- No private people or likenesses unless approved
- No identity documents or confidential screens
- No logos unless owned or licensed
- No legible text unless the model is being asked for exact text and the result will be reviewed
- No medical, financial, or legal records
- No misleading evidence-like imagery
- No copyrighted character or artist imitation requests unless clearly licensed

## Size And Aspect Ratio

Choose aspect ratio before generation:

- Vertical short: 9:16
- Horizontal explainer: 16:9
- Square social: 1:1
- Storyboard panel: match final video frame
- Thumbnail: platform-specific, often horizontal
- Presentation video: match slide export ratio

Record size, crop, and safe-area assumptions in the asset manifest.

## Asset Manifest

Every generated image should be tracked.

Minimum fields:

- Asset ID
- File path or storage location
- Prompt version
- Provider and model
- Generation or edit mode
- Source/reference assets used
- Approval status
- License or usage constraints
- Sensitive-content status
- Intended scene or shot
- Replacement notes

## Image Gallery

Use a gallery to compare generated candidates. Keep discarded candidates out of final handoff unless needed for audit.

Useful gallery metadata:

- Candidate ID
- Prompt variant
- Strengths
- Issues
- Selected or rejected
- Required edits
- Reviewer notes

## Model And Provider Abstraction

Do not hard-code a provider into the production plan unless the user has chosen one. Use a provider abstraction in docs and manifests:

- Provider
- Model
- Endpoint or tool
- Input modes: text-to-image, image edit, image-to-video, text-to-video
- Supported sizes/aspect ratios
- Privacy and retention posture
- Cost or quota notes
- Local vs external processing

OpenAI's current image docs distinguish direct image generation, image edits, and Responses API image generation inside multi-step workflows. Use that distinction when planning provider calls.

## Generated Image Provenance

Generated media should be traceable. Record enough provenance to answer:

- What generated this?
- What prompt and settings were used?
- Were private inputs used?
- Who approved it?
- Where is it allowed to appear?
- Is it final, draft, or reference-only?

## Generated Images Vs Local Or Private Assets

Use generated images when:

- The scene is generic or illustrative.
- A storyboard frame is enough.
- A thumbnail or background needs exploration.
- The source content is public or user-approved.

Use local/private assets only when:

- The user explicitly approves them.
- The asset is necessary to meet the brief.
- Storage, upload, retention, and publication boundaries are clear.

Prefer placeholders when approval is missing.
