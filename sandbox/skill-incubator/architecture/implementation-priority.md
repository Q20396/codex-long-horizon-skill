# Implementation Priority

This is a proposed ordering, not an execution authorization.

1. **MAD-SKILL-002**: Capability Contract and Real Output Harness. It enables
   every later candidate without a third-party runtime and addresses false
   success from exit-code-only validation. Its current status remains locked.
2. **Unified Skill Router** from MAD-SKILL-008: a future bounded entry point
   for catalog display, risk explanations, progressive disclosure, and customer
   choice. The current catalog has no recommendation-eligible or execution-
   routable entries, so this proposal cannot recommend, invoke, or bypass
   approval.
3. **MAD-SKILL-012 candidate**: Engineering Traceability Pipeline. It remains
   candidate_only and is not a current routing target.
4. **MAD-SKILL-003**: lightweight planning and handoff.
5. **MAD-SKILL-001**: bounded repository cartography.
6. **MAD-SKILL-013 candidate**: Browser and Visual QA Gate. It is planning
   only; browser execution stays a separate skill.
7. **MAD-SKILL-014 candidate**: Scheduled Automation Safety Controller. It is
   planning only; no schedule, timer, or background service is authorized.

Later: multi-agent runtimes, video, voice, 3D, MCP, finance, security, and
external communication. This ordering is based on safety and dependency
structure, not stars, rankings, downloads, or screenshot claims.

`MAD-SKILL-010` does not fully cover Browser QA, `MAD-SKILL-006` and 011 do not
fully cover traceability, and `MAD-SKILL-002` does not fully cover scheduled
automation. Those statements are intentionally partial-overlap design
assessments, not implementation claims.
