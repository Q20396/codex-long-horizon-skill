# Repository governance change card

## Scope and identity

- Repository: `Q20396/codex-long-horizon-skill`
- Observed on: 2026-08-01
- Authority: repository administrator action; this record does not grant source,
  release, installation, account, customer-data, or runtime authority.

## Applied controls

The following settings were read back from GitHub after the governance change:

- Dependabot security updates: enabled.
- Secret Scanning: enabled.
- Secret Scanning Push Protection: enabled.
- Private vulnerability reporting: enabled.
- `main` branch protection: enabled with strict required checks
  `check-skill` and `formal-schema-gate`; force pushes and deletion are
  disabled.

`main` does not require reviewer approval or administrator enforcement in this
configuration. This is deliberate for the current single-maintainer workflow;
it is not equivalent to multi-party review or a security guarantee.

## Exclusions and limitations

- Non-provider secret patterns and secret validity checks were observed disabled
  on 2026-08-01. They are not prerequisites for the controls above and must not
  be reported as enabled without a separate read-back.
- GitHub settings can drift or be changed outside Git. This document is an
  audit record, not a live control-plane source.
- Passing required checks does not authorize a tag, GitHub Release, marketplace
  resolution, installation, account connection, network action, or trade.

## Rollback

Only a repository administrator may alter these controls. Before rollback,
record the reason, affected branches, current settings, expected duration, and
the restoration command or GitHub UI path. Re-read the settings after any
change. Do not weaken `main` protection merely to merge a failing change; fix
or explicitly reject the change instead.
