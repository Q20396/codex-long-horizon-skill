# Security Policy

## Supported Versions

| Line | Status | Security policy |
| --- | --- | --- |
| `main` / v0.6.x | Current supported line | Fixes land on `main`; tag, GitHub Release, Marketplace resolution, and installed update remain separate evidence stages. |
| v0.5.0 | Security-only until 2026-11-02 | Security reports remain in scope during this bounded window. Any backport requires a separate support decision, independent change, review, validation, tag, release, and installation decision. |
| v0.4.x and earlier | Unsupported | Upgrade guidance or a separately approved exceptional fix is required. |

This includes the historical `release/0.2.x` line and its tags, which remain a
Retired maintenance line. Its maintenance window ended on 2026-07-31. No routine security or feature backports are provided. A fix on `main` does not
automatically advance an unsupported line, and a tagged maintenance commit does
not by itself establish a GitHub Release, Marketplace resolution, or installed
update.

## Repository Security Observability

Observed at: 2026-08-05.

Public GitHub API checks observed private vulnerability reporting, Dependabot
security updates and vulnerability alerts, Secret Scanning, and Push Protection
as enabled. GitHub Code Scanning default setup: CodeQL default setup was
`not-configured`. This is an external
repository-control snapshot, not proof that a vulnerability is absent, source is
safe, Actions are vulnerability-free, host enforcement exists, or a release is
authorized. Recheck these controls before each release; a source change or
passing CI does not establish their current state.

## Reporting A Vulnerability

Do not open a public issue with sensitive vulnerability details.

Use GitHub private vulnerability reporting for sensitive reports where it is
available. Do not place sensitive vulnerability details in a public issue, pull
request, log, or discussion.

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
