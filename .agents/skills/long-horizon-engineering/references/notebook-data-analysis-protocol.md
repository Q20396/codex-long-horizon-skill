# Notebook Data Analysis Protocol

Use this protocol for exploratory data analysis, notebooks, local calculations,
charts, tables, or stateful analytical work.

## Workflow

1. Define the question and expected output.
2. Identify data sources and privacy limits.
3. Inspect schema, shape, missingness, and sample rows.
4. Work incrementally, keeping assumptions visible.
5. Validate intermediate results before building on them.
6. Separate exploration cells from final narrative cells.
7. Clean rerun before claiming results.
8. Summarize limitations and reproducibility notes.

## Stateful Work Rules

- Track what data was loaded and transformed.
- Avoid hidden state when possible.
- Re-run from a clean kernel before final claims.
- Do not rely on stale variables or partial reruns.
- Save generated outputs only when useful and approved.

## Privacy

Do not load private client data, financial records, medical data, family
information, legal evidence, identity documents, or confidential research data
without explicit scope approval. Prefer synthetic, redacted, or aggregate data
for examples.

## Final Evidence

Record:

- Data source
- Filters and transformations
- Commands or notebook sections run
- Checks performed
- Known limitations
- Whether a clean rerun passed
