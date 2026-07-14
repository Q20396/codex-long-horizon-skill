from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "planner-builder-evaluator-loop.md"


class PlannerBuilderEvaluatorLoopContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_reference_defines_safe_role_boundaries(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Planner",
                "Builder",
                "Evaluator",
                "not separate agents",
                "do not grant extra permissions",
                "The plan is not write permission",
                "Evaluator is proposal-only",
                "must not edit files, silently retry until a desired result appears",
                "A human approves",
                "Do not run an unbounded plan-build-evaluate loop",
                "Do not store secrets",
            ],
        )

    def test_templates_make_completion_evidence_and_freshness_explicit(self) -> None:
        plan = self.read(LHE / "templates" / "implementation-plan.md")
        state = self.read(LHE / "templates" / "WORKING_STATE_TEMPLATE.md")
        evidence = self.read(LHE / "templates" / "verification-evidence.md")
        self.assert_contains_all(
            plan,
            [
                "Definition of Done",
                "Planned File Scope (Not Write Permission)",
                "Acceptance Criteria And Evidence",
                "Role Handoff",
                "Stop Conditions",
            ],
        )
        self.assert_contains_all(
            state,
            [
                "Last Verified Commit",
                "Last Verified Command",
                "State Freshness Check",
                "Do not resume from this file",
            ],
        )
        self.assert_contains_all(
            evidence,
            [
                "Acceptance Evidence",
                "Evaluator Scope",
                "proposal-only conclusion",
                "A passing command is evidence",
                "Known Blind Spots",
            ],
        )

    def test_resume_protocol_requires_revalidation_when_state_is_stale(self) -> None:
        text = self.read(LHE / "references" / "resume-protocol.md")
        self.assert_contains_all(
            text,
            [
                "recorded branch",
                "last verified commit",
                "both staged and unstaged diffs",
                "mark the old state stale",
                "Do not continue the old plan blindly",
            ],
        )

    def test_skill_readme_and_checkers_reference_the_contract(self) -> None:
        skill = self.read(LHE / "SKILL.md")
        readme = self.read(ROOT / "README.md")
        package_checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")
        self.assert_contains_all(
            skill,
            [
                "Definition of Done",
                "planner-builder-evaluator-loop.md",
                "Planner, Builder, and Evaluator are serial working roles",
            ],
        )
        self.assert_contains_all(
            readme,
            [
                "Role-Based Engineering Loop",
                "Planner -> Builder -> Evaluator -> Human Gate",
                "not autonomous sub-agents",
            ],
        )
        self.assertIn("planner-builder-evaluator-loop.md", package_checker)
        self.assertIn("planner-builder-evaluator-loop.md", doctor)


if __name__ == "__main__":
    unittest.main()
