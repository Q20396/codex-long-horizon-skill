# Notebook and Data Analysis Protocol

Use this protocol for data exploration, CSV/XLSX/JSON analysis, benchmarks,
financial calculations, repository metrics, charts, notebooks, and experiments.

This protocol is inspired by stateful notebook workflows, but it is
provider-neutral and does not require a specific notebook service.

## Workflow

1. Define the question.
2. Load data safely.
3. Record assumptions.
4. Explore incrementally.
5. Save intermediate artifacts if useful.
6. Separate exploration from final result.
7. Clean-rerun the final calculation when possible.
8. Report reproducible commands and files.

## Rules

- Do not treat exploratory state as final evidence.
- Do not silently drop rows or columns.
- State timezone, currency, units, and date.
- For charts, label axes and source.
- For notebooks, restart and rerun when claiming final reproducibility if
  possible.

## Privacy

Do not upload private data to external notebooks, kernels, or hosted analysis
services without explicit permission.
