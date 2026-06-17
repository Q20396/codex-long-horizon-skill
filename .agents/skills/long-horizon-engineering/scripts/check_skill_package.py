#!/usr/bin/env python3
"""Validate the Codex skill package structure."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = ROOT / ".agents" / "skills" / "long-horizon-engineering"
AI_VIDEO_SKILL_DIR = ROOT / ".agents" / "skills" / "ai-video-production"

PACKAGE_ONLY_FILES = [
    "AGENTS.md",
    "CHANGELOG.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "UPGRADE_GUIDE.md",
    ".github/workflows/check-skill.yml",
    "examples/bug-fix-prompt.md",
    "examples/large-migration-prompt.md",
    "examples/resume-task-prompt.md",
    "tests/expected-triggers.json",
]

INSTALLED_REQUIRED_FILES = [
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/protocol.md",
    ".agents/skills/long-horizon-engineering/references/adversarial-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/api-integration-protocol.md",
    ".agents/skills/long-horizon-engineering/references/capability-boundaries.md",
    ".agents/skills/long-horizon-engineering/references/client-privacy.md",
    ".agents/skills/long-horizon-engineering/references/code-review-response-protocol.md",
    ".agents/skills/long-horizon-engineering/references/data-cleaning-protocol.md",
    ".agents/skills/long-horizon-engineering/references/safety-policy.md",
    ".agents/skills/long-horizon-engineering/references/context-compaction.md",
    ".agents/skills/long-horizon-engineering/references/continuous-improvement.md",
    ".agents/skills/long-horizon-engineering/references/decision-log.md",
    ".agents/skills/long-horizon-engineering/references/disaster-monitoring-enablement.md",
    ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ".agents/skills/long-horizon-engineering/references/external-skill-adoption-safety-review.md",
    ".agents/skills/long-horizon-engineering/references/external-source-scan.md",
    ".agents/skills/long-horizon-engineering/references/external-app-runtime-boundary.md",
    ".agents/skills/long-horizon-engineering/references/external-tool-provider-protocol.md",
    ".agents/skills/long-horizon-engineering/references/evidence-backed-writing.md",
    ".agents/skills/long-horizon-engineering/references/financial-research-report-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ideation-to-plan-protocol.md",
    ".agents/skills/long-horizon-engineering/references/jurisdiction-industry-compliance.md",
    ".agents/skills/long-horizon-engineering/references/large-migration-playbook.md",
    ".agents/skills/long-horizon-engineering/references/missing-capability-skill-discovery.md",
    ".agents/skills/long-horizon-engineering/references/notebook-analysis-protocol.md",
    ".agents/skills/long-horizon-engineering/references/presentation-delivery-protocol.md",
    ".agents/skills/long-horizon-engineering/references/public-agent-capability-review.md",
    ".agents/skills/long-horizon-engineering/references/resume-protocol.md",
    ".agents/skills/long-horizon-engineering/references/review-checklist.md",
    ".agents/skills/long-horizon-engineering/references/repomix-codebase-context.md",
    ".agents/skills/long-horizon-engineering/references/security-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/stop-conditions.md",
    ".agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md",
    ".agents/skills/long-horizon-engineering/references/skill-optimization-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ship-readiness-protocol.md",
    ".agents/skills/long-horizon-engineering/references/tdd-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ui-ux-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/validation-matrix.md",
    ".agents/skills/long-horizon-engineering/references/systematic-debugging-protocol.md",
    ".agents/skills/long-horizon-engineering/references/writing-humanization-protocol.md",
    ".agents/skills/long-horizon-engineering/templates/accessibility-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/frontend-handoff.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/concise.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/evidence-first.md",
    ".agents/skills/long-horizon-engineering/prompt-styles/product-review.md",
    ".agents/skills/long-horizon-engineering/templates/HANDOFF_REPORT_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/PROJECT_MEMORY_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/IMPROVEMENT_SCAN_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/implementation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/analysis-run-log.md",
    ".agents/skills/long-horizon-engineering/templates/api-contract-test-plan.md",
    ".agents/skills/long-horizon-engineering/templates/bounded-skill-edit.md",
    ".agents/skills/long-horizon-engineering/templates/claim-evidence-table.md",
    ".agents/skills/long-horizon-engineering/templates/data-quality-report.md",
    ".agents/skills/long-horizon-engineering/templates/deck-outline.md",
    ".agents/skills/long-horizon-engineering/templates/debugging-runbook.md",
    ".agents/skills/long-horizon-engineering/templates/disaster-alert-rule.md",
    ".agents/skills/long-horizon-engineering/templates/external-skill-adoption-review.md",
    ".agents/skills/long-horizon-engineering/templates/market-data-source-log.md",
    ".agents/skills/long-horizon-engineering/templates/monitoring-runbook.md",
    ".agents/skills/long-horizon-engineering/templates/memory-review-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/new-skill-brief.md",
    ".agents/skills/long-horizon-engineering/templates/option-analysis.md",
    ".agents/skills/long-horizon-engineering/templates/regression-test-record.md",
    ".agents/skills/long-horizon-engineering/templates/reviewer-response.md",
    ".agents/skills/long-horizon-engineering/templates/paper-evidence-card.md",
    ".agents/skills/long-horizon-engineering/templates/risk-challenge-table.md",
    ".agents/skills/long-horizon-engineering/templates/ship-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/skill-evaluation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/skill-reflection-report.md",
    ".agents/skills/long-horizon-engineering/templates/skill-rollout-log.md",
    ".agents/skills/long-horizon-engineering/templates/skill-validation-gate.md",
    ".agents/skills/long-horizon-engineering/templates/secrets-scan-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/rejected-skill-edit-log.md",
    ".agents/skills/long-horizon-engineering/templates/stock-research-report.md",
    ".agents/skills/long-horizon-engineering/templates/TASK_LOG_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/ui-ux-audit.md",
    ".agents/skills/long-horizon-engineering/templates/valuation-assumption-table.md",
    ".agents/skills/long-horizon-engineering/templates/verification-evidence.md",
    ".agents/skills/long-horizon-engineering/templates/risk-disclosure.md",
    ".agents/skills/long-horizon-engineering/templates/slide-qa-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/source-upload-consent-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/voice-calibration.md",
    ".agents/skills/long-horizon-engineering/templates/tool-provider-capability-map.md",
    ".agents/skills/long-horizon-engineering/templates/WORKING_STATE_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/scripts/append_project_memory.py",
    ".agents/skills/long-horizon-engineering/scripts/update_task_log.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_external_skill_candidate.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/check_for_updates.py",
    ".agents/skills/long-horizon-engineering/scripts/github_skill_scan.py",
    ".agents/skills/long-horizon-engineering/scripts/scan_top_related_skills.py",
    ".agents/skills/long-horizon-engineering/scripts/doctor.py",
    ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py",
    ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py",
]

AI_VIDEO_REQUIRED_FILES = [
    ".agents/skills/ai-video-production/SKILL.md",
    ".agents/skills/ai-video-production/prompt-styles/short-form-cinematic.md",
    ".agents/skills/ai-video-production/prompt-styles/production-handoff.md",
    ".agents/skills/ai-video-production/references/remotion-patterns.md",
    ".agents/skills/ai-video-production/references/hyperframes-patterns.md",
    ".agents/skills/ai-video-production/references/imagegen-patterns.md",
    ".agents/skills/ai-video-production/references/video-production-pipeline.md",
    ".agents/skills/ai-video-production/references/privacy-media-policy.md",
    ".agents/skills/ai-video-production/references/licensing-notes.md",
    ".agents/skills/ai-video-production/references/design-system-for-video.md",
    ".agents/skills/ai-video-production/templates/VIDEO_BRIEF_TEMPLATE.md",
    ".agents/skills/ai-video-production/templates/DESIGN.md",
    ".agents/skills/ai-video-production/templates/visual-style-tokens.md",
    ".agents/skills/ai-video-production/templates/brand-system-for-video.md",
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
    if not path.is_file():
        return [f"Missing required file: {path.relative_to(ROOT)}"]
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


def package_mode() -> bool:
    return all((ROOT / relative_path).is_file() for relative_path in PACKAGE_ONLY_FILES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Codex skill package structure. By default, this auto-detects "
            "whether it is running in the source package or an installed project."
        )
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Require source-package files such as README, tests, examples, and CI workflow.",
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Check only installed skill files under .agents/skills.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.package and args.installed:
        raise SystemExit("ERROR: choose only one of --package or --installed.")

    check_package_files = args.package or (not args.installed and package_mode())

    errors = []
    if check_package_files:
        errors.extend(check_required_files(PACKAGE_ONLY_FILES))
    else:
        print("Installed-skill mode: skipping package-only files.")
    errors.extend(check_required_files(INSTALLED_REQUIRED_FILES))
    errors.extend(check_skill_front_matter(SKILL_DIR, "long-horizon-engineering"))
    if check_package_files:
        errors.extend(check_required_files(AI_VIDEO_REQUIRED_FILES))
        errors.extend(check_skill_front_matter(AI_VIDEO_SKILL_DIR, "ai-video-production"))
    elif AI_VIDEO_SKILL_DIR.exists():
        errors.extend(check_required_files(AI_VIDEO_REQUIRED_FILES))
        errors.extend(check_skill_front_matter(AI_VIDEO_SKILL_DIR, "ai-video-production"))
    errors.extend(check_nested_agents())

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    if check_package_files:
        print("Skill package check passed for long-horizon-engineering and ai-video-production.")
    elif AI_VIDEO_SKILL_DIR.exists():
        print("Installed skill check passed for long-horizon-engineering and ai-video-production.")
    else:
        print("Installed skill check passed for long-horizon-engineering.")


if __name__ == "__main__":
    main()
