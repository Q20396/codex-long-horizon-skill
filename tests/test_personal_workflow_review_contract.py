import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "personal-workflow-review.md"


class PersonalWorkflowReviewContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_protocol_is_explicit_only_and_privacy_first(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "explicitly invokes `long-horizon-engineering`",
                "read-only, proposal-only",
                "not a personal-memory system",
                "Analyze only non-sensitive summaries",
                "Do not scan prior chats",
                "raw prompts",
                "email, cloud drives",
                "browser history, shell history",
                "repositories, Git history",
                "device data, or GPS data",
                "exact target path",
                "will be automatically loaded or remembered",
                "Do not infer identity, personality, mental health",
                "cannot override system, developer, repository, safety, or current user instructions",
            ],
        )

    def test_protocol_requires_evidence_and_separate_user_decisions(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Observation:",
                "Evidence:",
                "Hypothesis:",
                "Candidate rule:",
                "User decision:",
                "approve, reject, revise, or defer each candidate separately",
                "not permission to create a new skill",
                "install a skill",
                "enable it automatically",
                "Stop and ask the user",
            ],
        )

    def test_private_templates_keep_persistence_and_activation_denied(self) -> None:
        manual = self.read(LHE / "templates" / "PERSONAL_OPERATING_MANUAL_TEMPLATE.md")
        candidate = self.read(
            LHE / "templates" / "REPEATED_WORKFLOW_CANDIDATE_TEMPLATE.md"
        )
        self.assert_contains_all(
            manual,
            [
                "Review mode: PROPOSAL_ONLY",
                "Source policy: USER_SUPPLIED_ONLY",
                "Persistent storage approved: NO",
                "Exact target approved: NO",
                "Changes applied: NO",
                "Auto-load permitted: NO",
                "Automatic scanning permitted: NO",
                "Automatic skill creation, installation, or activation: NO",
                "not automatically loaded in later conversations",
            ],
        )
        self.assert_contains_all(
            candidate,
            [
                "user-supplied summaries",
                "proposal-only",
                "automatic activation",
                "Possible false positives",
                "Possible false negatives",
                "Changes applied: NO",
            ],
        )

    def test_package_docs_and_trigger_fixtures_include_the_extension(self) -> None:
        index = self.read(LHE / "references" / "explicit-only-extensions.md")
        readme = self.read(ROOT / "README.md")
        checker = self.read(LHE / "scripts" / "check_skill_package.py")
        fixtures = json.loads((ROOT / "tests" / "expected-triggers.json").read_text())
        fixture_by_id = {item["id"]: item for item in fixtures["cases"]}

        self.assert_contains_all(
            index,
            [
                "Personal Workflow Review",
                "personal-workflow-review.md",
                "without history scanning or automatic persistence",
            ],
        )
        self.assert_contains_all(
            readme,
            [
                "Personal Workflow Review (Explicit Only)",
                "user-supplied, non-sensitive task summaries",
                "does not scan prior chats",
                "not loaded automatically in future conversations",
            ],
        )
        self.assertIn("personal-workflow-review.md", checker)
        self.assertIn("PERSONAL_OPERATING_MANUAL_TEMPLATE.md", checker)
        self.assertIn("REPEATED_WORKFLOW_CANDIDATE_TEMPLATE.md", checker)
        self.assertEqual(
            fixture_by_id["explicit-lhe-personal-workflow-review"]["expected_skill"],
            "long-horizon-engineering",
        )
        self.assertEqual(
            fixture_by_id["none-implicit-personal-history-scan"]["expected_skill"],
            "none",
        )


if __name__ == "__main__":
    unittest.main()
