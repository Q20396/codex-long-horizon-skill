# Capability Profile / Doctor Contract

Status: `sandbox-only`

This is an explicit-only, dependency-free static contract for synthetic
capability declarations and diagnostics. It is not an installed doctor,
runtime probe, router, repair tool, capability launcher, or host-enforced
isolation mechanism.

## Purpose

The contract keeps four questions separate:

1. what a capability declares;
2. what static repository evidence was locally observed;
3. what remains unverified or blocked; and
4. what non-authorizing recovery suggestion a reviewer may consider.

The supported capability statuses are:

- `declared`: represented by declaration evidence only;
- `locally_observed`: supported by synthetic static-repository observation;
- `unverified`: lacks sufficient implementation evidence; and
- `blocked`: cannot proceed under the stated boundary.

No status means installed, callable, routed, executable, approved, promoted,
or runtime-enforced.

## Default-deny doctor boundary

The profile fixes every doctor effect to `false`. The contract cannot read:

- installed skills;
- user or host configuration;
- accounts or credentials;
- project or client materials; or
- logs or conversation history.

It also cannot use the network, start a process, install a dependency, mutate a
default profile, change routing, or invoke a capability. Capability `effects`
must be an empty list.

Diagnostics contain a stable reason and a non-empty recovery suggestion. A
suggestion is informational only. It cannot repair state, grant authority,
change a status, or trigger an action.

## Synthetic evidence

Fixtures use only `SYN-*` identifiers and `synthetic://` locators. They contain
no real repository, person, account, client, host, package, or project data.
Identifiers are globally unique, and every reference resolves to the expected
object type.

`locally_observed` means only that the synthetic record contains an
`lhe_implementation` evidence card with kind
`static_repository_observation`. It does not prove runtime availability.

## Comparative design references

An external tool or architecture may be represented only as an
`external_source_statement` evidence card. A comparative record must separately
reference LHE implementation evidence. External statements never become LHE
implementation evidence, automatic dependencies, compatibility claims, or
authority.

Comparative dispositions are limited to `adopt-principle-only`, `reject`, or
`defer`. The contract contains no third-party code, wording, commands, package
metadata, or installation instructions.

## Static validation

The Draft 2020-12 Schema is a structural gate. The dependency-free contract
tests additionally check:

- recursively closed objects;
- required fields, JSON types, enums, and constants;
- array minimum/maximum cardinality and deep JSON uniqueness;
- string minimum/maximum length and regular-expression patterns;
- fail-closed handling of invalid Schema regular expressions;
- synthetic identifier format and global uniqueness;
- type-correct evidence and diagnostic references;
- status/evidence consistency;
- non-empty recovery suggestions;
- sensitive-field and external-effect rejection; and
- separation of external statements from LHE implementation evidence.

Static validation can establish consistency of synthetic records only. It
cannot prove capability availability, source accuracy, installation state,
runtime behavior, permissions, security, compatibility, or host enforcement.

## Candidate human state

The candidate is fixed to:

```text
human_disposition: pending
next_stage_authorized: false
promotion_state: not-promoted
```

No fixture, diagnostic, comparison, or evidence card can change that state.
Any implementation, integration, installation, promotion, or external
architecture adoption requires a separate customer-approved envelope.

## Rollback

This candidate adds only five sandbox architecture, schema, fixture, and test
paths. It creates no runtime state. Before integration, rollback is discarding
the isolated worktree.
