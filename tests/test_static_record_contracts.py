import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "sandbox/skill-incubator/schemas"
CASES = ROOT / "tests/fixtures/static-record-contracts/cases.json"

class StaticRecordContractsTests(unittest.TestCase):
    def _records(self):
        return json.loads(CASES.read_text())["records"]

    def _assert_linked(self, records):
        self.assertEqual({"RTE-SYNTHETIC-001"}, {record["request_id"] for record in records})
        for field in ("subject_identity_digest", "requested_effects_digest", "source_scope_digest", "input_contract_digest"):
            self.assertEqual(1, len({record[field] for record in records}), field)

    def test_records_are_synthetic_and_orthogonal(self):
        records = self._records()
        self.assertEqual({"CAPABILITY_DESCRIPTOR","RUNTIME_OBSERVATION","TASK_GRANT","EXECUTION_RECEIPT"},{r["record_kind"] for r in records})
        self._assert_linked(records)
        for record in records:
            self.assertTrue(record["synthetic"]); self.assertTrue(record["fixture_only"]); self.assertEqual("ephemeral",record["persistence"])
        capability = next(r for r in records if r["record_kind"] == "CAPABILITY_DESCRIPTOR")
        self.assertTrue(capability["declaration_only"])
        for field in ("installation_proven", "callability_proven", "authorization_proven", "execution_proven"):
            self.assertFalse(capability[field])
        grant = next(r for r in records if r["record_kind"] == "TASK_GRANT")
        self.assertEqual("NOT_ISSUED", grant["grant_status"])
        self.assertEqual([], grant["granted_effects"])
        for field in ("grant_token", "signature", "issued_at", "expires_at", "consumed_at"):
            self.assertIsNone(grant[field])
        observation = next(r for r in records if r["record_kind"] == "RUNTIME_OBSERVATION")
        self.assertEqual("NOT_OBSERVED", observation["installation_status"])
        self.assertEqual("NOT_OBSERVED", observation["callability_status"])
        receipt = next(r for r in records if r["record_kind"] == "EXECUTION_RECEIPT")
        self.assertEqual("NOT_EXECUTED", receipt["execution_status"])
        self.assertEqual("NONE", receipt["tool_invocation"])
        self.assertEqual([], receipt["external_effects_observed"])
        self.assertIsNone(receipt["output_material"])

    def test_same_kind_digest_mismatch_is_detected(self):
        records = copy.deepcopy(self._records())
        records[-1]["input_contract_digest"] = "sha256:" + "e" * 64
        with self.assertRaises(AssertionError):
            self._assert_linked(records)

    def test_schemas_close_unknown_fields_and_real_states(self):
        for name in ("capability-descriptor","runtime-observation","task-grant-record","execution-receipt"):
            schema=json.loads((SCHEMAS/f"{name}.schema.json").read_text())
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("synthetic",schema["required"])
            self.assertEqual("string", schema["properties"]["request_id"]["type"])
            self.assertEqual("string", schema["properties"]["subject_identity_digest"]["type"])

if __name__ == "__main__": unittest.main()
