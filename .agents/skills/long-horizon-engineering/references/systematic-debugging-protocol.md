# Systematic Debugging Protocol

Use this protocol for bugs, failing tests, build failures, regressions,
unexpected behavior, and performance problems where guessing would be risky.

## Core Rule

Find the root cause before changing behavior. A quick patch is not a fix if the
failure mechanism is still unknown.

## Workflow

1. Define the symptom in concrete terms.
2. Reproduce the issue or record why it is not reproducible yet.
3. Read the full error output, logs, stack traces, and changed files.
4. Check recent diffs, dependency changes, configuration changes, and
   environment differences.
5. Compare the broken path with nearby working examples.
6. State one hypothesis at a time.
7. Test the hypothesis with the smallest safe check.
8. Fix the root cause, not just the visible symptom.
9. Add or update regression coverage when appropriate.
10. Re-run the verification that proves the original symptom is resolved.

## Evidence To Record

- Symptom:
- Reproduction steps:
- Relevant files:
- Error output or failing command:
- Recent changes inspected:
- Working examples compared:
- Hypothesis:
- Test of hypothesis:
- Root cause:
- Final verification:

## Stop Conditions

Stop and ask before continuing when:

- the issue cannot be reproduced and more information is needed
- logs or files appear to contain sensitive data
- multiple fixes have failed without improving the diagnosis
- the likely fix changes public behavior, data, auth, security, or production
  configuration
- the repository state changed underneath the investigation

## Safety

Do not copy secrets, private client data, legal evidence, financial records,
medical information, identity documents, or confidential source material into
debugging notes or handoff reports. Use file paths and generic descriptions
when details are sensitive.
