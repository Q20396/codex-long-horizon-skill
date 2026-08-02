"""Static contract tests for the non-executing research task envelope."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sandbox/skill-incubator/schemas/research-task-envelope.schema.json"
CASES_PATH = ROOT / "tests/fixtures/research-task-envelope/cases.json"

FORBIDDEN_EFFECTS = [
    "account_access",
    "credential_access",
    "customer_data_upload",
    "trade_execution",
    "background_monitoring",
    "external_notification",
]


class ResearchTaskEnvelopeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def test_contract_is_static_ephemeral_and_non_executing(self) -> None:
        properties = self.schema["properties"]
        self.assertEqual("1.0.0", properties["schema_version"]["const"])
        self.assertEqual("NOT_GRANTED", properties["authorization_state"]["const"])
        self.assertEqual(
            {"NOT_IMPLEMENTED", "OUT_OF_SCOPE"},
            set(properties["runtime_execution"]["enum"]),
        )
        self.assertEqual("ephemeral", properties["persistence"]["const"])
        self.assertEqual("NOT_PERFORMED", properties["financial_data_access"]["const"])
        self.assertEqual("NONE", properties["external_action"]["const"])
        self.assertNotIn("allowed_effects", properties)
        self.assertNotIn("granted_effects", properties)

    def test_task_types_and_portfolio_descriptor_boundary_are_declared(self) -> None:
        task_types = set(self.schema["properties"]["task_type"]["enum"])
        self.assertEqual(
            {"single_security", "peer_set", "sector", "index", "etf", "strategy_research", "portfolio_research"},
            task_types,
        )
        portfolio_case = self.cases["base_records"]["portfolio_descriptor"]
        self.assertEqual("DESCRIPTOR_ONLY", portfolio_case["support_status"])
        self.assertEqual("NOT_GRANTED", portfolio_case["authorization_state"])
        self.assertEqual("OUT_OF_SCOPE", portfolio_case["runtime_execution"])
        self.assertEqual([], portfolio_case["subjects"])
        self.assertEqual([], portfolio_case["requested_effects"])
        for forbidden_field in ("holdings", "account_identifier", "cost_basis", "tax_information", "portfolio_weights", "broker", "credentials"):
            self.assertNotIn(forbidden_field, self.schema["properties"])

    def test_effect_request_is_not_an_authorization(self) -> None:
        properties = self.schema["properties"]
        self.assertEqual(FORBIDDEN_EFFECTS, properties["forbidden_effects"]["const"])
        self.assertEqual("required_for_effect", properties["grant_requirement"]["const"])
        self.assertIsNone(properties["grant_ref"]["const"])
        self.assertTrue(self.cases["schema_contract_only"])
        self.assertEqual("NOT_IMPLEMENTED", self.cases["runtime_execution"])

    def test_single_security_fixture_uses_composite_identity(self) -> None:
        subject = self.cases["base_records"]["single_security"]["subjects"][0]
        self.assertEqual("listed_security", subject["subject_type"])
        self.assertEqual("SYN", subject["ticker"])
        self.assertEqual("ASX", subject["exchange"])
        self.assertEqual("XASX", subject["mic"])

    def test_negative_fixtures_are_declared_without_a_runtime_validator(self) -> None:
        for case in self.cases["negative_cases"]:
            self.assertIn(case["base"], self.cases["base_records"])
            self.assertIn(case["op"], {"set", "delete"})
            self.assertTrue(case["path"].startswith("/"))
        self.assertFalse((ROOT / "scripts" / "validate_research_task_envelope.py").exists())


if __name__ == "__main__":
    unittest.main()
