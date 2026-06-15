#!/usr/bin/env python3
"""Append completed task entries to docs/TASK_LOG.md."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


TASK_LOG_PATH = Path("docs/TASK_LOG.md")
HEADER = """# Task Log

This file records completed engineering tasks in a concise, resumable format.

Do not store secrets, private client data, legal evidence, family information,
API keys, tokens, credentials, or other sensitive personal data here.

## Entries
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append a completed task entry to docs/TASK_LOG.md."
    )
    parser.add_argument("--title", required=True, help="Short completed task title.")
    parser.add_argument("--summary", required=True, help="Brief summary of the change.")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Changed file path. Repeat for multiple files.",
    )
    parser.add_argument(
        "--verification",
        action="append",
        default=[],
        help="Verification command and result. Repeat for multiple checks.",
    )
    parser.add_argument("--notes", default="", help="Optional risk, note, or follow-up.")
    return parser.parse_args()


def ensure_task_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER.rstrip() + "\n", encoding="utf-8")


def bullet_list(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return [f"- {fallback}\n"]
    return [f"- {item}\n" for item in cleaned]


def append_entry(path: Path, args: argparse.Namespace) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    notes = args.notes.strip() or "None."
    lines = [
        f"\n### {timestamp} - {args.title.strip()}\n\n",
        "**Summary**\n\n",
        f"- {args.summary.strip()}\n\n",
        "**Files**\n\n",
        *bullet_list(args.file, "No files recorded."),
        "\n**Verification**\n\n",
        *bullet_list(args.verification, "No verification recorded."),
        "\n**Risks / Notes**\n\n",
        f"- {notes}\n",
    ]

    with path.open("a", encoding="utf-8") as handle:
        handle.writelines(lines)


def main() -> None:
    args = parse_args()
    if not args.title.strip() or not args.summary.strip():
        raise SystemExit("--title and --summary must be non-empty.")

    ensure_task_log(TASK_LOG_PATH)
    append_entry(TASK_LOG_PATH, args)
    print(f"Appended task entry to {TASK_LOG_PATH}")


if __name__ == "__main__":
    main()
