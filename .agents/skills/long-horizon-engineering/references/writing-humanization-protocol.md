# Writing Humanization Protocol

Use this protocol for PR summaries, README edits, documentation, client
handoffs, reports, scripts, and client-facing copy when the user asks for
clearer, more natural, or less AI-like writing.

This protocol must not be used to hide authorship, fabricate personal style,
misrepresent provenance, or make unsupported claims sound more persuasive.

## Workflow

1. Identify audience and purpose.
2. If the user provides a writing sample, extract voice traits:
   - sentence rhythm
   - paragraph shape
   - vocabulary level
   - punctuation habits
   - transition style
   - directness/formality
3. Audit AI-like patterns:
   - generic transitions
   - inflated adjectives
   - vague attribution
   - repetitive sentence structure
   - over-polished marketing tone
   - filler phrases
   - unsupported certainty
4. Rewrite while preserving meaning, facts, constraints, and coverage.
5. Re-check factual claims, technical terms, caveats, and scope.

## Modes

| Mode | Use For | Notes |
| --- | --- | --- |
| technical-neutral | PRs, engineering docs, changelogs | Clear and direct; avoid hype |
| client-friendly | client handoffs, proposals | Natural but precise |
| Chinese concise | Chinese user-facing output | Keep technical identifiers unchanged |
| marketing but factual | landing copy, video copy | Persuasive but evidence-bounded |
| reviewer-facing | PR reviews, audit notes | Explicit claims and evidence |

## Safety Rules

- Do not fabricate personal voice.
- Do not alter quoted text unless asked.
- Do not remove legal, financial, medical, or technical caveats.
- Do not make regulated claims more persuasive than evidence allows.
- For legal, medical, financial, or technical reports, clarity beats
  personality.
