from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
SKILL = LHE / "SKILL.md"
TEMPLATE = LHE / "templates" / "GOAL_DRIVEN_DELIVERY_CONTRACT.md"
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


class GoalDrivenDeliveryContractTests(unittest.TestCase):
    def test_skill_routes_explicit_requests_without_granting_authority(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("templates/GOAL_DRIVEN_DELIVERY_CONTRACT.md"),
            1,
        )
        self.assertIn("user explicitly requests", text)
        self.assertIn("bundled-optional", text)
        self.assertIn("explicit-only thin layer", text)
        self.assertIn("Do not create or persist", text)
        self.assertIn("## Routing And Promotion Governance", text)

    def test_template_reuses_existing_contracts_without_parallel_lifecycle(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for path in (
            "references/planner-builder-evaluator-loop.md",
            "templates/implementation-plan.md",
            "templates/WORKING_STATE_TEMPLATE.md",
            "templates/verification-evidence.md",
            "references/decision-map-and-frontier.md",
            "references/skill-routing-and-promotion-contract.md",
        ):
            self.assertIn(path, text)
        self.assertIn("does not create a new role, lifecycle", normalized)
        self.assertIn("These references remain authoritative", text)

    def test_human_and_promotion_state_remain_fixed_and_non_authorizing(self) -> None:
        text = normalized_text(TEMPLATE)
        for value in (
            "`human_disposition: pending`",
            "`human_actor: none`",
            "`decision_reference_status: unverified_claim`",
            "`promotion_state: not-promoted`",
            "`next_stage_authorized: false`",
        ):
            self.assertIn(value, text)
        for conflicting_value in (
            "human_disposition: approved",
            "promotion_state: promoted",
            "next_stage_authorized: true",
        ):
            self.assertNotIn(conflicting_value, text)
        for phrase in (
            "No model, Planner, Builder, Evaluator",
            "recommendation, computed Frontier, or `verified` result",
            "grant a next stage, execution, merge, release, deployment",
            "this template does not implement that source",
        ):
            self.assertIn(phrase, text)

    def test_template_denies_implicit_effects_and_sensitive_persistence(self) -> None:
        text = normalized_text(TEMPLATE)
        self.assertIn("Blank fields grant nothing", text)
        for phrase in (
            "does not implicitly authorize writes, network access, installation",
            "Persistence is denied by default",
            "secrets, credentials, tokens, private keys",
            "client materials",
            "account data",
            "private communications",
            "legal or financial evidence",
            "sensitive project content",
            "Do not create logs, caches, memory files, background state",
        ):
            self.assertIn(phrase, text)
        self.assertIn("It is not independent review", text)
        self.assertIn("runtime enforcement, or host-enforced isolation", text)

    def test_package_integration_and_derived_evidence_are_exact(self) -> None:
        template_path = (
            ".agents/skills/long-horizon-engineering/"
            "templates/GOAL_DRIVEN_DELIVERY_CONTRACT.md"
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        optional = manifest["components"]["bundled-optional"]["paths"]
        self.assertIn(template_path, optional)
        self.assertNotIn(template_path, manifest["components"]["core"]["paths"])
        self.assertEqual(len(manifest["components"]["core"]["paths"]), 42)
        self.assertEqual(len(optional), 101)
        self.assertEqual(
            sum(len(item["paths"]) for item in manifest["separate_skills"]),
            26,
        )

        checker = load_module("goal_delivery_checker", CHECKER)
        doctor = load_module("goal_delivery_doctor", DOCTOR)
        self.assertIn(template_path, checker.INSTALLED_REQUIRED_FILES)
        self.assertIn(template_path, doctor.INSTALLED_REQUIRED_PATHS)

        classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(
            classification["source_manifest_sha256"],
            hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        )
        self.assertEqual(classification["summary"]["manifest_paths_reviewed"], 169)
        self.assertEqual(classification["summary"]["core_retained"], 42)
        self.assertEqual(
            classification["summary"]["bundled_optional_retained"],
            86,
        )
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
