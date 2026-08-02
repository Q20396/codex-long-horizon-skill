import copy
import json
from pathlib import Path
import unittest

from scripts import validate_formal_schemas as formal


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sandbox/skill-incubator/schemas/research-review-package.schema.json"
CASES_PATH = ROOT / "tests/fixtures/research-review-package/cases.json"
DIGEST_FIELDS = (
    "subject_identity_digest",
    "requested_effects_digest",
    "source_scope_digest",
    "input_contract_digest",
    "evidence_set_digest",
    "claim_set_digest",
)
DIGEST_MISMATCH_LABELS = {
    "subject_identity_digest": "SUBJECT_IDENTITY_DIGEST_MISMATCH",
    "requested_effects_digest": "REQUESTED_EFFECTS_DIGEST_MISMATCH",
    "source_scope_digest": "SOURCE_SCOPE_DIGEST_MISMATCH",
    "input_contract_digest": "INPUT_CONTRACT_DIGEST_MISMATCH",
    "evidence_set_digest": "EVIDENCE_SET_DIGEST_MISMATCH",
    "claim_set_digest": "CLAIM_SET_DIGEST_MISMATCH",
}


class ResearchReviewPackageContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _apply_mutations(record, mutations):
        result = copy.deepcopy(record)
        for mutation in mutations:
            parts = mutation["path"].strip("/").split("/")
            parent = result
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            leaf = parts[-1]
            if mutation["op"] == "set":
                if isinstance(parent, list):
                    parent[int(leaf)] = copy.deepcopy(mutation["value"])
                else:
                    parent[leaf] = copy.deepcopy(mutation["value"])
            elif mutation["op"] == "append":
                target = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
                target.append(copy.deepcopy(mutation["value"]))
            elif mutation["op"] == "delete":
                if isinstance(parent, list):
                    del parent[int(leaf)]
                else:
                    del parent[leaf]
            else:
                raise AssertionError(f"unknown fixture operation: {mutation['op']}")
        return result

    def _bundle(self, mutations=()):
        return self._apply_mutations(self.cases["base_record"], mutations)

    @staticmethod
    def _ids(entries, field, label):
        values = [entry[field] for entry in entries]
        if len(values) != len(set(values)):
            raise AssertionError(label)
        return set(values)

    def _assert_linkage(self, bundle):
        package = bundle["research_review_package"]
        linkage = bundle["fixture_linkage"]
        if package["request_id"] != linkage["request_id"]:
            raise AssertionError("REQUEST_ID_LINKAGE_MISMATCH")
        for field, label in DIGEST_MISMATCH_LABELS.items():
            if package[field] != linkage[field]:
                raise AssertionError(label)

    def _assert_static_constraints(self, bundle):
        self._assert_linkage(bundle)
        package = bundle["research_review_package"]
        self._ids(
            package["evidence_record_refs"],
            "evidence_record_id",
            "EVIDENCE_REFERENCE_DUPLICATE",
        )
        support = self._ids(
            package["supporting_claim_refs"],
            "claim_id",
            "CLAIM_REFERENCE_DUPLICATE",
        )
        counter = self._ids(
            package["strongest_counter_claim_refs"],
            "claim_id",
            "CLAIM_REFERENCE_DUPLICATE",
        )
        for field in (
            "assumption_claim_refs",
            "conflict_claim_refs",
            "unknown_claim_refs",
            "falsification_claim_refs",
        ):
            self._ids(package[field], "claim_id", "CLAIM_REFERENCE_DUPLICATE")
        if support & counter:
            raise AssertionError("SUPPORT_COUNTER_CLAIM_OVERLAP")

    def test_static_contract_discloses_only_non_authorizing_state(self):
        properties = self.schema["properties"]
        self.assertEqual("1.0.0", properties["schema_version"]["const"])
        self.assertEqual("RESEARCH_REVIEW_ONLY", properties["purpose"]["const"])
        for field, value in (
            ("synthetic", True),
            ("fixture_only", True),
            ("persistence", "ephemeral"),
            ("financial_data_network_access", "NOT_PERFORMED"),
            ("runtime_execution", "NOT_IMPLEMENTED"),
            ("host_enforcement", "NOT_PROVEN"),
            ("external_action", "NONE"),
            ("investment_authorization", "NONE"),
            ("trade_authorization", "NONE"),
        ):
            self.assertEqual(value, properties[field]["const"], field)
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual("PASS", self.cases["contract_validation"])
        self.assertEqual("NOT_IMPLEMENTED", self.cases["runtime_execution"])
        self.assertEqual("NOT_PROVEN", self.cases["host_enforcement"])

    def test_positive_fixtures_cover_both_valuation_forms_and_all_review_statuses(self):
        statuses = set()
        valuation_forms = set()
        for case in self.cases["positive_cases"]:
            bundle = self._bundle(case["mutations"])
            self._assert_static_constraints(bundle)
            package = bundle["research_review_package"]
            statuses.add(package["customer_review_status"])
            material = package["valuation_material"]
            valuation_forms.add(
                (material["status"], material["provenance"], material["calculation_replay"])
            )
            self.assertIsNone(material["calculation_receipt_digest"])
        self.assertEqual(
            {"DRAFT_FOR_REVIEW", "MORE_EVIDENCE_NEEDED", "READY_FOR_CUSTOMER_REVIEW", "BLOCKED"},
            statuses,
        )
        self.assertEqual(
            {
                ("NOT_PROVIDED", "NONE", "NOT_APPLICABLE"),
                (
                    "EXTERNALLY_SUPPLIED_UNVERIFIED",
                    "USER_SUPPLIED",
                    "EXTERNALLY_SUPPLIED_UNVERIFIED",
                ),
            },
            valuation_forms,
        )

    def test_static_negative_fixtures_reject_id_and_linkage_violations(self):
        for case in self.cases["static_negative_cases"]:
            with self.subTest(case=case["case_id"]):
                with self.assertRaisesRegex(AssertionError, case["expected_label"]):
                    self._assert_static_constraints(self._bundle(case["mutations"]))

    def test_formal_fixture_registration_is_complete(self):
        name = "research-review-package.schema.json"
        self.assertIn(name, formal.FIXTURE_VALIDATED_SCHEMAS)
        self.assertNotIn(name, formal.SYNTAX_ONLY_SCHEMAS)
        positives, negatives = formal.materialized_fixture_cases()
        self.assertEqual([], formal.validate_fixture_coverage(positives, negatives))
        self.assertGreaterEqual(sum(item[0] == name for item in positives), 4)
        self.assertGreaterEqual(sum(item[0] == name for item in negatives), 20)

    def test_schema_is_closed_and_has_no_runtime_surface(self):
        prohibited = {
            "buy", "sell", "hold", "rating", "target_price", "position_size",
            "portfolio_weight", "order_quantity", "broker", "account", "credentials",
            "trade_instruction", "execution_instruction", "automatic_notification",
            "monitoring_schedule", "fixture_linkage",
        }
        self.assertFalse(prohibited & set(self.schema["properties"]))
        self.assertFalse(self.schema["$defs"]["review"]["additionalProperties"])
        self.assertEqual(
            {"adversarial_review", "independent_review"},
            set(self.schema["$defs"]["review"]["required"]),
        )


if __name__ == "__main__":
    unittest.main()
