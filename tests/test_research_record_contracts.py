import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "sandbox/skill-incubator/schemas"
CASES = ROOT / "tests/fixtures/research-record-contracts/cases.json"


class ResearchRecordContractsTests(unittest.TestCase):
    def _records(self):
        return json.loads(CASES.read_text())["records"]

    def _assert_linked(self, records):
        self.assertEqual({"RTE-SYNTHETIC-001"}, {record["request_id"] for record in records})
        for field in ("subject_identity_digest", "requested_effects_digest", "source_scope_digest", "input_contract_digest"):
            self.assertEqual(1, len({record[field] for record in records}), field)

    def test_records_are_synthetic_ephemeral_and_unexecuted(self):
        records = self._records()
        self.assertEqual({"EVIDENCE_RECORD", "CLAIM_RECORD", "CALCULATION_RECEIPT"}, {record["record_kind"] for record in records})
        self._assert_linked(records)
        for record in records:
            self.assertTrue(record["synthetic"])
            self.assertTrue(record["fixture_only"])
            self.assertEqual("ephemeral", record["persistence"])
        evidence = next(record for record in records if record["record_kind"] == "EVIDENCE_RECORD")
        self.assertEqual("SYNTHETIC_ONLY", evidence["evidence_status"])
        self.assertIsNone(evidence["evidence_material"])
        claim = next(record for record in records if record["record_kind"] == "CLAIM_RECORD")
        self.assertEqual("NOT_ASSESSED", claim["claim_status"])
        self.assertIsNone(claim["claim_material"])
        receipt = next(record for record in records if record["record_kind"] == "CALCULATION_RECEIPT")
        self.assertEqual("NOT_PERFORMED", receipt["calculation_status"])
        self.assertEqual("NOT_APPLICABLE", receipt["calculation_replay"])
        self.assertEqual("NONE", receipt["calculation_engine"])
        self.assertIsNone(receipt["calculation_output"])

    def test_same_kind_digest_mismatch_is_detected(self):
        records = copy.deepcopy(self._records())
        records[-1]["source_scope_digest"] = "sha256:" + "e" * 64
        with self.assertRaises(AssertionError):
            self._assert_linked(records)

    def test_schemas_close_unknown_fields_and_materialized_records(self):
        for name in ("evidence-record", "claim-record", "calculation-receipt"):
            schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("synthetic", schema["required"])
            self.assertEqual("string", schema["properties"]["request_id"]["type"])
            self.assertEqual("string", schema["properties"]["source_scope_digest"]["type"])


if __name__ == "__main__":
    unittest.main()
