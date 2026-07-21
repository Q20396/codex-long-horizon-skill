#!/usr/bin/env python3
"""Check Markdown local links without resolving external URLs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from validation_common import repository_root


LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    for markdown in (root / "sandbox/skill-incubator").rglob("*.md"):
        text = markdown.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for raw_target in LINK.findall(line):
                target = raw_target.split("#", 1)[0].strip("<>")
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                path = (markdown.parent / target).resolve()
                try:
                    path.relative_to(root.resolve())
                except ValueError:
                    errors.append(f"{markdown.relative_to(root)}:{line_number}: link escapes repository: {raw_target}")
                    continue
                if not path.exists():
                    errors.append(f"{markdown.relative_to(root)}:{line_number}: broken local link: {raw_target}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: local Markdown links resolve inside the repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
