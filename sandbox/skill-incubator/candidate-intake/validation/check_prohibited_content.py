#!/usr/bin/env python3
"""Reject accidental code import, credential material, or executable install shortcuts."""

from __future__ import annotations

import argparse
import re
import stat
from pathlib import Path

from validation_common import repository_root


RULES = {
    "remote-installer": re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:ba)?sh\b", re.I),
    "direct-downloader": re.compile(r"\b(?:curl|wget|aria2c)\b[^\n]*https?://", re.I),
    "package-install": re.compile(r"\b(?:pip|npm|pnpm|yarn)\s+install\b", re.I),
    "mcp-registration": re.compile(r"\b(?:mcp\s+(?:add|register)|oauth\s+(?:login|authorize))\b", re.I),
    "credential": re.compile(r"\b(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"][^'\"]+", re.I),
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf", ".pyc"}


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    incubator = root / "sandbox/skill-incubator"
    for path in incubator.rglob("*"):
        if path.is_symlink():
            errors.append(f"{path.relative_to(root)}: symlinks are not allowed in the incubator")
            continue
        if not path.is_file():
            continue
        if stat.S_IMODE(path.stat().st_mode) & 0o111:
            errors.append(f"{path.relative_to(root)}: executable bit is not allowed in the incubator")
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path.relative_to(root)}: binary or non-UTF-8 content is not allowed")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, rule in RULES.items():
                if rule.search(line):
                    errors.append(f"{path.relative_to(root)}:{line_number}: prohibited {label} pattern")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: no imported code, credentials, installers, or provider registration commands found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
