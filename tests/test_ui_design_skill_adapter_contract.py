from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
SKILL = LHE / "SKILL.md"
ADAPTER = LHE / "references" / "ui-design-skill-adapter.md"
PROTOCOL = LHE / "references" / "ui-ux-review-protocol.md"
MANIFEST = LHE / "package-manifest.json"
CHECKER = LHE / "scripts" / "check_skill_package.py"
DOCTOR = LHE / "scripts" / "doctor.py"
CLASSIFICATION = ROOT / "docs" / "design" / "package-layering-classification-v0.3.json"
PRESENTATION = ROOT / "docs" / "design" / "presentation-separate-skill-extraction-v0.3.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalized_text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class UiDesignSkillAdapterContractTests(unittest.TestCase):
    def test_skill_routes_to_adapter_and_preserves_lhe_authority(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(text.count("references/ui-design-skill-adapter.md"), 1)
        self.assertIn("LHE safety,", text)
        self.assertIn("privacy, authority, file-scope, validation, and delivery", text)
        self.assertIn("take precedence", text)
        self.assertIn("defaults to read-only audit", text)
        self.assertIn("Visual review does not replace build", text)
        self.assertIn("## Routing And Promotion Governance", text)

    def test_adapter_defaults_to_audit_and_requires_effect_approval(self) -> None:
        text = ADAPTER.read_text(encoding="utf-8")
        for heading in (
            "## Authority Order",
            "## Default Mode",
            "## Required Approval Before Build",
            "## Scope Boundaries",
            "## Persistence Policy",
            "## External-Source Policy",
            "## Validation Handoff",
            "## Hallmark-Specific Compatibility",
        ):
            self.assertIn(heading, text)
        for phrase in (
            "Default to audit-only",
            "Exact files to create, modify, or delete",
            "Global stylesheet impact",
            "Design-token or design-system impact",
            "Persistent state, cache, memory, or log files",
            "External network access and asset sources",
            "A rollback method",
        ):
            self.assertIn(phrase, text)

    def test_adapter_does_not_grant_unrelated_or_external_effects(self) -> None:
        text = normalized_text(ADAPTER)
        for phrase in (
            "Routes or navigation behavior",
            "APIs or data fetching",
            "Authentication or payment",
            "Analytics",
            "Domain or business logic",
            "Production configuration",
            "Dependencies",
            "Unrelated components",
        ):
            self.assertIn(phrase, text)
        self.assertIn("may not write files, download assets, study URLs", text)
        self.assertIn("install tools, execute project code", text)
        self.assertIn("requires approval for that specific access", text)

    def test_adapter_is_version_neutral_and_does_not_replace_validation(self) -> None:
        text = ADAPTER.read_text(encoding="utf-8")
        self.assertNotIn("58", text)
        self.assertNotIn("hallmark audit", text.lower())
        self.assertNotIn("hallmark redesign", text.lower())
        self.assertIn("visual-quality checklist is advisory", text)
        self.assertIn("does not replace engineering", text)
        self.assertIn("Do not mechanically", text)
        self.assertIn("Chinese-language product", text)

    def test_protocol_has_responsive_accessibility_and_evidence_contract(self) -> None:
        text = normalized_text(PROTOCOL)
        self.assertIn("## Design-Skill Integration Boundary", text)
        for value in ("320", "375", "414", "768"):
            self.assertIn(value, text)
        for phrase in (
            "No horizontal scrolling",
            "Keyboard access",
            "`:focus-visible`",
            "`prefers-reduced-motion`",
            "Empty, loading, error, disabled, hover, focus, and active states",
            "realistic Chinese content",
            "code location",
            "screenshot or browser observation",
            "design token",
            "actual validation result",
        ):
            self.assertIn(phrase, text)
        self.assertIn("Static inspection must not be reported as browser verification", text)

    def test_package_integration_and_evidence_binding_are_exact(self) -> None:
        adapter_path = (
            ".agents/skills/long-horizon-engineering/"
            "references/ui-design-skill-adapter.md"
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        optional = manifest["components"]["bundled-optional"]["paths"]
        self.assertIn(adapter_path, optional)
        self.assertNotIn(adapter_path, manifest["components"]["core"]["paths"])
        self.assertEqual(len(manifest["components"]["core"]["paths"]), 42)
        self.assertEqual(len(optional), 101)
        self.assertEqual(
            sum(len(item["paths"]) for item in manifest["separate_skills"]),
            26,
        )

        checker = load_module("ui_adapter_checker", CHECKER)
        doctor = load_module("ui_adapter_doctor", DOCTOR)
        self.assertIn(adapter_path, checker.INSTALLED_REQUIRED_FILES)
        self.assertIn(adapter_path, doctor.INSTALLED_REQUIRED_PATHS)

        classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(
            classification["source_manifest_sha256"],
            hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        )
        self.assertEqual(classification["summary"]["manifest_paths_reviewed"], 169)
        self.assertEqual(classification["summary"]["core_retained"], 42)
        self.assertEqual(classification["summary"]["bundled_optional_retained"], 86)
        self.assertEqual(
            classification["summary"]["candidate_separate_skill_extractions"],
            15,
        )
        self.assertEqual(
            classification["summary"]["existing_separate_skill_paths_retained"],
            26,
        )

        presentation = json.loads(PRESENTATION.read_text(encoding="utf-8"))
        self.assertEqual(
            presentation["source_manifest_sha256"],
            hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            presentation["source_classification_sha256"],
            hashlib.sha256(CLASSIFICATION.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
