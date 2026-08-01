import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/long-horizon-engineering/scripts/append_project_memory.py"


class AppendProjectMemoryTests(unittest.TestCase):
    def run_script(self, project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_is_preview_only_and_creates_no_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory) / "project"
            project_root.mkdir()
            result = self.run_script(
                project_root,
                "--project-root",
                str(project_root),
                "--target-file",
                "docs/PROJECT_MEMORY.md",
                "A durable non-sensitive fact.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Preview only", result.stdout)
            self.assertFalse((project_root / "docs").exists())

    def test_apply_requires_explicit_confirmation_and_creates_no_files_without_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory) / "project"
            project_root.mkdir()
            result = self.run_script(
                project_root,
                "--apply",
                "--project-root",
                str(project_root),
                "--target-file",
                "docs/PROJECT_MEMORY.md",
                "A durable non-sensitive fact.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--confirm", result.stderr)
            self.assertFalse((project_root / "docs").exists())

    def test_apply_writes_only_to_explicit_target_below_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory) / "project"
            project_root.mkdir()
            result = self.run_script(
                project_root,
                "--apply",
                "--confirm",
                "--project-root",
                str(project_root),
                "--target-file",
                "docs/PROJECT_MEMORY.md",
                "A durable non-sensitive fact.",
            )

            memory_file = project_root / "docs/PROJECT_MEMORY.md"
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(memory_file.is_file())
            self.assertIn("A durable non-sensitive fact.", memory_file.read_text(encoding="utf-8"))

    def test_rejects_target_outside_project_root_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project_root = base / "project"
            outside = base / "outside.md"
            project_root.mkdir()
            result = self.run_script(
                project_root,
                "--apply",
                "--confirm",
                "--project-root",
                str(project_root),
                "--target-file",
                "../outside.md",
                "A durable non-sensitive fact.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("inside --project-root", result.stderr)
            self.assertFalse(outside.exists())

    def test_rejects_symlink_escape_without_creating_the_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project_root = base / "project"
            outside = base / "outside"
            project_root.mkdir()
            outside.mkdir()
            (project_root / "docs").symlink_to(outside, target_is_directory=True)
            result = self.run_script(
                project_root,
                "--apply",
                "--confirm",
                "--project-root",
                str(project_root),
                "--target-file",
                "docs/PROJECT_MEMORY.md",
                "A durable non-sensitive fact.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("inside --project-root", result.stderr)
            self.assertFalse((outside / "PROJECT_MEMORY.md").exists())

    def test_rejects_sensitive_input_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory) / "project"
            project_root.mkdir()
            result = self.run_script(
                project_root,
                "--apply",
                "--confirm",
                "--project-root",
                str(project_root),
                "--target-file",
                "docs/PROJECT_MEMORY.md",
                "api_key=example-not-a-real-secret",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sensitive", result.stderr.lower())
            self.assertFalse((project_root / "docs").exists())
