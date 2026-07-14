from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS = ROOT / ".agents" / "skills"


class UserSkillValidationLayoutTests(unittest.TestCase):
    def run_user_level_script(self, script_name: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_name:
            skills_root = Path(temp_name) / ".codex" / "skills"
            skills_root.mkdir(parents=True)
            shutil.copytree(
                SOURCE_SKILLS / "long-horizon-engineering",
                skills_root / "long-horizon-engineering",
            )
            shutil.copytree(
                SOURCE_SKILLS / "ai-video-production",
                skills_root / "ai-video-production",
            )
            script = skills_root / "long-horizon-engineering" / "scripts" / script_name
            return subprocess.run(
                [sys.executable, str(script)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_check_skill_package_supports_user_level_layout(self) -> None:
        result = self.run_user_level_script("check_skill_package.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Installed skill check passed", result.stdout)

    def test_doctor_supports_user_level_layout(self) -> None:
        result = self.run_user_level_script("doctor.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Doctor check passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
