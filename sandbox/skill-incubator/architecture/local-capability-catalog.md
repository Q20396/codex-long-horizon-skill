# Local Capability Catalog

Status: sandbox-only, explicit-only, static descriptor contract.

The packaged catalog at
`.agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json`
lets LHE recognize customer language and suggest a bounded
capability card. Discovery is not routing, installation, loading, execution,
approval, or evidence that a provider exists. Only locally available,
host-visible skills can be called, and every non-core capability remains
unavailable until a separate installation or one-run authorization is approved.

## Fixed Boundaries

- Keyword matches may produce a suggestion only.
- Uninstalled code is never loaded or fetched.
- Sandbox and proposal records are never executable.
- Ambiguous matches require clarification.
- No match returns `CAPABILITY_NOT_DECLARED`.
- A capability card cannot grant read, write, network, account, connector,
  persistence, installation, execution, publication, or external-action effects.
- Customer-sensitive information is never uploaded, pasted, synced,
  transmitted, or included in model memory or telemetry.
- LHE Core does not implement a runtime router or host enforcement.

## Package Boundaries

`local-governance-core` is a compatibility alias for the existing minimal
`core` component. It does not include the domain-pack implementations or any
provider runtime.

The following descriptors are physically separated under `domain-packs/`:

- Australian legal-evidence organization;
- family and office document governance; and
- Australian and US public-equity research.

Each descriptor is `sandbox-only`, `explicit-only`, `descriptor-only`,
`installed: false`, `callable: false`, and `executable: false`. The files define
future product boundaries; they are not host-discoverable skills because they
contain no `SKILL.md`.

The Local Case Evidence Provider is a separate, default-disabled provider
contract. The packaged provider registry records only an interface declaration:
`declared-disabled`, `runtime_present: false`, and synthetic pilot status
`fixture-only`. It is not part of LHE Core and has no connector implementation.
Capability cards that name a provider must resolve to this closed registry.

A synthetic pilot loads only repository fixtures and exercises structural
contracts in tests. It has no network, account, credential, persistence,
encryption, or connector behavior and cannot establish that a production
provider is feasible at runtime.

## Static Validation Limits

Static checks can prove that the catalog is closed, that fixed fields have safe
values, that descriptor files exist, and that synthetic keyword cases map to
suggestions. The dependency-free fallback validates types before semantic
membership or reference checks and returns `FIELD_TYPE_INVALID` without
traversing the malformed branch. A node-aware keyword inventory fails the test
suite if the schema starts using an unsupported validation keyword.

These checks cover only the explicitly enumerated schema nodes, fixtures, and
product-language surfaces. They cannot detect arbitrary natural-language
overclaims and cannot prove host routing, installation state, provider
availability, connector behavior, encryption, credential isolation, runtime
permissions, or customer approval.
