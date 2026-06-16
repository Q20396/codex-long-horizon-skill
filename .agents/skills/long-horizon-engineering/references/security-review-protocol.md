# Security Review Protocol

Use this optional protocol for defensive security review of code, configuration,
dependencies, data handling, authentication, authorization, deployment changes,
or pull requests.

This protocol is defensive only. Do not use it for exploit development,
credential harvesting, bypass guidance, malware, stealth, exfiltration,
unauthorized access, or active scanning outside approved scope.

## Scope First

Before reviewing, identify:

- Repository, branch, PR, commit, or paths in scope
- System boundaries and trusted/untrusted inputs
- Authentication and authorization surfaces
- Data types handled by the change
- Secrets, credentials, tokens, or private files that must not be exposed
- Whether production systems, client systems, or third-party services are
  involved

If scope is unclear, sensitive, or production-impacting, stay plan-only and ask
for confirmation.

## Review Areas

Check only within authorized scope:

- Secrets and credential exposure
- Authentication and authorization changes
- Input validation and output encoding
- Data access, storage, logging, and retention
- Dependency and supply-chain risk
- Network calls and external integrations
- File upload, download, archive, and path handling
- Permission boundaries and role checks
- Error handling that may leak sensitive details
- Deployment, CI, and environment configuration

## Evidence Standard

For each finding, record:

- File and line or configuration path
- Observed behavior
- Why it matters
- Required preconditions
- Potential impact
- Safer fix or mitigation
- Verification performed or still needed

Do not report speculative vulnerabilities as confirmed. Label uncertainty.

## Secrets and Private Data

Never copy secrets, keys, tokens, credentials, private client data, legal
evidence, family information, financial account details, medical data, identity
documents, or confidential source content into review notes, memory, logs,
handoff reports, commits, or public PR text.

Use generic labels such as `private credential file`, `client evidence
document`, or `account export` when details are not needed.

Use explicit path staging. Do not use broad staging commands such as `git add .`
when sensitive files may be present.

## Stop Conditions

Stop and ask before continuing if:

- A file appears to contain secrets, legal evidence, client data, financial
  accounts, medical data, identity documents, or private correspondence.
- The requested action could publish, upload, push, or share private material.
- The review would require active testing against a system without clear
  authorization.
- The user asks for bypass, exploitation, stealth, credential handling, or
  exfiltration.
- A staged diff includes raw evidence files, screenshots, exports, keys, or
  private documents.

## Output Shape

For review reports, prefer:

1. Scope reviewed
2. Summary of risk
3. Findings by severity
4. Evidence and affected paths
5. Recommended fixes
6. Verification performed
7. Residual risk and follow-up

If no issues are found, say that clearly and list remaining test gaps or
unchecked areas.
