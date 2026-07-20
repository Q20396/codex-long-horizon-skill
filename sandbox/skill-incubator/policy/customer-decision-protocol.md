# Customer Decision Protocol

Decision records may contain `step_id`, `experiment_id`, `proposed_action`,
`risk_level`, `customer_decision`, exact authorization text, timestamps,
execution result, and rollback status. They must not contain tokens, cookies,
passwords, API keys, private keys, unrelated private information, or hidden
reasoning.

Customer silence, context loss, and a Codex-authored recommendation mean
`not_approved`. A decision record does not persist an unlocked state: every
later high-impact action needs a new explicit customer decision.
