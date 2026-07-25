# Investment Decision Gate

## Status

- Contract status: `contract_foundation_approved`
- Runtime integration: `false`
- Registered skill: `false`
- Automatic execution: `false`
- Human decision required: `true`

This document defines a research-readiness contract for public-equity work. It
does not install or modify the Public Equity Investing plugin. It does not
connect to market-data providers, brokers, accounts, portfolios, or execution
systems.

## Responsibility Boundary

The gate is a shared contract layer, not a lead research skill:

1. An existing research workflow prepares evidence, assumptions, valuation,
   scenarios, a counter-case, falsifiers, and known gaps.
2. The gate evaluates whether that packet is ready for human consideration.
3. A human decides whether to wait, reject, request more research, or adopt a
   monitoring posture.
4. A thesis-monitoring workflow may record approved monitoring rules and later
   compare expectations with observed results.

The gate never approves its own output. `decision_candidate` means only that
the required research fields are present and internally reviewable.

## Gate States

- `research_only`: early observations or hypotheses that need more work.
- `blocked`: a mandatory identity, source, valuation, or boundary check failed.
- `conditional`: evidence is usable, but a named threshold or input remains
  unresolved.
- `decision_candidate`: the packet is complete enough for a human decision.
- `re_underwrite`: material evidence weakened or invalidated the prior thesis.

Every output keeps `human_decision.status` equal to `pending`. A future human
decision is a separate record with separate provenance and is outside this
contract.

## Required Inputs

The machine-readable record contains:

- issuer/security identity, market, currency, and as-of time;
- workflow owner and version identifiers;
- a source and freshness ledger;
- assumptions separated from facts;
- a valuation or decision framework when posture goes beyond research-only;
- a strongest counter-case;
- observable falsifiers;
- explicit data gaps and conflicts;
- a non-executable proposed posture;
- monitoring rules that remain drafts until separately approved;
- an append-only audit record.

Missing values remain explicit as `null`, empty collections, or gate-failure
codes. They are not silently invented.

## Data Freshness And Licensing

Each evidence item records its source type, factual as-of time, retrieval time,
reliability, use, direction, licence status, redistribution status, and known
limitations.

- `verified` means the relevant use and citation boundary was checked.
- `restricted` means the source may support local analysis but not copying or
  redistribution.
- `unknown` means the item cannot support `decision_candidate`.
- Stale or conflicting evidence remains visible and lowers readiness.
- Source access does not imply permission to retain, reproduce, train on, or
  redistribute the source.

Fixtures contain only synthetic data. Real customer, account, position,
broker, order, credential, tax, identity, or material non-public information
is prohibited.

## Execution Isolation

The gate may produce research summaries, scenarios, risks, falsifiers,
monitoring drafts, and decision-readiness records. It must not:

- connect to or inspect a broker, account, wallet, mailbox, cloud drive, or
  portfolio system;
- generate, route, transmit, simulate as executable, or submit an order;
- request or retain credentials, API keys, account identifiers, or execution
  logs;
- turn a recommendation into permission;
- start background monitoring, scraping, provider calls, or publication;
- upload customer material or restricted source content.

The schema deliberately uses `proposed_posture` values such as `watch` and
`wait_for_proof`, not buy, sell, hold, size, rebalance, or order terminology.

## Monitoring And Review

Monitoring entries define a review plan and an append-only calibration history:

- metric and source;
- comparison direction and threshold;
- freshness expectation;
- review cadence and next review date;
- approval status, which defaults to `draft_pending_human_approval`.
- expected and actual results, variance, attribution, evidence sources, and
  decision impact for each completed review.

No entry schedules a job. Reviews are recorded for human review and never
approve a posture. Historical packets remain immutable; revisions create a new
record linked through `supersedes_record_id`.

## Router Remediation

The observed `public-equity-investing@0.1.31` router advertises
`test-public-equity-investing-workflows`, but the installed package contains no
matching skill directory.

The recommended upstream correction is to remove that user-visible route and
keep workflow verification in package-level tests. Restoring a production
testing skill is not recommended. This repository records the discrepancy but
does not edit the installed plugin cache or claim the upstream router is fixed.

## Versioning And Rollback

- Initial schema version: `1.0.0`.
- Contract changes require explicit schema-version review.
- Existing packets remain readable and are never rewritten in place.
- Runtime integration, if separately approved, must be additive and removable.
- Rollback removes routing to the gate while retaining historical records and
  the schema needed to read them.

## Definition Of Done For Contract Foundation

- Draft 2020-12 schemas are valid.
- Ten or more synthetic scenarios cover positive and negative states.
- `decision_candidate` always retains a pending human decision.
- Source freshness and licence limitations are explicit.
- Forbidden execution and sensitive-data fields are absent.
- The missing router target is recorded without claiming it is repaired.
- No plugin, provider, network, account, or execution integration exists.
