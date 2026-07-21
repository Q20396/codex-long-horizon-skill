# Public Equity Research Sandbox

## Status

- Candidate ID: `PUBLIC-EQUITY-RESEARCH-SANDBOX`
- Status: `locked`
- Registered experiment: `false`
- Implementation exists: `false`
- Customer decision: `not_approved`
- Investment advice: `NOT PROVIDED`

This is a proposal for evidence-led research design concerning ASX and US
listed equities. It is not a research product, signal service, brokerage
integration, portfolio-management system, or execution system.

## Purpose

The candidate would make a future research process inspectable before any
market-data or provider decision:

1. Define the question, universe, as-of date, and source-license boundaries.
2. Record a falsifiable hypothesis and its invalidation conditions.
3. Design a time-safe backtest, including corporate actions, delisted names,
   trading costs, liquidity assumptions, and out-of-sample evaluation.
4. Prepare evidence and known unknowns for a human investment decision.

It does not claim that a model, an agent, or a backtest produces a valid
investment recommendation.

## Activation And Input Boundary

Invocation is contextual and explicit. A standalone `review` request may select
this candidate only when the active conversation already contains an
unambiguous, customer-provided public-equity object: ASX or US-listed tickers,
holdings, or a watchlist. Before research, the response must state the exact
market and supplied instruments it understood. It must ask a clarifying question
when the context is absent, mixed with another review subject, or leaves the
market or instruments uncertain.

The following are research-intake examples only, not permission to access data
or provide investment advice:

- `review my ASX holdings`
- `review my US stock holdings`
- `review this stock watchlist`
- `review my portfolio`
- `review my listed stocks`

The sandbox accepts only tickers or holdings that the customer supplies in the
current conversation. It must not infer them from earlier hidden context, logs,
or account data. Reading a local file requires separate exact-path approval. It
must not scan broker accounts, email, cloud drives, wallets, browser history,
or other customer records.

Customer-provided financial material may be organized and analyzed only within
the approved local conversation or exact approved path. It must not be uploaded,
pasted, synchronized, summarized into an external service, or otherwise
transferred to a provider, cloud drive, mailbox, broker, or third party. This
candidate may produce research-oriented analysis summaries and educational risk
considerations; it must not provide personalized buy, sell, hold, allocation, or
execution advice.

This boundary controls the candidate's external tool behavior. It does not
override the data-handling terms or organizational settings of the Codex
platform through which a customer voluntarily supplies material. Sensitive
customer material should be excluded unless the customer is authorized to share
it in that platform.

For a request about today's market, the sandbox must ask for the market,
tickers or universe, date and time horizon, and approval to verify named public
sources. Until that approval is given, it may only prepare a research plan and
known-unknowns record.

## Market-Specific Evidence Requirements

### ASX

- Confirm the market-data licence, currency convention, trading calendar, and
  as-of timestamp before analysis.
- Model corporate actions, suspensions, delistings, and liquidity explicitly.
- Treat franking credits, tax consequences, and individual suitability as out
  of scope for this sandbox.

### US Listed Equities

- Preserve filing, earnings-release, and market-data publication timestamps.
- Model corporate actions, survivorship bias, trading costs, and regular versus
  extended-hours assumptions explicitly.
- Do not treat a public filing, sentiment score, or model output as a trade
  instruction.

## Permitted Outputs

- source evidence cards
- research hypotheses
- known-unknowns records
- backtest designs
- risk and invalidation criteria
- research-oriented analysis summaries
- educational risk considerations
- human review packets

All outputs remain research material. A reviewer must be able to identify the
source, time basis, assumptions, limitations, and the decision that remains
with the human.

## Prohibited Actions

- broker connection, account inspection, or account synchronization
- credential, API-key, cookie, wallet, or portfolio access
- customer-material upload, external transfer, synchronization, or provider
  submission
- market-data download, scraping, provider invocation, or third-party code
  execution
- automatic signal generation, trade recommendation, order creation,
  submission, copy trading, rebalancing, or publication
- importing source code, prompts, benchmark claims, or marketing claims from a
  third party into a stable skill

No permission is implied by a repository name, an image, a benchmark claim, a
Star count, a public URL, or a previous approval for a different operation.

## Candidate Source Discipline

`TradingAgents` is an existing locked methodology lead in this Incubator. Its
recorded source pin and Apache-2.0 repository-level licence do not authorize
execution, code import, financial data use, or investment advice.

Qlib, FinGPT, FinRobot, AI-Trader, ValueCell, QuantDinger, OpenAlice,
AutoHedge, and ai-berkshire are external leads only. Before any separate
candidate is proposed, each requires an immutable 40-character commit pin,
repository and per-file licence review, security review, maintenance review,
and an explicit customer decision. No public claim about ASX or US coverage is
accepted until supported by a scoped, reproducible evaluation.

## Future Gates

Any future work must pass all of these separate gates:

1. Source identity and licence are independently verified.
2. A data-source, data-retention, privacy, and external-access proposal is
   reviewed.
3. A synthetic or licensed fixture is approved before an evaluation begins.
4. Backtest assumptions and out-of-sample criteria are reviewed before any
   results are interpreted.
5. A human independently reviews the evidence. No gate authorizes trading.

The machine-readable locked contract is
`public-equity-research-sandbox.json`, validated by
`../schemas/public-equity-research-sandbox.schema.json`.
