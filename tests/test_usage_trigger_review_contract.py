from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
PROTOCOL = LHE / "references" / "usage-and-trigger-review.md"
TEMPLATE = LHE / "templates" / "TRIGGER_REVIEW_TEMPLATE.md"
FIXTURE = ROOT / "tests" / "expected-triggers.json"

RECOMMENDATIONS = [
    "KEEP",
    "OPTIMIZE",
    "NARROW_TRIGGER",
    "SPLIT",
    "FREEZE",
    "DEPRECATE",
]


class UsageTriggerReviewContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_protocol_declares_manual_local_aggregate_contract(self) -> None:
        text = self.read(PROTOCOL)
        self.assert_contains_all(
            text,
            [
                "Manual",
                "Local",
                "Aggregated",
                "Privacy-preserving",
                "Explicitly supplied by the user",
                "Read-only with respect to current skill behavior",
                "Proposal-only",
                "Non-telemetric",
                "Non-background",
                "Non-automatic",
                "A recommendation is not approval",
            ],
        )

    def test_protocol_forbids_private_or_inferred_sources(self) -> None:
        text = self.read(PROTOCOL)
        self.assert_contains_all(
            text,
            [
                "Usage review may read only an explicit user-supplied aggregate artifact",
                "Raw prompts",
                "Full conversations",
                "Codex logs",
                "Shell history",
                "Browser history",
                "Hidden files",
                "Repositories",
                "Git history",
                "Email",
                "Gmail",
                "Cloud drives",
                "Connected services",
                "Device information",
                "GPS or location",
                "User identities",
                "Client identities",
                "Account identifiers",
                "Credentials",
                "Tokens",
                "API keys",
                "Repository source contents",
                "Private absolute paths",
            ],
        )

    def test_protocol_and_template_defaults_are_proposal_only(self) -> None:
        combined = self.read(PROTOCOL) + "\n" + self.read(TEMPLATE)
        self.assert_contains_all(
            combined,
            [
                "Proposal status: PROPOSAL_ONLY",
                "User decision: PENDING",
                "Changes applied: NO",
                "Trigger description modified: NO",
                "Trigger fixtures modified: NO",
                "Lifecycle state modified: NO",
                "Telemetry enabled: NO",
                "Background collection enabled: NO",
                "The reviewer must not change the user-decision field to an approved value",
            ],
        )

    def test_recommendation_enum_is_exact(self) -> None:
        text = self.read(PROTOCOL)
        match = re.search(
            r"Use exactly one of these lifecycle recommendations:\n\n"
            r"(?P<body>(?:- [A-Z_]+\n)+)",
            text,
        )
        self.assertIsNotNone(match, "Recommendation enum block not found.")
        values = [
            line.removeprefix("- ").strip()
            for line in match.group("body").splitlines()
            if line.strip()
        ]
        self.assertEqual(values, RECOMMENDATIONS)
        for value in RECOMMENDATIONS:
            self.assertIn(f"### {value}", text)

    def test_routing_decision_rules_are_explicit(self) -> None:
        text = self.read(PROTOCOL)
        self.assert_contains_all(
            text,
            [
                "Narrow trigger wording",
                "Add negative trigger fixtures",
                "Clarify positive trigger wording",
                "Add positive trigger fixtures",
                "Narrow the implicit trigger threshold",
                "Recommend explicit-only invocation for expensive behavior",
                "Optimize workflow steps without weakening required validation",
                "Treat low usage as evidence requiring context, not as automatic proof",
                "Do not automatically deprecate",
                "Safety and privacy boundaries override usage optimization",
                "Never weaken approval, network, privacy, filesystem, deployment, update, or mutation rules",
            ],
        )

    def test_fixture_model_keeps_static_and_live_routing_separate(self) -> None:
        text = self.read(PROTOCOL)
        self.assert_contains_all(
            text,
            [
                "Proposed trigger-description change",
                "Proposed positive fixture",
                "Proposed negative fixture",
                "Proposed explicit-invocation fixture",
                "Proposed boundary fixture",
                "Proposed no-skill fixture",
                "Prompt or privacy-safe abstract prompt",
                "Source aggregate signal",
                "Static trigger fixtures validate declared routing expectations",
                "Static fixtures do not prove live Codex routing behavior",
                "`docs/evals/live-routing.md` remains advisory/non-required",
                "Live model routing must not become a hard deterministic CI gate",
                "Fixture updates do not authorize editing `SKILL.md`",
                "Fixture updates require a separate implementation approval",
            ],
        )

    def test_template_contains_required_sections_and_non_actions(self) -> None:
        text = self.read(TEMPLATE)
        required_sections = [
            "## 1. Review Status",
            "## 2. Review Scope",
            "## 3. User-Supplied Input",
            "## 4. Privacy Validation",
            "## 5. Aggregate Metrics",
            "## 6. Existing Routing Mode",
            "## 7. False-Positive Evidence",
            "## 8. Missed-Trigger Evidence",
            "## 9. Too-Heavy Evidence",
            "## 10. Task-Category Evidence",
            "## 11. Trigger-Overlap Findings",
            "## 12. Safety and Privacy Constraints",
            "## 13. Proposed Trigger-Description Changes",
            "## 14. Proposed Positive Fixtures",
            "## 15. Proposed Negative Fixtures",
            "## 16. Proposed Explicit-Invocation Fixtures",
            "## 17. Proposed Boundary Fixtures",
            "## 18. Proposed No-Skill Fixtures",
            "## 19. Lifecycle Recommendation",
            "## 20. Recommendation Rationale",
            "## 21. Files That Would Change",
            "## 22. Validation Plan",
            "## 23. Compatibility Impact",
            "## 24. Rollback Plan",
            "## 25. User Decision",
            "## 26. Changes Applied",
        ]
        self.assert_contains_all(text, required_sections)
        self.assert_contains_all(
            text,
            [
                "No usage data was collected automatically",
                "Completing this template does not change trigger descriptions",
                "Codex logs scanned: NO",
                "Shell history scanned: NO",
                "Browser history scanned: NO",
                "Hidden files scanned: NO",
                "Repositories scanned for usage evidence: NO",
                "Gmail, email, cloud drives, or connected services scanned: NO",
                "Safety or privacy rule weakened: NO",
            ],
        )

    def test_expected_trigger_fixture_additions_cover_usage_review(self) -> None:
        payload = json.loads(self.read(FIXTURE))
        cases = {case["id"]: case for case in payload["cases"]}
        required = {
            "explicit-lhe-usage-review-aggregate": "long-horizon-engineering",
            "explicit-lhe-trigger-counts-proposal": "long-horizon-engineering",
            "boundary-lhe-too-heavy-proposal-only": "long-horizon-engineering",
            "none-implicit-auto-scan-usage-logs": "none",
            "none-implicit-background-telemetry-deprecate": "none",
        }
        for case_id, expected_skill in required.items():
            self.assertIn(case_id, cases)
            self.assertEqual(cases[case_id]["expected_skill"], expected_skill)
        self.assertEqual(cases["none-implicit-auto-scan-usage-logs"]["invocation_mode"], "implicit")
        self.assertEqual(cases["none-implicit-background-telemetry-deprecate"]["invocation_mode"], "implicit")


if __name__ == "__main__":
    unittest.main()
