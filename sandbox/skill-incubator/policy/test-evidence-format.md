# Test Evidence Format

Each remediation or experiment review records every executed check as one JSON
object in a local `test-runs.jsonl` audit file. The audit file and its stdout
and stderr files are not committed unless a separate customer-approved policy
says otherwise.

Each record contains `test_id`, `command`, `commit`, `cwd`, `started_at`,
`ended_at`, `exit_code`, `status`, `stdout_file`, `stderr_file`, and
`limitations`. `status` is one of `passed`, `failed`, `skipped`, `blocked`, or
`warning`.

Records describe command evidence only. A passing command does not authorize
execution, promotion, routing, installation, or a claim that a formal schema
engine ran. Missing tools, unavailable credentials, and unverified external
sources remain explicit limitations.
