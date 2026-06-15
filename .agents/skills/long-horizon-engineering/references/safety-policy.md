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