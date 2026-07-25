from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
MANIFEST = LHE / "package-manifest.json"
SCHEMA = LHE / "schemas" / "package-manifest.schema.json"
SPEC = ROOT / "docs" / "design" / "package-layering-v0.3.md"


class PackageLayeringV03SpecificationTests(unittest.TestCase):
    def load_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_spec_is_proposal_only_and_names_all_layers(self) -> None:
        text = SPEC.read_text(encoding="utf-8")
        self.assertIn("Status: Proposed", text)
        self.assertIn("not authorization to move files", text)
        for layer in ("`core`", "`bundled-optional`", "`separate-skill`"):
            self.assertIn(layer, text)

    def test_manifest_remains_single_path_authority(self) -> None:
        text = SPEC.read_text(encoding="utf-8")
        self.assertIn("owned exclusively by", text)
        self.assertIn(
            ".agents/skills/long-horizon-engineering/package-manifest.json",
            text,
        )
        self.assertIn("MUST NOT maintain a second path list", text)

    def test_spec_counts_match_current_manifest(self) -> None:
        manifest = self.load_json(MANIFEST)
        text = SPEC.read_text(encoding="utf-8")
        core_count = len(manifest["components"]["core"]["paths"])
        optional_count = len(manifest["components"]["bundled-optional"]["paths"])
        [ai_video] = manifest["separate_skills"]
        self.assertIn(f"{core_count} `core` paths", text)
        self.assertIn(f"{optional_count} `bundled-optional` paths", text)
        self.assertIn(
            f"{len(ai_video['paths'])} `ai-video-production` paths",
            text,
        )

    def test_spec_phase_preserves_legacy_defaults(self) -> None:
        manifest = self.load_json(MANIFEST)
        self.assertEqual(manifest["default_profile"], "legacy-full")
        self.assertFalse(manifest["migration"]["physical_layout_changed"])
        self.assertFalse(manifest["migration"]["default_install_changed"])
        self.assertTrue(manifest["migration"]["legacy_checker_fallback"])

    def test_existing_profiles_keep_disjoint_layer_meanings(self) -> None:
        manifest = self.load_json(MANIFEST)
        self.assertEqual(
            manifest["profiles"],
            {
                "legacy-full": {
                    "components": ["core", "bundled-optional"],
                    "separate_skills": ["ai-video-production"],
                },
                "core-only": {
                    "components": ["core"],
                    "separate_skills": [],
                },
                "lhe-bundled": {
                    "components": ["core", "bundled-optional"],
                    "separate_skills": [],
                },
            },
        )

    def test_existing_schema_already_expresses_three_layers(self) -> None:
        schema = self.load_json(SCHEMA)
        self.assertEqual(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertEqual(
            schema["properties"]["components"]["required"],
            ["core", "bundled-optional"],
        )
        self.assertEqual(
            schema["$defs"]["component"]["properties"]["layer"]["enum"],
            ["core", "bundled-optional"],
        )
        self.assertEqual(
            schema["$defs"]["separateSkill"]["properties"]["layer"]["const"],
            "separate-skill",
        )

    def test_spec_forbids_runtime_and_default_changes(self) -> None:
        text = SPEC.read_text(encoding="utf-8")
        required_boundaries = (
            "does not:",
            "move, delete, or duplicate package files",
            "change `legacy-full` as the default",
            "change updater or installer behavior",
            "add a provider, runtime, dependency, network call, or telemetry",
            "authorize automatic migration, publication, or promotion",
        )
        for boundary in required_boundaries:
            self.assertIn(boundary, text)

    def test_spec_requires_incremental_migration_and_rollback(self) -> None:
        text = SPEC.read_text(encoding="utf-8")
        for heading in (
            "## Migration Sequence",
            "## Validation Matrix",
            "## Rollback",
            "## Completion Criteria",
        ):
            self.assertIn(heading, text)
        self.assertIn("No v0.3 implementation PR may change more than one", text)
        self.assertIn("do not delete a separately installed skill", text)


if __name__ == "__main__":
    unittest.main()
