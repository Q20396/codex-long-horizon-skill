# Security Policy

## Supported Versions

| Line | Status | Security policy |
| --- | --- | --- |
| `main` / v0.3.2 release line | Supported stable and development line | Fixes land on `main`; tag, GitHub Release, Marketplace resolution, and installed update remain separate evidence stages. |
| v0.3.0 tag | Historical candidate | Immutable candidate evidence only; it is not the supported stable installation ref. |
| `release/0.2.x` / v0.2.5 | Retired maintenance line | The maintenance window ended on 2026-07-31 after v0.3.1 publication and independent replacement-install verification. No routine security or feature backports. |
| v0.2.4 and earlier | Unsupported | Upgrade guidance or a separately approved exceptional fix is required. |

Any exceptional retired-line fix requires a separate support decision,
independent change, review, validation, tag, release, and installation decision.
A fix on `main` does not automatically advance `release/0.2.x`, and a tagged
maintenance commit does not by itself establish a GitHub Release, Marketplace
resolution, or installed update.

## Repository Security Observability

Public GitHub API checks on 2026-08-01 reported private vulnerability reporting,
Code Scanning analysis, Dependabot alerts/security updates, Secret Scanning, and
push protection as disabled or unavailable for this repository. This is a
repository-control gap, not evidence that a vulnerability exists or that the
source is unsafe. Recheck these controls before each release. Enabling them is a
separate repository-administration decision and must not be inferred from a
source change or passing CI.

## Reporting A Vulnerability

Do not open a public issue with sensitive vulnerability details.

Private vulnerability reporting was not enabled at the 2026-08-01 check. Ask
the maintainers to establish a verified private security contact before sharing
sensitive details. Do not place sensitive vulnerability details in a public
issue, pull request, log, or discussion.

## What To Include

Include only the minimum necessary information:

- A short summary of the issue
- Affected files or components
- Reproduction steps using non-sensitive data
- Expected and actual behavior
- Potential impact
- Suggested fix, if known

Do not include secrets, real credentials, private client data, legal evidence,
or confidential documents.

## Disclosure Expectations

Maintainers should avoid publishing sensitive vulnerability details before a fix
or mitigation is available. Coordinate disclosure in a way that protects users
and avoids exposing private data.
