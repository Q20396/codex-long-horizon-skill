#!/usr/bin/env python3
"""Static completeness checks for LHE helper-script effect declarations."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts"
MANIFEST = ROOT / "docs" / "maintainers" / "effect-manifest.json"
EFFECT_KEYS = {"network", "writes", "deletes", "external_commands", "requires_apply_flag", "requires_human_confirmation"}


class EffectManifestContractTests(unittest.TestCase):
    def load_manifest(self) -> dict[str, object]:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_covers_exactly_the_installed_helper_scripts(self) -> None:
        manifest = self.load_manifest()
        declared = manifest["scripts"]
        self.assertIsInstance(declared, dict)
        actual = {path.name for path in SCRIPTS.glob("*.py")}
        self.assertEqual(actual, set(declared))

    def test_each_effect_declaration_has_valid_closed_shape(self) -> None:
        for name, effects in self.load_manifest()["scripts"].items():
            with self.subTest(script=name):
                self.assertEqual(EFFECT_KEYS, set(effects))
                self.assertIn(effects["network"], {"none", "explicit-only"})
                for key in ("writes", "deletes", "external_commands"):
                    self.assertIsInstance(effects[key], list)
                    self.assertTrue(all(isinstance(item, str) and item for item in effects[key]))
                self.assertIsInstance(effects["requires_apply_flag"], bool)
                self.assertIsInstance(effects["requires_human_confirmation"], bool)

    def test_static_surfaces_match_declared_high_impact_effects(self) -> None:
        manifest = self.load_manifest()["scripts"]
        write_markers = ("write_text(", "write_bytes(", "mkdir(", "open(\"a\"", "open(\"w\"")
        for name, effects in manifest.items():
            with self.subTest(script=name):
                source = (SCRIPTS / name).read_text(encoding="utf-8")
                if re.search(r"add_argument\(\s*[\"']--apply", source):
                    self.assertTrue(effects["requires_apply_flag"])
                if any(marker in source for marker in write_markers):
                    self.assertTrue(effects["writes"])
                if "subprocess.run" in source:
                    self.assertTrue(effects["external_commands"])
                if re.search(r"^(?:import socket|from urllib\b)", source, re.MULTILINE):
                    self.assertEqual("explicit-only", effects["network"])


if __name__ == "__main__":
    unittest.main()
