#!/usr/bin/env python3
"""Append non-sensitive durable facts to docs/PROJECT_MEMORY.md."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


MEMORY_PATH = Path("docs/PROJECT_MEMORY.md")
HEADER = """# Project Memory

This file stores durable, non-sensitive project facts for future Codex runs.

Do not store secrets, private client data, legal evidence, family information,
API keys, tokens, credentials, or other sensitive personal data here.

## Durable Facts
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append durable, non-sensitive project facts to docs/PROJECT_MEMORY.md."
    )
    parser.add_argument(
        "facts",
        nargs="+",
        help="One or more non-sensitive project facts to append.",
    )
    return parser.parse_args()


def ensure_memory_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER.rstrip() + "\n", encoding="utf-8")


def append_facts(path: Path, facts: list[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n### {timestamp}\n"]
    lines.extend(f"- {fact.strip()}\n" for fact in facts if fact.strip())

    if len(lines) == 1:
        raise SystemExit("No non-empty facts were provided.")

    with path.open("a", encoding="utf-8") as handle:
        handle.writelines(lines)


def main() -> None:
    args = parse_args()
    ensure_memory_file(MEMORY_PATH)
    append_facts(MEMORY_PATH, args.facts)
    print(f"Appended {len(args.facts)} fact(s) to {MEMORY_PATH}")


if __name__ == "__main__":
    main()
