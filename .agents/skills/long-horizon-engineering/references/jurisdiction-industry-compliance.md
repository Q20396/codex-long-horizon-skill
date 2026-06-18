# Jurisdiction And Industry Compliance

Use this guide when a task needs location-aware or industry-aware legal,
regulatory, or rule-of-practice context.

This guide is for engineering and product planning support only. It is not
legal advice. For high-stakes legal, financial, medical, employment, tax,
immigration, insurance, education, or regulated-industry decisions, tell the
user to consult a qualified professional.

## Location Handling

Location can be sensitive. Do not silently enable GPS, read device location,
scan location history, or infer precise location from private files.

Before using location, ask the user to provide or approve:

- Country or region
- State, province, territory, or city when needed
- Whether approximate location is enough
- Whether cross-region comparison is needed
- Whether the location may be mentioned in the output

Use an explicit choice prompt:

"To provide relevant legal, regulatory, and industry-rule context, should I use
your approved device/GPS location, or would you prefer to manually provide the
country, state/province, and city or region?"

If a location tool is available, request explicit permission before using it.
If no approved location is available, ask the user to provide the jurisdiction
manually.

Do not store precise location, addresses, client locations, travel history, or
private operational locations in memory, logs, working state, or handoff files.

## Optional Regional Skill Loading

When cross-region rules may matter, ask whether the user wants Codex to load or
read additional legal, regulatory, or industry-rule skills or reference files for
other regions.

Use an explicit privacy-preserving prompt:

"Would you like me to load any approved skills or reference files for other
regions' laws, regulations, or industry rules? I can use public/non-sensitive
sources only, or you can name the exact skill, folder, or file to read. I will
not read private client materials, precise locations, legal evidence, or
confidential documents unless you explicitly approve the exact scope."

Before loading any additional skill or reference source, confirm:

- Region or jurisdiction to compare
- Industry or rule category to check
- Skill, folder, file, connector, or public source to read
- Whether metadata-only review is enough
- Whether any private client material is excluded
- Whether findings may be summarized in the answer

Do not load broad local folders, cloud drives, Gmail, private legal files, or
client documents merely to find regional rules. Prefer public official sources
or user-approved reusable skills. If the requested source may contain sensitive
material, stop and ask for narrower approval.

## Industry Context

Before giving legal, regulatory, or industry-rule guidance, identify the user's
industry or operating context. When unclear, ask a short clarification such as:

- What industry or business activity is this for?
- Who is the target customer or user?
- Is the work consumer-facing, business-facing, internal, or regulated?
- Which country, state, province, or city should be considered?

Examples of industry context include:

- Health, medical, wellness, or aged care
- Finance, investment, lending, tax, payments, or insurance
- Legal services, disputes, evidence, or contracts
- Education, childcare, family services, or immigration
- Real estate, construction, transport, logistics, or employment
- AI, software, media, advertising, e-commerce, or data services

## Source And Evidence Rules

Legal and regulatory information changes. Use current public sources when
making jurisdiction-specific claims. Prefer:

- Official government websites
- Regulator guidance
- Statutes, codes, or rules from official sources
- Court or tribunal guidance when relevant
- Industry body rules from the relevant jurisdiction
- Platform policy pages when platform compliance matters

Separate:

- Fact: directly supported by a cited source
- Inference: a practical implication based on the facts
- Recommendation: a suggested next step
- Uncertainty: what still needs professional or official confirmation

Do not invent laws, dates, penalties, licensing requirements, or regulator
positions. If evidence is unclear, say so and ask whether the user wants a
deeper jurisdiction-specific check.

## Local Source Gap And Online Search Prompt

When the user asks about laws, tax rules, regulatory requirements, platform
rules, or industry rules for a country, state, province, city, or region, first
check whether approved local references already contain current, relevant
sources.

If local references are missing, stale, too generic, or do not cover the
requested jurisdiction, automatically identify the source gap and prompt the
customer before searching online.

Use a privacy-first prompt such as:

"I do not have enough current local reference material for this jurisdiction,
tax topic, or industry rule. Would you like me to search current public sources
online? I will use official or reputable public sources where possible, avoid
sending private client details, and summarize facts separately from practical
implications."

Before online search, confirm:

- Jurisdiction or region to check
- Tax, legal, regulatory, platform, or industry-rule topic
- Industry or business activity
- Whether official government or regulator sources are required
- Whether cross-region comparison is needed
- Whether any private client facts must be excluded from the search query

When searching online:

- Prefer generic, non-sensitive search queries.
- Do not include client names, private facts, legal evidence, financial account
  details, family information, precise addresses, or confidential documents in
  search terms.
- Prefer official government, regulator, tax authority, court, standards-body,
  platform, or industry-body sources.
- Capture source name, URL, publication or update date when available, and the
  date searched.
- Treat unofficial summaries as secondary only.

After the search, tell the customer what was found, what remains uncertain, and
whether the skill package or project docs should be updated. Do not update
reusable skill guidance with jurisdiction-specific claims unless the user asks
for a bounded, reviewed change and the source is appropriate for public reuse.

## Cross-Region Check

After giving a local or industry-specific answer, ask whether the user wants to
compare other jurisdictions when that could matter.

Useful prompts:

- "Do you also operate in another state, province, country, or online market?"
- "Should I compare the rules for nearby regions or target customer locations?"
- "Do you want a cross-region compliance table before implementation?"

Do not expand to broad cross-region research unless the user approves the
regions and scope.

## Safe Output Pattern

When providing location-aware industry guidance, use this structure:

1. Confirmed jurisdiction and industry
2. Public facts and sources used
3. Practical implications
4. Recommended engineering or product actions
5. Open questions and professional-review flags
6. Ask whether cross-region rules should be checked

Keep sensitive facts generic. Use labels such as "client operating region" or
"regulated business activity" instead of copying private client details.

## Stop And Ask

Pause before continuing if:

- The user asks Codex to enable GPS or device location without clear consent.
- The task requires precise address, travel history, family location, client
  location, or private operational location.
- The jurisdiction or industry is unclear and the answer would change by region.
- The requested output could be mistaken for legal advice.
- The work involves legal evidence, financial accounts, medical data, identity
  documents, immigration, employment disputes, tax filings, insurance claims, or
  regulated professional services.
- Current legal or regulatory facts are needed but cannot be verified from
  reliable public sources.
