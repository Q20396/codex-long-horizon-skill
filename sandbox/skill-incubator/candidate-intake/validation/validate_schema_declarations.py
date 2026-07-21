#!/usr/bin/env python3
"""Parse local schemas and verify Draft 2020-12 declarations without a schema engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation_common import issue, repository_root


SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def _refs(value: object) -> list[str]:
    if isinstance(value, dict):
        found = [item for key, item in value.items() if key == "$ref" and isinstance(item, str)]
        for child in value.values():
            found.extend(_refs(child))
        return found
    if isinstance(value, list):
        return [item for child in value for item in _refs(child)]
    return []


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    directory = root / "sandbox/skill-incubator/schemas"
    identifiers: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        relative = str(path.relative_to(root))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(issue(relative, "json", "valid JSON", exc.msg, exc.lineno))
            continue
        if payload.get("$schema") != SCHEMA_URI:
            errors.append(issue(relative, "$schema", SCHEMA_URI, payload.get("$schema")))
        identifier = payload.get("$id")
        if not isinstance(identifier, str) or not identifier:
            errors.append(issue(relative, "$id", "non-empty unique local ID", identifier))
        elif identifier in identifiers:
            errors.append(issue(relative, "$id", "unique local ID", identifier))
        else:
            identifiers.add(identifier)
        for reference in _refs(payload):
            if reference.startswith(("http://", "https://", "#")):
                continue
            target = (path.parent / reference.split("#", 1)[0]).resolve()
            if not target.is_file():
                errors.append(issue(relative, "$ref", "existing local schema", reference))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: local Draft 2020-12 schema declarations, IDs, JSON parsing, and local refs are structurally valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
