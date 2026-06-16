#!/usr/bin/env python3
"""Validate the Codex skill package structure."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = ROOT / ".agents" / "skills" / "long-horizon-engineering"
AI_VIDEO_SKILL_DIR = ROOT / ".agents" / "skills" / "ai-video-production"

REQUIRED_FILES = [
    "AGENTS.md",
    "CHANGELOG.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    ".github/workflows/check-skill.yml",
    "examples/bug-fix-prompt.md",
    "examples/large-migration-prompt.md",
    "examples/resume-task-prompt.md",
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/protocol.md",
    ".agents/skills/long-horizon-engineering/references/capability-boundaries.md",
    ".agents/skills/long-horizon-engineering/references/client-privacy.md",
    ".agents/skills/long-horizon-engineering/references/safety-policy.md",
    ".agents/skills/long-horizon-engineering/references/context-compaction.md",
    ".agents/skills/long-horizon-engineering/references/continuous-improvement.md",
    ".agents/skills/long-horizon-engineering/references/decision-log.md",
    ".agents/skills/long-horizon-engineering/references/external-source-scan.md",
    ".agents/skills/long-horizon-engineering/references/jurisdiction-industry-compliance.md",
    ".agents/skills/long-horizon-engineering/references/large-migration-playbook.md",
    ".agents/skills/long-horizon-engineering/references/public-agent-capability-review.md",
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
    ".agents/skills/long-horizon-engineering/scripts/check_for_updates.py",
    ".agents/skills/long-horizon-engineering/scripts/github_skill_scan.py",
    ".agents/skills/long-horizon-engineering/scripts/scan_top_related_skills.py",
]

AI_VIDEO_REQUIRED_FILES = [
    ".agents/skills/ai-video-production/SKILL.md",
    ".agents/skills/ai-video-production/references/remotion-patterns.md",
    ".agents/skills/ai-video-production/references/hyperframes-patterns.md",
    ".agents/skills/ai-video-production/references/imagegen-patterns.md",
    ".agents/skills/ai-video-production/references/video-production-pipeline.md",
    ".agents/skills/ai-video-production/references/privacy-media-policy.md",
    ".agents/skills/ai-video-production/references/licensing-notes.md",
    ".agents/skills/ai-video-production/templates/VIDEO_BRIEF_TEMPLATE.md",
    ".agents/skills/ai-video-production/templates/STORYBOARD_TEMPLATE.md",
    ".agents/skills/ai-video-production/templates/SHOT_LIST_TEMPLATE.md",
    ".agents/skills/ai-video-production/templates/ASSET_MANIFEST_TEMPLATE.md",
    ".agents/skills/ai-video-production/templates/RENDER_HANDOFF_TEMPLATE.md",
    ".agents/skills/ai-video-production/scripts/scan_top_media_skills.py",
]


def check_required_files(required_files: list[str]) -> list[str]:
    errors = []
    for relative_path in required_files:
        if not (ROOT / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path}")
    return errors


def check_skill_front_matter(skill_dir: Path, expected_name: str) -> list[str]:
    path = skill_dir / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [f"{path.relative_to(ROOT)} is missing YAML front matter."]

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return [f"{path.relative_to(ROOT)} front matter is not closed."]

    front_matter = parts[1]
    errors = []
    if f"name: {expected_name}" not in front_matter:
        errors.append(
            f"{path.relative_to(ROOT)} front matter must include name: {expected_name}"
        )
    if "description:" not in front_matter:
        errors.append(f"{path.relative_to(ROOT)} front matter must include description.")
    return errors


def check_nested_agents() -> list[str]:
    skills_dir = ROOT / ".agents" / "skills"
    nested = [
        path
        for path in skills_dir.rglob(".agents")
        if path != skills_dir
    ]
    return [f"Nested .agents path found: {path.relative_to(ROOT)}" for path in nested]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Codex skill package structure."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()

    errors = []
    errors.extend(check_required_files(REQUIRED_FILES))
    errors.extend(check_required_files(AI_VIDEO_REQUIRED_FILES))
    errors.extend(check_skill_front_matter(SKILL_DIR, "long-horizon-engineering"))
    errors.extend(check_skill_front_matter(AI_VIDEO_SKILL_DIR, "ai-video-production"))
    errors.extend(check_nested_agents())

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("Skill package check passed for long-horizon-engineering and ai-video-production.")


if __name__ == "__main__":
    main()
