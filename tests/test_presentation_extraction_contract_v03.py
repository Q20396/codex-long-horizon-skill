from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
MANIFEST = LHE / "package-manifest.json"
CLASSIFICATION = ROOT / "docs" / "design" / "package-layering-classification-v0.3.json"
CONTRACT = ROOT / "docs" / "design" / "presentation-separate-skill-extraction-v0.3.json"
REPORT = ROOT / "docs" / "design" / "presentation-separate-skill-extraction-v0.3.md"


class PresentationExtractionContractV03Tests(unittest.TestCase):
    def load_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_is_bound_to_current_sources(self) -> None:
        contract = self.load_json(CONTRACT)
        self.assertEqual(
            contract["source_manifest_sha256"],
            hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            contract["source_classification_sha256"],
            hashlib.sha256(CLASSIFICATION.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            contract["baseline_commit"],
            "c8bf79a8abb5740ba99c90c73df70cf568a54d9b",
        )

    def test_candidate_is_locked_and_non_executable(self) -> None:
        contract = self.load_json(CONTRACT)
        self.assertEqual(contract["status"], "candidate_only")
        for field in (
            "registered",
            "execution_authorized",
            "physical_moves_authorized",
            "manifest_changes_authorized",
            "default_profile_change_authorized",
            "runtime_changes_authorized",
            "dependencies_authorized",
            "network_authorized",
            "publication_authorized",
        ):
            self.assertFalse(contract[field], field)

    def test_source_boundary_matches_classification_exactly(self) -> None:
        contract = self.load_json(CONTRACT)
        classification = self.load_json(CLASSIFICATION)
        expected = {
            item["path"]
            for item in classification["candidate_extractions"]
            if item["target_boundary"] == "presentation-skill"
        }
        actual = {item["path"] for item in contract["source_paths"]}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 3)

    def test_source_digests_are_exact(self) -> None:
        contract = self.load_json(CONTRACT)
        for item in contract["source_paths"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(
                item["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )

    def test_current_manifest_preserves_paths_after_v04_default_change(self) -> None:
        contract = self.load_json(CONTRACT)
        manifest = self.load_json(MANIFEST)
        optional_paths = set(
            manifest["components"]["bundled-optional"]["paths"]
        )
        for item in contract["source_paths"]:
            self.assertIn(item["path"], optional_paths)
        self.assertEqual(manifest["default_profile"], "local-governance-core")
        self.assertFalse(manifest["migration"]["physical_layout_changed"])
        self.assertTrue(manifest["migration"]["default_install_changed"])

    def test_ownership_is_unresolved_and_avoids_duplicate_runtime(self) -> None:
        decision = self.load_json(CONTRACT)["ownership_decision"]
        self.assertEqual(decision["state"], "unresolved")
        self.assertEqual(
            decision["preferred_evaluation_order"][0],
            "installed-platform-presentation-capability",
        )
        joined = " ".join(decision["selection_requirements"])
        self.assertIn("No duplicate presentation runtime", joined)
        self.assertIn("independent from LHE", joined)

    def test_routing_separates_presentation_from_engineering_and_video(self) -> None:
        routing = self.load_json(CONTRACT)["routing_contract"]
        positives = " ".join(routing["positive_intents"])
        negatives = " ".join(routing["negative_intents"])
        self.assertIn("slide deck", positives)
        self.assertIn("PPTX", positives)
        self.assertIn("engineering implementation plan", negatives)
        self.assertIn("code diff", negatives)
        self.assertIn("AI video", negatives)
        self.assertEqual(routing["ambiguous_intent_action"], "clarify")

    def test_installation_use_and_side_effect_approvals_are_separate(self) -> None:
        permissions = self.load_json(CONTRACT)["permission_contract"]
        self.assertTrue(permissions["artifact_write_requires_exact_path_approval"])
        self.assertTrue(
            permissions["binary_generation_requires_available_approved_tooling"]
        )
        self.assertTrue(
            permissions["external_asset_fetch_requires_separate_approval"]
        )
        self.assertTrue(permissions["publication_requires_separate_approval"])
        self.assertTrue(permissions["installation_is_not_use_authorization"])

    def test_implementation_gate_requires_routing_install_and_rollback_evidence(self) -> None:
        gate = self.load_json(CONTRACT)["future_implementation_gate"]
        evidence = " ".join(gate["required_evidence"])
        stops = " ".join(gate["stop_conditions"])
        self.assertIn("Negative routing tests", evidence)
        self.assertIn("Clean-room package validation", evidence)
        self.assertIn("upgrade and rollback evidence", evidence)
        self.assertIn("Ownership overlaps", stops)
        self.assertIn("broken reference", stops)

    def test_rollback_preserves_separate_installations(self) -> None:
        rollback = self.load_json(CONTRACT)["rollback_contract"]
        self.assertTrue(
            rollback["separate_installation_must_not_be_deleted_implicitly"]
        )
        actions = " ".join(rollback["future_extraction_rollback"])
        self.assertIn("Restore the previous package manifest", actions)
        self.assertIn("Restore the three source paths", actions)

    def test_report_discloses_candidate_and_non_goals(self) -> None:
        text = " ".join(REPORT.read_text(encoding="utf-8").split())
        for phrase in (
            "Status: Candidate only",
            "Supersession",
            "does not create or register a skill",
            "owner is unresolved",
            "installed platform presentation capability",
            "Planning a presentation does not authorize artifact writes",
            "`legacy-full` as the default profile",
            "No migration is required",
            "must never silently delete a separately installed presentation capability",
            "does not:",
            "generate a deck",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
