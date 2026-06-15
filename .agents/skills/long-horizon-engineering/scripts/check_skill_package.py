#!/usr/bin/env python3
"""Validate the long-horizon-engineering skill package structure."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = ROOT / ".agents" / "skills" / "long-horizon-engineering"

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/protocol.md",
    ".agents/skills/long-horizon-engineering/references/safety-policy.md",
    ".agents/skills/long-horizon-engineering/references/context-compaction.md",
    ".agents/skills/long-horizon-engineering/references/continuous-improvement.md",
    ".agents/skills/long-horizon-engineering/references/decision-log.md",
    ".agents/skills/long-horizon-engineering/references/external-source-scan.md",
    ".agents/skills/long-horizon-engineering/references/large-migration-playbook.md",
    ".agents/skills/long-horizon-engineering/references/resume-protocol.md",
    ".agents/skills/long-horizon-engineering/references/review-checklist.md",
    ".agents/skills/long-horizon-engineering/references/stop-conditions.md",
    ".agents/skills/long-horizon-engineering/references/validation-matrix.md",
    ".agents/skills/long-horizon-engineering/templates/HANDOFF_REPORT_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/PROJECT_MEMORY_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/IMPROVEMENT_SCAN_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/TASK_LOG_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/WORKING_STATE_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/scripts/append_project_memory.py",
    ".agents/skills/long-horizon-engineering/scripts/update_task_log.py",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/github_skill_scan.py",
]


def check_required_files() -> list[str]:
    errors = []
    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path}")
    return errors


def check_skill_front_matter() -> list[str]:
    path = SKILL_DIR / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ["SKILL.md is missing YAML front matter."]

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return ["SKILL.md front matter is not closed."]

    front_matter = parts[1]
    errors = []
    if "name: long-horizon-engineering" not in front_matter:
        errors.append("SKILL.md front matter must include name: long-horizon-engineering")
    if "description:" not in front_matter:
        errors.append("SKILL.md front matter must include description.")
    return errors


def check_nested_agents() -> list[str]:
    nested = [
        path
        for path in (ROOT / ".agents").rglob(".agents")
        if path != ROOT / ".agents"
    ]
    return [f"Nested .agents path found: {path.relative_to(ROOT)}" for path in nested]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the long-horizon-engineering skill package structure."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()

    errors = []
    errors.extend(check_required_files())
    errors.extend(check_skill_front_matter())
    errors.extend(check_nested_agents())

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("Skill package check passed.")


if __name__ == "__main__":
    main()
