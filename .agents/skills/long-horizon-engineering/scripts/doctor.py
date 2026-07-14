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
    "CODE_OF_CONDUCT.md",
    "COMMUNITY_SKILLS.md",
    "CONTRIBUTING.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "UPGRADE_GUIDE.md",
    ".codex-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/skill_proposal.md",
    ".github/pull_request_template.md",
    ".github/workflows/check-skill.yml",
    "docs/demo/README.md",
    "docs/demo/recording-script.md",
    "docs/evals/live-routing.md",
    "docs/first-contribution.md",
    "docs/maintainers/release-checklist.md",
    "docs/plugin-install.md",
    "docs/releases/v0.1.0.md",
    "examples/bug-investigation/expected-output.md",
    "examples/bug-investigation/prompt.md",
    "examples/bug-investigation/workflow.md",
    "examples/large-refactor/expected-output.md",
    "examples/large-refactor/prompt.md",
    "examples/large-refactor/workflow.md",
    "examples/repository-migration/expected-output.md",
    "examples/repository-migration/prompt.md",
    "examples/repository-migration/workflow.md",
    "examples/resume-work/expected-output.md",
    "examples/resume-work/prompt.md",
    "examples/resume-work/workflow.md",
    "prompts/bug-investigation.md",
    "prompts/large-refactor.md",
    "prompts/pr-review.md",
    "prompts/repository-migration.md",
    "prompts/resume-work.md",
    "templates/findings-report.md",
    "templates/migration-report.md",
    "templates/project-plan.md",
    "templates/validation-report.md",
    "scripts/generate_skill_catalog.py",
    "scripts/full_skill_validation.py",
    "scripts/validate_plugin_package.py",
    "scripts/test_fresh_install.py",
    "scripts/check_release_readiness.py",
    "tests/expected-triggers.json",
    "tests/skill-eval-cases.json",
]

INSTALLED_REQUIRED_PATHS = [
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/references/adversarial-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/api-integration-protocol.md",
    ".agents/skills/long-horizon-engineering/references/data-cleaning-protocol.md",
    ".agents/skills/long-horizon-engineering/references/evidence-backed-writing.md",
    ".agents/skills/long-horizon-engineering/references/code-review-response-protocol.md",
    ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ".agents/skills/long-horizon-engineering/references/explicit-only-extensions.md",
    ".agents/skills/long-horizon-engineering/references/external-skill-adoption-safety-review.md",
    ".agents/skills/long-horizon-engineering/references/financial-research-report-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ideation-to-plan-protocol.md",
    ".agents/skills/long-horizon-engineering/references/missing-capability-skill-discovery.md",
    ".agents/skills/long-horizon-engineering/references/notebook-analysis-protocol.md",
    ".agents/skills/long-horizon-engineering/references/obsidian-knowledge-workflow.md",
    ".agents/skills/long-horizon-engineering/references/presentation-delivery-protocol.md",
    ".agents/skills/long-horizon-engineering/references/planner-builder-evaluator-loop.md",
    ".agents/skills/long-horizon-engineering/references/repomix-codebase-context.md",
    ".agents/skills/long-horizon-engineering/references/security-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ship-readiness-protocol.md",
    ".agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md",
    ".agents/skills/long-horizon-engineering/references/skill-lifecycle-management.md",
    ".agents/skills/long-horizon-engineering/references/skill-optimization-protocol.md",
    ".agents/skills/long-horizon-engineering/references/skillopt-training-layer.md",
    ".agents/skills/long-horizon-engineering/references/systematic-debugging-protocol.md",
    ".agents/skills/long-horizon-engineering/references/tdd-protocol.md",
    ".agents/skills/long-horizon-engineering/references/ui-ux-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/writing-humanization-protocol.md",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py",
    ".agents/skills/long-horizon-engineering/scripts/validate_json_canvas.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_external_skill_candidate.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py",
    ".agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py",
    ".agents/skills/long-horizon-engineering/scripts/score_skill_candidate.py",
    ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py",
    ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py",
    ".agents/skills/long-horizon-engineering/templates/implementation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/accessibility-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/analysis-run-log.md",
    ".agents/skills/long-horizon-engineering/templates/api-contract-test-plan.md",
    ".agents/skills/long-horizon-engineering/templates/bounded-skill-edit.md",
    ".agents/skills/long-horizon-engineering/templates/claim-evidence-table.md",
    ".agents/skills/long-horizon-engineering/templates/data-quality-report.md",
    ".agents/skills/long-horizon-engineering/templates/deck-outline.md",
    ".agents/skills/long-horizon-engineering/templates/debugging-runbook.md",
    ".agents/skills/long-horizon-engineering/templates/external-skill-adoption-review.md",
    ".agents/skills/long-horizon-engineering/templates/frontend-handoff.md",
    ".agents/skills/long-horizon-engineering/templates/market-data-source-log.md",
    ".agents/skills/long-horizon-engineering/templates/new-skill-brief.md",
    ".agents/skills/long-horizon-engineering/templates/option-analysis.md",
    ".agents/skills/long-horizon-engineering/templates/OBSIDIAN_ARTIFACT_PLAN_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/regression-test-record.md",
    ".agents/skills/long-horizon-engineering/templates/reviewer-response.md",
    ".agents/skills/long-horizon-engineering/templates/risk-challenge-table.md",
    ".agents/skills/long-horizon-engineering/templates/rejected-skill-edit-log.md",
    ".agents/skills/long-horizon-engineering/templates/ship-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/skill-evaluation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/skill-reflection-report.md",
    ".agents/skills/long-horizon-engineering/templates/skill-rollout-log.md",
    ".agents/skills/long-horizon-engineering/templates/skill-training-report.md",
    ".agents/skills/long-horizon-engineering/templates/skill-eval-cases.json",
    ".agents/skills/long-horizon-engineering/templates/skill-usage-report.md",
    ".agents/skills/long-horizon-engineering/templates/skill-validation-gate.md",
    ".agents/skills/long-horizon-engineering/templates/secrets-scan-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/stock-research-report.md",
    ".agents/skills/long-horizon-engineering/templates/ui-ux-audit.md",
    ".agents/skills/long-horizon-engineering/templates/valuation-assumption-table.md",
    ".agents/skills/long-horizon-engineering/templates/verification-evidence.md",
    ".agents/skills/long-horizon-engineering/templates/risk-disclosure.md",
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
    if not path.is_file():
        return [f"Missing required skill file: {relative_path}"]
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
    cases = payload.get("cases")
    if payload.get("schema_version") != 2:
        errors.append("tests/expected-triggers.json schema_version must be 2.")
    if not isinstance(cases, list) or not cases:
        return ["tests/expected-triggers.json must contain a non-empty cases list."]

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"Trigger fixture case {index} must be an object.")
            continue
        for key in ("id", "prompt", "invocation_mode", "expected_skill", "category", "rationale", "tags"):
            if key not in case:
                errors.append(f"Trigger fixture case {index} is missing {key}.")
        if case.get("expected_skill") not in {"long-horizon-engineering", "ai-video-production", "none"}:
            errors.append(f"Trigger fixture case {case.get('id', index)} has invalid expected_skill.")
    return errors


def run_checks() -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    is_package = package_mode()
    ai_video_path = ROOT / ".agents/skills/ai-video-production/SKILL.md"

    required_paths = [
        path for path in INSTALLED_REQUIRED_PATHS
        if is_package
        or ai_video_path.exists()
        or not path.startswith(".agents/skills/ai-video-production/")
    ]
    errors.extend(check_required_paths(required_paths, "installed skill"))

    if is_package:
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
    if is_package or ai_video_path.exists():
        errors.extend(check_front_matter(
            ".agents/skills/ai-video-production/SKILL.md",
            "ai-video-production",
        ))
    errors.extend(check_nested_agents())
    if is_package:
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
