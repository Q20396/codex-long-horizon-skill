# Public Equity Data Freshness Contract

## Status

- Contract status: `contract_foundation_approved`
- Runtime integration: `false`
- Registered skill: `false`
- Automatic retrieval: `false`
- Human decision required: `true`

This contract records whether a synthetic or separately authorized public
equity evidence packet has adequate provenance, timing, licence, calendar, and
conflict evidence to enter the Investment Decision Gate. It does not retrieve
data, call a provider, inspect customer accounts, upload customer material, or
produce trading instructions.

## Responsibility Boundary

The contract separates three layers:

1. **Source facts** record what a named source stated and when that statement
   was effective, published, and retrieved.
2. **Derived claims** identify calculations or interpretations and preserve
   their source IDs and model version.
3. **Human judgment** remains visibly classified and never becomes a verified
   fact merely because a model produced it.

`decision_gate_eligible` means only that the source packet passed this
contract's structural and freshness checks. It is not an investment decision,
recommendation, suitability determination, approval, or execution permission.

## Time Model

Every assessment records three distinct times:

- `effective_at`: when the fact or observation applies;
- `published_at`: when the source made it available;
- `retrieved_at`: when the permitted workflow observed it.

Freshness is evaluated at `assessed_at` against an explicit
`max_age_seconds`. The calculated `age_seconds` remains inspectable. Missing
timestamps produce `unknown`, not an inferred time.

Market-price and corporate-action evidence also records:

- market;
- exchange timezone;
- trading date;
- session state;
- calendar verification status.

ASX records use `Australia/Sydney`. US-listed-equity records use
`America/New_York`. UTC timestamps remain the interchange format; the exchange
timezone preserves the market interpretation. A holiday, suspension, delayed
feed, or unverified calendar is not silently treated as a normal trading day.

Freshness thresholds are source- and purpose-specific inputs. This contract
does not declare one universal threshold for filings, prices, corporate
actions, or research estimates.

## Provenance And Licence Model

Each source records:

- stable source ID and source class;
- publisher and non-secret locator;
- access basis;
- reliability;
- licence status and redistribution boundary;
- supported claim IDs;
- known limitations;
- conflict status.

Source access is not permission to retain, reproduce, train on, upload, or
redistribute content. Raw source bodies, credentials, account identifiers,
positions, order data, and private paths do not belong in the record. Fixtures
use synthetic locators and synthetic statements only.

## Blocking Rules

An assessment must remain ineligible for the Investment Decision Gate when any
material source has:

- stale or unknown freshness;
- an unknown licence boundary;
- an unresolved source conflict;
- missing provenance;
- an unverified market calendar where one is required;
- a market/timezone mismatch;
- a missing factual as-of time;
- no separately recorded basis for public-source access.

An ineligible assessment keeps explicit `block_reasons`. An eligible
assessment has no block reasons, uses only fresh or not-applicable sources, and
retains `human_decision.status` as `pending`.

## ASX And US Listed Equities

### ASX

- Exchange timezone: `Australia/Sydney`.
- Calendar basis: `ASX`.
- Corporate actions, suspensions, delistings, and delayed market data remain
  explicit limitations.
- Franking credits, tax treatment, and personal suitability remain outside
  this contract.

### US Listed Equities

- Exchange timezone: `America/New_York`.
- Calendar basis: `US_MARKET`.
- Filing publication time, earnings-release time, regular versus extended
  session, and corporate actions remain explicit.
- A filing or price observation is evidence, not an instruction to trade.

## Non-Execution Boundary

This contract must not:

- connect to a broker, account, portfolio, wallet, mailbox, or cloud drive;
- request credentials, API keys, cookies, holdings, or order records;
- retrieve, scrape, subscribe to, or continuously monitor a source;
- upload customer material or transfer it to an external service;
- generate, route, transmit, simulate as executable, or submit an order;
- convert research eligibility into permission or approval.

Any future source retrieval needs a separate exact-source approval and a
separate provider/data-licence contract. Any future monitoring remains a
human-approved review plan, not a background job.

## Versioning And Rollback

- Initial schema version: `1.0.0`.
- The contract is additive to Investment Decision Gate `1.0.0`.
- Existing gate packets remain readable and are not rewritten.
- Runtime integration, if ever approved, must be independently removable.
- Rollback removes the companion contract route while retaining records and
  schemas needed to interpret historical assessments.

## Definition Of Done

- Draft 2020-12 schema is closed and machine-readable.
- Synthetic ASX and US scenarios cover eligible and blocked states.
- Freshness arithmetic and market/timezone mappings are independently checked.
- Facts, derived claims, and judgments remain distinguishable.
- Stale, unknown, conflicted, unlicensed, or calendar-unverified evidence
  cannot be represented as decision-gate eligible.
- No runtime, provider, network, customer-upload, account, or trading
  capability is added.
