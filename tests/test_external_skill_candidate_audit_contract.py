from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "external-skill-adoption-safety-review.md"
TEMPLATE = LHE / "templates" / "external-skill-adoption-review.md"

EXPECTED_CONCLUSIONS = [
    "ADOPT IDEA",
    "ADAPT WITH CHANGES",
    "REJECT",
    "NEEDS MANUAL SECURITY REVIEW",
]

TRIGGER_OVERLAP_VALUES = [
    "NO_OVERLAP",
    "COMPLEMENTARY",
    "PARTIAL_OVERLAP",
    "CONFLICTING",
    "OVERBROAD",
    "NEEDS_MANUAL_ROUTING_REVIEW",
]

SOURCE_LEDGER_FIELDS = [
    "candidate_name",
    "source_url",
    "requested_ref",
    "requested_tag",
    "resolved_commit_sha",
    "identity_verification_status",
    "reviewed_at",
    "files_inspected",
    "files_not_inspected",
    "license_name",
    "license_file",
    "license_status",
    "attribution_requirement",
    "provenance_notes",
    "provenance_verified",
    "copied_code_or_prose",
    "copied_assets",
    "copied_tests",
    "reusable_ideas",
    "security_findings",
    "privacy_findings",
    "trigger_overlap",
    "review_status",
    "user_approval_state",
    "final_conclusion",
]


class ExternalSkillCandidateAuditContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        for phrase in phrases:
            self.assertIn(phrase, text)

    def conclusion_values(self, text: str) -> list[str]:
        marker = "Allowed final conclusions (exact values):"
        self.assertIn(marker, text)
        tail = text.split(marker, 1)[1]
        for delimiter in ("Meanings:", "Selected final_conclusion:"):
            if delimiter in tail:
                tail = tail.split(delimiter, 1)[0]
                break
        return re.findall(r"^- `([^`]+)`$", tail, flags=re.MULTILINE)

    def test_reference_requires_exact_sha_and_rejects_mutable_identity(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Exact commit SHA is the reproducible audit identity",
                "REQUIRE EXACT COMMIT SHA",
                "requested_tag",
                "resolved_commit_sha",
                "A moved tag must be detected and reported",
                "A tag without its resolved SHA is insufficient",
                "`main`",
                "`master`",
                "`latest`",
                "branch names",
                "`refs/heads/**`",
                "moving aliases",
                "GitHub Stars are discovery metadata only",
                "Stars do not prove safety",
                "Stars do not prove correctness",
                "Stars do not prove compatibility",
                "Stars do not prove license suitability",
                "Popularity is not safety evidence",
            ],
        )

    def test_reference_is_read_only_proposal_only_and_mutation_denying(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Audit status: PROPOSAL_ONLY",
                "User decision: PENDING",
                "Changes applied: NO",
                "Candidate installed: NO",
                "Candidate executed: NO",
                "Stable modified: NO",
                "Candidate files are read as data only",
                "install the candidate",
                "execute candidate code",
                "import candidate code",
                "run candidate scripts",
                "run candidate installers",
                "copy candidate files into Stable",
                "apply a candidate patch",
                "modify the current skill",
                "update the current skill",
                "automatically change trigger scope",
                "automatically change Stable policies",
                "Network behavior is not added by PR-04",
                "Default mutation action: DENY",
                "Default exact-path write allowlist: EMPTY",
                "Exact repository-relative path approval is required",
            ],
        )

    def test_source_ledger_license_and_provenance_contract(self) -> None:
        text = self.read(REFERENCE)
        for field in SOURCE_LEDGER_FIELDS:
            self.assertIn(field, text)
        self.assert_contains_all(
            text,
            [
                "copied_code_or_prose: NO",
                "copied_assets: NO",
                "copied_tests: NO",
                "user_approval_state: PENDING",
                "changes_applied: NO",
                "candidate_installed: NO",
                "candidate_executed: NO",
                "No code, prose, asset, or test may be copied merely because it is public",
                "Unknown or incompatible license blocks copying and direct adoption",
                "Missing provenance requires manual security review",
            ],
        )

    def test_dangerous_behavior_taxonomy_is_explicit(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "A. SHELL AND PROCESS EXECUTION",
                "shell=True",
                "os.system",
                "subprocess misuse",
                "B. DYNAMIC CODE",
                "eval",
                "exec",
                "runpy",
                "__import__",
                "dynamic imports",
                "C. INSTALLER AND SUPPLY-CHAIN BEHAVIOR",
                "curl | sh",
                "wget | sh",
                "install-time execution",
                "submodules",
                "gitlinks",
                "unexplained binaries",
                "D. CREDENTIAL AND SECRET ACCESS",
                "Environment-variable harvesting",
                "API keys",
                "Cloud credentials",
                "E. PRIVACY AND USER-DATA ACCESS",
                "Raw prompt collection",
                "Full conversation collection",
                "GPS or location access",
                "Hidden logging",
                "F. FILESYSTEM BEHAVIOR",
                "Writes outside the authorized repository",
                "G. NETWORK BEHAVIOR",
                "Hidden network requests",
                "Telemetry",
                "H. GIT AND RELEASE BEHAVIOR",
                "Auto-merge",
                "Production execution",
                "I. PERSISTENCE",
                "Background jobs",
                "J. SELF-MUTATION",
                "Policy weakening",
                "Test weakening",
            ],
        )

    def test_privacy_prohibited_external_query_fields_are_explicit(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Customer names",
                "Client names",
                "Private repository names",
                "Private class names",
                "Private function names",
                "Private file paths",
                "Internal domains",
                "Database names",
                "Credentials",
                "Tokens",
                "API keys",
                "Customer source excerpts",
                "Raw prompts",
                "Conversation text",
                "Email addresses",
                "Account identifiers",
                "Local absolute paths",
                "Convert a private problem into a generic technical query",
            ],
        )

    def test_trigger_overlap_contract_and_enum(self) -> None:
        text = self.read(REFERENCE)
        for value in TRIGGER_OVERLAP_VALUES:
            self.assertIn(value, text)
        self.assert_contains_all(
            text,
            [
                "existing installed `SKILL.md` descriptions",
                "root trigger fixtures",
                "explicit-only extension boundaries",
                "safety and privacy trigger boundaries",
                "existing routing exclusions",
                "Trigger overlap does not authorize routing changes",
                "may not edit Stable trigger descriptions",
            ],
        )

    def test_allowed_conclusion_enum_is_exact_in_reference_and_template(self) -> None:
        self.assertEqual(self.conclusion_values(self.read(REFERENCE)), EXPECTED_CONCLUSIONS)
        self.assertEqual(self.conclusion_values(self.read(TEMPLATE)), EXPECTED_CONCLUSIONS)
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "`ADOPT IDEA` permits independent reimplementation of a design pattern only",
                "It does not authorize copying, installation, execution, patch application, or",
                "Stable modification",
                "`ADAPT WITH CHANGES` requires a new proposal and separate approval",
                "`REJECT` authorizes no installation, execution, copying, or adaptation",
                "`NEEDS MANUAL SECURITY REVIEW` authorizes no adoption action",
            ],
        )

    def test_template_contains_required_sections_and_defaults(self) -> None:
        text = self.read(TEMPLATE)
        required_sections = [
            "## 1. Audit Status",
            "## 2. Candidate Identity",
            "## 3. Source Ledger",
            "## 4. Scope Reviewed",
            "## 5. Files Inspected",
            "## 6. Files Not Inspected",
            "## 7. License Review",
            "## 8. Provenance Review",
            "## 9. Dangerous-Behavior Findings",
            "## 10. Privacy Findings",
            "## 11. Security Findings",
            "## 12. Network and Persistence Findings",
            "## 13. Filesystem Findings",
            "## 14. Git, Release, and Deployment Findings",
            "## 15. Self-Mutation Findings",
            "## 16. Trigger-Overlap Review",
            "## 17. Reusable Ideas",
            "## 18. Material Proposed for Copying",
            "## 19. Required Adaptations",
            "## 20. Residual Risks",
            "## 21. Final Conclusion",
            "## 22. User Decision",
            "## 23. Changes Applied",
            "## 24. Rollback or Rejection Notes",
        ]
        self.assert_contains_all(text, required_sections)
        self.assert_contains_all(
            text,
            [
                "Audit status: PROPOSAL_ONLY",
                "User decision: PENDING",
                "Changes applied: NO",
                "Candidate installed: NO",
                "Candidate executed: NO",
                "Stable modified: NO",
                "copied_code_or_prose: NO",
                "copied_assets: NO",
                "copied_tests: NO",
                "Patch application performed: NO",
                "Trigger scope changed: NO",
                "Default mutation action: DENY",
                "Default exact-path write allowlist: EMPTY",
            ],
        )
        for field in SOURCE_LEDGER_FIELDS:
            self.assertIn(field, text)


if __name__ == "__main__":
    unittest.main()
