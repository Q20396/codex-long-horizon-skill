# Multi-Perspective Financial Research Workflow

Use this explicit-only, static workflow to prepare a public-equity research
packet for customer review. It organizes competing research views; it is not a
multi-agent runtime, data service, portfolio manager, broker, or trading
system.

This workflow borrows only a general research discipline from external
multi-perspective frameworks: separate evidence, counter-case, and risk review
before reaching a research conclusion. It imports no third-party code,
dependency, prompt, provider configuration, model, or runtime.

## Preconditions

- State the research question, market, universe, as-of time, and currency.
- Use only non-sensitive, approved material. Do not read holdings, accounts,
  credentials, private portfolios, or non-public research.
- Default to offline work. A one-run network approval is required before any
  public data retrieval; that approval never permits customer-data upload.
- Record an expiry and revocation route for the research agreement.

## Four research views

Use the same evidence ledger for each view. Each conclusion must be labelled
`FACT`, `INFERENCE`, or `UNKNOWN`.

1. **Fundamentals** — business quality, financial durability, capital needs,
   governance, and material accounting or balance-sheet risks.
2. **Market and valuation** — market expectations, comparable framing,
   valuation assumptions, sensitivity, and the data-date limitation.
3. **Counter-case** — the strongest credible disconfirming evidence, what the
   base hypothesis misses, and explicit falsifiers.
4. **Risk and backtest review** — point-in-time data availability, selection
   bias, survivorship, fees, slippage, corporate actions, sample split, and
   conditions that would invalidate a simulation.

The views are review lenses, not separate autonomous agents. They do not
debate, invoke tools, create memory, fetch data, or make a decision.

## Evidence and conclusion discipline

- A `FACT` names a source locator, source version, and available-at time.
- An `INFERENCE` identifies the facts and assumptions from which it follows.
- An `UNKNOWN` names the missing evidence and why it matters.
- Present a supporting case and counter-case with equal visibility; do not
  collapse disagreement into a single confidence score.
- A simulation or backtest plan must be reproducible and explicitly describe
  universe, rebalancing, fees, slippage, corporate actions, survivorship,
  in-sample/out-of-sample separation, and look-ahead controls.

## Non-negotiable boundary

No account access, no credential access, no order generation, no order
transmission, no trade execution, no automatic rebalancing, no automated
monitoring, no customer-data upload, and no persistent memory are allowed.
The customer remains the only decision authority. A research packet may request
one customer decision or a narrowly scoped one-run network approval; it cannot
send a notification or perform an external action.

This is research assistance, not investment advice. Verify current information
and make independent decisions before taking financial action.
