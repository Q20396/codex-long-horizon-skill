#!/usr/bin/env python3
"""Optionally validate all incubator schemas and high-impact instances with Draft 2020-12."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA_SETS = (
    (
        "base-experiment-contract.schema.json",
        "sandbox/skill-incubator/schemas/base-experiment-contract.schema.json",
        "sandbox/skill-incubator/candidate-intake/base-experiment-contracts",
        lambda payload: [payload],
    ),
    (
        "candidate-state.schema.json",
        "sandbox/skill-incubator/schemas/candidate-state.schema.json",
        "sandbox/skill-incubator/candidate-intake/candidate-states",
        lambda payload: [payload],
    ),
    (
        "capability-family.schema.json",
        "sandbox/skill-incubator/schemas/capability-family.schema.json",
        "sandbox/skill-incubator/architecture",
        lambda payload: payload.get("families", []) if isinstance(payload, dict) else [],
    ),
    (
        "proposal-evidence.schema.json",
        "sandbox/skill-incubator/schemas/proposal-evidence.schema.json",
        "sandbox/skill-incubator/candidate-intake/proposal-evidence",
        lambda payload: [payload],
    ),
    (
        "public-equity-research-sandbox.schema.json",
        "sandbox/skill-incubator/schemas/public-equity-research-sandbox.schema.json",
        "sandbox/skill-incubator/architecture",
        lambda payload: [payload],
    ),
)


def validate_root(root: Path) -> tuple[list[str], int, int]:
    from jsonschema import Draft202012Validator

    errors: list[str] = []
    checked_instances = 0
    schema_paths = sorted((root / "sandbox/skill-incubator/schemas").glob("*.json"))
    validated_schemas: dict[str, dict] = {}
    for path in schema_paths:
        relative = str(path.relative_to(root))
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{relative}: invalid Draft 2020-12 schema: {exc}")
        else:
            validated_schemas[relative] = schema

    for label, schema_relative, instances_relative, extract in SCHEMA_SETS:
        schema = validated_schemas.get(schema_relative)
        if schema is None:
            continue
        validator = Draft202012Validator(schema)
        directory = root / instances_relative
        if label == "capability-family.schema.json":
            paths = [directory / "capability-families.json"]
        elif label == "public-equity-research-sandbox.schema.json":
            paths = [directory / "public-equity-research-sandbox.json"]
        else:
            paths = sorted(directory.glob("*.json"))
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for index, instance in enumerate(extract(payload)):
                checked_instances += 1
                for error in validator.iter_errors(instance):
                    location = ".".join(str(part) for part in error.path) or "<root>"
                    errors.append(f"{path.relative_to(root)}[{index}]: {location}: {error.message}")
    return errors, len(schema_paths), checked_instances


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    errors, checked_schemas, checked_instances = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print(
        "PASS: Draft 2020-12 validated "
        f"{checked_schemas} schemas and {checked_instances} high-impact contract instances."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
