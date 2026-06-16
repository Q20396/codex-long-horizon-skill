# Data Cleaning Protocol

Use this optional protocol for CSV, spreadsheet, JSON, database export, or
notebook work where the task is to profile, clean, normalize, transform, or
prepare data for analysis.

This protocol is for reproducible data work. It must not be used to expose
private datasets or store sensitive records in reusable skill logs.

## Workflow

1. Confirm the question and intended use of the cleaned data.
2. Identify whether the dataset is sensitive.
3. Inspect schema, row counts, column types, units, dates, currencies, and
   identifiers.
4. Profile missing values, duplicates, outliers, invalid values, and inconsistent
   categories.
5. Propose cleaning rules before applying destructive transformations.
6. Preserve the original data unless the user explicitly approves overwriting.
7. Record before/after counts and transformation decisions.
8. Produce a reproducible command, script, or notebook rerun path when possible.

## Common Cleaning Areas

- Column naming and schema normalization
- Type conversion
- Date, timezone, currency, and unit normalization
- Missing value strategy
- Duplicate detection and deduplication keys
- Categorical value normalization
- Text cleanup
- Outlier review
- Join key validation
- Data quality summary

## Evidence Standard

For each transformation, record:

- Column or field
- Issue found
- Rule applied
- Rows affected
- Before example, redacted if needed
- After example, redacted if needed
- Risk or limitation

## Privacy

Treat client names, emails, addresses, legal evidence, family information,
medical information, financial account details, identity documents, private
correspondence, and confidential source content as sensitive. Prefer aggregate
counts, redacted examples, or synthetic examples in reports.

Do not upload private data to external notebooks, cleaning tools, or hosted
services without explicit approval.
