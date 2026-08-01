from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
MANIFEST = LHE / "package-manifest.json"
PROPOSAL = ROOT / "docs" / "design" / "package-layering-classification-v0.3.json"
REPORT = ROOT / "docs" / "design" / "package-layering-classification-v0.3.md"


class PackageLayeringClassificationV03Tests(unittest.TestCase):
    def load_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def manifest_paths_by_layer(self) -> dict[str, set[str]]:
        manifest = self.load_json(MANIFEST)
        result = {
            layer: set(component["paths"])
            for layer, component in manifest["components"].items()
        }
        result["separate-skill"] = {
            path
            for skill in manifest["separate_skills"]
            for path in skill["paths"]
        }
        return result

    def test_proposal_is_bound_to_reviewed_manifest(self) -> None:
        proposal = self.load_json(PROPOSAL)
        digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        self.assertEqual(proposal["source_manifest_sha256"], digest)
        self.assertEqual(proposal["baseline_commit"], "1fd15b8e2123f0a7cd85ff39ac778d265cedfb1b")

    def test_proposal_is_historical_and_non_executable(self) -> None:
        proposal = self.load_json(PROPOSAL)
        self.assertEqual(proposal["status"], "proposed")
        self.assertFalse(proposal["execution_authorized"])
        self.assertFalse(proposal["physical_moves_authorized"])
        self.assertFalse(proposal["manifest_changes_authorized"])
        self.assertFalse(proposal["default_profile_change_authorized"])
        self.assertEqual(proposal["default_action"], "retain-current-layer")

        manifest = self.load_json(MANIFEST)
        self.assertEqual(manifest["default_profile"], "local-governance-core")
        self.assertFalse(manifest["migration"]["physical_layout_changed"])
        self.assertTrue(manifest["migration"]["default_install_changed"])

    def test_every_override_is_unique_existing_optional_content(self) -> None:
        proposal = self.load_json(PROPOSAL)
        layers = self.manifest_paths_by_layer()
        paths = [item["path"] for item in proposal["candidate_extractions"]]
        self.assertEqual(len(paths), len(set(paths)))
        for item in proposal["candidate_extractions"]:
            self.assertEqual(item["current_layer"], "bundled-optional")
            self.assertIn(item["path"], layers["bundled-optional"])
            self.assertEqual(
                item["proposed_disposition"],
                "candidate-separate-skill-extraction",
            )
            self.assertTrue(item["target_boundary"])
            self.assertTrue(item["rationale"])

    def test_summary_covers_entire_manifest_exactly(self) -> None:
        proposal = self.load_json(PROPOSAL)
        layers = self.manifest_paths_by_layer()
        extracted = {item["path"] for item in proposal["candidate_extractions"]}
        summary = proposal["summary"]

        self.assertEqual(summary["core_retained"], len(layers["core"]))
        self.assertEqual(
            summary["bundled_optional_retained"],
            len(layers["bundled-optional"] - extracted),
        )
        self.assertEqual(
            summary["candidate_separate_skill_extractions"],
            len(extracted),
        )
        self.assertEqual(
            summary["existing_separate_skill_paths_retained"],
            len(layers["separate-skill"]),
        )
        self.assertEqual(
            summary["manifest_paths_reviewed"],
            sum(len(paths) for paths in layers.values()),
        )
        self.assertEqual(
            summary["manifest_paths_reviewed"],
            summary["core_retained"]
            + summary["bundled_optional_retained"]
            + summary["candidate_separate_skill_extractions"]
            + summary["existing_separate_skill_paths_retained"],
        )

    def test_no_core_or_existing_separate_skill_move_is_proposed(self) -> None:
        proposal = self.load_json(PROPOSAL)
        layers = self.manifest_paths_by_layer()
        extracted = {item["path"] for item in proposal["candidate_extractions"]}
        self.assertTrue(extracted.isdisjoint(layers["core"]))
        self.assertTrue(extracted.isdisjoint(layers["separate-skill"]))

    def test_target_boundaries_are_bounded_known_categories(self) -> None:
        proposal = self.load_json(PROPOSAL)
        actual = {
            item["target_boundary"] for item in proposal["candidate_extractions"]
        }
        self.assertEqual(
            actual,
            {
                "finance-domain-skill",
                "disaster-monitoring-skill",
                "knowledge-workspace-skill",
                "presentation-skill",
                "content-writing-skill",
                "personal-workflow-skill",
            },
        )

    def test_report_discloses_candidate_and_compatibility_boundaries(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        for value in (
            "Status: Proposed",
            "Supersession",
            "does not move files",
            "groups 15 paths into six candidate boundaries",
            "not approval to create a skill",
            "`legacy-full` as the default profile",
            "one candidate boundary per PR",
            "Finance should wait",
        ):
            self.assertIn(value, text)

    def test_report_counts_match_inventory_and_candidate_subset(self) -> None:
        proposal = self.load_json(PROPOSAL)
        summary = proposal["summary"]
        bundled_inventory = (
            summary["bundled_optional_retained"]
            + summary["candidate_separate_skill_extractions"]
        )
        total_inventory = (
            summary["core_retained"]
            + bundled_inventory
            + summary["existing_separate_skill_paths_retained"]
        )
        text = REPORT.read_text(encoding="utf-8")

        expected_rows = (
            f"| Retain in `core` | {summary['core_retained']} |",
            f"| `bundled-optional` inventory | {bundled_inventory} |",
            f"| Retain in `bundled-optional` | "
            f"{summary['bundled_optional_retained']} |",
            f"| Candidate separate-skill extraction | "
            f"{summary['candidate_separate_skill_extractions']} |",
            f"| Retain existing `separate-skill` | "
            f"{summary['existing_separate_skill_paths_retained']} |",
        )
        report_rows = tuple(
            line for line in text.splitlines() if line.startswith("|")
        )
        for expected in expected_rows:
            self.assertEqual(
                sum(row.startswith(expected) for row in report_rows),
                1,
                f"Expected exactly one report row starting with: {expected}",
            )

        self.assertIn(
            f"`{summary['bundled_optional_retained']} + "
            f"{summary['candidate_separate_skill_extractions']} = "
            f"{bundled_inventory}`",
            text,
        )
        self.assertIn(
            f"`{summary['core_retained']} + {bundled_inventory} + "
            f"{summary['existing_separate_skill_paths_retained']} = "
            f"{total_inventory}`",
            text,
        )


if __name__ == "__main__":
    unittest.main()
