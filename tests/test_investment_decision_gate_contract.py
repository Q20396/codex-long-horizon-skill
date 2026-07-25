"""Contract checks for the Investment Decision Gate foundation."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
CONTRACT = INCUBATOR / "architecture" / "investment-decision-gate.json"
GUIDE = INCUBATOR / "architecture" / "investment-decision-gate.md"
GATE_SCHEMA = INCUBATOR / "schemas" / "investment-decision-gate.schema.json"
EVIDENCE_SCHEMA = INCUBATOR / "schemas" / "evidence-ledger.schema.json"
MONITORING_SCHEMA = INCUBATOR / "schemas" / "monitoring-review.schema.json"
CASES = ROOT / "tests" / "fixtures" / "investment-decision-gate" / "cases.json"


class InvestmentDecisionGateContractTests(unittest.TestCase):
    def load_json(self, path: Path):
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_is_research_only_and_non_executable(self) -> None:
        contract = self.load_json(CONTRACT)
        self.assertEqual("contract_foundation_approved", contract["status"])
        self.assertFalse(contract["registered_skill"])
        self.assertFalse(contract["runtime_integration_exists"])
        self.assertTrue(contract["human_decision_required"])
        self.assertTrue(contract["research_only"])
        denied = (
            "broker_access_authorized",
            "account_access_authorized",
            "credential_access_authorized",
            "position_execution_data_authorized",
            "order_generation_authorized",
            "order_transmission_authorized",
            "trade_execution_authorized",
            "network_execution_authorized",
            "provider_access_authorized",
            "customer_material_upload_authorized",
            "customer_material_external_transfer_authorized",
            "code_import_allowed",
        )
        for field in denied:
            self.assertIs(contract[field], False, field)

    def test_schemas_are_closed_draft_2020_12_contracts(self) -> None:
        for path in (GATE_SCHEMA, EVIDENCE_SCHEMA, MONITORING_SCHEMA):
            schema = self.load_json(path)
            self.assertEqual(
                "https://json-schema.org/draft/2020-12/schema",
                schema["$schema"],
            )
        gate = self.load_json(GATE_SCHEMA)
        self.assertFalse(gate["additionalProperties"])
        self.assertEqual("pending", gate["properties"]["human_decision"]["properties"]["status"]["const"])
        self.assertEqual(
            ["research_only", "watch", "wait_for_proof", "decision_candidate"],
            gate["properties"]["proposed_posture"]["enum"],
        )
        self.assertTrue(gate["$id"].startswith("urn:codex-long-horizon-skill:"))
        self.assertEqual(
            "urn:codex-long-horizon-skill:schema:evidence-ledger:1.0.0",
            gate["properties"]["evidence_ledger"]["$ref"],
        )
        candidate = gate["allOf"][0]["then"]["properties"]
        evidence_quality = candidate["evidence_ledger"]["items"]["properties"]
        self.assertEqual(
            {"const": "unverified"},
            evidence_quality["reliability"]["not"],
        )
        self.assertEqual(
            {"const": "unknown"},
            evidence_quality["license_status"]["not"],
        )
        self.assertIn(
            "stale",
            evidence_quality["limitations"]["not"]["contains"]["enum"],
        )
        self.assertEqual(
            ["high", "critical"],
            candidate["data_gaps"]["not"]["contains"]["properties"]["materiality"]["enum"],
        )

        monitoring = self.load_json(MONITORING_SCHEMA)
        self.assertIn("review_history", monitoring["items"]["required"])
        review = monitoring["items"]["properties"]["review_history"]["items"]
        self.assertEqual("recorded_for_human_review", review["properties"]["reviewer_status"]["const"])
        self.assertIn("re_underwrite", review["properties"]["decision_impact"]["enum"])

    def test_fixture_set_covers_ten_synthetic_gate_scenarios(self) -> None:
        cases = self.load_json(CASES)
        self.assertGreaterEqual(len(cases), 10)
        self.assertLessEqual(len(cases), 20)
        expected = {
            "ticker-only-research": "research_only",
            "earnings-without-market-price": "blocked",
            "complete-thesis": "decision_candidate",
            "conflicting-kpi": "blocked",
            "thesis-falsified": "re_underwrite",
            "execution-inducement": "blocked",
            "stale-consensus": "conditional",
            "draft-threshold": "conditional",
            "missing-valuation": "blocked",
            "unspecified-source": "blocked",
        }
        self.assertEqual(expected, {case["case_id"]: case["expected_state"] for case in cases})
        for case in cases:
            self.assertEqual(case["expected_state"], case["record"]["gate_state"])
            self.assertEqual("pending", case["record"]["human_decision"]["status"])
            self.assertTrue(case["record"]["research_packet_id"].startswith("SYNTHETIC-"))

    def test_fixture_states_obey_gate_semantics(self) -> None:
        for case in self.load_json(CASES):
            record = case["record"]
            state = record["gate_state"]
            if state == "decision_candidate":
                self.assertIsNotNone(record["as_of"])
                self.assertTrue(record["evidence_ledger"])
                self.assertIsNotNone(record["valuation_or_decision_framework"])
                self.assertTrue(record["counter_case"]["summary"])
                self.assertTrue(record["falsifiers"])
                self.assertEqual("decision_candidate", record["proposed_posture"])
                self.assertEqual([], record["gate_failures"])
            elif state in {"blocked", "conditional"}:
                self.assertTrue(record["gate_failures"])
            elif state == "re_underwrite":
                self.assertIn("THESIS_FALSIFIED", record["gate_failures"])
                reviews = [
                    review
                    for monitor in record["monitoring_plan"]
                    for review in monitor["review_history"]
                ]
                self.assertTrue(reviews)
                self.assertIn("re_underwrite", {review["decision_impact"] for review in reviews})

            source_ids = {item["source_id"] for item in record["evidence_ledger"]}
            assumption_ids = {item["assumption_id"] for item in record["assumptions"]}
            for assumption in record["assumptions"]:
                self.assertTrue(set(assumption["source_ids"]).issubset(source_ids))
            self.assertTrue(set(record["counter_case"]["source_ids"]).issubset(source_ids))
            for falsifier in record["falsifiers"]:
                self.assertIn(falsifier["source_id"], source_ids)
            for monitor in record["monitoring_plan"]:
                self.assertIn(monitor["source_id"], source_ids)
                for review in monitor["review_history"]:
                    self.assertTrue(set(review["source_ids"]).issubset(source_ids))
            framework = record["valuation_or_decision_framework"]
            if framework is not None:
                self.assertTrue(set(framework["key_assumption_ids"]).issubset(assumption_ids))

    def test_fixture_keys_do_not_create_execution_or_sensitive_data_contracts(self) -> None:
        forbidden_keys = {
            "broker",
            "broker_id",
            "account",
            "account_id",
            "api_key",
            "credential",
            "order",
            "place_order",
            "quantity_to_trade",
            "execution_route",
            "position_execution_data",
        }

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        for case in self.load_json(CASES):
            self.assertTrue(forbidden_keys.isdisjoint(set(walk(case["record"]))), case["case_id"])

    def test_formal_schema_validation_when_engine_is_available(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource

        schemas = [
            self.load_json(GATE_SCHEMA),
            self.load_json(EVIDENCE_SCHEMA),
            self.load_json(MONITORING_SCHEMA),
        ]
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        validator = Draft202012Validator(schemas[0], registry=registry)
        for case in self.load_json(CASES):
            errors = sorted(validator.iter_errors(case["record"]), key=lambda error: list(error.path))
            self.assertEqual([], errors, case["case_id"])

    def test_guide_preserves_human_gate_and_router_remediation_boundary(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        required = (
            "not a lead research skill",
            "`decision_candidate` means only",
            "`human_decision.status` equal to `pending`",
            "does not install or modify the Public Equity Investing plugin",
            "No entry schedules a job",
            "`test-public-equity-investing-workflows`",
            "remove that user-visible route",
            "does not edit the installed plugin cache",
        )
        normalized = " ".join(guide.split())
        for phrase in required:
            self.assertIn(" ".join(phrase.split()), normalized)


if __name__ == "__main__":
    unittest.main()
