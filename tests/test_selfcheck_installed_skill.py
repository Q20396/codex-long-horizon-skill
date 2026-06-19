from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "selfcheck_installed_skill.py"


def load_selfcheck_module():
    spec = importlib.util.spec_from_file_location("selfcheck_installed_skill_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SELF = load_selfcheck_module()


def write_file(root: Path, relative: str, content: str, executable: bool = False) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def snapshot_tree(root: Path) -> dict[str, tuple[str, str, str, int]]:
    snapshot: dict[str, tuple[str, str, str, int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        st = path.lstat()
        mode = oct(stat.S_IMODE(st.st_mode))
        mtime = st.st_mtime_ns
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path), mode, mtime)
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[relative] = ("file", digest, mode, mtime)
        elif path.is_dir():
            snapshot[relative] = ("dir", "", mode, mtime)
        else:
            snapshot[relative] = ("special", "", mode, mtime)
    return snapshot


class SelfCheckInstalledSkillTests(unittest.TestCase):
    def test_help_succeeds_and_exposes_no_mutation_options(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for forbidden in ("--apply", "--update", "--delete", "--fix", "--install", "--sync", "--write"):
            self.assertIsNone(
                re.search(rf"(^|\s){re.escape(forbidden)}(\s|$)", result.stdout),
                f"{forbidden} must not be exposed as a standalone option.",
            )

    def test_unknown_mutation_options_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            for option in ("--apply", "--update", "--delete"):
                result = run_cli(
                    "--installed-dir",
                    str(installed),
                    "--reference-dir",
                    str(reference),
                    option,
                )
                self.assertEqual(result.returncode, 2)

    def test_identical_local_packages_return_zero_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            write_file(installed, "SKILL.md", "name: demo\n")
            write_file(reference, "SKILL.md", "name: demo\n")

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["total_differences"], 0)
            self.assertEqual(payload["comparison_mode"], "local")
            self.assertIn("No files were modified.", payload["statements"])
            self.assertIn("No update was applied.", payload["statements"])
            self.assertNotIn(str(installed), result.stdout)
            self.assertNotIn(str(reference), result.stdout)

    def test_changed_missing_and_unexpected_entries_are_reported_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            write_file(installed, "SKILL.md", "installed\n")
            write_file(reference, "SKILL.md", "reference\n")
            unexpected = write_file(installed, "local-only.md", "keep me\n")
            write_file(reference, "missing.md", "expected\n")

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["changed_entries"], 1)
            self.assertEqual(payload["summary"]["missing_entries"], 1)
            self.assertEqual(payload["summary"]["unexpected_entries"], 1)
            self.assertTrue(unexpected.exists(), "Unexpected entries must be reported, not deleted.")

    def test_type_mode_and_symlink_target_changes_are_reported(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks are not supported on this platform.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            write_file(installed, "kind-change", "file\n")
            os.symlink("target", reference / "kind-change")
            write_file(installed, "script.py", "print('x')\n", executable=False)
            write_file(reference, "script.py", "print('x')\n", executable=True)
            os.symlink("old-target", installed / "link")
            os.symlink("new-target", reference / "link")

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["type_changes"], 1)
            self.assertEqual(payload["summary"]["mode_or_executable_changes"], 1)
            self.assertEqual(payload["summary"]["symlink_changes"], 1)

    def test_symlinked_directory_is_not_traversed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks are not supported on this platform.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            outside = root / "outside"
            installed.mkdir()
            reference.mkdir()
            outside.mkdir()
            write_file(outside, "secret.txt", "do not read\n")
            os.symlink(outside, installed / "linked-dir")

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("linked-dir", result.stdout)
            self.assertNotIn("secret.txt", result.stdout)
            self.assertNotIn(str(outside), result.stdout)

    def test_top_level_symlink_roots_are_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks are not supported on this platform.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            real_installed = root / "real-installed"
            reference = root / "reference"
            installed_link = root / "installed-link"
            real_installed.mkdir()
            reference.mkdir()
            os.symlink(real_installed, installed_link)

            result = run_cli(
                "--installed-dir",
                str(installed_link),
                "--reference-dir",
                str(reference),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("must not be a symlink", result.stderr)

    def test_unsupported_special_file_is_reported_when_supported(self) -> None:
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is not supported on this platform.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            os.mkfifo(installed / "named-pipe")

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["unsupported_entries"], 1)
            self.assertEqual(payload["unsupported_entries"][0]["risk_level"], "REVIEW_REQUIRED")

    def test_local_comparison_preserves_files_modes_symlinks_and_mtimes(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks are not supported on this platform.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            installed.mkdir()
            reference.mkdir()
            write_file(installed, "SKILL.md", "installed\n")
            write_file(reference, "SKILL.md", "reference\n")
            os.symlink("SKILL.md", installed / "skill-link")
            os.symlink("SKILL.md", reference / "skill-link")
            before_installed = snapshot_tree(installed)
            before_reference = snapshot_tree(reference)

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(before_installed, snapshot_tree(installed))
            self.assertEqual(before_reference, snapshot_tree(reference))
            self.assertIn("No files were modified.", result.stdout)
            self.assertIn("No update was applied.", result.stdout)

    def test_reference_code_and_install_scripts_are_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            installed = root / "installed"
            reference = root / "reference"
            sentinel = root / "executed"
            installed.mkdir()
            reference.mkdir()
            payload = textwrap.dedent(
                f"""
                from pathlib import Path
                Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')
                """
            )
            write_file(installed, "scripts/install.sh", "touch should-not-run\n", executable=True)
            write_file(reference, "scripts/install.sh", "touch should-not-run\n", executable=True)
            write_file(installed, "scripts/tool.py", payload)
            write_file(reference, "scripts/tool.py", payload)

            result = run_cli(
                "--installed-dir",
                str(installed),
                "--reference-dir",
                str(reference),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists(), "Compared Python files must not be imported or executed.")

    def test_package_checker_tracks_selfcheck_script(self) -> None:
        checker = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "check_skill_package.py"
        text = checker.read_text(encoding="utf-8")
        self.assertIn(
            ".agents/skills/long-horizon-engineering/scripts/selfcheck_installed_skill.py",
            text,
        )


if __name__ == "__main__":
    unittest.main()
