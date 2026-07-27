# UI Design Skill Adapter

Use this bundled-optional adapter when LHE coordinates Hallmark or a similar
downstream UI or design skill. It is a governance boundary, not a runtime
integration, installation contract, or grant of authority.

## Authority Order

LHE governance overrides downstream design skills. LHE retains control of
safety, privacy, authority, file scope, external effects, validation, delivery,
and stop conditions. A downstream recommendation cannot widen the approved task
or authorize its own implementation.

## Default Mode

Default to audit-only. The downstream skill may inspect only the approved input
and report findings. It may not write files, download assets, study URLs, create
state or log files, install tools, execute project code, or invoke external
services without separate approval.

## Required Approval Before Build

Before any implementation, list and obtain approval for:

- Exact files to create, modify, or delete
- Global stylesheet impact
- Design-token or design-system impact
- Persistent state, cache, memory, or log files
- External network access and asset sources
- Expected build, typecheck, lint, test, browser, and accessibility checks
- A rollback method

Approval for an audit is not approval to build. Approval for one file or effect
does not authorize another.

## Scope Boundaries

A downstream design skill must not independently change:

- Routes or navigation behavior
- APIs or data fetching
- Authentication or payment
- Analytics
- Domain or business logic
- Production configuration
- Dependencies
- Unrelated components

Any such change requires a separately bounded task and explicit approval.

## Persistence Policy

A design skill must not create tool-state directories, design-system documents,
token files, logs, caches, or project memory by default. Every persistent file
must appear in the approved file-level plan. Sensitive projects default to no
design-state persistence.

## External-Source Policy

URL study is limited to public pages and requires approval for that specific
access. Do not upload, paste, or send private code, client information, medical,
legal, financial, identity, credential, or session material. Extract only
design facts needed for the task. Do not copy branding, images, text, or a
copyrighted page structure.

Asset downloads, fonts, animations, and third-party components require their
own source, license, privacy, and file-scope review. Public availability is not
permission to copy or redistribute.

## Validation Handoff

Visual rules are not validation conclusions. Report at least:

- Actual build, typecheck, lint, and test results
- The page-validation method and evidence
- Responsive viewport results
- Keyboard, focus, semantics, contrast, and reduced-motion results
- Known limitations
- Unverified items
- The rollback path

Static inspection must be labeled as static evidence. Do not describe a
responsive, browser, accessibility, or interaction result as verified unless
the relevant check actually ran.

## Hallmark-Specific Compatibility

Hallmark may be used as an optional downstream design skill when it is available
and separately authorized. Prefer its audit capability. Any redesign capability
must operate only on the exact LHE-approved file list.

Do not create Hallmark state, token, or design-system files by default.
Hallmark's visual-quality checklist is advisory and does not replace engineering
tests, browser validation, or accessibility validation. Do not mechanically
copy English-language typography, font pairings, layout density, or text length
into a Chinese-language product.
