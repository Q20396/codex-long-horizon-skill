# High-Stakes Customer Workflows

Status: static guidance. No connector, account, storage, legal-advice,
investment-advice, or execution capability is included.

## Common entry

The customer starts with an outcome and decision question. LHE reads only
public, synthetic, or exact approved non-sensitive local material. It may match
the language to a descriptor-only capability card, but the match does not load
or run a domain skill.

Every result has three layers:

1. **Customer**: `FACT`, `INFERENCE`, `UNKNOWN`, one status, one next safe
   action, and one decision question.
2. **Operator**: exact read scope, forbidden effects, data-locality boundary,
   stop conditions, and fixed pending human disposition.
3. **Engineering evidence**: source locators, hashes where appropriate,
   validation performed, validation omitted, and limitations.

Customer-sensitive material must never be uploaded, pasted into a remote model,
recorded in model memory, or sent to telemetry. An exact local path is not
permission to read it. The customer must separately approve the path and use.

## Australian legal-evidence organization

LHE may suggest the `australian-legal-evidence` descriptor when the customer
asks to organize evidence, chronology, provenance, or disclosure preparation.
It does not provide legal advice, determine admissibility, contact a lawyer,
file material, or decide preservation duties.

The safe first result normally identifies:

- the matter boundary and jurisdiction as declared, not inferred;
- approved source classes and date range;
- source/version/hash/locator requirements;
- the distinction between source-supported facts, analysis, and gaps;
- whether counsel direction is required for legal hold or preservation.

Dropbox, Gmail, Outlook, Hotmail, and Google Drive are not read by LHE Core.
A future Local Case Evidence Provider may reconnect for one approved delta,
update an encrypted local index, and disconnect. That provider remains
`declared-disabled` and unimplemented.

## Family and office document governance

LHE may suggest the `family-office-document-governance` descriptor for local
document inventories, retention schedules, ownership tables, or review queues.
It does not store records, make tax or legal decisions, delete files, or
publish documents.

A safe result can use synthetic metadata to propose:

- local classification and ownership labels;
- review and retention decisions that remain pending;
- duplicate and missing-document evidence;
- one explicitly approved next local inspection.

Deletion remains blocked when ownership, retention, or legal-hold status is
unknown.

## Australian and US public-equity research

LHE may suggest the `public-equity-research` descriptor for public-source,
as-of-date company research. It does not connect a brokerage account, access
credentials, place orders, rebalance a portfolio, or make the customer's
allocation decision.

The research boundary requires:

- approved public source classes and an as-of time;
- company and market identifiers;
- source freshness and claim locators;
- separate business-quality, valuation, risk, and portfolio-fit analysis;
- `UNKNOWN` for missing or stale evidence.

Any request to access an account, submit an order, or execute a trade is
`BLOCKED`. The next safe action must return to a public-source, research-only
scope.

## Future Local Case Evidence Provider

The provider is outside LHE Core and default-disabled. A future implementation
must use:

- per-connector, per-run approval and minimum scopes;
- tokens only in OS credential storage;
- an encrypted local case store separate from repositories;
- an immutable source/version/hash/locator ledger;
- extraction provenance and `FACT` / `INFERENCE` / `UNKNOWN` timeline;
- cursors as hints that are rejected when stale or inconsistent;
- explicit retention, raw-snapshot, deletion, export, and legal-hold controls;
- no model memory, telemetry, background sync, or automatic reconnection.

Raw snapshots are off by default. A new email or document requires a new
approved connector run for fresh deltas, while the previously indexed local
ledger remains usable. Counsel, not LHE, defines preservation or legal-hold
requirements.

The current synthetic pilot is `fixture-only`. It compares two repository
checkpoints and shows how one new content hash could be distinguished from
unchanged hashes. It does not call a connector, authenticate, encrypt, persist,
or process customer material, and it cannot validate any production behavior.

## Static limits

These documents, schemas, and synthetic fixtures can test structure and
fail-closed policy. They cannot prove encryption, OS credential isolation,
connector behavior, deletion, legal compliance, source authenticity, runtime
permissions, host isolation, or customer authorization.
