import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import socket
import stat
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "long-horizon-engineering"
    / "scripts"
    / "update_installed_skill.py"
)

spec = importlib.util.spec_from_file_location(
    "update_installed_skill_replacement",
    SCRIPT,
)
updater = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(updater)


class UpdateInstalledSkillReplacementContractTests(unittest.TestCase):
    skill = "long-horizon-engineering"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source_root = self.root / "source-skills"
        self.source = self.source_root / self.skill
        self.source.mkdir(parents=True)
        self._write(self.source / "SKILL.md", "name: long-horizon-engineering\n")
        self._write(self.source / "references" / "guide.md", "source guide\n")
        self.skills_patch = mock.patch.object(updater, "SKILLS_ROOT", self.source_root)
        self.skills_patch.start()
        self.addCleanup(self.skills_patch.stop)
        self.audit_patch = mock.patch.object(
            updater,
            "run_pre_upgrade_safety_audit",
            return_value=None,
        )
        self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _plan(self, target_root: Path) -> updater.TargetPlan:
        args = updater.parse_args(
            ["--target-root", str(target_root), "--skill", self.skill]
        )
        return updater.resolve_target_plan(args, self.skill, apply=True)

    def _apply(
        self,
        plan: updater.TargetPlan,
        *,
        allow_remove_extra_files: bool = False,
    ) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            updater.update_skill(
                plan,
                self.skill,
                apply=True,
                allow_remove_extra_files=allow_remove_extra_files,
            )
        return output.getvalue()

    def _manifest(self, path: Path) -> dict[str, updater.ManifestEntry]:
        return updater.build_tree_manifest(path, "test tree")

    def test_dry_run_is_zero_write_and_reports_diff(self) -> None:
        target_root = self.root / "missing-target-root"
        plan = self._plan(target_root)
        output = io.StringIO()

        with redirect_stdout(output):
            updater.update_skill(plan, self.skill, apply=False)

        self.assertFalse(target_root.exists())
        self.assertIn("Mode: dry-run", output.getvalue())
        self.assertIn("SKILL.md", output.getvalue())
        self.assertNotIn("source guide", output.getvalue())

    def test_new_install_uses_staging_and_publishes_exact_manifest(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        output = self._apply(plan)

        self.assertEqual(self._manifest(self.source), self._manifest(plan.target))
        self.assertFalse(plan.backup_root.exists())
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in plan.target.parent.iterdir())
        )
        self.assertIn("Update complete.", output)

    def test_target_only_file_blocks_apply_before_any_artifact(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        self._write(target / "local-only.txt", "private local content\n")
        before = self._manifest(target)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "target-only files block apply"):
            self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse(plan.backup_root.exists())
        self.assertEqual(
            [],
            [
                path
                for path in target.parent.iterdir()
                if path.name.startswith(f".{self.skill}.")
            ],
        )

    def test_explicit_extra_file_approval_replaces_target_and_retains_backup(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        self._write(target / "local-only.txt", "private local content\n")
        plan = self._plan(target_root)

        output = self._apply(plan, allow_remove_extra_files=True)

        self.assertEqual(self._manifest(self.source), self._manifest(target))
        self.assertFalse((target / "local-only.txt").exists())
        backups = list(plan.backup_root.iterdir())
        self.assertEqual(1, len(backups))
        self.assertEqual("private local content\n", (backups[0] / "local-only.txt").read_text())
        self.assertIn("Backup retained:", output)

    def test_staging_copy_failure_does_not_modify_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)

        def partial_failure(source: Path, destination: Path) -> None:
            destination.mkdir()
            self._write(destination / "partial.txt", "partial\n")
            raise updater.UpdateError("injected staging failure")

        with mock.patch.object(updater, "copy_validated_tree", side_effect=partial_failure):
            with self.assertRaisesRegex(updater.UpdateError, "injected staging failure"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse(plan.backup_root.exists())
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in target.parent.iterdir())
        )

    def test_staging_manifest_mismatch_does_not_modify_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_copy = updater.copy_validated_tree

        def corrupt_staging(source: Path, destination: Path) -> None:
            original_copy(source, destination)
            self._write(destination / "unexpected.txt", "unexpected\n")

        with mock.patch.object(updater, "copy_validated_tree", side_effect=corrupt_staging):
            with self.assertRaisesRegex(updater.UpdateError, "staging manifest mismatch"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse(plan.backup_root.exists())

    def test_post_publish_failure_quarantines_new_tree_and_restores_old_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        self._write(target / "old-local.txt", "old local\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_verify = updater.verify_exact_manifest

        def fail_published(
            expected: dict[str, updater.ManifestEntry],
            actual: dict[str, updater.ManifestEntry],
            label: str,
        ) -> None:
            if label == "published target":
                raise updater.UpdateError("injected post-publish failure")
            original_verify(expected, actual, label)

        with mock.patch.object(
            updater,
            "verify_exact_manifest",
            side_effect=fail_published,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "post-publish verification failed"):
                self._apply(plan, allow_remove_extra_files=True)

        self.assertEqual(before, self._manifest(target))
        backups = list(plan.backup_root.iterdir())
        self.assertEqual(1, len(backups))
        self.assertEqual(before, self._manifest(backups[0]))
        quarantines = [
            path
            for path in target.parent.iterdir()
            if path.name.startswith(f".{self.skill}.failed")
        ]
        self.assertEqual(1, len(quarantines))
        self.assertEqual(self._manifest(self.source), self._manifest(quarantines[0]))

    def test_new_install_post_publish_failure_leaves_no_active_target(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        original_verify = updater.verify_exact_manifest

        def fail_published(
            expected: dict[str, updater.ManifestEntry],
            actual: dict[str, updater.ManifestEntry],
            label: str,
        ) -> None:
            if label == "published target":
                raise updater.UpdateError("injected post-publish failure")
            original_verify(expected, actual, label)

        with mock.patch.object(
            updater,
            "verify_exact_manifest",
            side_effect=fail_published,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "post-publish verification failed"):
                self._apply(plan)

        self.assertFalse(plan.target.exists())
        quarantines = [
            path
            for path in plan.target.parent.iterdir()
            if path.name.startswith(f".{self.skill}.failed")
        ]
        self.assertEqual(1, len(quarantines))

    def test_source_nested_symlink_is_rejected_without_touching_target(self) -> None:
        external = self.root / "external.txt"
        self._write(external, "external sentinel\n")
        (self.source / "unsafe-link").symlink_to(external)
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())
        self.assertEqual("external sentinel\n", external.read_text())

    def test_source_skill_root_symlink_is_rejected_before_resolution(self) -> None:
        real_source = self.root / "real-source-skill"
        self.source.rename(real_source)
        self.source.symlink_to(real_source, target_is_directory=True)
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        with self.assertRaisesRegex(
            updater.UpdateError,
            "source skill root must not be a symbolic link",
        ):
            self._apply(plan)

        self.assertFalse(plan.target.exists())
        self.assertEqual(
            "name: long-horizon-engineering\n",
            (real_source / "SKILL.md").read_text(),
        )

    def test_target_nested_symlink_is_rejected_without_touching_external_data(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        external = self.root / "external.txt"
        self._write(external, "external sentinel\n")
        (target / "unsafe-link").symlink_to(external)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertEqual("external sentinel\n", external.read_text())
        self.assertEqual("old\n", (target / "SKILL.md").read_text())

    def test_target_root_symlink_is_rejected(self) -> None:
        real_root = self.root / "real-root"
        real_root.mkdir()
        linked_root = self.root / "linked-root"
        linked_root.symlink_to(real_root, target_is_directory=True)
        args = updater.parse_args(
            ["--target-root", str(linked_root), "--skill", self.skill]
        )

        with self.assertRaisesRegex(SystemExit, "must not be a symbolic link"):
            updater.resolve_target_plan(args, self.skill, apply=True)

    def test_agents_ancestor_symlink_is_rejected_without_external_write(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        external = self.root / "external-agents"
        external.mkdir()
        (target_root / ".agents").symlink_to(external, target_is_directory=True)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertEqual([], list(external.iterdir()))
        self.assertFalse(plan.target.exists())

    def test_skills_ancestor_symlink_is_rejected_without_external_write(self) -> None:
        target_root = self.root / "project"
        agents = target_root / ".agents"
        agents.mkdir(parents=True)
        external = self.root / "external-skills"
        external.mkdir()
        (agents / "skills").symlink_to(external, target_is_directory=True)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertEqual([], list(external.iterdir()))
        self.assertFalse(plan.target.exists())

    def test_direct_target_skills_ancestor_symlink_is_rejected(self) -> None:
        codex_root = self.root / "codex"
        real_skills = self.root / "external-direct-skills"
        target = real_skills / self.skill
        self._write(target / "SKILL.md", "old\n")
        codex_root.mkdir()
        (codex_root / "skills").symlink_to(real_skills, target_is_directory=True)
        args = updater.parse_args(
            [
                "--target-skill-dir",
                str(codex_root / "skills" / self.skill),
                "--skill",
                self.skill,
            ]
        )

        with self.assertRaisesRegex(SystemExit, "symbolic link rejected"):
            updater.resolve_target_plan(args, self.skill, apply=True)

        self.assertEqual("old\n", (target / "SKILL.md").read_text())

    def test_backup_root_symlink_is_rejected_without_modifying_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        external = self.root / "external-backups"
        external.mkdir()
        (target_root / ".codex-skill-backups").symlink_to(
            external,
            target_is_directory=True,
        )
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertEqual([], list(external.iterdir()))

    def test_backup_ancestor_symlink_is_rejected_without_external_write(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        external = self.root / "external-backup-root"
        external.mkdir()
        (target_root / ".codex-skill-backups").symlink_to(
            external,
            target_is_directory=True,
        )
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertEqual([], list(external.iterdir()))

    def test_existing_staging_symlink_is_rejected(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        plan.target.parent.mkdir(parents=True)
        external = self.root / "external-staging"
        external.mkdir()
        staged_link = plan.target.parent / ".forced-staging"
        staged_link.symlink_to(external, target_is_directory=True)

        with mock.patch.object(updater, "_unique_path", return_value=staged_link):
            with self.assertRaisesRegex(updater.UpdateError, "already exists"):
                self._apply(plan)

        self.assertEqual([], list(external.iterdir()))
        self.assertFalse(plan.target.exists())

    def test_fifo_source_entry_is_rejected_without_opening_it(self) -> None:
        fifo = self.source / "unsafe-fifo"
        os.mkfifo(fifo)
        plan = self._plan(self.root / "project")

        with self.assertRaisesRegex(updater.UpdateError, "special filesystem entry"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_socket_and_device_modes_are_rejected_by_entry_contract(self) -> None:
        for mode in (stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK):
            fake = argparse.Namespace(st_mode=mode | 0o600, st_nlink=1)
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    updater.UpdateError,
                    "special filesystem entry",
                ):
                    updater._validate_entry_type(fake, "unsafe-entry")

    def test_source_hardlink_is_rejected_when_link_count_is_detectable(self) -> None:
        original = self.source / "hardlink-source.txt"
        linked = self.source / "hardlink-copy.txt"
        self._write(original, "same inode\n")
        try:
            os.link(original, linked)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        plan = self._plan(self.root / "project")

        with self.assertRaisesRegex(updater.UpdateError, "hard-linked regular file"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_output_never_contains_file_contents_on_failure(self) -> None:
        secret_marker = "CUSTOMER-SECRET-CONTENT"
        self._write(self.source / "secret.txt", secret_marker)
        plan = self._plan(self.root / "project")
        output = io.StringIO()

        with mock.patch.object(
            updater,
            "copy_validated_tree",
            side_effect=updater.UpdateError("controlled copy failure"),
        ):
            with redirect_stdout(output):
                with self.assertRaisesRegex(updater.UpdateError, "controlled copy failure"):
                    updater.update_skill(plan, self.skill, apply=True)

        self.assertNotIn(secret_marker, output.getvalue())


if __name__ == "__main__":
    unittest.main()
