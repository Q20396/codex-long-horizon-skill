# Test Evidence Format

Each remediation or experiment review records every executed check as one JSON
object in a local `test-runs.jsonl` audit file. The audit file and its stdout
and stderr files are not committed unless a separate customer-approved policy
says otherwise.

Each record contains `test_id`, `command_argv`, `command_display`, `commit`,
`cwd`, `started_at`, `ended_at`, `duration_ms`, `exit_code`, `status`,
`stdout_file`, `stderr_file`, and `limitations`. `command_argv` is the actual
argument vector used for the check; it is never an empty placeholder.
`command_display` is a readable rendering of that same command and must not
contain a placeholder such as `<...>`.

`status` is one of `passed`, `failed`, `skipped`, `blocked`,
`blocked_not_installed`, or `warning`. A blocked check remains blocked even
when its probe command successfully confirms why the required tool is absent.
Every record, including a blocked record, has stdout and stderr files.

Records describe command evidence only. A passing command does not authorize
execution, promotion, routing, installation, or a claim that a formal schema
engine ran. Missing tools, unavailable credentials, and unverified external
sources remain explicit limitations.
