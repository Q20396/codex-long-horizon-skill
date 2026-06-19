# Self-Check Policy

Use this policy when reviewing this skill package or an installed copy of a
skill for possible improvement.

## Core Contract

Self-check is read-only and proposal-only. It may inspect approved local files,
compare evidence, explain risks, and recommend a change, but it must stop for
human review before any update is applied.

Required proposal state:

- Proposal status: PROPOSAL_ONLY
- User approval required: YES
- User decision: PENDING
- Changes applied: NO

Self-check cannot approve its own proposal. A recommendation is not permission
to edit, install, download, merge, push, deploy, publish, or release anything.
Update/apply is a separate user-authorized action.

## Allowed Flow

1. Observe the approved local package or installed skill.
2. Compare it with an approved local package, immutable tag, or exact commit.
3. Explain facts, assumptions, evidence, risks, and tradeoffs.
4. Recommend the smallest safe improvement.
5. Wait for user approval.

## Disallowed Behavior

Self-check must not:

- automatically mutate skills
- install or download skills
- make network calls without explicit approval
- query GitHub or other providers without explicit approval
- merge, push, deploy, publish, or release
- generate patches for automatic application
- run hooks, background jobs, telemetry, or log scanning
- delete unknown or additional files
- weaken tests, safety rules, privacy rules, or approval requirements to make a
  proposal pass

Unknown or additional files must be reported, not deleted.

## Reproducible Comparison Sources

Offline mode should compare against a user-supplied local exported package or
release directory.

Network mode requires explicit user approval and an immutable source:

- exact commit SHA
- immutable release tag that is resolved to an exact commit and reported

Mutable refs are not valid reproducible comparison sources:

- `main`
- `master`
- `latest`
- branch names
- moving aliases

If the source cannot be pinned, stop and ask.

## Privacy Rules

Do not include raw prompts, conversation contents, user identities, email
addresses, credentials, account identifiers, client data, device or GPS
location, private absolute paths, repository file contents, Codex logs, shell
history, browser history, or hidden-file contents in self-check reports.

If a repository appears sensitive, stay proposal-only and ask before inspecting
additional files.
