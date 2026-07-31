#!/usr/bin/env python3
"""Contract tests for manifest-selected profile assembly."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_skill_profile.py"


def load_module():
    spec = importlib.util.spec_from_file_location("assemble_skill_profile", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ASSEMBLER = load_module()


class ProfileAssemblyTests(unittest.TestCase):
    def test_all_declared_profiles_have_reference_closure(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        for profile in manifest["profiles"]:
            with self.subTest(profile=profile):
                paths = ASSEMBLER.selected_paths(manifest, profile)
                self.assertEqual([], ASSEMBLER.unresolved_lhe_references(paths, manifest))

    def test_core_only_apply_creates_only_selected_paths(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "core-only")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", str(output), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            actual = {
                str(path.relative_to(output))
                for path in output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(set(paths), actual)
            assembled_skill = (
                output / ".agents/skills/long-horizon-engineering/SKILL.md"
            ).read_text(encoding="utf-8")
            selected = ASSEMBLER.lhe_selected_relative_paths(paths)
            self.assertNotIn(ASSEMBLER.OPTIONAL_REFERENCE_MARKER, assembled_skill)
            self.assertIn("optional extension not included in profile core-only", assembled_skill)
            self.assertEqual(
                [],
                [
                    reference
                    for reference in ASSEMBLER.REFERENCE_RE.findall(assembled_skill)
                    if reference not in selected
                ],
            )

    def test_full_profile_keeps_marked_source_text_unchanged(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "legacy-full")
        source = (
            ROOT / ".agents/skills/long-horizon-engineering/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            source,
            ASSEMBLER.render_markdown(
                source, ASSEMBLER.lhe_selected_relative_paths(paths), "legacy-full"
            ),
        )

    def test_apply_rejects_nonempty_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            output.mkdir()
            (output / "existing.txt").write_text("x", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", str(output), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("output root must be empty", result.stderr)

    def test_output_root_requires_explicit_apply(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", "/tmp/profile"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--output-root requires --apply", result.stderr)

    def test_manifest_paths_fail_closed_before_source_or_output_access(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        for unsafe in ("../outside.md", "/tmp/outside.md", "dir\\file.md"):
            with self.subTest(unsafe=unsafe):
                tampered = json.loads(json.dumps(manifest))
                tampered["components"]["core"]["paths"][0] = unsafe
                with self.assertRaisesRegex(ASSEMBLER.ProfileError, "package path"):
                    ASSEMBLER.selected_paths(tampered, "core-only")

    def test_unavailable_reference_must_be_safe_to_render(self) -> None:
        with self.assertRaisesRegex(ASSEMBLER.ProfileError, "cannot safely render"):
            ASSEMBLER.render_markdown(
                "references/example.md <!-- profile-optional-reference -->\n",
                set(),
                "core-only",
            )

    def test_failed_assembly_does_not_create_a_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            with self.assertRaisesRegex(ASSEMBLER.ProfileError, "selected source path"):
                ASSEMBLER.assemble(["missing.md"], output, "core-only")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
