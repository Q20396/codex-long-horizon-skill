#!/usr/bin/env python3
"""Unit tests for skill_update_selfcheck.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import skill_update_selfcheck as checker


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SkillUpdateSelfcheckTests(unittest.TestCase):
    def make_report(self, skill_id: str, local_path: Path, remote_path: Path) -> checker.SkillReport:
        return checker.SkillReport(
            skill_id=skill_id,
            local_path=str(local_path),
            remote_path=str(remote_path),
            local_version=None,
            remote_version=None,
            local_missing=False,
            added_files=[],
            removed_files=[],
            modified_files=["SKILL.md"],
            possible_breaking_changes=[],
            risk_level="HIGH",
            upgrade_recommendation="Manual review recommended before upgrading.",
            backup_plan="Create backup.",
            rollback_plan="Restore backup.",
        )

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
            skill_id = "long-horizon-engineering"
            write(
                remote_repo / ".agents" / "skills" / skill_id / "SKILL.md",
                f"---\nversion: 0.2.0\nskill_id: {skill_id}\n---\n# Demo\n",
            )
            report = checker.build_skill_report(skill_id, installed, remote_repo)
            self.assertTrue(report.local_missing)
            self.assertEqual(report.remote_version, "0.2.0")
            self.assertIn("SKILL.md", report.added_files)

    def test_default_mode_does_not_apply_or_replace_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "installed"
            remote_repo = root / "repo"
            skill_id = "ai-video-production"
            write(installed / skill_id / "SKILL.md", "local")
            write(remote_repo / ".agents" / "skills" / skill_id / "SKILL.md", "remote")
            report = checker.build_skill_report(skill_id, installed, remote_repo)
            self.assertEqual((installed / skill_id / "SKILL.md").read_text(), "local")
            self.assertIn("SKILL.md", report.modified_files)

    def test_cli_default_skills_are_a_list(self) -> None:
        args = checker.parse_args([])
        self.assertEqual(args.skills, ["long-horizon-engineering", "ai-video-production"])

    def test_cli_custom_skills_are_restricted_to_approved_list(self) -> None:
        args = checker.parse_args(["--skills", "ai-video-production,long-horizon-engineering"])
        self.assertEqual(args.skills, ["ai-video-production", "long-horizon-engineering"])

    def test_validate_skill_id_rejects_traversal(self) -> None:
        invalid = [
            "../escape",
            "/absolute/path",
            "long-horizon-engineering/../../x",
            "",
            "other-skill",
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    checker.validate_skill_id(value)

    def test_validate_skill_id_accepts_approved_skills(self) -> None:
        self.assertEqual(
            checker.validate_skill_id("long-horizon-engineering"),
            "long-horizon-engineering",
        )
        self.assertEqual(checker.validate_skill_id("ai-video-production"), "ai-video-production")

    def test_parse_skill_list_removes_duplicates_preserving_order(self) -> None:
        skills = checker.parse_skill_list(
            "ai-video-production,long-horizon-engineering,ai-video-production"
        )
        self.assertEqual(skills, ["ai-video-production", "long-horizon-engineering"])

    def test_safe_child_path_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                checker.safe_child_path(Path(tmp), "../escape")

    def test_assert_direct_child_rejects_paths_outside_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                checker.assert_direct_child(root / "installed", root / "outside" / "skill", "test path")

    def test_local_target_symlink_is_rejected_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "installed"
            remote_repo = root / "repo"
            backup_root = installed / ".backups" / "20260620-000000"
            skill_id = "long-horizon-engineering"
            outside = root / "outside"
            outside.mkdir(parents=True)
            installed.mkdir(parents=True)
            (installed / skill_id).symlink_to(outside, target_is_directory=True)
            write(remote_repo / ".agents" / "skills" / skill_id / "SKILL.md", "remote")
            report = self.make_report(
                skill_id,
                installed / skill_id,
                remote_repo / ".agents" / "skills" / skill_id,
            )
            with self.assertRaises(ValueError):
                checker.apply_skill_update(report, remote_repo, backup_root)

    def test_remote_skill_symlink_is_rejected_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "installed"
            remote_repo = root / "repo"
            backup_root = installed / ".backups" / "20260620-000000"
            skill_id = "ai-video-production"
            write(installed / skill_id / "SKILL.md", "local")
            outside = root / "outside-remote"
            outside.mkdir(parents=True)
            remote_skills = remote_repo / ".agents" / "skills"
            remote_skills.mkdir(parents=True)
            (remote_skills / skill_id).symlink_to(outside, target_is_directory=True)
            report = self.make_report(skill_id, installed / skill_id, remote_skills / skill_id)
            with self.assertRaises(ValueError):
                checker.apply_skill_update(report, remote_repo, backup_root)

    def test_update_all_only_uses_selected_approved_skills(self) -> None:
        report = self.make_report(
            "long-horizon-engineering",
            Path("/tmp/skills/long-horizon-engineering"),
            Path("/tmp/repo/.agents/skills/long-horizon-engineering"),
        )
        with patch("builtins.input", return_value="UPDATE ALL"):
            self.assertEqual(checker.choose_skills_for_apply([report]), ["long-horizon-engineering"])


if __name__ == "__main__":
    unittest.main()
