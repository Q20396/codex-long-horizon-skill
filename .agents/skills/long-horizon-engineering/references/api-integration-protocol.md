# API Integration Protocol

Use this optional protocol when adding, changing, or reviewing an API
integration, connector, webhook, SDK wrapper, OpenAPI client, or backend
service boundary.

The goal is to make API work explicit: what is called, how it is authenticated,
what data crosses the boundary, how failures behave, and how the contract is
tested.

## Workflow

1. Identify the provider, consumer, environment, and ownership boundary.
2. Read existing integration code and tests before designing a new shape.
3. Map endpoints, methods, auth, request schemas, response schemas, and errors.
4. Classify sensitive data and secrets. Do not log or commit them.
5. Define timeout, retry, rate-limit, idempotency, and backoff behavior.
6. Add or update contract tests, mocks, fixtures, or recorded examples when safe.
7. Verify with the narrowest safe command first, then broader checks.
8. Document operational risks and rollback behavior.

## Integration Map

Capture:

- Provider and base URL source
- Authentication method and secret storage boundary
- Endpoint list
- Request and response fields
- Required headers
- Pagination and filtering
- Error status handling
- Retry and timeout policy
- Rate-limit behavior
- Idempotency keys or duplicate protection
- Test strategy

## Privacy And Security

- Never commit API keys, tokens, passwords, cookies, or private request bodies.
- Prefer mock fixtures or redacted examples.
- Do not paste private payloads into public issue text, PRs, memory, logs, or
  reusable templates.
- If real API calls require credentials, ask before using them and explain the
  target, command, data exposure, and expected result.

## Stop Conditions

Pause when:

- Auth scope or data ownership is unclear.
- The API call can modify external state.
- The integration touches billing, permissions, identity, legal, medical, or
  financial data.
- Rate limits or retry behavior could cause harm.
- The contract cannot be verified safely.
