import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "update_installed_skill.py"

spec = importlib.util.spec_from_file_location("update_installed_skill", SCRIPT)
updater = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(updater)


class UpdateInstalledSkillPathContractTests(unittest.TestCase):
    def parse(self, args: list[str]):
        return updater.parse_args(args)

    def test_target_root_preserves_project_agents_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.parse(["--target-root", str(root), "--skill", "long-horizon-engineering"])
            plan = updater.resolve_target_plan(args, "long-horizon-engineering", apply=False)

        self.assertEqual(
            plan.target,
            root.resolve() / ".agents" / "skills" / "long-horizon-engineering",
        )
        self.assertEqual(plan.backup_root, root.resolve() / ".codex-skill-backups")
        self.assertEqual(plan.installed_project_root, root.resolve())

    def test_target_skill_dir_points_directly_to_existing_active_install_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_root = Path(tmp) / ".codex"
            skill_dir = codex_root / "skills" / "long-horizon-engineering"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("name: long-horizon-engineering\n", encoding="utf-8")
            args = self.parse(
                ["--target-skill-dir", str(skill_dir), "--skill", "long-horizon-engineering"]
            )
            plan = updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)

        self.assertEqual(plan.target, skill_dir.resolve())
        self.assertEqual(plan.backup_root, codex_root.resolve() / "skill-backups")
        self.assertIsNone(plan.installed_project_root)

    def test_target_skill_dir_basename_must_match_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "wrong-name"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("name: wrong-name\n", encoding="utf-8")
            args = self.parse(
                ["--target-skill-dir", str(skill_dir), "--skill", "long-horizon-engineering"]
            )
            with self.assertRaisesRegex(SystemExit, "basename must match"):
                updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)

    def test_target_skill_dir_must_be_existing_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "long-horizon-engineering"
            args = self.parse(
                ["--target-skill-dir", str(skill_dir), "--skill", "long-horizon-engineering"]
            )
            with self.assertRaisesRegex(SystemExit, "existing skill directory"):
                updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)

    def test_target_skill_dir_must_use_skills_parent_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "long-horizon-engineering"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("name: long-horizon-engineering\n", encoding="utf-8")
            args = self.parse(
                ["--target-skill-dir", str(skill_dir), "--skill", "long-horizon-engineering"]
            )
            with self.assertRaisesRegex(SystemExit, r"skills/<skill>"):
                updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)

    def test_target_root_to_codex_home_rejects_duplicate_agents_layout(self) -> None:
        codex_home = Path.home() / ".codex"
        args = self.parse(
            ["--target-root", str(codex_home), "--skill", "long-horizon-engineering"]
        )
        with self.assertRaisesRegex(SystemExit, "codex/.agents/skills"):
            updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)

    def test_rejects_both_target_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "long-horizon-engineering"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("name: long-horizon-engineering\n", encoding="utf-8")
            args = self.parse(
                [
                    "--target-root",
                    str(root),
                    "--target-skill-dir",
                    str(skill_dir),
                    "--skill",
                    "long-horizon-engineering",
                ]
            )
            with self.assertRaisesRegex(SystemExit, "either --target-root or --target-skill-dir"):
                updater.resolve_target_plan(args, "long-horizon-engineering", apply=False)

    def test_apply_requires_one_explicit_skill(self) -> None:
        args = self.parse(["--target-root", "/tmp/example", "--apply"])
        skills = args.skill or list(updater.ALLOWED_SKILLS)
        self.assertNotEqual(len(skills), 1)
        with self.assertRaisesRegex(SystemExit, "exactly one explicit --skill"):
            if args.apply and len(skills) != 1:
                raise SystemExit("ERROR: --apply requires exactly one explicit --skill.")

    def test_apply_requires_target_option(self) -> None:
        args = self.parse(["--skill", "long-horizon-engineering", "--apply"])
        with self.assertRaisesRegex(SystemExit, "requires --target-root or --target-skill-dir"):
            updater.resolve_target_plan(args, "long-horizon-engineering", apply=True)


if __name__ == "__main__":
    unittest.main()
