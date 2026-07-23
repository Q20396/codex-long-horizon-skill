# License And Clean-Room Policy

Repository-level license metadata is not a per-file license grant. No third-party
code, prompts, datasets, assets, or prose may be copied into stable skills.

## Adoption States

Every external candidate remains in exactly one of these states:

1. `methodology_only`: The Incubator contains only an evidence-backed summary of
   a reusable idea. No source checkout, code, prompt corpus, asset, or dataset is
   stored here.
2. `external_reference_only`: A separately approved, read-only checkout may be
   kept outside this repository for review. It retains its original owner,
   copyright notices, license, commit pin, and directory boundary. It is not our
   code and must not be copied into this repository by default.
3. `clean_room_candidate`: A new implementation may be designed from approved
   behavioral requirements and tests. Its author must not copy third-party
   source, prose, prompts, assets, or datasets. Independent review must check
   provenance and similarity risks before any promotion.

No state authorizes runtime execution, network access, installation, provider
configuration, account access, or publication. A proposal, a license label, or
an external checkout is not permission to adopt code.

## Direct-Import Default

Direct third-party code import into a stable skill is `DENY`. A later exception
requires separate customer approval for the exact paths and commit, a
repository-level and per-file license review, dependency and security review,
attribution and notice plan, compatibility review, rollback plan, and an
independent review. The exception must be documented before any import; it does
not make third-party code "our own code."

AGPL candidates, including MiroFish, are clean-room methodology candidates only.
Any future implementation must be independently authored after a separate
license, provenance, and compatibility review.
