#!/usr/bin/env python3
"""Validate expected trigger fixtures for packaged skills."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests" / "expected-triggers.json"


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_skill(skill: dict) -> list[str]:
    errors = []
    name = skill.get("name")
    skill_path = skill.get("path")
    if not isinstance(name, str) or not name:
        errors.append("Skill entry is missing a valid name.")
    if not isinstance(skill_path, str) or not skill_path:
        errors.append(f"{name or 'unknown'} is missing a valid path.")
        return errors

    path = ROOT / skill_path
    if not path.is_file():
        errors.append(f"{name}: skill path does not exist: {skill_path}")
        return errors

    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        errors.append(f"{name}: SKILL.md must have YAML front matter.")
        return errors
    if f"name: {name}" not in parts[1]:
        errors.append(f"{name}: SKILL.md front matter does not match fixture name.")

    for key in ("should_trigger", "should_not_trigger", "required_phrases"):
        values = skill.get(key)
        if not isinstance(values, list) or not values:
            errors.append(f"{name}: {key} must be a non-empty list.")
            continue
        if not all(isinstance(value, str) and value.strip() for value in values):
            errors.append(f"{name}: {key} must contain non-empty strings.")

    for phrase in skill.get("required_phrases", []):
        if phrase not in text:
            errors.append(f"{name}: required phrase not found in SKILL.md: {phrase}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate packaged expected trigger examples. This is a static "
            "fixture check; it does not call a model or make network requests."
        )
    )
    parser.add_argument(
        "--fixture",
        default=str(FIXTURE),
        help="Path to expected trigger JSON fixture.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fixture_path = Path(args.fixture)
    payload = load_fixture(fixture_path)
    errors = []
    for skill in payload.get("skills", []):
        errors.extend(validate_skill(skill))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("Expected trigger fixtures passed.")


if __name__ == "__main__":
    main()
