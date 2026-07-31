# Customer-Guided Engineering Decision

Use the long-horizon-engineering skill in guided customer mode.

I need help deciding whether an engineering change is safe to consider.
Start with intake only. Ask me for the outcome, decision, success criteria,
approved materials, allowed effects, forbidden effects, sensitive-data limits,
and stop conditions in plain language.

Do not read additional files, write, use the network, install anything, or take
an external action unless I separately approve that exact scope.

When enough evidence is available, return:

1. a plain-language customer outcome with `FACT`, `INFERENCE`, `UNKNOWN`,
   exactly one status, exactly one next safe action, and one decision question;
2. a separate operator boundary showing scope, effects, stop conditions,
   `human_disposition: PENDING`, and `next_stage_authorized: false`;
3. a separate engineering evidence appendix with source locations, checks,
   gaps, and limitations.

Do not require me to understand schemas, receipts, CI, commits, hashes, or
validator internals. A recommendation or passing check is not my approval.
