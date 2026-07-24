from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
MANIFEST = LHE / "package-manifest.json"
SCHEMA = LHE / "schemas" / "package-manifest.schema.json"
CHECKER = LHE / "scripts" / "check_skill_package.py"

class PackageManifestContractTests(unittest.TestCase):
    def load_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_manifest_declares_legacy_full_without_layout_change(self) -> None:
        manifest = self.load_json(MANIFEST)
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["skill_id"], "long-horizon-engineering")
        self.assertEqual(manifest["default_profile"], "legacy-full")
        self.assertEqual(manifest["profiles"]["legacy-full"]["components"], ["core", "bundled-optional"])
        self.assertFalse(manifest["migration"]["physical_layout_changed"])
        self.assertFalse(manifest["migration"]["default_install_changed"])
        self.assertTrue(manifest["migration"]["legacy_checker_fallback"])

    def test_layers_are_disjoint_exact_repo_paths(self) -> None:
        manifest = self.load_json(MANIFEST)
        seen: set[str] = set()
        for component_id, component in manifest["components"].items():
            self.assertIn(component["layer"], {"core", "bundled-optional"})
            self.assertTrue(component["paths"], component_id)
            for value in component["paths"]:
                self.assertTrue(
                    value.startswith(".agents/skills/long-horizon-engineering/")
                )
                self.assertNotIn(value, seen)
                self.assertNotIn("*", value)
                self.assertNotIn("..", Path(value).parts)
                seen.add(value)
        self.assertIn(
            ".agents/skills/long-horizon-engineering/package-manifest.json",
            seen,
        )
        self.assertIn(
            ".agents/skills/long-horizon-engineering/schemas/package-manifest.schema.json",
            seen,
        )

    def test_ai_video_is_declared_as_separate_skill(self) -> None:
        manifest = self.load_json(MANIFEST)
        [ai_video] = manifest["separate_skills"]
        self.assertEqual(ai_video["skill_id"], "ai-video-production")
        self.assertEqual(ai_video["layer"], "separate-skill")
        self.assertTrue(ai_video["required_in_source_package"])
        self.assertTrue(
            all(
                path.startswith(".agents/skills/ai-video-production/")
                for path in ai_video["paths"]
            )
        )

    def test_manifest_covers_current_skill_inventories_exactly(self) -> None:
        manifest = self.load_json(MANIFEST)
        lhe_prefix = ".agents/skills/long-horizon-engineering/"
        declared_lhe = {
            path.removeprefix(lhe_prefix)
            for component in manifest["components"].values()
            for path in component["paths"]
        }
        actual_lhe = {
            str(path.relative_to(LHE))
            for path in LHE.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(declared_lhe, actual_lhe)

        [ai_video] = manifest["separate_skills"]
        ai_video_dir = ROOT / ".agents" / "skills" / "ai-video-production"
        ai_video_prefix = ".agents/skills/ai-video-production/"
        declared_ai_video = {
            path.removeprefix(ai_video_prefix) for path in ai_video["paths"]
        }
        actual_ai_video = {
            str(path.relative_to(ai_video_dir))
            for path in ai_video_dir.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(declared_ai_video, actual_ai_video)

    def test_schema_is_draft_2020_12(self) -> None:
        schema = self.load_json(SCHEMA)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0")

    def test_checker_loads_manifest_and_keeps_legacy_fallback(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        contract, errors = module.load_package_contract()
        self.assertEqual(errors, [])
        self.assertEqual(
            set(contract.lhe_required_files),
            set(module.INSTALLED_REQUIRED_FILES),
        )
        self.assertEqual(
            set(contract.ai_video_required_files),
            set(module.AI_VIDEO_REQUIRED_FILES),
        )
        self.assertTrue(contract.loaded_from_manifest)

    def test_checker_rejects_unsafe_manifest_paths(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        unsafe_paths = (
            "../outside",
            ".agents/skills/long-horizon-engineering/bad\\name.md",
            ".agents/skills/long-horizon-engineering/bad//name.md",
            ".agents/skills/long-horizon-engineering/*.md",
        )
        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path):
                manifest = self.load_json(MANIFEST)
                manifest["components"]["core"]["paths"][0] = unsafe_path
                with tempfile.TemporaryDirectory() as temp_name:
                    path = Path(temp_name) / "package-manifest.json"
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                    with mock.patch.object(module, "PACKAGE_MANIFEST_PATH", path):
                        _, errors = module.load_package_contract()
                self.assertTrue(
                    any("Unsafe package manifest path" in error for error in errors),
                    errors,
                )

    def test_checker_validates_unselected_separate_skills(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        manifest = self.load_json(MANIFEST)
        manifest["separate_skills"].append(
            {
                "skill_id": "future-provider",
                "layer": "bundled-optional",
                "required_in_source_package": "yes",
                "paths": [".agents/skills/future-provider/../outside"],
            }
        )
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "package-manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.object(module, "PACKAGE_MANIFEST_PATH", path):
                _, errors = module.load_package_contract()
        self.assertTrue(any("invalid layer" in error for error in errors), errors)
        self.assertTrue(
            any("boolean required_in_source_package" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("Unsafe package manifest path" in error for error in errors),
            errors,
        )

    def test_checker_rejects_malformed_unselected_profiles(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        manifest = self.load_json(MANIFEST)
        manifest["profiles"]["malformed-unselected"] = {
            "components": ["core", "core", "missing-component"],
            "separate_skills": ["missing-skill"],
            "unexpected": True,
        }
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "package-manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.object(module, "PACKAGE_MANIFEST_PATH", path):
                _, errors = module.load_package_contract()
        self.assertTrue(any("profile fields are invalid" in error for error in errors), errors)
        self.assertTrue(any("contains duplicates" in error for error in errors), errors)
        self.assertTrue(any("missing-component" in error for error in errors), errors)
        self.assertTrue(any("missing-skill" in error for error in errors), errors)

    def test_checker_enforces_schema_structure_without_jsonschema(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        def validate(mutator) -> list[str]:
            manifest = self.load_json(MANIFEST)
            mutator(manifest)
            with tempfile.TemporaryDirectory() as temp_name:
                path = Path(temp_name) / "package-manifest.json"
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with mock.patch.object(module, "PACKAGE_MANIFEST_PATH", path):
                    _, errors = module.load_package_contract()
            return errors

        cases = {
            "unknown root field": (
                lambda manifest: manifest.__setitem__("unexpected", True),
                "unknown fields",
            ),
            "missing canonical component": (
                lambda manifest: (
                    manifest["components"].__setitem__(
                        "renamed-core", manifest["components"].pop("core")
                    ),
                    manifest["profiles"]["legacy-full"]["components"].__setitem__(
                        0, "renamed-core"
                    ),
                ),
                "missing canonical components",
            ),
            "unknown component field": (
                lambda manifest: manifest["components"]["core"].__setitem__(
                    "unexpected", True
                ),
                "component fields are invalid",
            ),
            "unknown separate skill field": (
                lambda manifest: manifest["separate_skills"][0].__setitem__(
                    "unexpected", True
                ),
                "Separate skill fields are invalid",
            ),
            "invalid schema type": (
                lambda manifest: manifest.__setitem__("$schema", 3),
                "$schema must be a string",
            ),
            "empty separate skill id": (
                lambda manifest: manifest["separate_skills"][0].__setitem__(
                    "skill_id", ""
                ),
                "non-empty string skill_id",
            ),
        }
        for name, (mutator, expected_error) in cases.items():
            with self.subTest(name=name):
                errors = validate(mutator)
                self.assertTrue(
                    any(expected_error in error for error in errors),
                    errors,
                )

    def test_checker_uses_legacy_contract_when_manifest_is_absent(self) -> None:
        spec = importlib.util.spec_from_file_location("check_skill_package", CHECKER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp_name:
            missing = Path(temp_name) / "missing.json"
            with mock.patch.object(module, "PACKAGE_MANIFEST_PATH", missing):
                contract, errors = module.load_package_contract()
        self.assertEqual(errors, [])
        self.assertFalse(contract.loaded_from_manifest)
        self.assertEqual(
            set(contract.lhe_required_files),
            set(module.INSTALLED_REQUIRED_FILES)
            - set(module.POST_LEGACY_REQUIRED_FILES),
        )
        self.assertNotIn(
            ".agents/skills/long-horizon-engineering/package-manifest.json",
            contract.lhe_required_files,
        )

if __name__ == "__main__":
    unittest.main()
