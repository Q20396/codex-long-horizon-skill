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
