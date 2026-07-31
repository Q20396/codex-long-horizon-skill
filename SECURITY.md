# Security Policy

## Supported Versions

| Line | Status | Security policy |
| --- | --- | --- |
| `main` / v0.3 candidate | Supported development line | Fixes land on `main`; candidate evidence is not a released or installed capability. |
| `release/0.2.x` / v0.2.5 | Security-maintenance only | Eligible for narrowly backported security fixes until v0.3.0 is published and its replacement install path is independently verified. No feature backports. |
| v0.2.4 and earlier | Unsupported | Upgrade guidance or a separately approved exceptional fix is required. |

Every maintenance backport requires an independent change, review, validation,
tag, release, and installation decision. A fix on `main` does not automatically
advance `release/0.2.x`, and a tagged maintenance commit does not by itself
establish a GitHub Release, Marketplace resolution, or installed update.

## Reporting A Vulnerability

Do not open a public issue with sensitive vulnerability details.

If GitHub private vulnerability reporting is enabled for this repository, use
that channel. If it is not enabled, please ask the maintainers to add a private
security contact before sharing sensitive details.

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
