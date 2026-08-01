#!/usr/bin/env python3
"""Preview or explicitly append non-sensitive durable project facts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re


HEADER = """# Project Memory

This file stores durable, non-sensitive project facts for future Codex runs.

Do not store secrets, private client data, legal evidence, family information,
API keys, tokens, credentials, or other sensitive personal data here.

## Durable Facts
"""

SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:api[_ -]?key|secret|password|access[_ -]?token)\s*[:=]", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:account(?:\s+number)?|bsb|tax file number|date of birth)\s*[:#=]", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\+?\d{1,3}[ -]?\d{3,4}[ -]?\d{3,4}[ -]?\d{0,4}\b"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview durable, non-sensitive project facts; writing is explicit and guarded."
    )
    parser.add_argument(
        "facts",
        nargs="+",
        help="One or more non-sensitive project facts to append.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request preview-only mode (the default).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Allow a write after all other guards and --confirm succeed.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm the displayed preview for a non-interactive write.",
    )
    parser.add_argument(
        "--project-root",
        required=True,
        type=Path,
        help="Existing project root that must contain --target-file.",
    )
    parser.add_argument(
        "--target-file",
        required=True,
        type=Path,
        help="Explicit project-relative target file for the memory entry.",
    )
    args = parser.parse_args()
    if args.dry_run and args.apply:
        parser.error("--dry-run and --apply cannot be used together")
    if args.apply and not args.confirm:
        parser.error("--apply requires --confirm after reviewing the preview")
    if args.confirm and not args.apply:
        parser.error("--confirm requires --apply")
    return args


def ensure_memory_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER.rstrip() + "\n", encoding="utf-8")


def append_facts(path: Path, facts: list[str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(build_fact_entry(facts))


def build_fact_entry(facts: list[str]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n### {timestamp}\n"]
    lines.extend(f"- {fact.strip()}\n" for fact in facts if fact.strip())

    if len(lines) == 1:
        raise SystemExit("No non-empty facts were provided.")

    return "".join(lines)


def resolve_target(project_root: Path, target_file: Path) -> Path:
    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("--project-root must be an existing directory")

    candidate = target_file if target_file.is_absolute() else root / target_file
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("--target-file must resolve inside --project-root") from error
    return resolved


def contains_sensitive_content(facts: list[str]) -> bool:
    return any(pattern.search(fact) for fact in facts for pattern in SENSITIVE_PATTERNS)


def main() -> None:
    args = parse_args()
    if contains_sensitive_content(args.facts):
        raise SystemExit("Refusing potentially sensitive facts; do not store them in project memory.")

    try:
        target = resolve_target(args.project_root, args.target_file)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    entry = build_fact_entry(args.facts)
    if not args.apply:
        print("Preview only; nothing was written.")
        print(entry, end="")
        return

    print("Preview confirmed; writing the following entry:")
    print(entry, end="")
    ensure_memory_file(target)
    append_facts(target, args.facts)
    print(f"Appended {len(args.facts)} fact(s) to {target}")


if __name__ == "__main__":
    main()
