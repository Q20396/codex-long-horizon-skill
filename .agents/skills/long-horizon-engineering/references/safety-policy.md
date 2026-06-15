# Engineering Safety Policy

## Protected Areas

Treat the following as high-risk:

- Authentication
- Authorization
- Payment logic
- User data
- Database migrations
- Encryption
- Secrets
- CI/CD
- Production deployment
- Infrastructure as code
- Legal/compliance logging

## Confirmation Required

Ask for explicit confirmation before:

- Deleting files or directories
- Running destructive git commands
- Dropping or resetting databases
- Modifying production config
- Rotating or exposing secrets
- Disabling tests
- Removing safety checks
- Changing permission models
- Large dependency upgrades

## Secret Handling

Never display secrets.

If secrets are found:

- Do not copy them
- Do not print them
- Recommend rotation if exposed
- Move them to environment variables if appropriate

## Network / External Calls

Do not introduce external network calls unless required.

If required, document:

- Destination
- Data sent
- Failure behavior
- Privacy implications

## Data Privacy

For user data:

- Minimize access
- Avoid logging sensitive content
- Avoid sending data to third-party services
- Document any new data retention behavior

## Client And Confidential Data

Treat the following as protected by default:

- Client names and contact details
- Legal evidence and contracts
- Financial records, bank account details, and tax documents
- Identity documents
- Family information
- Medical or health information
- Private correspondence
- Screenshots of private systems
- Source documents supplied by clients
- Confidential business information
- API keys, tokens, passwords, and credentials
- Private research notes or corpus content

Rules:

- Do not put secrets in logs.
- Do not put private evidence in reusable memory.
- Do not store sensitive details in project memory, task logs, working state, or
  handoff reports.
- Do not use broad staging such as `git add .` in sensitive repositories.
- Stage explicit reviewed paths only.
- Ask for human approval before pushing any branch that may contain private
  data.
- Do not open public PRs containing private data.
- If unsure whether data is sensitive, treat it as sensitive and ask.
