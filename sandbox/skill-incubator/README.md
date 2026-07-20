# Skill Incubator

This is a locked, local source-ledger for researching candidate skill patterns.
It is not an installer, marketplace, runtime, provider configuration, or
automatic self-improvement system.

## Baseline And Status

- Repository baseline: `refs/remotes/origin/main`
- Pinned baseline commit: `5646f60d7c3c3fd63b27796096bc1400142fd055`
- Incubator status: `locked`
- Default action: collect metadata, explain risk, and wait for an explicit
  customer decision.

`status: locked` means no source may be cloned, installed, executed, imported,
registered as MCP, or promoted. `verification_status` independently records
whether a source identity and immutable reference were confirmed.

## Boundaries

- Third-party code is never copied into this repository through this ledger.
- GitHub metadata is pinned to complete 40-character commit SHAs.
- Screenshots, short videos, star counts, benchmark claims, and marketing copy
  are leads only, not source-of-truth evidence.
- Private files, connected services, credentials, customer materials, and
  unrelated financial documents are out of scope.
- Unrelated private financial documents were excluded.

Read `registry.json` first, then the applicable policy and source directory.
The `experiments/` directory contains no executable experiment code.
