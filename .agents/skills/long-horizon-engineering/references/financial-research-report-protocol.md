# Financial Research Report Protocol

Use this optional protocol when the user asks for stock, company, sector,
market, valuation, watchlist, or financial research reporting.

This protocol supports evidence-backed analysis only. It must not be used to
place trades, execute orders, provide personalized portfolio advice, or present
buy/sell conclusions as certainty.

## Safe Scope

Before starting, identify:

- Company, ticker, market, sector, or index under review
- Time period and reporting currency
- Intended audience and output format
- Whether the user wants a quick answer, research note, watchlist, or formal
  report
- Any data providers, files, or web sources approved by the user
- Whether private portfolio, client, or account data is involved

If the task involves private holdings, client portfolios, account statements,
tax records, brokerage exports, or non-public company information, treat it as
sensitive and ask before reading, summarizing, logging, staging, or sharing.

## Workflow

1. Define the research question.
2. Create a short research plan before collecting data.
3. Record data sources, dates, fields, units, and limitations.
4. Separate facts, assumptions, calculations, interpretation, and speculation.
5. Validate important numbers before using them in conclusions.
6. Present valuation assumptions and sensitivity where relevant.
7. Include risks, missing data, and alternative explanations.
8. Add a clear disclaimer that the output is data analysis, not investment
   advice.

## Data Source Discipline

Prefer current, primary, or well-documented sources when available:

- Company filings, annual reports, exchange announcements, and investor
  presentations
- Official exchange or regulator pages
- Reputable financial data providers approved by the user
- Public news sources, clearly dated and cited
- Local files only when the user approves the exact scope

For market data, record:

- Source/provider
- Access date
- Covered period
- Currency and unit scale
- Adjustments or transformations
- Missing fields or provider limitations

Do not invent missing values. If a source is unavailable or permission-limited,
say so and continue with caveats or ask for another source.

## Numerical Validation

Before finalizing, check:

- Dates and periods are consistent.
- Currency and units are stated.
- Per-share values use the correct share count.
- Market cap, enterprise value, and price data come from a stated date.
- Growth rates compare like-for-like periods.
- Ranking or screening outputs state the universe and filters.
- Valuation outputs show key assumptions and sensitivity.
- Charts or tables can be reproduced from the listed sources.

## Valuation Guidance

Use valuation methods only when the user asks for them or when they are needed
to answer the research question.

For discounted cash flow or intrinsic value work, record assumptions such as:

- Revenue or cash-flow growth
- Margins
- Capital expenditure or reinvestment
- Discount rate or WACC
- Terminal growth or exit multiple
- Net debt, cash, and share count
- Sensitivity ranges

For banks, insurers, and financial-sector companies, do not default to generic
DCF. Prefer sector-appropriate framing such as ROE/ROTE, capital ratios,
credit costs, net interest margin, payout, book value, and regulatory risk.

## Watchlists and Screens

If the user asks for stock selection or screening, frame the output as a
research watchlist, not a buy list.

For every screen, state:

- Universe
- Filters
- Ranking method
- Data date
- Missing data handling
- Key risks and next verification steps

Avoid deterministic trading signals. Recent price strength, valuation, or news
flow should be treated as an input for further research, not a guarantee.

## Report Shape

A concise financial report may include:

1. Scope and question
2. Sources and data dates
3. Company, sector, or market context
4. Key findings with evidence
5. Financial and valuation snapshot
6. Catalysts or recent developments
7. Risks, missing data, and what could change the view
8. Assumptions and sensitivity
9. Conclusion with caveats
10. Disclaimer

## Required Disclaimer

When discussing securities, include:

`This is data analysis only, not investment advice. Verify current information
and make independent decisions before taking financial action.`

Do not remove or soften this disclaimer for persuasive effect.
