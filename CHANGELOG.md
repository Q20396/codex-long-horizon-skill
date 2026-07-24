# Changelog

All notable changes to this project are summarized here.

## Unreleased

No unreleased changes.

## 0.2.4 - 2026-07-24

- Added a proposal-only renderer runtime sandbox protocol and approval card for
  AI video work. Environment inspection, dependency installation, preview,
  final render, external processing, and sharing remain separate approvals.
- Kept renderer selection and runtime execution separate: selecting a renderer
  does not authorize installation, rendering, provider use, uploads, or sharing.
- Added contract coverage for the renderer runtime sandbox boundary.

## 0.2.3 - 2026-07-24

- Documented `--ref v0.2.3` as the stable marketplace installation reference
  and retained `--ref main` only for users who explicitly want unreleased
  repository state.

## 0.2.2 - 2026-07-24

- Added proposal-only local voice-tool and external 3D asset-provider sandbox
  documentation, approval cards, package checks, and contract tests.
- Removed copy-ready external installation and MCP-configuration commands from
  the 3D provider record; any future command must be revalidated and separately
  approved.
- Added governed Skill Incubator capability research and routing safeguards
  with locked source ledgers, verification-blocked states, and no third-party
  runtime execution.
- Added a locked public equity research sandbox with no customer-data upload,
  no trading execution, and no financial advice automation.
- Added optional Decision Map and deterministic Frontier planning support for
  long-running engineering work without replacing checkpoints, approvals,
  rollback, resume, or validation gates.
- Fixed the updater path contract so `--target-root` continues to target
  project-scoped `.agents/skills/<skill>` installs while `--target-skill-dir`
  can safely target existing Codex user-level `skills/<skill>` installs.
- Rejected ambiguous updater targets, duplicate `~/.codex/.agents/skills`
  layouts, multi-skill apply operations, and mismatched direct skill
  directories.

## 0.2.1 - 2026-07-15

- Fixed `doctor.py` and `check_skill_package.py` for user-level installations
  under `~/.codex/skills/`.
- Added regression coverage for automatic source-package and user-level layout
  detection.
- Kept the update flow check-only by default, backup-first, and
  user-authorized.

## 0.2.0 - 2026-06-18

- Added safe online self-check/update protocol.
- Added explicit two-step approval model for update checking and applying updates.
- Hardened update self-check path-boundary validation.
- Added release manifests for installed skill comparison.
- Added dependency-free update self-check script.
- Added rollback-first update guidance.
- Restricted update targets to approved bundled skills.
- Added customer-facing update prompt templates.
- Added tests for update self-check behaviour.
- Added tests for traversal, unknown skill ids, and symlink safety.

## 0.1.0 - 2026-06-18

- Narrowed `long-horizon-engineering` routing scope to non-trivial software
  engineering and moved adjacent optional workflows behind an explicit-only
  extension index.
- Clarified `ai-video-production` routing boundaries for storyboard, shot list,
  visual prompt, asset manifest, and render handoff tasks.
- Expanded deterministic routing contract cases with positive, negative,
  overlap, and explicit invocation coverage.
- Added optional live routing evaluation documentation with clear limitations.
- Added Codex plugin manifest and repository marketplace files for reusable
  plugin distribution without duplicating canonical skill directories.
- Added plugin package validation, fresh isolated install verification, and
  deterministic release-readiness checks.
- Hardened release tooling so marketplace registration is tested independently
  from listing, failed advertised CLI commands fail, malformed skill front matter
  reports clean validation errors, and video licensing routing avoids legal
  conclusions.
- Updated README trust wording from production-grade claims to
  production-oriented positioning and added plugin installation navigation.
- Added first-contribution guide, demo recording script, and v0.1.0 release
  preparation notes without publishing a tag or GitHub Release.
- Added open-source growth scaffolding: issue templates, pull request template,
  educational workflow examples, demo recording guidance, community skills
  registry, security policy, code of conduct, and validation coverage.
- Redesigned README for catalog-first onboarding, added root prompt and report
  templates, added contributor guidance, and added automated catalog/link/skill
  quality checks.
- Added privacy-first disaster monitoring enablement guidance with manual
  monitored locations, optional one-time approximate current location, and
  alert-rule/runbook templates.
- Added external skill candidate safety review guidance and a read-only local
  audit helper for customer-reviewed adoption decisions.
- Added a source-gap prompt for jurisdiction, tax, regulatory, and industry-rule
  tasks so Codex asks before searching current public sources online.
- Added a SkillOpt-inspired training layer with non-sensitive eval cases, a
  local static skill scorer, and a candidate training report template.
- Added skill lifecycle management guidance and a local helper for non-sensitive
  usage tracking, freeze suggestions, and reversible freeze/restore workflows.
- Added a read-only skill safety audit and wired it into the apply path before
  installed skills are upgraded.
- Added review-gated missing capability skill discovery guidance for safely
  comparing public GitHub skills and proposing bounded local upgrades.
- Added lightweight SkillOpt-inspired skill optimization protocol and templates
  for rollout evidence, reflection, bounded edits, validation gates, and
  rejected edit logs without adding a runtime dependency.
- Added external tool provider and external app runtime boundary guidance with
  provider capability, source upload consent, paper evidence, and memory review
  templates.
- Added lightweight financial research report and defensive security review
  protocols with source, valuation, risk, and secrets-scan templates.
- Added adversarial review, TDD, API integration, ship-readiness, and data
  cleaning protocols with evidence templates.
- Added lightweight UI/UX review protocol, accessibility checklist, frontend
  handoff template, and UI/UX audit template.
- Added skill brief and skill evaluation planning templates.
- Added writing humanization protocol and voice calibration template.
- Added ideation-to-plan protocol and option analysis template.
- Added evidence-backed writing protocol and claim-evidence table.
- Added notebook/data analysis protocol and analysis run log.
- Added presentation delivery protocol and deck QA templates.
- Added video design system reference and `DESIGN.md` templates.
- Added systematic debugging and reviewer-response protocol templates.
- Extended academic source pattern in external search protocol.
- Extended trigger fixtures.
- Added follow-up methodology and search integration guidance: skill authoring
  methodology, provider-neutral external search protocol, implementation and
  verification templates, description audit checks, and richer trigger fixtures.
- Added productized package pieces: optional Repomix context protocol, doctor
  and backup-first update scripts, prompt-styles, trigger fixture checks, and
  upgrade documentation.
- Added plugin manifest packaging and a Git-backed repository marketplace for
  Codex plugin installation.
- Added fresh-install tooling for project-scoped direct skill installation,
  user-scoped direct skill installation, remote marketplace discovery, actual
  isolated plugin installation, and installed package identity verification.
- Added malformed front-matter handling and marketplace/plugin false-positive
  regression coverage.
- Added v0.1.0 release-readiness tooling.
- Added implementation plan and verification evidence templates.
- Added skill description audit script.
- Added public project polish: MIT license, installation guide, examples, and CI
  package checks.

## 2026-06-15

- Added capability boundaries for sub-agent orchestration, deployment,
  self-improvement, auto-merge, production execution, and security automation.
- Added public agent capability review guidance for evaluating Fable-style and
  Claude Code-style public capability descriptions.
- Added final long-horizon supports: large migration playbook, validation
  matrix, and handoff report template.
- Added external source scan consent protocol for local folders, connected
  cloud drives, Gmail, and similar sources.
- Added context compaction, working state, resume protocol, decision logging,
  review checklist, stop conditions, and safe continuous improvement guidance.
- Added project memory and task log templates with local helper scripts.
- Published the repository as a reusable Codex skill package.
