"""Contract checks for public-equity source provenance and freshness."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
CONTRACT = INCUBATOR / "architecture" / "public-equity-data-freshness.json"
GUIDE = INCUBATOR / "architecture" / "public-equity-data-freshness.md"
GATE_GUIDE = INCUBATOR / "architecture" / "investment-decision-gate.md"
SCHEMA = INCUBATOR / "schemas" / "public-equity-data-freshness.schema.json"
FORMAL_VALIDATOR = (
    INCUBATOR
    / "candidate-intake"
    / "validation"
    / "validate_formal_schema_instances.py"
)
CASES = ROOT / "tests" / "fixtures" / "public-equity-data-freshness" / "cases.json"


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PublicEquityDataFreshnessContractTests(unittest.TestCase):
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
            "automatic_retrieval_authorized",
            "automatic_monitoring_authorized",
            "broker_access_authorized",
            "account_access_authorized",
            "credential_access_authorized",
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

    def test_schema_is_closed_draft_2020_12_contract(self) -> None:
        schema = self.load_json(SCHEMA)
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema["$schema"],
        )
        self.assertEqual(
            "urn:codex-long-horizon-skill:schema:public-equity-data-freshness:1.0.0",
            schema["$id"],
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            "pending",
            schema["properties"]["human_decision"]["properties"]["status"]["const"],
        )
        eligible = schema["allOf"][0]["then"]["properties"]
        self.assertEqual(0, eligible["block_reasons"]["maxItems"])
        self.assertEqual(1, eligible["sources"]["minItems"])
        self.assertEqual(1, eligible["claims"]["minItems"])
        source_rules = eligible["sources"]["items"]["allOf"][0]["properties"]
        self.assertEqual(
            ["fresh", "not_applicable"],
            source_rules["freshness"]["properties"]["status"]["enum"],
        )
        self.assertEqual(
            {"const": "unknown"},
            source_rules["license_status"]["not"],
        )
        self.assertEqual(
            {"const": "public_read_approval_missing"},
            source_rules["access_basis"]["not"],
        )

    def test_fixture_set_covers_eligible_and_blocked_scenarios(self) -> None:
        cases = self.load_json(CASES)
        self.assertEqual(8, len(cases))
        expected = {
            "fresh-asx-filing": True,
            "fresh-us-market-price": True,
            "stale-market-price": False,
            "unknown-publication-time": False,
            "unknown-source-licence": False,
            "unresolved-source-conflict": False,
            "unverified-market-calendar": False,
            "public-source-approval-missing": False,
        }
        self.assertEqual(
            expected,
            {case["case_id"]: case["expected_eligible"] for case in cases},
        )
        for case in cases:
            record = case["record"]
            self.assertEqual(case["expected_eligible"], record["decision_gate_eligible"])
            self.assertEqual("pending", record["human_decision"]["status"])
            self.assertTrue(record["assessment_id"].startswith("PEDF-"))
            if record["decision_gate_eligible"]:
                self.assertEqual([], record["block_reasons"])
            else:
                self.assertTrue(record["block_reasons"])

    def test_market_timezone_and_calendar_mapping_is_canonical(self) -> None:
        expected = {
            "ASX": ("Australia/Sydney", "ASX"),
            "US_LISTED_EQUITIES": ("America/New_York", "US_MARKET"),
        }
        for case in self.load_json(CASES):
            context = case["record"]["market_context"]
            self.assertEqual(
                expected[context["market"]],
                (context["exchange_timezone"], context["calendar_basis"]),
                case["case_id"],
            )

    def test_freshness_arithmetic_matches_recorded_status(self) -> None:
        for case in self.load_json(CASES):
            for source in case["record"]["sources"]:
                freshness = source["freshness"]
                if freshness["status"] not in {"fresh", "stale"}:
                    continue
                basis_time = source[freshness["basis"]]
                self.assertIsNotNone(basis_time, case["case_id"])
                calculated = int(
                    (
                        parse_datetime(freshness["assessed_at"])
                        - parse_datetime(basis_time)
                    ).total_seconds()
                )
                self.assertEqual(freshness["age_seconds"], calculated, case["case_id"])
                if freshness["status"] == "fresh":
                    self.assertLessEqual(
                        freshness["age_seconds"],
                        freshness["max_age_seconds"],
                        case["case_id"],
                    )
                else:
                    self.assertGreater(
                        freshness["age_seconds"],
                        freshness["max_age_seconds"],
                        case["case_id"],
                    )

    def test_claims_preserve_fact_derived_and_judgment_boundaries(self) -> None:
        classifications = set()
        for case in self.load_json(CASES):
            record = case["record"]
            source_ids = {source["source_id"] for source in record["sources"]}
            claim_ids = {claim["claim_id"] for claim in record["claims"]}
            for source in record["sources"]:
                self.assertTrue(set(source["claim_ids"]).issubset(claim_ids))
            for claim in record["claims"]:
                classifications.add(claim["classification"])
                self.assertTrue(set(claim["source_ids"]).issubset(source_ids))
                if claim["classification"] in {"fact", "derived"}:
                    self.assertTrue(claim["source_ids"])
                if claim["classification"] == "derived":
                    self.assertTrue(claim["model_version"])
        self.assertEqual({"fact", "derived", "judgment"}, classifications)

    def test_eligible_records_have_no_stale_unknown_or_conflicted_sources(self) -> None:
        for case in self.load_json(CASES):
            record = case["record"]
            if not record["decision_gate_eligible"]:
                continue
            for source in record["sources"]:
                self.assertIn(source["freshness"]["status"], {"fresh", "not_applicable"})
                self.assertNotEqual("unknown", source["license_status"])
                self.assertNotEqual("unresolved", source["conflict_status"])
                self.assertNotEqual(
                    "public_read_approval_missing",
                    source["access_basis"],
                )
                if source["source_class"] in {"market_price", "corporate_action"}:
                    self.assertEqual("verified", source["market_calendar_status"])

    def test_formal_schema_rejects_false_eligibility_claims_when_engine_available(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator, FormatChecker

        schema = self.load_json(SCHEMA)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        cases = self.load_json(CASES)
        for case in cases:
            self.assertEqual(
                [],
                list(validator.iter_errors(case["record"])),
                case["case_id"],
            )

        stale = deepcopy(next(case["record"] for case in cases if case["case_id"] == "stale-market-price"))
        stale["decision_gate_eligible"] = True
        stale["block_reasons"] = []
        self.assertTrue(list(validator.iter_errors(stale)))

        missing_approval = deepcopy(
            next(
                case["record"]
                for case in cases
                if case["case_id"] == "public-source-approval-missing"
            )
        )
        missing_approval["decision_gate_eligible"] = True
        missing_approval["block_reasons"] = []
        self.assertTrue(list(validator.iter_errors(missing_approval)))

        no_claims = deepcopy(
            next(
                case["record"]
                for case in cases
                if case["case_id"] == "fresh-asx-filing"
            )
        )
        no_claims["claims"] = []
        self.assertTrue(list(validator.iter_errors(no_claims)))

    def test_fixture_keys_exclude_sensitive_and_execution_contracts(self) -> None:
        forbidden_keys = {
            "api_key",
            "credential",
            "account_id",
            "portfolio_id",
            "position",
            "holdings",
            "order",
            "quantity_to_trade",
            "execution_route",
            "private_path",
            "raw_source_body",
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
            self.assertTrue(
                forbidden_keys.isdisjoint(set(walk(case["record"]))),
                case["case_id"],
            )

    def test_guides_state_additive_non_runtime_boundary(self) -> None:
        guide = " ".join(GUIDE.read_text(encoding="utf-8").split())
        required = (
            "`decision_gate_eligible` means only",
            "does not retrieve data",
            "Missing timestamps produce `unknown`",
            "Source access is not permission",
            "must remain ineligible",
            "It is not an investment decision",
            "does not declare one universal threshold",
            "Any future source retrieval needs a separate exact-source approval",
        )
        for phrase in required:
            self.assertIn(" ".join(phrase.split()), guide)
        gate_guide = GATE_GUIDE.read_text(encoding="utf-8")
        self.assertIn("public-equity-data-freshness.md", gate_guide)
        self.assertIn("additive", gate_guide)

    def test_formal_validator_registers_companion_schema_and_fixtures(self) -> None:
        source = FORMAL_VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("public-equity-data-freshness.schema.json", source)
        self.assertIn("tests/fixtures/public-equity-data-freshness", source)


if __name__ == "__main__":
    unittest.main()
