# Writing Humanization Protocol

Use this explicitly selected protocol to draft or revise PR summaries, README
edits, documentation, client handoffs, reports, scripts, and client-facing copy.
It also supports requests for clearer, more natural, or less AI-like writing.

This protocol must not be used to hide authorship, fabricate personal style,
misrepresent provenance, or make unsupported claims sound more persuasive.

## Workflow

1. Establish the reader, intended outcome, channel, supplied facts, and requested
   operation (draft, review, or revise). Reuse information already provided;
   ask only for a missing choice that would materially change the result.
   For material claims, use `evidence-backed-writing.md` before drafting.
2. If the user provides a writing sample, extract voice traits:
   - sentence rhythm
   - paragraph shape
   - vocabulary level
   - punctuation habits
   - transition style
   - directness/formality
3. For a new draft, choose one organizing question the reader needs answered.
   Select supporting points by relevance, not by the order of a specification
   sheet. Use a structure suited to the request; do not impose a story arc,
   numbered list, or fixed paragraph count on every genre.
4. Draft, or audit the supplied text for AI-like patterns:
   - generic transitions
   - inflated adjectives
   - vague attribution
   - repetitive sentence structure
   - over-polished marketing tone
   - filler phrases
   - unsupported certainty
5. Review facts separately from expression. For each significant issue, identify
   the passage, what is wrong, and its effect on the intended reader. Distinguish
   a factual error or missing condition from an optional stylistic preference.
   A review-only request returns findings, not an unsolicited replacement draft.
6. Revise the affected passages while preserving accurate, effective material.
   Do not remove every transition, repetition, metaphor, or long sentence merely
   because it resembles an AI pattern; judge its function in this particular text.
7. Re-check claims, technical terms, qualifications, and whether the title and
   opening promise more than the body delivers. Return the requested copy, not
   the internal checklist, unless the user asks for the review trail.

## Product Posts And Xiaohongshu

For a product post aimed at potential buyers, a useful optional sequence is:
the buying question, the few features that matter to that question, their
practical implications, relevant limitations, and who should consider it.
Use only the parts that help this reader; do not manufacture a drawback or a
personal anecdote to complete the structure.

- Explain a feature's relevance without turning a plausible benefit into a
  measured result. Keep compatibility conditions next to the benefit they limit.
- Without supplied experience, write as a source-based introduction or buying
  guide, not a first-person ownership review. Never invent duration of use,
  sensory results, customer reactions, or comparisons tested by the author.
- Avoid blanket buying recommendations when budget, use case, or alternatives
  are unknown. Give conditional suitability rather than artificial certainty.
- Keep buyer-relevant limitations in the post, but do not turn it into an audit
  report. If a missing fact is not needed for the chosen angle, omit that claim
  rather than listing every absent test or specification in the finished copy.
- Provide titles, cover text, hashtags, or a call to action only when requested
  or needed by the agreed format; they must obey the same factual boundaries.

## Modes

| Mode | Use For | Notes |
| --- | --- | --- |
| technical-neutral | PRs, engineering docs, changelogs | Clear and direct; avoid hype |
| client-friendly | client handoffs, proposals | Natural but precise |
| Chinese concise | Chinese user-facing output | Keep technical identifiers unchanged |
| marketing but factual | landing copy, video copy | Persuasive but evidence-bounded |
| reviewer-facing | PR reviews, audit notes | Explicit claims and evidence |

## Safety Rules

- Do not fabricate personal voice traits.
- Do not alter quoted text unless asked.
- Do not remove legal, financial, medical, or technical caveats.
- Do not make regulated claims more persuasive than evidence allows.
- For legal, medical, financial, or technical reports, clarity beats
  personality.
