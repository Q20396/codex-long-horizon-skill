#!/usr/bin/env python3
"""Audit packaged SKILL.md descriptions for trigger-focused metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_FILES = [
    ROOT / ".agents" / "skills" / "long-horizon-engineering" / "SKILL.md",
    ROOT / ".agents" / "skills" / "ai-video-production" / "SKILL.md",
]
WORKFLOW_WORDS = {
    "first",
    "then",
    "step",
    "steps",
    "workflow",
    "procedure",
    "sequence",
}


def front_matter(text: str, path: Path) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path.relative_to(ROOT)} is missing YAML front matter.")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path.relative_to(ROOT)} front matter is not closed.")

    data = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def audit_description(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    meta = front_matter(text, path)
    name = meta.get("name", path.parent.name)
    description = meta.get("description", "")
    errors = []

    if not description:
        return [f"{name}: missing description."]
    if not description.startswith("Use "):
        errors.append(f"{name}: description should start with trigger language such as 'Use when' or 'Use this skill'.")
    if len(description) > 260:
        errors.append(f"{name}: description is too long for trigger metadata ({len(description)} chars).")

    lowered = description.lower()
    workflow_hits = sorted(word for word in WORKFLOW_WORDS if word in lowered.split())
    if len(workflow_hits) >= 2:
        errors.append(f"{name}: description may be summarizing workflow steps: {', '.join(workflow_hits)}.")
    if "\n" in description:
        errors.append(f"{name}: description should be a single-line metadata field.")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit skill descriptions for trigger-focused metadata. This is a "
            "static check and does not call a model or make network requests."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable audit results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors = []
    for path in SKILL_FILES:
        if not path.is_file():
            errors.append(f"Missing skill file: {path.relative_to(ROOT)}")
            continue
        errors.extend(audit_description(path))

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("Skill description audit passed.")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
