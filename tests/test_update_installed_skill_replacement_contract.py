import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
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
        self.approved_files = {"SKILL.md", "references/guide.md"}
        self.skills_patch = mock.patch.object(updater, "SKILLS_ROOT", self.source_root)
        self.skills_patch.start()
        self.addCleanup(self.skills_patch.stop)
        self.inventory_patch = mock.patch.object(
            updater,
            "load_approved_source_inventory",
            side_effect=self._approved_inventory,
        )
        self.inventory_patch.start()
        self.addCleanup(self.inventory_patch.stop)
        self.audit_patch = mock.patch.object(
            updater,
            "run_pre_upgrade_safety_audit",
            return_value=None,
        )
        self.audit_mock = self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _approved_inventory(self, skill: str) -> updater.ApprovedInventory:
        self.assertEqual(self.skill, skill)
        directories: set[str] = set()
        for path in self.approved_files:
            parent = Path(path).parent
            while parent != Path("."):
                directories.add(parent.as_posix())
                parent = parent.parent
        return updater.ApprovedInventory(
            files=frozenset(self.approved_files),
            directories=frozenset(directories),
            package_manifest_sha256="1" * 64,
            inventory_sha256="2" * 64,
        )

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

    def _replace_directory_with_empty(self, path: Path, detached: Path) -> None:
        path.rename(detached)
        path.mkdir(mode=0o700)

    def test_write_all_retries_short_writes_and_rejects_zero_write(self) -> None:
        calls = []

        def short_write(descriptor, view):
            calls.append(bytes(view))
            return min(2, len(view))

        with mock.patch.object(updater.os, "write", side_effect=short_write):
            updater._write_all(123, b"abcdef", "synthetic file")
        self.assertEqual([b"abcdef", b"cdef", b"ef"], calls)

        with mock.patch.object(updater.os, "write", return_value=0):
            with self.assertRaisesRegex(updater.UpdateError, "invalid short write"):
                updater._write_all(123, b"data", "synthetic file")

    def test_missing_nofollow_support_fails_closed_for_all_open_helpers(self) -> None:
        with mock.patch.object(updater.os, "O_NOFOLLOW", 0):
            with self.assertRaisesRegex(updater.UpdateError, "nofollow-not-supported"):
                updater._directory_open_flags()
            with self.assertRaisesRegex(updater.UpdateError, "nofollow-not-supported"):
                updater._nofollow_flags(os.O_RDONLY, "synthetic file")

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

    def test_dry_run_does_not_require_posix_owner_or_lock_support(self) -> None:
        target_root = self.root / "missing-target-root"
        plan = self._plan(target_root)
        output = io.StringIO()

        with mock.patch.object(
            updater,
            "_effective_uid",
            side_effect=updater.UpdateError("POSIX unavailable"),
        ):
            with redirect_stdout(output):
                updater.update_skill(plan, self.skill, apply=False)

        self.assertFalse(target_root.exists())
        self.assertIn("Mode: dry-run", output.getvalue())

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

    def test_apply_rejects_source_and_target_overlap_before_writing(self) -> None:
        target_root = self.root / "self-source"
        source = target_root / ".agents" / "skills" / self.skill
        self._write(source / "SKILL.md", "source\n")
        self._write(source / "references" / "guide.md", "source guide\n")
        before = self._manifest(source)

        with mock.patch.object(
            updater,
            "SKILLS_ROOT",
            target_root / ".agents" / "skills",
        ):
            plan = self._plan(target_root)
            with self.assertRaisesRegex(updater.UpdateError, "overlap the source package"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(source))
        self.assertFalse((target_root / updater.LOCK_FILE_NAME).exists())
        self.assertFalse((target_root / updater.RECEIPT_DIRECTORY_NAME).exists())

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

        def partial_failure(
            source: Path,
            parent_fd: int,
            destination_name: str,
            *,
            source_root_fd=None,
        ) -> None:
            raise updater.UpdateError("injected staging failure")

        with mock.patch.object(updater, "copy_validated_tree_at", side_effect=partial_failure):
            with self.assertRaisesRegex(updater.UpdateError, "injected staging failure"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse(plan.backup_root.exists())
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in target.parent.iterdir())
        )

    def test_early_anchor_failure_preserves_original_error_without_receipt(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        output = io.StringIO()

        with mock.patch.object(
            updater,
            "_verify_root_anchor",
            side_effect=updater.UpdateError("injected root identity failure"),
        ):
            with redirect_stdout(output):
                with self.assertRaisesRegex(
                    updater.UpdateError,
                    "injected root identity failure",
                ):
                    updater.update_skill(plan, self.skill, apply=True)

        self.assertIn("Recovery receipt: ", output.getvalue())
        self.assertIn("unavailable", output.getvalue())
        self.assertFalse(plan.target.exists())

    def test_staging_manifest_mismatch_does_not_modify_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_copy = updater.copy_validated_tree_at

        def corrupt_staging(
            source: Path,
            parent_fd: int,
            destination_name: str,
            *,
            source_root_fd=None,
        ) -> None:
            original_copy(source, parent_fd, destination_name)
            staging_fd = os.open(destination_name, os.O_RDONLY, dir_fd=parent_fd)
            try:
                extra_fd = os.open("unexpected.txt", os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=staging_fd)
                os.close(extra_fd)
            finally:
                os.close(staging_fd)

        with mock.patch.object(updater, "copy_validated_tree_at", side_effect=corrupt_staging):
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

    def test_explicit_target_root_intermediate_symlink_is_rejected_without_external_write(self) -> None:
        external = self.root / "external-target-root"
        external.mkdir()
        lexical_parent = self.root / "lexical-parent"
        lexical_parent.mkdir()
        redirect = lexical_parent / "redirect"
        redirect.symlink_to(external, target_is_directory=True)
        args = updater.parse_args(
            [
                "--target-root",
                str(redirect / "project"),
                "--skill",
                self.skill,
            ]
        )

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            updater.resolve_target_plan(args, self.skill, apply=True)

        self.assertEqual([], list(external.iterdir()))

    def test_authorized_root_parent_symlink_is_rejected_before_fd_anchor(self) -> None:
        external = self.root / "external-authorized-root"
        external.mkdir()
        lexical_parent = self.root / "authorized-parent"
        lexical_parent.mkdir()
        redirect = lexical_parent / "redirect"
        redirect.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(updater.UpdateError, "symbolic link rejected"):
            updater._open_authorized_root(redirect / "installation")

        self.assertEqual([], list(external.iterdir()))

    def test_explicit_target_skill_intermediate_symlink_is_rejected_without_external_write(self) -> None:
        external = self.root / "external-direct-target"
        external.mkdir()
        lexical_parent = self.root / "lexical-parent"
        lexical_parent.mkdir()
        redirect = lexical_parent / "redirect"
        redirect.symlink_to(external, target_is_directory=True)
        args = updater.parse_args(
            [
                "--target-skill-dir",
                str(redirect / "skills" / self.skill),
                "--skill",
                self.skill,
            ]
        )

        with self.assertRaisesRegex(SystemExit, "symbolic link rejected"):
            updater.resolve_target_plan(args, self.skill, apply=True)

        self.assertEqual([], list(external.iterdir()))

    def test_target_root_chmod_before_publish_fails_closed_without_publish(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_update_receipt = updater._update_receipt_at

        def weaken_root(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "staging_verified":
                target_root.chmod(0o700)

        with mock.patch.object(updater, "_update_receipt_at", side_effect=weaken_root):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "authorized installation root identity changed",
            ):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in target.parent.iterdir())
        )

    def test_target_root_inode_replacement_before_publish_writes_only_detached_root(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        detached = self.root / "detached-target-root"
        original_update_receipt = updater._update_receipt_at
        swapped = False

        def replace_root(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            nonlocal swapped
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "staging_verified" and not swapped:
                swapped = True
                target_root.rename(detached)
                target_root.mkdir(mode=0o700)

        with mock.patch.object(updater, "_update_receipt_at", side_effect=replace_root):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "authorized installation root identity changed",
            ):
                self._apply(plan)

        self.assertFalse((target_root / ".agents" / "skills" / self.skill).exists())
        self.assertEqual(before, self._manifest(detached / ".agents" / "skills" / self.skill))

    def test_target_root_chmod_after_active_move_restores_previous_without_publish(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_update_receipt = updater._update_receipt_at

        def weaken_after_move(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "active_target_moved":
                target_root.chmod(0o777)

        with mock.patch.object(updater, "_update_receipt_at", side_effect=weaken_after_move):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "publishing staging failed",
            ):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertFalse((target.parent / f".{self.skill}.previous").exists())

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

    def test_unapproved_regular_source_file_is_rejected_before_audit(self) -> None:
        self._write(self.source / "not-in-package.txt", "unapproved\n")
        plan = self._plan(self.root / "project")

        with self.assertRaisesRegex(updater.UpdateError, "unapproved files"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())
        self.audit_mock.assert_not_called()

    def test_source_mutation_during_audit_fails_before_target_artifacts(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        def mutate_source() -> None:
            self._write(self.source / "references" / "guide.md", "mutated during audit\n")

        with mock.patch.object(
            updater,
            "run_pre_upgrade_safety_audit",
            side_effect=mutate_source,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "source package after audit manifest mismatch",
            ):
                self._apply(plan)

        self.assertFalse(plan.target.exists())
        self.assertFalse((target_root / updater.RECEIPT_DIRECTORY_NAME).exists())

    def test_source_root_permission_mutation_during_audit_fails_closed(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        def weaken_source_root() -> None:
            self.source.chmod(0o777)

        with mock.patch.object(
            updater,
            "run_pre_upgrade_safety_audit",
            side_effect=weaken_source_root,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "group/world writable"):
                self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_target_ancestor_replacement_after_creation_fails_closed(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        external = self.root / "external"
        external.mkdir()
        original_open_anchor = updater._open_relative_directory_anchor

        def replace_target_parent(
            root_fd: int,
            root_path: Path,
            path: Path,
            label: str,
            *,
            create: bool,
            private: bool = False,
        ):
            anchor = original_open_anchor(
                root_fd,
                root_path,
                path,
                label,
                create=create,
                private=private,
            )
            if label == "target parent":
                shutil.rmtree(path)
                path.symlink_to(external, target_is_directory=True)
            return anchor

        with mock.patch.object(
            updater,
            "_open_relative_directory_anchor",
            side_effect=replace_target_parent,
        ):
            with self.assertRaises(updater.UpdateError):
                self._apply(plan)

        self.assertFalse(external.joinpath(self.skill).exists())

    def test_target_ancestor_replacement_after_anchor_never_writes_external(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        external = self.root / "external"
        external.mkdir()
        original_copy = updater.copy_validated_tree_at

        def replace_after_anchor(
            source: Path,
            parent_fd: int,
            destination_name: str,
            *,
            source_root_fd=None,
        ) -> None:
            shutil.rmtree(plan.target.parent)
            plan.target.parent.symlink_to(external, target_is_directory=True)
            original_copy(source, parent_fd, destination_name)

        with mock.patch.object(
            updater,
            "copy_validated_tree_at",
            side_effect=replace_after_anchor,
        ):
            with self.assertRaises(updater.UpdateError):
                self._apply(plan)

        self.assertFalse(external.joinpath(self.skill).exists())
        self.assertEqual([], list(external.iterdir()))

    def test_target_parent_regular_directory_swap_after_staging_fails_closed(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        detached = self.root / "detached-skills"
        original_update_receipt = updater._update_receipt_at
        swapped = False

        def swap_after_staging(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            nonlocal swapped
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "staging_verified" and not swapped:
                swapped = True
                self._replace_directory_with_empty(plan.target.parent, detached)

        with mock.patch.object(
            updater,
            "_update_receipt_at",
            side_effect=swap_after_staging,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "target parent identity changed"):
                self._apply(plan)

        self.assertEqual([], list(plan.target.parent.iterdir()))
        self.assertFalse(plan.target.exists())
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in detached.iterdir())
        )

    def test_target_parent_swap_after_active_move_restores_only_anchored_tree(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        detached = self.root / "detached-skills"
        original_update_receipt = updater._update_receipt_at
        swapped = False

        def swap_after_active_move(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            nonlocal swapped
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "active_target_moved" and not swapped:
                swapped = True
                self._replace_directory_with_empty(plan.target.parent, detached)

        with mock.patch.object(
            updater,
            "_update_receipt_at",
            side_effect=swap_after_active_move,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "target parent identity changed"):
                self._apply(plan)

        self.assertEqual([], list(plan.target.parent.iterdir()))
        self.assertEqual(before, self._manifest(detached / self.skill))
        self.assertFalse(
            any(path.name.startswith(f".{self.skill}.staging") for path in detached.iterdir())
        )

    def test_receipt_root_regular_directory_swap_never_writes_replacement(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        receipt_root = target_root / updater.RECEIPT_DIRECTORY_NAME
        detached = self.root / "detached-receipts"
        original_update_receipt = updater._update_receipt_at
        swapped = False

        def swap_receipt_root(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            nonlocal swapped
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "staging_verified" and not swapped:
                swapped = True
                self._replace_directory_with_empty(receipt_root, detached)

        with mock.patch.object(
            updater,
            "_update_receipt_at",
            side_effect=swap_receipt_root,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "update receipt directory identity changed",
            ):
                self._apply(plan)

        self.assertEqual([], list(receipt_root.iterdir()))
        receipts = list(detached.glob("*.json"))
        self.assertEqual(1, len(receipts))
        self.assertEqual("failed", json.loads(receipts[0].read_text())["status"])
        self.assertFalse(plan.target.exists())

    def test_receipt_root_replacement_before_each_visible_phase_is_contained(self) -> None:
        phases = (
            "prepared",
            "staging_verified",
            "backup_ready",
            "active_target_moved",
            "staging_published",
            "published_verified",
            "complete",
        )
        for phase in phases:
            with self.subTest(phase=phase):
                target_root = self.root / f"project-{phase}"
                target = target_root / ".agents" / "skills" / self.skill
                self._write(target / "SKILL.md", "old\n")
                before = self._manifest(target)
                plan = self._plan(target_root)
                receipt_root = target_root / updater.RECEIPT_DIRECTORY_NAME
                detached = self.root / f"detached-receipts-{phase}"
                original_update_receipt = updater._update_receipt_at
                swapped = False

                def replace_before_phase(
                    receipt_root_fd,
                    receipt_name,
                    payload,
                    *,
                    phase: str,
                    status="in_progress",
                    error_type=None,
                ):
                    nonlocal swapped
                    if phase == self_phase and not swapped:
                        swapped = True
                        receipt_root.rename(detached)
                        receipt_root.mkdir(mode=0o700)
                    return original_update_receipt(
                        receipt_root_fd,
                        receipt_name,
                        payload,
                        phase=phase,
                        status=status,
                        error_type=error_type,
                    )

                self_phase = phase
                with mock.patch.object(
                    updater,
                    "_update_receipt_at",
                    side_effect=replace_before_phase,
                ):
                    with self.assertRaises(updater.UpdateError):
                        self._apply(plan)

                self.assertEqual([], list(receipt_root.iterdir()))
                receipts = list(detached.glob("*.json"))
                self.assertEqual(1, len(receipts))
                self.assertEqual("failed", json.loads(receipts[0].read_text())["status"])
                self.assertEqual(before, self._manifest(target))

    def test_cleanup_rejects_replaced_transaction_object_without_deleting_external(self) -> None:
        parent = self.root / "cleanup-parent"
        transaction = parent / "staging"
        external = self.root / "cleanup-external"
        parent.mkdir()
        transaction.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        self._write(external / "sentinel.txt", "external sentinel\n")
        detached = self.root / "detached-transaction"
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        original_open_child = updater._open_child_directory_at

        def replace_before_cleanup(parent_arg, name, label):
            if label == "cleanup source":
                transaction.rename(detached)
                transaction.symlink_to(external, target_is_directory=True)
            return original_open_child(parent_arg, name, label)

        try:
            with mock.patch.object(
                updater,
                "_open_child_directory_at",
                side_effect=replace_before_cleanup,
            ):
                with self.assertRaisesRegex(
                    updater.UpdateError,
                    "unexpected|open cleanup source|symbolic link rejected|source",
                ):
                    cleanup = parent / ".cleanup"
                    cleanup.mkdir()
                    cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        updater._remove_owned_directory_at(
                            parent_fd,
                            transaction.name,
                            cleanup_fd=cleanup_fd,
                            cleanup_anchor="cleanup",
                            expected_identity=updater._entry_identity_payload(
                                os.stat(transaction, follow_symlinks=False)
                            ),
                        )
                    finally:
                        os.close(cleanup_fd)
        finally:
            os.close(parent_fd)

        self.assertEqual("external sentinel\n", (external / "sentinel.txt").read_text())
        self.assertTrue(transaction.is_symlink())
        self.assertTrue((detached / "owned.txt").is_file())

    def test_backup_root_regular_directory_swap_never_writes_replacement(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        detached = self.root / "detached-backups"
        original_copy = updater.copy_validated_tree_between_fds
        swapped = False
        copy_calls = 0

        def swap_after_backup_copy(
            source_fd,
            source_name,
            destination_fd,
            destination_name,
            **kwargs,
        ):
            nonlocal swapped
            nonlocal copy_calls
            copy_calls += 1
            original_copy(source_fd, source_name, destination_fd, destination_name, **kwargs)
            if copy_calls >= 2 and not swapped:
                swapped = True
                self._replace_directory_with_empty(plan.backup_root, detached)

        with mock.patch.object(
            updater,
            "copy_validated_tree_between_fds",
            side_effect=swap_after_backup_copy,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "backup root identity changed"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertEqual([], list(plan.backup_root.iterdir()))
        self.assertEqual(1, len(list(detached.iterdir())))

    def test_backup_root_replacement_at_candidate_final_rename_and_cleanup_is_contained(self) -> None:
        for point in ("candidate", "final_rename", "cleanup"):
            with self.subTest(point=point):
                target_root = self.root / f"project-backup-{point}"
                target = target_root / ".agents" / "skills" / self.skill
                self._write(target / "SKILL.md", "old\n")
                before = self._manifest(target)
                plan = self._plan(target_root)
                detached = self.root / f"detached-backup-{point}"
                original_copy = updater.copy_validated_tree_between_fds
                original_rename = updater._rename_child_and_confirm
                original_update_receipt = updater._update_receipt_at
                swapped = False
                copy_calls = 0

                def swap_backup_root() -> None:
                    nonlocal swapped
                    if not swapped:
                        swapped = True
                        self._replace_directory_with_empty(plan.backup_root, detached)

                def copy_hook(
                    source_fd,
                    source_name,
                    destination_fd,
                    destination_name,
                    **kwargs,
                ):
                    nonlocal copy_calls
                    copy_calls += 1
                    result = original_copy(
                        source_fd,
                        source_name,
                        destination_fd,
                        destination_name,
                        **kwargs,
                    )
                    if point == "candidate" and copy_calls >= 2:
                        swap_backup_root()
                    return result

                def rename_hook(parent_fd, source_name, destination_name):
                    result = original_rename(parent_fd, source_name, destination_name)
                    if point == "final_rename" and source_name.startswith(f".{self.skill}.backup-incomplete"):
                        swap_backup_root()
                    return result

                def receipt_hook(
                    receipt_root_fd,
                    receipt_name,
                    payload,
                    *,
                    phase,
                    status="in_progress",
                    error_type=None,
                ):
                    result = original_update_receipt(
                        receipt_root_fd,
                        receipt_name,
                        payload,
                        phase=phase,
                        status=status,
                        error_type=error_type,
                    )
                    if point == "cleanup" and phase == "published_verified":
                        swap_backup_root()
                    return result

                with mock.patch.object(
                    updater,
                    "copy_validated_tree_between_fds",
                    side_effect=copy_hook,
                ), mock.patch.object(
                    updater,
                    "_rename_child_and_confirm",
                    side_effect=rename_hook,
                ), mock.patch.object(
                    updater,
                    "_update_receipt_at",
                    side_effect=receipt_hook,
                ):
                    with self.assertRaises(updater.UpdateError):
                        self._apply(plan)

                self.assertEqual(before, self._manifest(target))
                self.assertEqual([], list(plan.backup_root.iterdir()))
                self.assertGreaterEqual(len(list(detached.iterdir())), 1)

    def test_state_machine_receipt_failure_contract_across_visible_phases(self) -> None:
        phases = (
            "prepared",
            "staging_verified",
            "backup_ready",
            "active_target_moved",
            "staging_published",
            "published_verified",
            "complete",
        )
        for fail_phase in phases:
            with self.subTest(fail_phase=fail_phase):
                target_root = self.root / f"project-receipt-failure-{fail_phase}"
                target = target_root / ".agents" / "skills" / self.skill
                self._write(target / "SKILL.md", "old\n")
                before = self._manifest(target)
                plan = self._plan(target_root)
                original_update_receipt = updater._update_receipt_at

                def fail_receipt(
                    receipt_root_fd,
                    receipt_name,
                    payload,
                    *,
                    phase,
                    status="in_progress",
                    error_type=None,
                ):
                    if phase == self_fail_phase:
                        raise updater.UpdateError(f"injected receipt failure at {phase}")
                    return original_update_receipt(
                        receipt_root_fd,
                        receipt_name,
                        payload,
                        phase=phase,
                        status=status,
                        error_type=error_type,
                    )

                self_fail_phase = fail_phase
                with mock.patch.object(
                    updater,
                    "_update_receipt_at",
                    side_effect=fail_receipt,
                ):
                    with self.assertRaisesRegex(
                        updater.UpdateError,
                        "injected receipt failure|recovery receipt could not record|publishing staging failed|completion receipt failed",
                    ):
                        self._apply(plan, allow_remove_extra_files=True)

                self.assertEqual(before, self._manifest(target))
                if fail_phase == "backup_ready":
                    self.assertEqual(1, len(list(plan.backup_root.iterdir())))
                else:
                    self.assertTrue(
                        not plan.backup_root.exists()
                        or len(list(plan.backup_root.iterdir())) >= 1
                    )
                receipts = list(
                    (target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json")
                )
                if fail_phase != "prepared":
                    self.assertEqual(1, len(receipts))
                    self.assertEqual("failed", json.loads(receipts[0].read_text())["status"])

    def test_package_inventory_mutation_during_audit_fails_closed(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        expected = self._approved_inventory(self.skill)
        changed = expected._replace(inventory_sha256="3" * 64)

        with mock.patch.object(
            updater,
            "load_approved_source_inventory",
            side_effect=[expected, expected, changed],
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "package manifest inventory changed during audit",
            ):
                self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_source_mutation_during_copy_fails_without_replacing_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_copy = updater.copy_validated_tree_at

        def mutate_after_copy(
            source: Path,
            parent_fd: int,
            destination_name: str,
            *,
            source_root_fd=None,
        ) -> None:
            original_copy(source, parent_fd, destination_name)
            if source.resolve() == self.source.resolve():
                self._write(
                    self.source / "references" / "guide.md",
                    "mutated after copy\n",
                )

        with mock.patch.object(
            updater,
            "copy_validated_tree_at",
            side_effect=mutate_after_copy,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "source package after staging copy manifest mismatch",
            ):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))

    def test_second_apply_is_rejected_while_target_lock_is_held(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        with updater.target_update_lock(target_root):
            with self.assertRaisesRegex(updater.UpdateError, "another update"):
                self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_group_world_writable_authorized_root_is_rejected(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir(mode=0o777)
        target_root.chmod(0o777)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "group/world writable"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_group_world_writable_target_ancestor_is_rejected(self) -> None:
        target_root = self.root / "project"
        skills = target_root / ".agents" / "skills"
        skills.mkdir(parents=True)
        (target_root / ".agents").chmod(0o777)
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "group/world writable"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_group_world_writable_source_file_is_rejected(self) -> None:
        source_file = self.source / "references" / "guide.md"
        source_file.chmod(0o666)
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        with self.assertRaisesRegex(updater.UpdateError, "group/world writable"):
            self._apply(plan)

        self.assertFalse(plan.target.exists())

    def test_success_persists_private_complete_recovery_receipt(self) -> None:
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)

        output = self._apply(plan)

        receipt_root = target_root / updater.RECEIPT_DIRECTORY_NAME
        receipts = list(receipt_root.glob("*.json"))
        self.assertEqual(1, len(receipts))
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual("complete", receipt["status"])
        self.assertEqual("complete", receipt["phase"])
        self.assertEqual("manual_only", receipt["recovery_authority"])
        self.assertEqual(
            updater.manifest_sha256(self._manifest(self.source)),
            receipt["source_manifest_sha256"],
        )
        self.assertEqual(0, stat.S_IMODE(receipts[0].stat().st_mode) & 0o077)
        self.assertIn(str(receipts[0]), output)

    def test_keyboard_interrupt_leaves_durable_manual_recovery_receipt(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        plan = self._plan(target_root)
        original_rename = updater._rename_child_at

        def interrupt_publish(parent_fd: int, path: str, destination: str) -> None:
            if (
                path.startswith(f".{self.skill}.staging")
                and destination == self.skill
            ):
                raise KeyboardInterrupt("simulated abrupt stop")
            original_rename(parent_fd, path, destination)

        with mock.patch.object(updater, "_rename_child_at", side_effect=interrupt_publish):
            with self.assertRaisesRegex(KeyboardInterrupt, "simulated abrupt stop"):
                self._apply(plan)

        receipts = list(
            (target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json")
        )
        self.assertEqual(1, len(receipts))
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual("in_progress", receipt["status"])
        self.assertEqual("active_target_moved", receipt["phase"])
        self.assertEqual("manual_only", receipt["recovery_authority"])
        self.assertFalse(target.exists())
        self.assertTrue(Path(receipt["previous"]).is_dir())
        self.assertTrue(Path(receipt["backup"]).is_dir())

    def test_lock_path_inode_replacement_fails_closed_without_unlocking_new_inode(self) -> None:
        target_root = self.root / "project-lock-replacement"
        target_root.mkdir()
        with updater.target_update_lock(target_root) as lock:
            lock_path = target_root / updater.LOCK_FILE_NAME
            detached = self.root / "detached-lock"
            lock_path.rename(detached)
            lock_path.write_text("replacement\n", encoding="utf-8")
            with self.assertRaisesRegex(
                updater.UpdateError,
                "lock pathname identity changed",
            ):
                updater._verify_target_lock(lock)
            self.assertTrue(lock_path.is_file())
            self.assertTrue(detached.is_file())

    def test_quarantine_false_or_unknown_status_stops_recovery(self) -> None:
        for reported_status in (False, "unknown"):
            with self.subTest(reported_status=reported_status):
                target_root = self.root / f"project-quarantine-{reported_status}"
                target = target_root / ".agents" / "skills" / self.skill
                self._write(target / "SKILL.md", "old\n")
                plan = self._plan(target_root)
                original_rename = updater._rename_for_transaction
                original_update = updater._update_receipt_at

                def fake_quarantine(
                    parent_fd,
                    source_name,
                    destination_name,
                    payload,
                    *,
                    parent_anchor=None,
                ):
                    if destination_name.startswith(f".{self.skill}.failed-"):
                        source_identity = updater._entry_identity_payload(
                            updater._entry_lstat_at(parent_fd, source_name)
                        )
                        status = updater.RenameStatus(
                            operation="target_to_quarantine",
                            source_name=source_name,
                            destination_name=destination_name,
                            rename_committed=reported_status,
                            source_identity_before=source_identity,
                            destination_identity_before=None,
                            source_identity_after=source_identity,
                            destination_identity_after=None,
                            fsync_status="unknown" if reported_status == "unknown" else "not_attempted",
                            error_type="injected_quarantine_status",
                            error_message="injected quarantine status",
                        )
                        updater._record_rename_status(
                            payload,
                            status,
                            parent_anchor=parent_anchor,
                        )
                        return status
                    return original_rename(
                        parent_fd,
                        source_name,
                        destination_name,
                        payload,
                        parent_anchor=parent_anchor,
                    )

                def fail_published_receipt(
                    receipt_root_fd,
                    receipt_name,
                    payload,
                    *,
                    phase,
                    status="in_progress",
                    error_type=None,
                ):
                    if phase == "published_verified":
                        raise updater.UpdateError("injected published receipt failure")
                    return original_update(
                        receipt_root_fd,
                        receipt_name,
                        payload,
                        phase=phase,
                        status=status,
                        error_type=error_type,
                    )

                with mock.patch.object(
                    updater,
                    "_rename_for_transaction",
                    side_effect=fake_quarantine,
                ), mock.patch.object(
                    updater,
                    "_update_receipt_at",
                    side_effect=fail_published_receipt,
                ):
                    with self.assertRaisesRegex(
                        updater.UpdateError,
                        "active target could not be quarantined",
                    ):
                        self._apply(plan)

                self.assertTrue(target.exists())
    def test_receipt_failure_after_active_target_move_restores_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        self._write(target / "old-local.txt", "old local\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_update_receipt = updater._update_receipt_at

        def fail_moved_receipt(
            receipt_root_fd: int,
            receipt_name: str,
            payload: dict[str, object],
            *,
            phase: str,
            status: str = "in_progress",
            error_type=None,
        ) -> None:
            if phase == "active_target_moved":
                raise updater.UpdateError("injected receipt persistence failure")
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )

        with mock.patch.object(
            updater,
            "_update_receipt_at",
            side_effect=fail_moved_receipt,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "recovery receipt could not record the moved active target",
            ):
                self._apply(plan, allow_remove_extra_files=True)

        self.assertEqual(before, self._manifest(target))
        backups = list(plan.backup_root.iterdir())
        self.assertEqual(1, len(backups))
        self.assertEqual(before, self._manifest(backups[0]))

    def test_receipt_failure_after_staging_publish_restores_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_update_receipt = updater._update_receipt_at

        def fail_published_receipt(
            receipt_root_fd,
            receipt_name,
            payload,
            *,
            phase,
            status="in_progress",
            error_type=None,
        ):
            if phase == "staging_published":
                raise updater.UpdateError("injected published receipt failure")
            original_update_receipt(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )

        with mock.patch.object(updater, "_update_receipt_at", side_effect=fail_published_receipt):
            with self.assertRaisesRegex(updater.UpdateError, "publishing staging failed"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        quarantines = [p for p in target.parent.iterdir() if p.name.startswith(f".{self.skill}.failed")]
        self.assertEqual(1, len(quarantines))

    def test_target_mutation_during_move_is_detected_and_active_path_restored(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_rename = updater._rename_child_at

        def mutate_moved_target(parent_fd: int, path: str, destination: str) -> None:
            original_rename(parent_fd, path, destination)
            if destination.startswith(f".{self.skill}.previous"):
                self._write(
                    target.parent / destination / "SKILL.md",
                    "changed during move\n",
                )

        with mock.patch.object(updater, "_rename_child_at", side_effect=mutate_moved_target):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "target identity changed during move",
            ):
                self._apply(plan)

        self.assertTrue(target.is_dir())
        self.assertEqual(before, self._manifest(target))
        quarantines = [
            path
            for path in target.parent.iterdir()
            if path.name.startswith(f".{self.skill}.failed")
        ]
        self.assertEqual(1, len(quarantines))
        self.assertEqual("changed during move\n", (quarantines[0] / "SKILL.md").read_text())

    def test_post_rename_error_during_active_move_restores_target(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_rename = updater._rename_child_at

        def fail_after_active_move(parent_fd: int, source: str, destination: str) -> None:
            original_rename(parent_fd, source, destination)
            if destination.startswith(f".{self.skill}.previous"):
                raise updater.UpdateError("injected post-rename durability failure")

        with mock.patch.object(
            updater,
            "_rename_child_at",
            side_effect=fail_after_active_move,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "active target move completed",
            ):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        self.assertEqual(1, len(list(plan.backup_root.iterdir())))

    def test_post_rename_error_during_publish_quarantines_and_restores(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        before = self._manifest(target)
        plan = self._plan(target_root)
        original_rename = updater._rename_child_at

        def fail_after_publish(parent_fd: int, source: str, destination: str) -> None:
            original_rename(parent_fd, source, destination)
            if source.startswith(f".{self.skill}.staging") and destination == self.skill:
                raise updater.UpdateError("injected post-publish durability failure")

        with mock.patch.object(
            updater,
            "_rename_child_at",
            side_effect=fail_after_publish,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "publishing staging failed"):
                self._apply(plan)

        self.assertEqual(before, self._manifest(target))
        quarantines = [
            path
            for path in target.parent.iterdir()
            if path.name.startswith(f".{self.skill}.failed")
        ]
        self.assertEqual(1, len(quarantines))
        self.assertEqual(self._manifest(self.source), self._manifest(quarantines[0]))

    def test_output_never_contains_file_contents_on_failure(self) -> None:
        secret_marker = "CUSTOMER-SECRET-CONTENT"
        self._write(self.source / "secret.txt", secret_marker)
        self.approved_files.add("secret.txt")
        target_root = self.root / "project"
        target_root.mkdir()
        plan = self._plan(target_root)
        output = io.StringIO()

        with mock.patch.object(
            updater,
            "copy_validated_tree_at",
            side_effect=updater.UpdateError("controlled copy failure"),
        ):
            with redirect_stdout(output):
                with self.assertRaisesRegex(updater.UpdateError, "controlled copy failure"):
                    updater.update_skill(plan, self.skill, apply=True)

        self.assertNotIn(secret_marker, output.getvalue())

    def test_rename_status_distinguishes_not_committed_and_post_rename_failure(self) -> None:
        parent = self.root / "rename-parent"
        parent.mkdir()
        source = parent / ".long-horizon-engineering.staging-test"
        source.mkdir()
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, fd)
        original = updater._rename_child_at

        with mock.patch.object(
            updater,
            "_rename_child_at",
            side_effect=updater.UpdateError("rename did not start"),
        ):
            not_committed = updater._rename_child_and_confirm(
                fd, source.name, self.skill
            )
        self.assertEqual("staging_to_target", not_committed.operation)
        self.assertFalse(not_committed.rename_committed)
        self.assertEqual("not_attempted", not_committed.fsync_status)
        self.assertIsNotNone(not_committed.source_identity_before)
        self.assertIsNone(not_committed.destination_identity_after)

        def rename_then_fail(parent_fd: int, source_name: str, destination_name: str) -> None:
            original(parent_fd, source_name, destination_name)
            raise updater.UpdateError("fsync failed after visible rename")

        with mock.patch.object(updater, "_rename_child_at", side_effect=rename_then_fail):
            post_rename = updater._rename_child_and_confirm(
                fd, source.name, self.skill
            )
        self.assertTrue(post_rename.rename_committed)
        self.assertEqual("failed", post_rename.fsync_status)
        self.assertIsNone(post_rename.source_identity_after)
        self.assertEqual(
            post_rename.source_identity_before,
            post_rename.destination_identity_after,
        )

    def test_no_replace_rename_rejects_destination_inserted_after_preflight(self) -> None:
        parent = self.root / "rename-race-parent"
        parent.mkdir()
        source = parent / ".long-horizon-engineering.staging-race"
        source.mkdir()
        destination = parent / self.skill
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, fd)
        original_lstat = updater._entry_lstat_at
        inserted = False

        def insert_after_destination_preflight(parent_fd: int, name: str):
            nonlocal inserted
            result = original_lstat(parent_fd, name)
            if name == destination.name and not inserted:
                inserted = True
                destination.mkdir()
                (destination / "attacker.txt").write_text("must survive\n")
            return result

        with mock.patch.object(
            updater,
            "_entry_lstat_at",
            side_effect=insert_after_destination_preflight,
        ):
            status = updater._rename_child_and_confirm(
                fd,
                source.name,
                destination.name,
            )

        self.assertTrue(inserted)
        self.assertIn(status.rename_committed, (False, "unknown"))
        self.assertTrue(source.is_dir())
        self.assertEqual("must survive\n", (destination / "attacker.txt").read_text())

    def test_cleanup_claim_rejects_object_replaced_before_atomic_claim(self) -> None:
        parent = self.root / "cleanup-claim-parent"
        transaction = parent / "staging"
        detached = self.root / "detached-cleanup-object"
        external = self.root / "cleanup-claim-external"
        parent.mkdir()
        transaction.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        self._write(external / "sentinel.txt", "external sentinel\n")
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, parent_fd)
        original_claim = updater._rename_no_replace_between_fds
        swapped = False

        def replace_before_claim(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal swapped
            if source_name == transaction.name and not swapped:
                swapped = True
                transaction.rename(detached)
                transaction.mkdir()
                self._write(transaction / "replacement.txt", "replacement\n")
            return original_claim(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )

        with mock.patch.object(
            updater,
            "_rename_no_replace_between_fds",
            side_effect=replace_before_claim,
        ):
            with self.assertRaisesRegex(
                updater.UpdateError,
                "identity changed after atomic move",
            ):
                cleanup = parent / ".cleanup"
                cleanup.mkdir()
                cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    updater._remove_owned_directory_at(
                        parent_fd,
                        transaction.name,
                        cleanup_fd=cleanup_fd,
                        cleanup_anchor="cleanup",
                        expected_identity=updater._entry_identity_payload(
                            os.stat(transaction, follow_symlinks=False)
                        ),
                    )
                finally:
                    os.close(cleanup_fd)

        self.assertTrue(swapped)
        self.assertEqual("owned\n", (detached / "owned.txt").read_text())
        self.assertEqual("external sentinel\n", (external / "sentinel.txt").read_text())
        cleanup_claims = list((parent / ".cleanup").iterdir())
        self.assertEqual(1, len(cleanup_claims))
        self.assertEqual("replacement\n", (cleanup_claims[0] / "replacement.txt").read_text())

    def test_cleanup_never_final_deletes_transaction_object(self) -> None:
        parent = self.root / "cleanup-native-parent"
        transaction = parent / "staging"
        parent.mkdir()
        transaction.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, parent_fd)

        with mock.patch.object(
            updater.os, "unlink", side_effect=AssertionError("path unlink used")
        ):
            with mock.patch.object(
                updater.os, "rmdir", side_effect=AssertionError("path rmdir used")
            ):
                cleanup = parent / ".cleanup"
                cleanup.mkdir()
                cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    updater._remove_owned_directory_at(
                        parent_fd,
                        transaction.name,
                        cleanup_fd=cleanup_fd,
                        cleanup_anchor="cleanup",
                        expected_identity=updater._entry_identity_payload(
                            os.stat(transaction, follow_symlinks=False)
                        ),
                    )
                finally:
                    os.close(cleanup_fd)

        self.assertFalse(transaction.exists())

    def test_cleanup_destination_competition_fails_closed_and_retains_source(self) -> None:
        parent = self.root / "cleanup-destination-competition"
        transaction = parent / "staging"
        cleanup = parent / ".cleanup"
        parent.mkdir()
        transaction.mkdir()
        cleanup.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, parent_fd)
        self.addCleanup(os.close, cleanup_fd)
        original_uuid = updater.uuid.uuid4
        generated = iter([mock.Mock(hex="claim")])

        def competing_uuid():
            value = next(generated)
            (cleanup / ".staging.cleanup.claim").mkdir()
            return value

        with mock.patch.object(updater.uuid, "uuid4", side_effect=competing_uuid):
            with self.assertRaisesRegex(updater.UpdateError, "without replacement|destination"):
                updater._remove_owned_directory_at(
                    parent_fd,
                    transaction.name,
                    cleanup_fd=cleanup_fd,
                    cleanup_anchor="cleanup",
                    expected_identity=updater._entry_identity_payload(
                        os.stat(transaction, follow_symlinks=False)
                    ),
                )
        self.assertEqual("owned\n", (transaction / "owned.txt").read_text())
        self.assertTrue((cleanup / ".staging.cleanup.claim").is_dir())

    def test_cleanup_post_rename_error_retains_private_claim(self) -> None:
        parent = self.root / "cleanup-post-rename-error"
        transaction = parent / "staging"
        cleanup = parent / ".cleanup"
        parent.mkdir()
        transaction.mkdir()
        cleanup.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, parent_fd)
        self.addCleanup(os.close, cleanup_fd)
        original_claim = updater._rename_no_replace_between_fds

        def rename_then_fail(source_fd, source_name, destination_fd, destination_name):
            original_claim(source_fd, source_name, destination_fd, destination_name)
            raise updater.UpdateError("injected post-rename claim error")

        with mock.patch.object(
            updater,
            "_rename_no_replace_between_fds",
            side_effect=rename_then_fail,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "claim"):
                updater._remove_owned_directory_at(
                    parent_fd,
                    transaction.name,
                    cleanup_fd=cleanup_fd,
                    cleanup_anchor="cleanup",
                    expected_identity=updater._entry_identity_payload(
                        os.stat(transaction, follow_symlinks=False)
                    ),
                )
        self.assertFalse(transaction.exists())
        claimed = list(cleanup.iterdir())
        self.assertEqual(1, len(claimed))
        self.assertEqual("owned\n", (claimed[0] / "owned.txt").read_text())

    def test_cleanup_final_identity_replacement_is_retained_not_deleted(self) -> None:
        parent = self.root / "cleanup-final-replacement"
        transaction = parent / "staging"
        cleanup = parent / ".cleanup"
        external = self.root / "cleanup-final-external"
        parent.mkdir()
        transaction.mkdir()
        cleanup.mkdir()
        external.mkdir()
        self._write(transaction / "owned.txt", "owned\n")
        self._write(external / "sentinel.txt", "external\n")
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        cleanup_fd = os.open(cleanup, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, parent_fd)
        self.addCleanup(os.close, cleanup_fd)
        original_open = updater._open_cleanup_entry_fd
        swapped = False

        def replace_after_claim(parent_arg, name, expected):
            nonlocal swapped
            if not swapped:
                claimed = cleanup / name
                detached = self.root / "detached-final-claim"
                claimed.rename(detached)
                claimed.symlink_to(external, target_is_directory=True)
                swapped = True
            return original_open(parent_arg, name, expected)

        with mock.patch.object(
            updater,
            "_open_cleanup_entry_fd",
            side_effect=replace_after_claim,
        ):
            with self.assertRaisesRegex(updater.UpdateError, "identity|claim"):
                updater._remove_owned_directory_at(
                    parent_fd,
                    transaction.name,
                    cleanup_fd=cleanup_fd,
                    cleanup_anchor="cleanup",
                    expected_identity=updater._entry_identity_payload(
                        os.stat(transaction, follow_symlinks=False)
                    ),
                )
        self.assertTrue(swapped)
        self.assertEqual("external\n", (external / "sentinel.txt").read_text())
        self.assertTrue((self.root / "detached-final-claim").is_dir())
        self.assertTrue((cleanup / next(iter(cleanup.iterdir())).name).is_symlink())

    def test_success_receipt_binds_all_anchors_objects_and_visible_renames(self) -> None:
        target_root = self.root / "project"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        output = self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("complete", receipt["status"])
        self.assertEqual(
            {"authorized_root", "target_parent", "backup_root", "receipt_root", "cleanup_root"},
            set(receipt["directory_anchors"]),
        )
        self.assertTrue(receipt["cleanup_claims"])
        for claim in receipt["cleanup_claims"]:
            self.assertIn("original_parent_anchor", claim)
            self.assertIn("original_name", claim)
            self.assertIn("expected_identity", claim)
            self.assertIn("claimed_cleanup_anchor", claim)
            self.assertIn("claimed_cleanup_name", claim)
            self.assertIn("claim_outcome", claim)
            self.assertIn("delete_outcome", claim)
            self.assertNotEqual("deleted", claim["delete_outcome"])
            if claim["claim_outcome"] == "claimed_and_retained":
                self.assertEqual("retained_by_security_policy", claim["delete_outcome"])
        for outcome in receipt["cleanup_outcomes"]:
            self.assertIn("claimed_cleanup_anchor", outcome)
            self.assertIn("claim_outcome", outcome)
            self.assertIn("delete_outcome", outcome)
            self.assertNotEqual("deleted", outcome["delete_outcome"])
        for anchor in receipt["directory_anchors"].values():
            self.assertIn("display_path", anchor)
            self.assertIn("st_dev", anchor)
            self.assertIn("st_ino", anchor)
            self.assertIn("uid", anchor)
            self.assertIn("mode", anchor)
            self.assertIn("verified_at_phase", anchor)
        self.assertEqual(
            {"target", "previous", "staging", "backup", "quarantine"},
            set(receipt["objects"]),
        )
        for record in receipt["objects"].values():
            self.assertIn("display_name", record)
            self.assertIn("parent_anchor", record)
            self.assertIn("expected_identity", record)
            self.assertIn("current_identity_or_null", record)
        operations = {entry["operation"] for entry in receipt["rename_operations"]}
        self.assertIn("target_to_previous", operations)
        self.assertIn("staging_to_target", operations)
        self.assertIn("backup_candidate_to_backup", operations)
        self.assertIn(str(receipt_path), output)

    def test_post_rename_failure_receipt_records_state_and_verified_restore(self) -> None:
        target_root = self.root / "project-post-rename"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        original_manifest_sha = updater.manifest_sha256(self._manifest(target))
        original = updater._rename_child_at

        def fail_after_move(parent_fd: int, source_name: str, destination_name: str) -> None:
            original(parent_fd, source_name, destination_name)
            if ".previous-" in destination_name:
                raise updater.UpdateError("injected post-rename failure")

        with mock.patch.object(updater, "_rename_child_at", side_effect=fail_after_move):
            with self.assertRaises(updater.UpdateError):
                self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        move = next(
            item for item in receipt["rename_operations"]
            if item["operation"] == "target_to_previous"
        )
        self.assertTrue(move["rename_committed"])
        self.assertEqual("failed", move["fsync_status"])
        self.assertEqual("restored_verified", receipt["restore_status"])
        self.assertIsNotNone(receipt["restored_target_identity"])
        self.assertEqual(
            original_manifest_sha,
            receipt["restored_manifest_sha256"],
        )

    def test_previous_cleanup_failure_is_structured_and_not_silent(self) -> None:
        target_root = self.root / "project-previous-cleanup"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        original_remove = updater._remove_owned_directory_at

        def fail_previous(parent_fd: int, name: str, **kwargs) -> None:
            if ".previous-" in name:
                raise updater.UpdateError("injected previous cleanup failure")
            return original_remove(parent_fd, name, **kwargs)

        with mock.patch.object(updater, "_remove_owned_directory_at", side_effect=fail_previous):
            with self.assertRaisesRegex(updater.UpdateError, "previous cleanup failed"):
                self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", receipt["status"])
        self.assertEqual("cleanup_failed", receipt["phase"])
        outcome = next(item for item in receipt["cleanup_outcomes"] if item["object_kind"] == "previous")
        self.assertTrue(outcome["attempted"])
        self.assertFalse(outcome["completed"])
        self.assertEqual("UpdateError", outcome["failure_type"])
        self.assertIsNotNone(outcome["object_identity"])

    def test_staging_cleanup_failure_is_structured_and_retained(self) -> None:
        target_root = self.root / "project-staging-cleanup"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        original_update = updater._update_receipt_at
        original_remove = updater._remove_owned_directory_at

        def fail_staging_receipt(
            receipt_root_fd: int,
            receipt_name: str,
            payload: dict[str, object],
            *,
            phase: str,
            status: str = "in_progress",
            error_type=None,
        ) -> None:
            if phase == "staging_verified":
                raise updater.UpdateError("injected staging phase failure")
            original_update(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )

        def fail_staging_cleanup(parent_fd: int, name: str, **kwargs) -> None:
            if ".staging-" in name:
                raise updater.UpdateError("injected staging cleanup failure")
            return original_remove(parent_fd, name, **kwargs)

        with mock.patch.object(updater, "_update_receipt_at", side_effect=fail_staging_receipt), \
            mock.patch.object(updater, "_remove_owned_directory_at", side_effect=fail_staging_cleanup):
            with self.assertRaises(updater.UpdateError):
                self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", receipt["status"])
        outcome = next(item for item in receipt["cleanup_outcomes"] if item["object_kind"] == "staging")
        self.assertFalse(outcome["completed"])
        self.assertTrue(any(path.name.startswith(f".{self.skill}.staging-") for path in target.parent.iterdir()))

    def test_backup_candidate_cleanup_failure_is_structured_and_retained(self) -> None:
        target_root = self.root / "project-backup-cleanup"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        original_rename = updater._rename_child_at
        original_remove = updater._remove_owned_directory_at

        def fail_backup_finalize(parent_fd: int, source_name: str, destination_name: str) -> None:
            if ".backup-incomplete-" in source_name:
                raise updater.UpdateError("injected backup finalization failure")
            original_rename(parent_fd, source_name, destination_name)

        def fail_backup_cleanup(parent_fd: int, name: str, **kwargs) -> None:
            if ".backup-incomplete-" in name:
                raise updater.UpdateError("injected backup cleanup failure")
            return original_remove(parent_fd, name, **kwargs)

        with mock.patch.object(updater, "_rename_child_at", side_effect=fail_backup_finalize), \
            mock.patch.object(updater, "_remove_owned_directory_at", side_effect=fail_backup_cleanup):
            with self.assertRaises(updater.UpdateError):
                self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", receipt["status"])
        outcome = next(item for item in receipt["cleanup_outcomes"] if item["object_kind"] == "backup_candidate")
        self.assertFalse(outcome["completed"])
        self.assertTrue(any(path.name.startswith(f".{self.skill}.backup-incomplete-") for path in (target_root / ".codex-skill-backups").iterdir()))

    def test_complete_receipt_failure_is_failed_manual_only(self) -> None:
        target_root = self.root / "project-complete-receipt"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        original_update = updater._update_receipt_at

        def fail_complete(
            receipt_root_fd: int,
            receipt_name: str,
            payload: dict[str, object],
            *,
            phase: str,
            status: str = "in_progress",
            error_type=None,
        ) -> None:
            if phase == "complete":
                raise updater.UpdateError("injected complete receipt fsync failure")
            original_update(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )

        with mock.patch.object(updater, "_update_receipt_at", side_effect=fail_complete):
            with self.assertRaises(updater.UpdateError):
                self._apply(self._plan(target_root))
        receipt_path = next((target_root / updater.RECEIPT_DIRECTORY_NAME).glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", receipt["status"])
        self.assertEqual("complete_receipt_unpersisted", receipt["phase"])
        self.assertEqual("manual_only", receipt["recovery_authority"])

    def test_display_anchor_replacement_is_stale_and_writes_only_through_old_fd(self) -> None:
        target_root = self.root / "project-anchor-replacement"
        target = target_root / ".agents" / "skills" / self.skill
        self._write(target / "SKILL.md", "old\n")
        detached = self.root / "detached-receipts"
        original_update = updater._update_receipt_at
        swapped = False

        def replace_receipt_root(
            receipt_root_fd: int,
            receipt_name: str,
            payload: dict[str, object],
            *,
            phase: str,
            status: str = "in_progress",
            error_type=None,
        ) -> None:
            nonlocal swapped
            result = original_update(
                receipt_root_fd,
                receipt_name,
                payload,
                phase=phase,
                status=status,
                error_type=error_type,
            )
            if phase == "staging_verified" and not swapped:
                swapped = True
                self._replace_directory_with_empty(target_root / updater.RECEIPT_DIRECTORY_NAME, detached)
            return result

        with mock.patch.object(updater, "_update_receipt_at", side_effect=replace_receipt_root):
            with self.assertRaises(updater.UpdateError):
                self._apply(self._plan(target_root))
        self.assertEqual([], list((target_root / updater.RECEIPT_DIRECTORY_NAME).iterdir()))
        receipt_path = next(detached.glob("*.json"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        anchor = receipt["directory_anchors"]["receipt_root"]
        self.assertEqual("STALE_OR_REPLACED", anchor["display_path_identity"])
        self.assertTrue(anchor["recovery_requires_fd_identity"])


class PackageManifestSourceInventoryTests(unittest.TestCase):
    def test_manifest_closes_each_updatable_source_tree_exactly(self) -> None:
        for skill in updater.ALLOWED_SKILLS:
            with self.subTest(skill=skill):
                inventory = updater.load_approved_source_inventory(skill)
                source = updater.source_skill_path(skill)
                manifest = updater.build_tree_manifest(source, f"{skill} source")
                updater.verify_approved_source_inventory(
                    manifest,
                    inventory,
                    f"{skill} source",
                )


if __name__ == "__main__":
    unittest.main()
