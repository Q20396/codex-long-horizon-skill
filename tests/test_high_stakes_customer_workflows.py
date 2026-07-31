from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/fixtures/high-stakes-customer-workflows/cases.json"
GUIDE = ROOT / "docs/high-stakes-customer-workflows.md"
EXAMPLES = ROOT / "examples/high-stakes-customer-workflows.md"
CATALOG = (
    ROOT
    / ".agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json"
)
STATUSES = {
    "READY_FOR_CUSTOMER_DECISION",
    "MORE_EVIDENCE_NEEDED",
    "BLOCKED",
}


class HighStakesCustomerWorkflowTests(unittest.TestCase):
    def test_synthetic_golden_cases_are_closed_and_customer_controlled(self) -> None:
        data = json.loads(CASES.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        capability_ids = {
            card["capability_id"] for card in catalog["capabilities"]
        }
        self.assertTrue(data["synthetic_only"])
        self.assertFalse(data["customer_sensitive_data_present"])
        self.assertEqual(len(data["cases"]), 3)
        self.assertEqual(
            {case["status"] for case in data["cases"]},
            STATUSES,
        )
        for case in data["cases"]:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(
                    set(case),
                    {
                        "case_id",
                        "capability_id",
                        "status",
                        "FACT",
                        "INFERENCE",
                        "UNKNOWN",
                        "next_safe_action",
                        "decision_authority",
                        "forbidden_effects",
                    },
                )
                self.assertIn(case["capability_id"], capability_ids)
                self.assertEqual(case["decision_authority"], "customer")
                self.assertIsInstance(case["next_safe_action"], str)
                self.assertTrue(case["next_safe_action"].strip())
                for evidence_class in ("FACT", "INFERENCE", "UNKNOWN"):
                    self.assertIsInstance(case[evidence_class], list)
                    self.assertTrue(case[evidence_class])
                    self.assertTrue(
                        all(
                            isinstance(item, str) and item.strip()
                            for item in case[evidence_class]
                        )
                    )
                self.assertIn("upload", case["forbidden_effects"])

    def test_domain_boundaries_are_visible_and_non_executing(self) -> None:
        text = " ".join(GUIDE.read_text(encoding="utf-8").split())
        for phrase in (
            "Customer-sensitive material must never be uploaded",
            "does not provide legal advice",
            "does not connect a brokerage account",
            "Dropbox, Gmail, Outlook, Hotmail, and Google Drive are not read by LHE Core",
            "declared-disabled",
            "no model memory, telemetry, background sync, or automatic reconnection",
            "Counsel, not LHE",
        ):
            self.assertIn(phrase, text)
        self.assertIn("All names, locators, dates, and evidence identifiers", EXAMPLES.read_text(encoding="utf-8"))

    def test_fixtures_contain_no_real_person_or_local_customer_locator(self) -> None:
        text = CASES.read_text(encoding="utf-8")
        self.assertNotRegex(
            text,
            re.compile(
                r"(?i)(@[a-z0-9.-]+\.[a-z]{2,}|/Users/|C:\\|Bearer\s+|"
                r"api[_-]?key|dropbox\.com|drive\.google\.com|gmail\.com)"
            ),
        )

    def test_investment_case_blocks_account_and_execution_effects(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
        investment = next(
            case
            for case in cases
            if case["capability_id"] == "public-equity-research"
        )
        self.assertEqual(investment["status"], "BLOCKED")
        self.assertTrue(
            {
                "account_access",
                "credential_access",
                "order",
                "trade",
                "rebalance",
            }.issubset(investment["forbidden_effects"])
        )


if __name__ == "__main__":
    unittest.main()
