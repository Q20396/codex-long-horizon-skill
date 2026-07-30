import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / ".agents/skills/long-horizon-engineering/SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
UPGRADE = (ROOT / "UPGRADE_GUIDE.md").read_text(encoding="utf-8")


class InstallationPathGuidanceContractTests(unittest.TestCase):
    def test_skill_distinguishes_project_and_codex_user_paths(self):
        self.assertIn("project-level: `.agents/skills/<skill_id>`", SKILL)
        self.assertIn("Codex user-level: `~/.codex/skills/<skill_id>`", SKILL)
        self.assertIn("Do not infer an installed path", SKILL)

    def test_user_level_docs_use_direct_skill_directory(self):
        for document in (README, INSTALL, UPGRADE):
            self.assertIn("--target-skill-dir ~/.codex/skills/long-horizon-engineering", document)

    def test_legacy_selfcheck_is_not_presented_as_codex_user_default(self):
        self.assertIn("legacy/project-style `.agents/skills` layout", README)
        self.assertIn("`--target-skill-dir` updater flow", README)
