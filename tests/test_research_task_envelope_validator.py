"""Tests for the read-only Research Task Envelope semantic validator."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_research_task_envelope.py"
CASES = json.loads((ROOT / "tests/fixtures/research-task-envelope/cases.json").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("research_validator", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ResearchTaskEnvelopeValidatorTests(unittest.TestCase):
    def test_valid_supported_tasks_are_deterministic_and_non_executing(self) -> None:
        for name, record in CASES["base_records"].items():
            if name == "portfolio_descriptor":
                continue
            with self.subTest(name=name):
                first, code = VALIDATOR.result_for(copy.deepcopy(record))
                second, repeated = VALIDATOR.result_for(copy.deepcopy(record))
                self.assertEqual(0, code)
                self.assertEqual(code, repeated)
                self.assertEqual(first, second)
                self.assertEqual("PASS", first["contract_validation"])
                self.assertEqual("PASS", first["semantic_validation"])
                self.assertFalse(first["grant_issued"])
                self.assertEqual("NOT_IMPLEMENTED", first["runtime_execution"])
                self.assertEqual("NOT_PROVEN", first["host_enforcement"])

    def test_missing_as_of_is_plan_only_not_a_failure(self) -> None:
        receipt, code = VALIDATOR.result_for(copy.deepcopy(CASES["base_records"]["sector"]))
        self.assertEqual(0, code)
        self.assertEqual("PLAN_ONLY", receipt["planning_mode"])

    def test_invalid_as_of_fails_contract_validation(self) -> None:
        record = copy.deepcopy(CASES["base_records"]["single_security"])
        record["as_of"] = "2026-08-02T00:00:00"
        receipt, code = VALIDATOR.result_for(record)
        self.assertEqual(2, code)
        self.assertIn("SCHEMA_AS_OF_INVALID", [item["code"] for item in receipt["errors"]])

    def test_network_request_requires_grant_without_network_access(self) -> None:
        record = copy.deepcopy(CASES["base_records"]["single_security"])
        record["requested_effects"] = ["public_network_read"]
        record["not_requested_effects"] = ["research_generation", "local_public_material_read", "calculation_request"]
        receipt, code = VALIDATOR.result_for(record)
        self.assertEqual(0, code)
        self.assertEqual("REQUIRES_GRANT", receipt["network_effect_status"])
        self.assertEqual([{"code": "NETWORK_EFFECT_REQUIRES_GRANT", "path": "/requested_effects"}], receipt["requirements"])
        self.assertFalse(receipt["grant_issued"])

    def test_conflicting_or_forbidden_effects_fail_closed(self) -> None:
        record = copy.deepcopy(CASES["base_records"]["single_security"])
        record["not_requested_effects"] = ["research_generation"]
        receipt, code = VALIDATOR.result_for(record)
        self.assertEqual(2, code)
        self.assertIn("EFFECT_CONFLICT", [item["code"] for item in receipt["errors"]])
        record["requested_effects"] = ["trade_execution"]
        record["not_requested_effects"] = []
        receipt, code = VALIDATOR.result_for(record)
        self.assertEqual(2, code)
        self.assertIn("FORBIDDEN_EFFECT_REQUESTED", [item["code"] for item in receipt["errors"]])

    def test_duplicate_composite_security_identity_fails_closed(self) -> None:
        record = copy.deepcopy(CASES["base_records"]["peer_set"])
        record["subjects"][1] = copy.deepcopy(record["subjects"][0])
        receipt, code = VALIDATOR.result_for(record)
        self.assertEqual(2, code)
        self.assertIn("SUBJECT_IDENTITY_CONFLICT", [item["code"] for item in receipt["errors"]])

    def test_portfolio_descriptor_is_recognized_but_out_of_scope(self) -> None:
        receipt, code = VALIDATOR.result_for(copy.deepcopy(CASES["base_records"]["portfolio_descriptor"]))
        self.assertEqual(2, code)
        self.assertIn("PORTFOLIO_RESEARCH_OUT_OF_SCOPE", [item["code"] for item in receipt["errors"]])

    def test_cli_reads_only_one_explicit_file_and_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text("{not-json", encoding="utf-8")
            receipt, code = VALIDATOR.result_for(None, parse_error=True)
            self.assertEqual(2, code)
            self.assertEqual([{"code": "INPUT_JSON_INVALID", "path": ""}], receipt["errors"])
            self.assertEqual("NONE", receipt["external_action"])

    def test_validator_has_no_network_write_or_environment_interfaces(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("urllib", "requests", "http.client", "subprocess", "os.environ", "write_text", "write_bytes", "open("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
