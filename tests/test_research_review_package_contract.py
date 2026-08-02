import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sandbox/skill-incubator/schemas/research-review-package.schema.json"
CASES_PATH = ROOT / "tests/fixtures/research-review-package/cases.json"
DIGEST_FIELDS = ("subject_identity_digest", "requested_effects_digest", "source_scope_digest", "input_contract_digest", "evidence_set_digest", "claim_set_digest")


class ResearchReviewPackageContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def _package(self, name="not_provided"):
        base = copy.deepcopy(self.cases["packages"]["not_provided"])
        if name == "externally_supplied":
            override = self.cases["packages"][name]
            base["research_review_package"]["customer_review_status"] = override["customer_review_status"]
            base["research_review_package"]["valuation_material"] = override["valuation_material"]
        return base

    def _assert_linkage(self, bundle):
        package = bundle["research_review_package"]
        linkage = bundle["fixture_linkage"]
        self.assertEqual(package["request_id"], linkage["request_id"])
        for field in DIGEST_FIELDS:
            self.assertEqual(package[field], linkage[field], field)

    @staticmethod
    def _ids(entries, field):
        values = [entry[field] for entry in entries]
        if len(values) != len(set(values)):
            raise AssertionError(field)
        return set(values)

    def test_static_contract_discloses_only_non_authorizing_state(self):
        properties = self.schema["properties"]
        self.assertEqual("1.0.0", properties["schema_version"]["const"])
        self.assertEqual("RESEARCH_REVIEW_ONLY", properties["purpose"]["const"])
        for field, value in (("synthetic", True), ("fixture_only", True), ("persistence", "ephemeral"), ("financial_data_network_access", "NOT_PERFORMED"), ("runtime_execution", "NOT_IMPLEMENTED"), ("host_enforcement", "NOT_PROVEN"), ("external_action", "NONE"), ("investment_authorization", "NONE"), ("trade_authorization", "NONE")):
            self.assertEqual(value, properties[field]["const"], field)
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual("PASS", self.cases["contract_validation"])
        self.assertEqual("NOT_IMPLEMENTED", self.cases["runtime_execution"])
        self.assertEqual("NOT_PROVEN", self.cases["host_enforcement"])

    def test_fixture_linkage_is_test_only_and_all_six_digests_match(self):
        bundle = self._package()
        self._assert_linkage(bundle)
        self.assertNotIn("fixture_linkage", self.schema["properties"])
        for field in DIGEST_FIELDS:
            self.assertRegex(bundle["research_review_package"][field], r"^sha256:[0-9a-f]{64}$")
        bundle["fixture_linkage"]["claim_set_digest"] = "sha256:" + "0" * 64
        with self.assertRaises(AssertionError):
            self._assert_linkage(bundle)

    def test_claim_and_evidence_references_are_id_based_and_synthetic(self):
        package = self._package()["research_review_package"]
        evidence = self._ids(package["evidence_record_refs"], "evidence_record_id")
        support = self._ids(package["supporting_claim_refs"], "claim_id")
        counter = self._ids(package["strongest_counter_claim_refs"], "claim_id")
        self.assertTrue(evidence)
        self.assertTrue(support)
        self.assertTrue(counter)
        self.assertFalse(support & counter)
        for field in ("assumption_claim_refs", "conflict_claim_refs", "unknown_claim_refs", "falsification_claim_refs"):
            self._ids(package[field], "claim_id")
        duplicate = copy.deepcopy(package)
        duplicate["supporting_claim_refs"].append({"claim_id": "SYNTHETIC-CLAIM-001", "relevance": "MATERIAL"})
        with self.assertRaises(AssertionError):
            self._ids(duplicate["supporting_claim_refs"], "claim_id")
        overlap = copy.deepcopy(package)
        overlap["strongest_counter_claim_refs"] = [{"claim_id": "SYNTHETIC-CLAIM-001", "relevance": "MATERIAL"}]
        self.assertTrue(self._ids(overlap["supporting_claim_refs"], "claim_id") & self._ids(overlap["strongest_counter_claim_refs"], "claim_id"))

    def test_only_the_two_valuation_combinations_are_designed(self):
        for name, expected in (("not_provided", ("NOT_PROVIDED", "NONE", "NOT_APPLICABLE")), ("externally_supplied", ("EXTERNALLY_SUPPLIED_UNVERIFIED", "USER_SUPPLIED", "EXTERNALLY_SUPPLIED_UNVERIFIED"))):
            material = self._package(name)["research_review_package"]["valuation_material"]
            self.assertEqual(expected, (material["status"], material["provenance"], material["calculation_replay"]))
            self.assertIsNone(material["calculation_receipt_digest"])
        self.assertEqual(2, len(self.schema["$defs"]["valuationMaterial"]["oneOf"]))

    def test_schema_is_closed_and_has_no_runtime_surface(self):
        prohibited = {"buy", "sell", "hold", "rating", "target_price", "position_size", "portfolio_weight", "order", "broker", "account", "credential", "trade_instruction", "monitoring_schedule", "fixture_linkage"}
        self.assertFalse(prohibited & set(self.schema["properties"]))
        self.assertFalse(self.schema["$defs"]["review"]["additionalProperties"])
        self.assertEqual({"adversarial_review", "independent_review"}, set(self.schema["$defs"]["review"]["required"]))


if __name__ == "__main__":
    unittest.main()
