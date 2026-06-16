#!/usr/bin/env python3
"""Run local product-readiness checks for this skill package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

REQUIRED_PATHS = [
    "AGENTS.md",
    "CHANGELOG.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "UPGRADE_GUIDE.md",
    ".github/workflows/check-skill.yml",
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ".agents/skills/long-horizon-engineering/references/repomix-codebase-context.md",
    ".agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py",
    ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py",
    ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py",
    ".agents/skills/long-horizon-engineering/templates/implementation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/verification-evidence.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/concise.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/evidence-first.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/product-review.md",
    ".agents/skills/ai-video-production/SKILL.md",
    ".agents/skills/ai-video-production/prompt-styles/short-form-cinematic.md",
    ".agents/skills/ai-video-production/prompt-styles/production-handoff.md",
    "tests/expected-triggers.json",
]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def check_required_paths() -> list[str]:
    return [
        f"Missing required product file: {relative_path}"
        for relative_path in REQUIRED_PATHS
        if not (ROOT / relative_path).is_file()
    ]


def check_front_matter(relative_path: str, expected_name: str) -> list[str]:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [f"{relative_path} is missing YAML front matter."]
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return [f"{relative_path} YAML front matter is not closed."]
    front_matter = parts[1]
    errors = []
    if f"name: {expected_name}" not in front_matter:
        errors.append(f"{relative_path} must include name: {expected_name}.")
    if "description:" not in front_matter:
        errors.append(f"{relative_path} must include description.")
    return errors


def check_nested_agents() -> list[str]:
    skills_dir = ROOT / ".agents" / "skills"
    return [
        f"Nested .agents path found: {path.relative_to(ROOT)}"
        for path in skills_dir.rglob(".agents")
    ]


def check_trigger_fixture() -> list[str]:
    path = ROOT / "tests" / "expected-triggers.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"tests/expected-triggers.json is invalid JSON: {error}"]

    errors = []
    skills = payload.get("skills")
    if not isinstance(skills, list) or not skills:
        return ["tests/expected-triggers.json must contain a non-empty skills list."]

    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"Trigger fixture entry {index} must be an object.")
            continue
        for key in ("name", "path", "should_trigger", "should_not_trigger", "required_phrases"):
            if key not in skill:
                errors.append(f"Trigger fixture entry {index} is missing {key}.")
        skill_path = skill.get("path")
        if isinstance(skill_path, str) and not (ROOT / skill_path).is_file():
            errors.append(f"Trigger fixture path does not exist: {skill_path}")
    return errors


def run_checks() -> list[str]:
    errors = []
    errors.extend(check_required_paths())
    errors.extend(check_front_matter(
        ".agents/skills/long-horizon-engineering/SKILL.md",
        "long-horizon-engineering",
    ))
    errors.extend(check_front_matter(
        ".agents/skills/ai-video-production/SKILL.md",
        "ai-video-production",
    ))
    errors.extend(check_nested_agents())
    errors.extend(check_trigger_fixture())
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether the local skill package has the expected productized "
            "structure. This does not make network calls or modify files."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable check results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors = run_checks()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("Doctor check passed.")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
