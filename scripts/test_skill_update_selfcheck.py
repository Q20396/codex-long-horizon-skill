#!/usr/bin/env python3
"""Unit tests for skill_update_selfcheck.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import skill_update_selfcheck as checker


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SkillUpdateSelfcheckTests(unittest.TestCase):
    def test_front_matter_metadata_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            write(
                path,
                """---
name: demo
description: Demo skill.
version: 0.2.0
repo: https://example.test/repo
skill_id: demo
update_channel: stable
---

# Demo
""",
            )
            metadata = checker.parse_front_matter(path)
            self.assertEqual(metadata["version"], "0.2.0")
            self.assertEqual(metadata["repo"], "https://example.test/repo")
            self.assertEqual(metadata["skill_id"], "demo")
            self.assertEqual(metadata["update_channel"], "stable")

    def test_directory_comparison_detects_added_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local"
            remote = root / "remote"
            write(local / "SKILL.md", "same")
            write(remote / "SKILL.md", "same")
            write(remote / "new.md", "new")
            diff = checker.compare_directories(local, remote)
            self.assertEqual(diff["added_files"], ["new.md"])

    def test_directory_comparison_detects_removed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local"
            remote = root / "remote"
            write(local / "old.md", "old")
            write(remote / "SKILL.md", "same")
            diff = checker.compare_directories(local, remote)
            self.assertIn("old.md", diff["removed_files"])

    def test_directory_comparison_detects_modified_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local"
            remote = root / "remote"
            write(local / "SKILL.md", "one")
            write(remote / "SKILL.md", "two")
            diff = checker.compare_directories(local, remote)
            self.assertEqual(diff["modified_files"], ["SKILL.md"])

    def test_risk_high_when_skill_md_changes(self) -> None:
        diff = {"added_files": [], "removed_files": [], "modified_files": ["SKILL.md"]}
        self.assertEqual(checker.classify_risk(diff), "HIGH")

    def test_risk_medium_when_references_changed(self) -> None:
        diff = {"added_files": ["references/new.md"], "removed_files": [], "modified_files": []}
        self.assertEqual(checker.classify_risk(diff), "MEDIUM")

    def test_risk_low_for_manifest_only_changes(self) -> None:
        diff = {"added_files": ["releases/latest.json"], "removed_files": [], "modified_files": []}
        self.assertEqual(checker.classify_risk(diff), "LOW")

    def test_missing_local_skill_is_handled_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote_repo = root / "repo"
            installed = root / "installed"
            write(
                remote_repo / ".agents" / "skills" / "demo" / "SKILL.md",
                "---\nversion: 0.2.0\nskill_id: demo\n---\n# Demo\n",
            )
            report = checker.build_skill_report("demo", installed, remote_repo)
            self.assertTrue(report.local_missing)
            self.assertEqual(report.remote_version, "0.2.0")
            self.assertIn("SKILL.md", report.added_files)

    def test_default_mode_does_not_apply_or_replace_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "installed"
            remote_repo = root / "repo"
            write(installed / "demo" / "SKILL.md", "local")
            write(remote_repo / ".agents" / "skills" / "demo" / "SKILL.md", "remote")
            report = checker.build_skill_report("demo", installed, remote_repo)
            self.assertEqual((installed / "demo" / "SKILL.md").read_text(), "local")
            self.assertIn("SKILL.md", report.modified_files)

    def test_cli_default_skills_are_a_list(self) -> None:
        args = checker.parse_args([])
        self.assertEqual(args.skills, ["long-horizon-engineering", "ai-video-production"])

    def test_cli_custom_skills_are_parsed_as_list(self) -> None:
        args = checker.parse_args(["--skills", "one,two"])
        self.assertEqual(args.skills, ["one", "two"])


if __name__ == "__main__":
    unittest.main()
