# UI/UX Review Protocol

Use this optional protocol when a long-horizon engineering task changes a user
interface, design system, frontend component, visual layout, interaction flow,
or customer-facing product surface.

This protocol is for practical engineering review. It is not a brand-cloning
tool, a replacement for user research, or permission to copy another product's
visual identity.

## Review Order

1. Confirm the product goal, target user, and affected screens.
2. Inspect the implementation and any available screenshots, mockups, tokens,
   stories, or design notes.
3. Check accessibility before visual polish.
4. Check responsive behavior and layout stability.
5. Check interaction states and error states.
6. Check visual consistency with the local design system.
7. Check performance risks such as layout shift, heavy assets, and unnecessary
   animation.
8. Record findings with evidence and validation steps.

## Design-Skill Integration Boundary

Before involving a downstream design skill, define the product goal, target
user, affected pages, and exact files the skill may inspect. Default to
audit-only; the design skill must not directly refactor or write project files.

Before build work, list and confirm each proposed effect separately:

1. Global CSS
2. `tokens.css`, `tokens.json`, or a Tailwind theme
3. `design.md` or other design-system documentation
4. `.hallmark/` or any tool state, cache, or log directory
5. Images, fonts, animation, or third-party components
6. External URL research or asset downloads

The downstream skill must not change routes, data fetching, APIs,
authentication, payment, analytics, business rules, domain logic, production
configuration, dependencies, or unrelated components unless the task
separately authorizes those changes.

For responsive work, validate at a minimum of 320, 375, 414, and 768 CSS pixels.
Check:

- No horizontal scrolling
- No clipped, overlapping, or unreadable text
- Keyboard access and visible `:focus-visible` behavior
- `prefers-reduced-motion`
- Empty, loading, error, disabled, hover, focus, and active states
- Wrapping and information density with realistic Chinese content

A visual finding must cite at least one of: a code location, screenshot or
browser observation, design token, rendered observation, or actual validation
result. Static inspection must not be reported as browser verification.
Anti-template or anti-slop guidance is only a review prompt; it is not evidence
of functional correctness or commercial effectiveness.

## Accessibility Checks

- Keyboard access works for interactive controls.
- Focus states are visible and follow the interaction order.
- Controls have accessible names or labels.
- Text contrast is sufficient for its context.
- Images and icons have appropriate alt text or are marked decorative.
- Motion is purposeful and respects reduced-motion preferences when applicable.
- Touch targets are large enough for mobile use.
- Error messages are visible, specific, and connected to the relevant field.

## Responsive And Interaction Checks

- Layouts work at mobile, tablet, and desktop widths relevant to the product.
- Important text does not overflow, overlap, or become unreadable.
- Navigation remains discoverable without forcing excessive scrolling.
- Empty, loading, error, disabled, hover, focus, and active states are covered.
- Forms preserve user input where reasonable after validation errors.
- Charts and dense data views remain understandable on smaller screens.

## Visual System Checks

- Colors, typography, spacing, radius, shadows, and motion align with the
  existing project style or documented design tokens.
- New components reuse existing patterns where possible.
- Visual hierarchy matches the user task instead of decorative weight.
- Decorative effects do not hide content, reduce contrast, or slow scanning.
- The implementation avoids copying another company's exact brand system.

## Evidence Standard

Do not write a UI/UX finding as a preference alone. Attach at least one of:

- File path and relevant code location
- Screenshot or browser observation
- Design token or documented product requirement
- Accessibility rule or platform convention
- Test, lint, build, or browser verification result

## Stop Conditions

Pause and ask the user when:

- The desired audience, brand direction, or product goal is unclear.
- The change affects regulated, medical, financial, legal, or child-directed
  experiences.
- A finding depends on private customer data or unreleased client material.
- Fixing the issue would require a redesign beyond the requested scope.
- The user asks to clone another product's exact visual identity.
