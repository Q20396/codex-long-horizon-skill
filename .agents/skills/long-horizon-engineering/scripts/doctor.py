#!/usr/bin/env python3
"""Run local product-readiness checks for this skill package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

PACKAGE_ONLY_PATHS = [
    "AGENTS.md",
    "CHANGELOG.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "UPGRADE_GUIDE.md",
    ".github/workflows/check-skill.yml",
    "tests/expected-triggers.json",
]

INSTALLED_REQUIRED_PATHS = [
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/adversarial-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/api-integration-protocol.md",
    ".agents/skills/long-horizon-engineering/references/data-cleaning-protocol.md",
    ".agents/skills/long-horizon-engineering/references/evidence-backed-writing.md",
    ".agents/skills/long-horizon-engineering/references/code-review-response-protocol.md",
    ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ideation-to-plan-protocol.md",
    ".agents/skills/long-horizon-engineering/references/notebook-analysis-protocol.md",
    ".agents/skills/long-horizon-engineering/references/presentation-delivery-protocol.md",
    ".agents/skills/long-horizon-engineering/references/repomix-codebase-context.md",
    ".agents/skills/long-horizon-engineering/references/ship-readiness-protocol.md",
    ".agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md",
    ".agents/skills/long-horizon-engineering/references/systematic-debugging-protocol.md",
    ".agents/skills/long-horizon-engineering/references/tdd-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ui-ux-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/writing-humanization-protocol.md",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py",
    ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py",
    ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py",
    ".agents/skills/long-horizon-engineering/templates/implementation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/accessibility-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/analysis-run-log.md",
    ".agents/skills/long-horizon-engineering/templates/api-contract-test-plan.md",
    ".agents/skills/long-horizon-engineering/templates/claim-evidence-table.md",
    ".agents/skills/long-horizon-engineering/templates/data-quality-report.md",
    ".agents/skills/long-horizon-engineering/templates/deck-outline.md",
    ".agents/skills/long-horizon-engineering/templates/debugging-runbook.md",
    ".agents/skills/long-horizon-engineering/templates/frontend-handoff.md",
    ".agents/skills/long-horizon-engineering/templates/new-skill-brief.md",
    ".agents/skills/long-horizon-engineering/templates/option-analysis.md",
    ".agents/skills/long-horizon-engineering/templates/regression-test-record.md",
    ".agents/skills/long-horizon-engineering/templates/reviewer-response.md",
    ".agents/skills/long-horizon-engineering/templates/risk-challenge-table.md",
    ".agents/skills/long-horizon-engineering/templates/ship-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/skill-evaluation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/ui-ux-audit.md",
    ".agents/skills/long-horizon-engineering/templates/verification-evidence.md",
    ".agents/skills/long-horizon-engineering/templates/slide-qa-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/voice-calibration.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/concise.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/evidence-first.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/product-review.md",
    ".agents/skills/ai-video-production/SKILL.md",
    ".agents/skills/ai-video-production/references/design-system-for-video.md",
    ".agents/skills/ai-video-production/prompt-styles/short-form-cinematic.md",
    ".agents/skills/ai-video-production/prompt-styles/production-handoff.md",
    ".agents/skills/ai-video-production/templates/DESIGN.md",
    ".agents/skills/ai-video-production/templates/visual-style-tokens.md",
    ".agents/skills/ai-video-production/templates/brand-system-for-video.md",
]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def package_mode() -> bool:
    return all((ROOT / relative_path).is_file() for relative_path in PACKAGE_ONLY_PATHS)


def check_required_paths(required_paths: list[str], label: str) -> list[str]:
    return [
        f"Missing required {label} file: {relative_path}"
        for relative_path in required_paths
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
    if not path.is_file():
        return []
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


def run_checks() -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    errors.extend(check_required_paths(INSTALLED_REQUIRED_PATHS, "installed skill"))
    if package_mode():
        errors.extend(check_required_paths(PACKAGE_ONLY_PATHS, "package"))
    else:
        warnings.append(
            "Package-level files not found; running installed-skill checks only."
        )
        warnings.append(
            "Skipped tests/expected-triggers.json trigger fixture check."
        )
    errors.extend(check_front_matter(
        ".agents/skills/long-horizon-engineering/SKILL.md",
        "long-horizon-engineering",
    ))
    errors.extend(check_front_matter(
        ".agents/skills/ai-video-production/SKILL.md",
        "ai-video-production",
    ))
    errors.extend(check_nested_agents())
    if package_mode():
        errors.extend(check_trigger_fixture())
    return errors, warnings


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
    errors, warnings = run_checks()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, indent=2))
    elif errors:
        for warning in warnings:
            print(f"WARNING: {warning}")
        for error in errors:
            print(f"ERROR: {error}")
    else:
        for warning in warnings:
            print(f"WARNING: {warning}")
        print("Doctor check passed.")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
