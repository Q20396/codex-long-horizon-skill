#!/usr/bin/env python3
"""Run local product-readiness checks for this skill package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]
SKILLS_DIR = SKILL_DIR.parent
SOURCE_ROOT = SCRIPT_PATH.parents[4]
SOURCE_SKILL_DIR = SOURCE_ROOT / ".agents" / "skills" / "long-horizon-engineering"
IS_SOURCE_LAYOUT = SOURCE_SKILL_DIR == SKILL_DIR
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
    "docs/maintainers/local-first-feasibility-review-plan.md",
    "docs/plugin-install.md",
    "docs/customer-guided-workflow.md",
    "docs/high-stakes-customer-workflows.md",
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
    "examples/customer-guided-decision/expected-output.md",
    "examples/customer-guided-decision/prompt.md",
    "examples/customer-guided-decision/workflow.md",
    "examples/high-stakes-customer-workflows.md",
    "prompts/bug-investigation.md",
    "prompts/large-refactor.md",
    "prompts/pr-review.md",
    "prompts/repository-migration.md",
    "prompts/resume-work.md",
    "prompts/customer-guided-decision.md",
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
CAPABILITY_CATALOG_PATH = SKILL_DIR / "catalog" / "local-capability-catalog.json"
PACKAGE_MANIFEST_PATH = SKILL_DIR / "package-manifest.json"

_LEGACY_STATIC_INSTALLED_REQUIRED_PATHS = [
    ".agents/skills/long-horizon-engineering/SKILL.md",
    ".agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json",
    ".agents/skills/long-horizon-engineering/references/approved-tool-contract-card.md",
    ".agents/skills/long-horizon-engineering/references/local-voice-tool-sandbox.md",
    ".agents/skills/long-horizon-engineering/references/three-d-asset-provider-sandbox.md",
    ".agents/skills/long-horizon-engineering/references/adversarial-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/api-integration-protocol.md",
    ".agents/skills/long-horizon-engineering/references/data-cleaning-protocol.md",
    ".agents/skills/long-horizon-engineering/references/evidence-backed-writing.md",
    ".agents/skills/long-horizon-engineering/references/code-review-response-protocol.md",
    ".agents/skills/long-horizon-engineering/references/decision-map-and-frontier.md",
    ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ".agents/skills/long-horizon-engineering/references/explicit-only-extensions.md",
    ".agents/skills/long-horizon-engineering/references/external-skill-adoption-safety-review.md",
    ".agents/skills/long-horizon-engineering/references/financial-research-report-protocol.md",
    ".agents/skills/long-horizon-engineering/references/investment-research-agent-protocol.md",
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
    ".agents/skills/long-horizon-engineering/references/ui-design-skill-adapter.md",
    ".agents/skills/long-horizon-engineering/references/ui-ux-review-protocol.md",
    ".agents/skills/long-horizon-engineering/references/upgrade-audit-protocol.md",
    ".agents/skills/long-horizon-engineering/references/writing-humanization-protocol.md",
    ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py",
    ".agents/skills/long-horizon-engineering/scripts/compute_frontier.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py",
    ".agents/skills/long-horizon-engineering/scripts/validate_json_canvas.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_external_skill_candidate.py",
    ".agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py",
    ".agents/skills/long-horizon-engineering/scripts/manage_skill_lifecycle.py",
    ".agents/skills/long-horizon-engineering/scripts/score_skill_candidate.py",
    ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py",
    ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py",
    ".agents/skills/long-horizon-engineering/templates/implementation-plan.md",
    ".agents/skills/long-horizon-engineering/templates/DECISION_MAP_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/GOAL_DRIVEN_DELIVERY_CONTRACT.md",
    ".agents/skills/long-horizon-engineering/templates/APPROVED_TOOL_CONTRACT_CARD.md",
    ".agents/skills/long-horizon-engineering/templates/LOCAL_VOICE_TOOL_APPROVAL_CARD.md",
    ".agents/skills/long-horizon-engineering/templates/THREE_D_ASSET_DELIVERY_APPROVAL_CARD.md",
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
    ".agents/skills/long-horizon-engineering/templates/INVESTMENT_RESEARCH_AGENT_AGREEMENT.md",
    ".agents/skills/long-horizon-engineering/templates/ui-ux-audit.md",
    ".agents/skills/long-horizon-engineering/templates/UPGRADE_AUDIT_REPORT_TEMPLATE.md",
    ".agents/skills/long-horizon-engineering/templates/valuation-assumption-table.md",
    ".agents/skills/long-horizon-engineering/templates/verification-evidence.md",
    ".agents/skills/long-horizon-engineering/templates/risk-disclosure.md",
    ".agents/skills/long-horizon-engineering/templates/slide-qa-checklist.md",
    ".agents/skills/long-horizon-engineering/templates/voice-calibration.md",
    ".agents/skills/long-horizon-engineering/schemas/decision-map.schema.json",
    ".agents/skills/long-horizon-engineering/schemas/frontier.schema.json",
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


def load_legacy_full_manifest_paths() -> list[str]:
    """Return the installed LHE inventory from its package manifest."""
    manifest = json.loads(PACKAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    profile = manifest["profiles"]["legacy-full"]
    return [
        path
        for component_name in profile["components"]
        for path in manifest["components"][component_name]["paths"]
    ]


LHE_INSTALLED_REQUIRED_PATHS = load_legacy_full_manifest_paths()
AI_VIDEO_INSTALLED_REQUIRED_PATHS = [
    path
    for path in _LEGACY_STATIC_INSTALLED_REQUIRED_PATHS
    if path.startswith(".agents/skills/ai-video-production/")
]
INSTALLED_REQUIRED_PATHS = (
    LHE_INSTALLED_REQUIRED_PATHS + AI_VIDEO_INSTALLED_REQUIRED_PATHS
)


def read_text(relative_path: str) -> str:
    return (SOURCE_ROOT / relative_path).read_text(encoding="utf-8")


def installed_path(relative_path: str) -> Path:
    path = Path(relative_path)
    expected_prefix = (".agents", "skills")
    if path.parts[:2] != expected_prefix:
        raise ValueError(f"Installed skill path must start with .agents/skills: {relative_path}")
    return SKILLS_DIR.joinpath(*path.parts[2:])


def package_mode() -> bool:
    return IS_SOURCE_LAYOUT and all(
        (SOURCE_ROOT / relative_path).is_file() for relative_path in PACKAGE_ONLY_PATHS
    )


def check_required_paths(
    required_paths: list[str], label: str, *, installed: bool
) -> list[str]:
    return [
        f"Missing required {label} file: {relative_path}"
        for relative_path in required_paths
        if not (installed_path(relative_path) if installed else SOURCE_ROOT / relative_path).is_file()
    ]


def check_front_matter(relative_path: str, expected_name: str) -> list[str]:
    path = installed_path(relative_path)
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
    return [
        f"Nested .agents path found: {path.relative_to(SKILLS_DIR)}"
        for path in SKILLS_DIR.rglob(".agents")
    ]


def check_trigger_fixture() -> list[str]:
    path = SOURCE_ROOT / "tests" / "expected-triggers.json"
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


def load_object(path: Path, label: str) -> tuple[dict, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {}, [f"{label} could not be read: {error}"]
    if not isinstance(value, dict):
        return {}, [f"{label} must contain a JSON object."]
    return value, []


def capability_health_report(
    requested_profile: str | None,
) -> tuple[dict, list[str]]:
    """Report only static declarations; never inspect host config or accounts."""
    errors: list[str] = []
    manifest, manifest_errors = load_object(
        PACKAGE_MANIFEST_PATH,
        "Package manifest",
    )
    catalog, catalog_errors = load_object(
        CAPABILITY_CATALOG_PATH,
        "Local capability catalog",
    )
    errors.extend(manifest_errors)
    errors.extend(catalog_errors)

    profiles = manifest.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        errors.append("Package manifest profiles must be an object.")
    selected_profile = requested_profile or manifest.get("default_profile")
    if not isinstance(selected_profile, str) or selected_profile not in profiles:
        errors.append(
            "Capability report profile must name a declared package profile."
        )

    authority = catalog.get("authority", {})
    if not isinstance(authority, dict):
        authority = {}
        errors.append("Local capability catalog authority must be an object.")
    expected_false = {
        "keyword_match_grants_authority",
        "auto_load_uninstalled_code",
        "auto_install",
        "auto_execute",
        "network_access",
        "account_access",
        "persistence",
        "customer_sensitive_data_upload",
        "model_memory",
        "telemetry",
    }
    for field in sorted(expected_false):
        if authority.get(field) is not False:
            errors.append(
                f"Local capability catalog authority must keep {field}=false."
            )

    provider_records = catalog.get("providers", [])
    if not isinstance(provider_records, list):
        provider_records = []
        errors.append("Local capability catalog providers must be a list.")
    safe_providers: list[dict] = []
    provider_ids: set[str] = set()
    for index, provider_record in enumerate(provider_records):
        if not isinstance(provider_record, dict):
            errors.append(f"Provider declaration {index} must be an object.")
            continue
        provider_id = provider_record.get("provider_id")
        if not isinstance(provider_id, str) or not provider_id:
            errors.append(f"Provider declaration {index} must have a provider_id.")
            continue
        if provider_id in provider_ids:
            errors.append(f"Provider declaration is duplicated: {provider_id}")
            continue
        provider_ids.add(provider_id)
        fixed_provider_fields = {
            "status": "declared-disabled",
            "interface_only": True,
            "runtime_present": False,
            "connector_implementations_present": False,
            "synthetic_pilot_status": "fixture-only",
            "network_access": False,
            "account_access": False,
            "credential_access": False,
            "persistence_authority": False,
            "customer_sensitive_data_upload": False,
            "model_memory": False,
            "telemetry": False,
            "expires_at": None,
        }
        for field, expected in fixed_provider_fields.items():
            if (
                type(provider_record.get(field)) is not type(expected)
                or provider_record.get(field) != expected
            ):
                errors.append(
                    f"Provider {provider_id} must keep {field}={expected!r}."
                )
        safe_providers.append(
            {
                "provider_id": provider_id,
                **{
                    field: provider_record.get(field)
                    for field in fixed_provider_fields
                },
            }
        )

    cards = catalog.get("capabilities", [])
    if not isinstance(cards, list):
        cards = []
        errors.append("Local capability catalog capabilities must be a list.")
    safe_cards: list[dict] = []
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"Capability card {index} must be an object.")
            continue
        if (
            card.get("availability") != "descriptor-only"
            or card.get("installed") is not False
            or card.get("callable") is not False
            or card.get("executable") is not False
        ):
            errors.append(
                f"Capability card must remain descriptor-only: "
                f"{card.get('capability_id', index)}"
            )
        provider = card.get("required_provider")
        if provider is not None and not isinstance(provider, str):
            errors.append(
                "Capability card required_provider must be a string or null: "
                f"{card.get('capability_id', index)}"
            )
        elif isinstance(provider, str) and provider not in provider_ids:
            errors.append(
                f"Capability card references an undeclared provider: {provider}"
            )
        safe_cards.append(
            {
                "capability_id": card.get("capability_id"),
                "status": card.get("availability"),
                "activation": card.get("activation"),
                "installed": card.get("installed"),
                "callable": card.get("callable"),
                "executable": card.get("executable"),
                "required_provider": provider,
                "allowed_effects": card.get("allowed_effects"),
                "forbidden_effects": card.get("forbidden_effects"),
            }
        )

    report = {
        "mode": "static-read-only",
        "active_profile": selected_profile,
        "profile_activation_verified": False,
        "available_profiles": sorted(profiles),
        "capability_catalog": {
            "catalog_id": catalog.get("catalog_id"),
            "discovery_mode": catalog.get("discovery_mode"),
            "host_routing_verified": False,
            "cards": safe_cards,
        },
        "declared_providers": sorted(
            safe_providers,
            key=lambda provider: provider["provider_id"],
        ),
        "permission_effects": {
            "network": False,
            "account_access": False,
            "upload": False,
            "persistence": False,
            "installation": False,
            "execution": False,
            "external_action": False,
        },
        "data_locality": {
            "customer_sensitive_data_upload": False,
            "model_memory": False,
            "telemetry": False,
            "local_provider_storage_verified": False,
        },
        "limitations": [
            "The report reads package declarations only.",
            "It does not inspect user config, installed providers, accounts, credentials, project materials, logs, connector state, or runtime permissions.",
            "A descriptor is not an installed or callable capability.",
        ],
    }
    return report, errors


def run_checks() -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    is_package = package_mode()
    ai_video_path = SKILLS_DIR / "ai-video-production" / "SKILL.md"

    required_paths = [
        path for path in INSTALLED_REQUIRED_PATHS
        if is_package
        or ai_video_path.exists()
        or not path.startswith(".agents/skills/ai-video-production/")
    ]
    errors.extend(check_required_paths(required_paths, "installed skill", installed=True))

    if is_package:
        errors.extend(check_required_paths(PACKAGE_ONLY_PATHS, "package", installed=False))
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
    parser.add_argument(
        "--profile",
        help=(
            "Report a declared package profile. This does not inspect or change "
            "the host's active configuration."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors, warnings = run_checks()
    capability_report, capability_errors = capability_health_report(args.profile)
    errors.extend(capability_errors)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "capability_report": capability_report,
                },
                indent=2,
            )
        )
    elif errors:
        for warning in warnings:
            print(f"WARNING: {warning}")
        for error in errors:
            print(f"ERROR: {error}")
    else:
        for warning in warnings:
            print(f"WARNING: {warning}")
        print("Doctor check passed.")
        print(
            "Capability profile: "
            f"{capability_report['active_profile']} "
            "(static declaration; host activation not verified)."
        )
        print(
            "Declared domain capabilities: "
            f"{len(capability_report['capability_catalog']['cards'])}; "
            "all descriptor-only and non-executable."
        )

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
