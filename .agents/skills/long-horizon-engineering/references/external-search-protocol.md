# External Search Protocol

External search is optional. Use it only when local repository inspection and
user-provided context are not enough.

Search providers may include built-in web search, GitHub search, package
registry search, documentation search, AnySearch-style unified search, or other
approved tools. No provider is mandatory or exclusive. AnySearch is one example
of a unified search provider; this skill does not depend on it.

## Privacy Rules

Never send the following to external search providers:

- Secrets, `.env` files, credentials, tokens, or API keys
- Private client data
- Legal evidence
- Financial documents
- Medical information
- Proprietary source not intended for disclosure
- Confidential documents or private correspondence

Prefer searching for public facts, public docs, package docs, public GitHub
repositories, release notes, CVEs, standards, and vendor docs.

For private repository work, search public docs for libraries, frameworks,
tools, errors, standards, or APIs. Do not paste private code snippets into
external search unless the user explicitly approves the exact content.

## Search Planning

Before searching:

1. Define the question.
2. Split it into targeted queries.
3. Choose source classes:
   - official docs
   - GitHub repos/issues
   - package registries
   - security advisories/CVEs
   - standards/specs
   - vendor changelogs
   - broad web only if needed
4. Prefer authoritative sources.
5. Record date, source, and confidence.

## Structured Output Schema

Use this structure for search findings when a task needs traceability:

```text
query:
source_type:
source_url_or_identifier:
finding:
evidence:
confidence:
actionability:
risk:
checked_at:
```

## Search Decision Matrix

| Situation | Search Choice |
| --- | --- |
| Local files already answer the question | No external search needed |
| Library or API usage is uncertain | Search official docs only |
| Behavior may be affected by known bugs | Search GitHub repos/issues |
| Security impact is possible | Search security advisories/CVEs |
| Current rules, standards, or vendor behavior may have changed | Search official standards, specs, or vendor changelogs |
| Authoritative sources are insufficient | Search broad web |
| Query would expose private data | Do not search externally because data is private |

## Batch Search Pattern

- Use one query per independent uncertainty.
- Run independent searches in parallel when tooling allows.
- Deduplicate sources before synthesizing.
- Synthesize findings before acting.
- Do not paste raw search dumps into final output.
- Keep source quotes short and use links or identifiers for traceability.

## Acting On Search Results

Treat search as evidence, not permission to change code. Before editing, connect
external findings back to local files, tests, and user requirements. If sources
conflict, name the conflict and prefer official or primary sources.
