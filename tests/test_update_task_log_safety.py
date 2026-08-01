"""Black-box safety checks for the task-log helper's write boundary."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "update_task_log.py"


class UpdateTaskLogSafetyTests(unittest.TestCase):
    def invoke(self, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--title",
                "Synthetic task",
                "--summary",
                "Synthetic summary",
                "--project-root",
                str(project),
                "--target-file",
                "docs/TASK_LOG.md",
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_is_preview_and_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            project = Path(temp_name) / "project"
            project.mkdir()
            result = self.invoke(project)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Preview only", result.stdout)
            self.assertFalse((project / "docs").exists())

    def test_apply_requires_typed_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            project = Path(temp_name) / "project"
            project.mkdir()
            result = self.invoke(project, "--apply")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((project / "docs").exists())

    def test_apply_creates_only_explicit_project_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            project = Path(temp_name) / "project"
            project.mkdir()
            result = self.invoke(project, "--apply", "--confirm", "WRITE_TASK_LOG")
            target = project / "docs" / "TASK_LOG.md"
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(target.is_file())
            self.assertIn("Synthetic task", target.read_text(encoding="utf-8"))

    def test_rejects_escape_control_paths_and_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            project = temp / "project"
            project.mkdir()
            outside = temp / "outside.md"
            outside.write_text("unchanged", encoding="utf-8")
            docs = project / "docs"
            docs.mkdir()
            (docs / "TASK_LOG.md").symlink_to(outside)

            result = self.invoke(project, "--apply", "--confirm", "WRITE_TASK_LOG")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("unchanged", outside.read_text(encoding="utf-8"))

            for target in ("../outside.md", ".agents/TASK_LOG.md", ".git/TASK_LOG.md"):
                command = [
                    sys.executable, str(SCRIPT), "--title", "Synthetic task", "--summary", "Synthetic summary",
                    "--project-root", str(project), "--target-file", target,
                ]
                rejected = subprocess.run(command, text=True, capture_output=True, check=False)
                self.assertNotEqual(0, rejected.returncode, target)

    def test_rejects_symlinked_docs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            project = temp / "project"
            outside = temp / "outside-docs"
            project.mkdir()
            outside.mkdir()
            (project / "docs").symlink_to(outside, target_is_directory=True)

            result = self.invoke(project, "--apply", "--confirm", "WRITE_TASK_LOG")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((outside / "TASK_LOG.md").exists())

    def test_rejects_symlinked_docs_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            project = temp / "project"
            outside = temp / "outside-subdir"
            docs = project / "docs"
            project.mkdir()
            docs.mkdir()
            outside.mkdir()
            (docs / "subdir").symlink_to(outside, target_is_directory=True)
            command = [
                sys.executable,
                str(SCRIPT),
                "--title", "Synthetic task",
                "--summary", "Synthetic summary",
                "--project-root", str(project),
                "--target-file", "docs/subdir/TASK_LOG.md",
                "--apply", "--confirm", "WRITE_TASK_LOG",
            ]
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((outside / "TASK_LOG.md").exists())


if __name__ == "__main__":
    unittest.main()
