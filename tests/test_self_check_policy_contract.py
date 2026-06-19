from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"


class SelfCheckPolicyContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def test_self_check_policy_exists_and_is_proposal_only(self) -> None:
        text = self.read(LHE / "references" / "self-check-policy.md")
        required = [
            "Self-check is read-only and proposal-only",
            "Proposal status: PROPOSAL_ONLY",
            "User approval required: YES",
            "User decision: PENDING",
            "Changes applied: NO",
            "Self-check cannot approve its own proposal",
            "Update/apply is a separate user-authorized action",
            "make network calls without explicit approval",
            "exact commit SHA",
            "Mutable refs are not valid reproducible comparison sources",
            "`main`",
            "`master`",
            "`latest`",
            "Unknown or additional files must be reported, not deleted",
            "weaken tests, safety rules, privacy rules, or approval requirements",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_self_improvement_review_template_contract_defaults(self) -> None:
        text = self.read(LHE / "templates" / "SELF_IMPROVEMENT_REVIEW_TEMPLATE.md")
        required = [
            "Reason for the proposed change",
            "Concrete evidence",
            "Proposed behavior change",
            "Files affected",
            "Trigger Impact",
            "Possible false positives",
            "Possible false negatives",
            "Security impact",
            "Privacy impact",
            "Network and dependency impact",
            "Validation plan",
            "Compatibility and migration impact",
            "Rollback plan",
            "User Approval State",
            "Whether changes have already been applied: NO",
            "Proposal status: PROPOSAL_ONLY",
            "User approval required: YES",
            "User decision: PENDING",
            "Changes applied: NO",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_usage_review_template_is_privacy_preserving(self) -> None:
        text = self.read(LHE / "templates" / "SKILL_USAGE_REVIEW_TEMPLATE.yaml")
        required = [
            "Manual, local, aggregated, privacy-preserving",
            "user_supplied_aggregate",
            "explicit_invocation_count",
            "implicit_invocation_count",
            "correct_trigger_count",
            "false_positive_trigger_count",
            "missed_trigger_count",
            "task_categories",
            "too_heavy_feedback",
            "KEEP / OPTIMIZE / NARROW_TRIGGER / SPLIT / FREEZE / DEPRECATE",
            "raw prompts",
            "conversation contents",
            "user names or identities",
            "email addresses",
            "credentials",
            "account identifiers",
            "client data",
            "device or GPS location",
            "private absolute paths",
            "repository file contents",
            "Codex logs",
            "shell history",
            "browser history",
            "hidden-file contents",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_readme_documents_short_self_check_contract(self) -> None:
        text = self.read(ROOT / "README.md")
        required = [
            "## Self-Check and Review-Gated Improvement",
            "Observe → Compare → Explain → Recommend → Wait for approval",
            "self-check is read-only",
            "findings remain proposal-only",
            "Updating or applying a change",
            "separate explicit action",
        ]
        for phrase in required:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
