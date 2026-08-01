# v0.3 Package Layering Specification

Status: Proposed

> **Supersession.** This is a v0.3 historical design specification. The
> approved v0.4 Local Governance Upgrade changes the default profile to
> `local-governance-core` while retaining `legacy-full` as an explicit
> compatibility profile. It does not authorize a path move, runtime, or
> provider. At v0.3, this record did not change `legacy-full` as the default.

This specification defines how Long-Horizon Engineering (LHE) evolves from a
single full bundle into three explicit package layers. It is a design contract,
not authorization to move files, change an installation default, publish a
release, or split a skill.

## Decision

LHE uses three package layers:

| Layer | Purpose | Installation contract |
| --- | --- | --- |
| `core` | The minimum safe engineering workflow, approval boundaries, recovery guidance, validation, and package self-checks. | Required by every LHE installation. Missing content is an error. |
| `bundled-optional` | Repository-shipped extensions, templates, and specialized references that are useful but not required for the core workflow. | Selected by an explicit package profile. Missing selected content is an error; unselected content is not inspected or required. |
| `separate-skill` | Independently routed domains or capabilities with their own lifecycle, permissions, or runtime boundary. | Installed, updated, validated, and approved separately. Presence in the source repository does not imply installation or activation. |

The exact path inventory is owned exclusively by
`.agents/skills/long-horizon-engineering/package-manifest.json`. Documentation
MUST NOT maintain a second path list. At the time this specification was
written, that manifest classifies 44 `core` paths, 103 `bundled-optional` paths,
and 28 `ai-video-production` paths as one `separate-skill`.

## Layer Rules

### Core

A path belongs in `core` only when removing it would prevent at least one of:

- loading the LHE entry point;
- enforcing approval, privacy, capability, or stop boundaries;
- resuming and recovering a long-running engineering task;
- selecting and recording validation evidence;
- validating the installed core package;
- safely checking or applying an explicitly approved skill update.

Core MUST remain dependency-free and locally usable. It MUST NOT require a
network connection, provider account, MCP registration, OAuth grant, model
download, media runtime, or another skill.

### Bundled Optional

A path belongs in `bundled-optional` when it:

- extends an intact core workflow;
- remains useful without an external service or independent runtime;
- can be omitted without weakening core safety or recovery;
- is selected explicitly through a package profile;
- does not become implicitly active merely because it is present.

Optional content selected by a profile is required for that selected profile.
Optional does not mean unchecked, untrusted, or safe to ignore after selection.

### Separate Skill

A capability belongs in `separate-skill` when it has an independent trigger,
domain contract, release lifecycle, permission boundary, or runtime/provider
surface. A separate skill MUST have its own `SKILL.md` and MUST NOT be treated
as an LHE component.

External providers, hosted services, login-dependent tools, MCP servers, model
downloads, publication workflows, and media-generation runtimes SHOULD remain
outside all LHE package profiles. Their documentation may describe an
integration boundary, but installation and use require separate decisions.

## Current Manifest Contract

The version 1.0 package manifest and its Draft 2020-12 schema already express
the three layers. v0.3 does not require a new schema version merely to move
files between existing layers.

The canonical files are:

- `.agents/skills/long-horizon-engineering/package-manifest.json`
- `.agents/skills/long-horizon-engineering/schemas/package-manifest.schema.json`

The following current profiles retain their meanings during migration:

| Profile | Components | Separate skills | Compatibility role |
| --- | --- | --- | --- |
| `legacy-full` | `core`, `bundled-optional` | `ai-video-production` | Explicit compatibility profile. |
| `lhe-bundled` | `core`, `bundled-optional` | none | Full LHE without independent skills. |
| `core-only` | `core` | none | Minimal LHE installation. |
| `local-governance-core` | `core` | none | Compatibility alias for the minimal local-only governance/evidence kernel. Recommended for high-sensitivity workflows; it does not install domain packs or providers. |

During the compatibility period, `legacy-full` may continue to validate the
combined source package. That compatibility behavior does not combine install,
update, activation, or provider authorization: each separate skill still
requires an explicit target and its own applicable approvals.

The schema MUST change only when the existing structure cannot express an
approved requirement. A schema change requires its own migration proposal,
negative tests, compatibility analysis, and rollback plan.

## Compatibility Strategy

The v0.3 specification phase preserved all current behavior. The approved v0.4
default change is documented separately; it preserves physical layout and the
legacy fallback:

- `default_profile` is `local-governance-core`;
- `migration.physical_layout_changed` remains `false`;
- `migration.default_install_changed` is `true`;
- `migration.legacy_checker_fallback` remains `true`;
- current profile names and component meanings remain stable;
- current repository paths remain in place;
- old installations without a manifest continue through the existing legacy
  checker fallback;
- profile selection remains explicit;
- selecting `core-only` or `lhe-bundled` does not install a separate skill.
- `local-governance-core` selects the same files as `core-only`; the alias is a
  customer-facing declaration, not host isolation or a new runtime.

No v0.3 implementation PR may change more than one of these concerns at once:

1. path classification;
2. installed package assembly;
3. default profile;
4. manifest schema;
5. updater behavior;
6. separate-skill lifecycle.

## Migration Sequence

Migration proceeds through reviewable PRs:

1. **Specification:** define layer ownership, invariants, compatibility, tests,
   and rollback. No file or default changes.
2. **Classification review:** propose individual path moves with evidence that
   core remains complete. No physical moves.
3. **Assembly support:** teach packaging tools to materialize selected profiles
   in temporary directories. Keep `legacy-full` available as compatibility.
4. **Clean-room install validation:** verify each profile in an isolated
   temporary home and verify upgrades from the current stable release.
5. **Default decision:** separately decide whether to retain or change the
   default profile. A default change requires explicit customer approval and
   release notes.
6. **Optional physical migration:** move files only if profile assembly cannot
   remain manifest-driven. Physical movement is not a goal by itself.

Each PR MUST preserve exact manifest coverage, disjoint layer membership,
package checks for every selected profile, and a documented rollback.

## Validation Matrix

Before any migration is promoted:

| Concern | Required evidence |
| --- | --- |
| Manifest integrity | Draft 2020-12 validation plus dependency-free structural checks. |
| Inventory | Every shipped skill file appears exactly once in the manifest. |
| Core completeness | A clean `core-only` install passes package and doctor checks without optional or separate content. |
| Optional isolation | A clean `lhe-bundled` install passes without `ai-video-production`. |
| Separate lifecycle | Separate skills validate and update independently. |
| Backward compatibility | `legacy-full` remains available as the prior full profile after the separately approved v0.4 default change. |
| Upgrade safety | Stable-to-candidate dry-run, backup, apply, validation, and rollback are exercised in temporary directories. |
| Routing | Removing an unselected layer does not broaden or silently redirect triggers. |

Static contract checks do not replace clean-room installation or manual routing
evaluation.

## Rollback

The specification is rolled back by reverting its documentation and tests.

For later migration PRs:

- preserve the previous manifest and selected profile;
- retain a backup before replacing an installed package;
- never silently preserve or delete target-only files;
- restore the previous package and re-run its package and doctor checks;
- report partial recovery rather than claiming transactional rollback;
- do not delete a separately installed skill when rolling back LHE.

## Non-Goals

This specification does not:

- move, delete, or duplicate package files;
- change the historical `legacy-full` compatibility profile;
- change updater or installer behavior;
- install or remove `ai-video-production`;
- add a provider, runtime, dependency, network call, or telemetry;
- authorize automatic migration, publication, or promotion;
- revive the hostile same-UID filesystem research branch;
- define v0.3 release readiness beyond package layering.

## Completion Criteria

The package-layering migration is complete only when:

- all three profiles have clean-room install and upgrade evidence;
- the manifest remains the single path authority;
- core is independently usable and safety-complete;
- optional omissions produce no core failure;
- separate skills have independent install, update, validation, and approval
  paths;
- compatibility and rollback evidence is independently reviewable;
- any default-profile change is explicitly approved and documented.
