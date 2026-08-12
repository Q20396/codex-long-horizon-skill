"""Static K0-K5 knowledge-governance contract tests."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.validate_knowledge_governance_contracts import (
    _validate_payload,
    validate_contract_bundle,
    validate_fixture_case,
)


class _PassingDraft202012Gate:
    """Test-only gate for dependency-free behavioral tests.

    The production validator remains fail-closed when ``jsonschema`` is not
    installed.  This fixture only supplies the already-established successful
    Schema-gate precondition to tests that exercise cross-record behavior.
    Draft 2020-12 behavior itself is tested separately when the real engine is
    available.
    """

    def iter_errors(self, _record: object):
        return ()


class KnowledgeGovernanceContractTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def setUp(self) -> None:
        self._schema_gate_patcher = patch(
            "scripts.validate_knowledge_governance_contracts._load_draft202012_validator",
            return_value=_PassingDraft202012Gate(),
        )
        self._schema_gate_patcher.start()
        self.addCleanup(self._schema_gate_patcher.stop)

    def descriptor(self, kind: str = "ARCHITECTURE_DECISION") -> dict[str, object]:
        return {
            "knowledge_item_id": "KID-ABCD2345EFGH6723",
            "project_scope": "SINGLE_PROJECT_ONLY",
            "knowledge_kind": kind,
            "statement": "Synthetic knowledge statement",
            "classification": "FACT",
            "source_locator": None if kind == "OPEN_QUESTION" else {
                "relative_path": "docs/synthetic.md",
                "section_heading": "Decision",
            },
            "sensitivity_basis": "PROJECT_POLICY",
            "observed_at": "2030-01-01T00:00:00Z",
            "review_by": "2030-02-01",
            "retention_status": "EPHEMERAL_ONLY",
        }

    def request(self) -> dict[str, object]:
        return {
            "request_id": "KRR-ABCDEFGH23456723",
            "task_reference": "KRT-ABCDEFGH23456723",
            "authorization_reference": "KRA-ABCDEFGH23456723",
            "sensitivity_basis": "HUMAN_DECLARED",
            "target_locator": {"relative_path": "docs/synthetic-note.md", "section_heading": "Decision"},
            "requested_effect": "READ_ONE_DECLARED_NON_SENSITIVE_SECTION_ONLY",
            "requested_read_range": "EXACT_DECLARED_SECTION_ONLY",
            "request_evaluated_at": "2030-01-01T00:00:00Z",
            "proposed_expires_at": "2030-01-02T00:00:00Z",
        }

    def authorization(self) -> dict[str, object]:
        return {
            "authorization_id": "KRA-ABCDEFGH23456723",
            "request_reference": "KRR-ABCDEFGH23456723",
            "task_reference": "KRT-ABCDEFGH23456723",
            "effect": "READ_ONE_DECLARED_NON_SENSITIVE_SECTION_ONLY",
            "target_locator": {"relative_path": "docs/synthetic-note.md", "section_heading": "Decision"},
            "requested_read_range": "EXACT_DECLARED_SECTION_ONLY",
            "expires_at": "2030-01-03T00:00:00Z",
            "authorization_status": "GRANTED",
            "revoked_at": None,
        }

    def proposal(self) -> dict[str, object]:
        return {
            "proposal_id": "KWP-ABCDEFGH23456723",
            "task_reference": "KRT-ABCDEFGH23456723",
            "source_request_reference": "KRR-ABCDEFGH23456723",
            "proposed_target_path": "docs/synthetic-output.md",
            "proposed_effect": "WRITE_ONE_DECLARED_PROJECT_RELATIVE_FILE_ONLY",
            "proposed_change_summary": "Synthetic minimal change summary",
            "sensitivity_basis": "HUMAN_DECLARED",
            "proposed_expires_at": "2030-01-02T00:00:00Z",
        }

    def receipt(self, outcome: str, recorded_at: str) -> dict[str, object]:
        no_auth = outcome in {
            "NOT_EXECUTED", "BLOCKED_SENSITIVITY_UNKNOWN",
            "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID",
        }
        no_revocation = no_auth or outcome in {
            "BLOCKED_REQUEST_EXPIRED", "BLOCKED_AUTHORIZATION_EXPIRED",
        }
        return {
            "request_reference": "KRR-ABCDEFGH23456723",
            "task_reference": "KRT-ABCDEFGH23456723",
            "authorization_reference": "KRA-ABCDEFGH23456723",
            "outcome": outcome,
            "recorded_at": recorded_at,
            "authorization_expiry_at": None if no_auth else "2030-01-03T00:00:00Z",
            "revocation_checked_at": "NOT_APPLICABLE" if no_revocation else recorded_at,
            "revocation_checked_authorization_reference": (
                "NOT_APPLICABLE" if no_revocation else "KRA-ABCDEFGH23456723"
            ),
        }

    def test_all_six_knowledge_kinds_are_accepted_as_complete_synthetic_records(self) -> None:
        kinds = {
            "ARCHITECTURE_DECISION", "GOVERNANCE_BOUNDARY", "VERIFICATION_EVIDENCE",
            "GLOSSARY_ENTRY", "OPEN_QUESTION", "KNOWN_LIMITATION",
        }
        for kind in kinds:
            with self.subTest(kind=kind):
                result = validate_contract_bundle({
                    "synthetic": True,
                    "fixture_only": True,
                    "payload": {
                        "case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR",
                        "record": self.descriptor(kind),
                    },
                })
                self.assertEqual("ACCEPT", result["result"])

    def test_k3_ordered_first_match_prioritizes_authorization_expiry(self) -> None:
        evaluation_at = "2030-01-03T00:00:00Z"
        result = validate_contract_bundle({
            "synthetic": True,
            "fixture_only": True,
            "payload": {
                "case_subject": "K3_READ_EVALUATION",
                "request": self.request(),
                "authorization": self.authorization(),
                "receipt": self.receipt("BLOCKED_AUTHORIZATION_EXPIRED", evaluation_at),
                "evaluation_at": evaluation_at,
                "evaluator_ran": True,
                "future_execution_terminal_state": None,
            },
        })
        self.assertEqual("BLOCKED", result["result"])
        self.assertEqual("BLOCKED_AUTHORIZATION_EXPIRED", result["outcome"])

    def test_fixture_files_are_synthetic_deterministic_and_match_expectations(self) -> None:
        fixture_root = self.root / "tests/fixtures/knowledge-governance"
        case_ids: set[str] = set()
        subjects: set[str] = set()
        results: set[str] = set()
        for fixture_path in sorted(fixture_root.rglob("*.json")):
            for case in json.loads(fixture_path.read_text(encoding="utf-8")):
                self.assertNotIn(case["case_id"], case_ids)
                case_ids.add(case["case_id"])
                subjects.add(case["payload"]["case_subject"])
                results.add(case["expected_result"])
                first = validate_fixture_case(case)
                second = validate_fixture_case(copy.deepcopy(case))
                self.assertEqual(first, second)
                self.assertTrue(first["expectation_matches"], case["case_id"])
                self.assertEqual("NOT_IMPLEMENTED", first["runtime_execution"])
                self.assertEqual(
                    "CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED",
                    first["fixture_input_read"],
                )
                self.assertEqual("NOT_IMPLEMENTED", first["governed_target_io"])
                self.assertEqual("NOT_PROVEN", first["host_enforcement"])
                self.assertEqual("NONE", first["external_action"])
        self.assertEqual(50, len(case_ids))
        self.assertTrue({
            "KNOWLEDGE_ITEM_DESCRIPTOR", "K3_READ_EVALUATION",
            "K4_WRITE_EVALUATION", "K5_CAPABILITY_ATTEMPT", "K5_RUNTIME_SCENARIO",
            "K5_STATIC_SECURITY_RELATION", "K5_STATIC_RENDER_RISK",
        }.issubset(subjects))
        self.assertEqual(
            {"ACCEPT", "REJECT", "BLOCKED", "NOT_AUTHORIZED", "OUT_OF_SCOPE"},
            results,
        )

    def test_all_embedded_static_records_validate_against_draft_2020_12_when_available(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ModuleNotFoundError:
            self.skipTest("BLOCKED_UNVERIFIED: jsonschema is unavailable; no Schema behavior claim")

        schema = json.loads((
            self.root / "sandbox/skill-incubator/knowledge-governance-k6/knowledge-governance.schema.json"
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        record_subjects = {
            "request": "KNOWLEDGE_READ_REQUEST",
            "authorization": "AUTHORIZATION_RECORD",
            "receipt": "KNOWLEDGE_READ_RECEIPT",
            "proposal": "WRITE_PROPOSAL",
            "source_request": "KNOWLEDGE_READ_REQUEST",
            "human_disposition": "HUMAN_DISPOSITION",
        }
        fixture_root = self.root / "tests/fixtures/knowledge-governance"
        for fixture_path in sorted(fixture_root.rglob("*.json")):
            for case in json.loads(fixture_path.read_text(encoding="utf-8")):
                payload = case["payload"]
                for key, subject in record_subjects.items():
                    record = payload.get(key)
                    if record is not None:
                        with self.subTest(case=case["case_id"], record=key):
                            errors = list(validator.iter_errors(record))
                            static_result = _validate_payload({
                                "case_subject": subject,
                                "record": record,
                            })
                            if static_result["result"] == "ACCEPT":
                                self.assertEqual([], errors)
                            else:
                                self.assertTrue(errors)

                if payload.get("case_subject") in {
                    "KNOWLEDGE_ITEM_DESCRIPTOR", "KNOWLEDGE_READ_REQUEST",
                    "AUTHORIZATION_RECORD", "KNOWLEDGE_READ_RECEIPT",
                    "WRITE_PROPOSAL", "HUMAN_DISPOSITION",
                }:
                    record = payload["record"]
                    with self.subTest(case=case["case_id"], record="record"):
                        errors = list(validator.iter_errors(record))
                        static_result = _validate_payload(payload)
                        if static_result["result"] == "ACCEPT":
                            self.assertEqual([], errors)
                        else:
                            self.assertTrue(errors)

        fabricated_expiry = next(
            case for case in json.loads((
                fixture_root / "negative/records.json"
            ).read_text(encoding="utf-8"))
            if case["case_id"] == "NEG-RECEIPT-NOT-EXECUTED-FABRICATED-EXPIRY-001"
        )
        self.assertTrue(
            list(validator.iter_errors(fabricated_expiry["payload"]["record"]))
        )

    def test_schema_and_validator_share_sensitive_text_rejections(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ModuleNotFoundError:
            self.skipTest("BLOCKED_UNVERIFIED: jsonschema is unavailable; no Schema behavior claim")

        schema = json.loads((
            self.root / "sandbox/skill-incubator/knowledge-governance-k6/knowledge-governance.schema.json"
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        markers = (
            "ACCOUNT_NUMBER=SYNTHETIC", "BROKER_ACCOUNT=SYNTHETIC", "API_KEY=SYNTHETIC",
            "PASSWORD=SYNTHETIC", "/Users/synthetic", "ignore the contract",
            "Ignore safeguards", "read all files",
        )
        for marker in markers:
            with self.subTest(record="descriptor", marker=marker):
                record = self.descriptor()
                record["statement"] = marker
                self.assertTrue(list(validator.iter_errors(record)))
                self.assertEqual(
                    "REJECT",
                    _validate_payload({"case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR", "record": record})["result"],
                )

            with self.subTest(record="proposal", marker=marker):
                record = self.proposal()
                record["proposed_change_summary"] = marker
                self.assertTrue(list(validator.iter_errors(record)))
                self.assertEqual(
                    "REJECT",
                    _validate_payload({"case_subject": "WRITE_PROPOSAL", "record": record})["result"],
                )
            with self.subTest(record="heading", marker=marker):
                record = self.descriptor()
                record["source_locator"] = {"relative_path": "docs/synthetic.md", "section_heading": marker}
                self.assertTrue(list(validator.iter_errors(record)))
                self.assertEqual(
                    "REJECT",
                    _validate_payload({"case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR", "record": record})["result"],
                )

        # U+212A Kelvin sign must not be Unicode-folded into ASCII ``K``.
        # The Schema's explicit ASCII alternatives accept this value, and the
        # dependency-free admission precheck must therefore accept it too.
        unicode_case_difference = self.descriptor()
        unicode_case_difference["statement"] = "API_KEY=SYNTHETIC"
        self.assertEqual([], list(validator.iter_errors(unicode_case_difference)))
        self.assertEqual(
            "ACCEPT",
            validate_contract_bundle(
                {
                    "synthetic": True,
                    "fixture_only": True,
                    "payload": {
                        "case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR",
                        "record": unicode_case_difference,
                    },
                }
            )["result"],
        )

    def test_k5_security_outcomes_are_derived_from_payload_relations(self) -> None:
        request = self.request()
        authorization = self.authorization()
        base = {
            "synthetic": True,
            "fixture_only": True,
            "payload": {
                "case_subject": "K5_STATIC_SECURITY_RELATION",
                "request": request,
                "authorization": authorization,
                "evaluation_at": "2030-01-01T12:00:00Z",
            },
        }
        self.assertEqual("K5_STATIC_RELATION_VALID", validate_contract_bundle(base)["outcome"])

        id_mismatch = copy.deepcopy(base)
        id_mismatch["payload"]["authorization"]["authorization_id"] = "KRA-BCDEFGH234567234"
        self.assertEqual("BLOCKED_AUTHORIZATION_MISSING_OR_INVALID", validate_contract_bundle(id_mismatch)["outcome"])

        expired = copy.deepcopy(base)
        expired["payload"]["evaluation_at"] = "2030-01-03T00:00:00Z"
        self.assertEqual("BLOCKED_AUTHORIZATION_EXPIRED", validate_contract_bundle(expired)["outcome"])

        revoked = copy.deepcopy(base)
        revoked["payload"]["authorization"]["authorization_status"] = "REVOKED"
        revoked["payload"]["authorization"]["revoked_at"] = "2030-01-01T12:00:00Z"
        self.assertEqual("BLOCKED_AUTHORIZATION_REVOKED", validate_contract_bundle(revoked)["outcome"])

        unknown_sensitivity = copy.deepcopy(base)
        unknown_sensitivity["payload"]["request"]["sensitivity_basis"] = "UNKNOWN"
        self.assertEqual(
            "BLOCKED_SENSITIVITY_UNKNOWN",
            validate_contract_bundle(unknown_sensitivity)["outcome"],
        )

        request_expired = copy.deepcopy(base)
        request_expired["payload"]["evaluation_at"] = "2030-01-02T00:00:00Z"
        self.assertEqual(
            "BLOCKED_REQUEST_EXPIRED",
            validate_contract_bundle(request_expired)["outcome"],
        )

        evaluation_before_request = copy.deepcopy(base)
        evaluation_before_request["payload"]["evaluation_at"] = "2029-12-31T23:59:59Z"
        evaluation_before_result = validate_contract_bundle(evaluation_before_request)
        self.assertEqual(
            ("REJECT", "K3_EVALUATION_TIME_INVALID"),
            (evaluation_before_result["result"], evaluation_before_result["outcome"]),
        )

        expired_with_future_revocation = copy.deepcopy(base)
        expired_with_future_revocation["payload"]["evaluation_at"] = "2030-01-03T00:00:00Z"
        expired_with_future_revocation["payload"]["authorization"]["authorization_status"] = "REVOKED"
        expired_with_future_revocation["payload"]["authorization"]["revoked_at"] = "2030-01-04T00:00:00Z"
        self.assertEqual(
            "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID",
            validate_contract_bundle(expired_with_future_revocation)["outcome"],
        )

        render = {
            "synthetic": True,
            "fixture_only": True,
            "payload": {
                "case_subject": "K5_STATIC_RENDER_RISK",
                "protected_source_locator": "docs/synthetic.md",
                "protected_sensitive_marker": None,
                "attempted_value": "other-value",
            },
        }
        self.assertEqual("REJECT", validate_contract_bundle(render)["result"])

        contained_locator = copy.deepcopy(render)
        contained_locator["payload"]["attempted_value"] = "Summary: docs/synthetic.md"
        self.assertEqual("BLOCKED", validate_contract_bundle(contained_locator)["result"])
        self.assertEqual(
            "BLOCKED_RENDERING_RISK",
            validate_contract_bundle(contained_locator)["outcome"],
        )

    def test_schema_owned_acceptance_requires_draft_gate_and_untrusted_json_is_total(self) -> None:
        descriptor_bundle = {
            "synthetic": True,
            "fixture_only": True,
            "payload": {
                "case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR",
                "record": self.descriptor(),
            },
        }
        with patch(
            "scripts.validate_knowledge_governance_contracts._load_draft202012_validator",
            return_value=None,
        ):
            blocked = validate_contract_bundle(descriptor_bundle)
        self.assertEqual("BLOCKED", blocked["result"])
        self.assertEqual("SCHEMA_UNVERIFIED", blocked["outcome"])

        self.assertEqual("ACCEPT", validate_contract_bundle(descriptor_bundle)["result"])

        invalid_values = ([], {}, None, 1)
        for invalid in invalid_values:
            with self.subTest(case_subject=repr(invalid)):
                bundle = copy.deepcopy(descriptor_bundle)
                bundle["payload"]["case_subject"] = invalid
                self.assertEqual("REJECT", validate_contract_bundle(bundle)["result"])

        enum_records = (
            ("KNOWLEDGE_ITEM_DESCRIPTOR", self.descriptor(), "knowledge_kind"),
            ("KNOWLEDGE_ITEM_DESCRIPTOR", self.descriptor(), "classification"),
            ("KNOWLEDGE_ITEM_DESCRIPTOR", self.descriptor(), "sensitivity_basis"),
            ("KNOWLEDGE_READ_REQUEST", self.request(), "sensitivity_basis"),
            ("AUTHORIZATION_RECORD", self.authorization(), "authorization_status"),
            ("WRITE_PROPOSAL", self.proposal(), "proposed_effect"),
        )
        for subject, record, field in enum_records:
            for invalid in invalid_values:
                with self.subTest(subject=subject, field=field, value=repr(invalid)):
                    mutated = copy.deepcopy(record)
                    mutated[field] = invalid
                    result = validate_contract_bundle({
                        "synthetic": True,
                        "fixture_only": True,
                        "payload": {"case_subject": subject, "record": mutated},
                    })
                    self.assertEqual("REJECT", result["result"])

    def test_schema_is_json_with_six_closed_record_definitions(self) -> None:
        schema_path = self.root / "sandbox/skill-incubator/knowledge-governance-k6/knowledge-governance.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        records = {
            "KnowledgeItemDescriptor", "KnowledgeReadRequest", "AuthorizationRecord",
            "KnowledgeReadReceipt", "WriteProposal", "HumanDisposition",
        }
        self.assertTrue(records.issubset(schema["$defs"]))
        for name in records:
            self.assertIs(schema["$defs"][name]["additionalProperties"], False)
        self.assertEqual("NOT_IMPLEMENTED", schema["x-k6-boundary"]["runtime_execution"])
        self.assertEqual(
            "DRAFT202012_SCHEMA_ONLY",
            schema["x-k6-boundary"]["local_acceptance_authority"],
        )
        self.assertEqual(
            "CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED",
            schema["x-k6-boundary"]["fixture_input_read"],
        )
        self.assertEqual("NOT_IMPLEMENTED", schema["x-k6-boundary"]["governed_target_io"])
        self.assertEqual("NOT_AUTHORIZED", schema["x-k6-boundary"]["persistence"])
        self.assertEqual("NOT_PROVEN", schema["x-k6-boundary"]["host_enforcement"])

        internal_refs = {
            node["$ref"]
            for node in self._walk_json(schema)
            if isinstance(node, dict) and isinstance(node.get("$ref"), str)
        }
        for reference in internal_refs:
            self.assertTrue(reference.startswith("#/$defs/"), reference)
            self.assertIn(reference.removeprefix("#/$defs/"), schema["$defs"])

    def _walk_json(self, value: object):
        yield value
        if isinstance(value, dict):
            for child in value.values():
                yield from self._walk_json(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._walk_json(child)

    def test_candidate_schema_does_not_rewrite_the_formal_release_inventory(self) -> None:
        formal_validator = (
            self.root / "scripts/validate_formal_schemas.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("knowledge-governance.schema.json", formal_validator)

    def test_validator_has_no_target_io_network_process_renderer_or_writer_import(self) -> None:
        path = self.root / "scripts/validate_knowledge_governance_contracts.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertTrue(imported_modules.isdisjoint({"os", "socket", "subprocess", "urllib", "requests"}))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(called_names.isdisjoint({"open", "exec", "eval", "compile", "input"}))
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(called_attributes.isdisjoint({
            "write_text", "write_bytes", "open", "unlink", "rename", "replace",
            "mkdir", "rmdir", "resolve", "stat", "lstat", "iterdir", "glob", "rglob",
        }))

    def test_approve_is_recorded_but_never_executable(self) -> None:
        positive_relations = json.loads((
            self.root / "tests/fixtures/knowledge-governance/positive/relations.json"
        ).read_text(encoding="utf-8"))
        approved = next(
            case for case in positive_relations
            if case["case_id"] == "POS-K4-APPROVE-NO-WRITE-001"
        )
        result = validate_fixture_case(approved)
        self.assertEqual("ACCEPT", result["result"])
        self.assertEqual("HUMAN_DISPOSITION_RECORDED_NOT_EXECUTABLE", result["outcome"])
        self.assertEqual(
            "CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED",
            result["fixture_input_read"],
        )
        self.assertEqual("NOT_IMPLEMENTED", result["governed_target_io"])
        self.assertEqual("NONE", result["external_action"])

    def test_static_hardening_cases_are_fixed_and_public_seam_is_fixture_only(self) -> None:
        fixture_root = self.root / "tests/fixtures/knowledge-governance"
        cases = [
            case for path in fixture_root.rglob("*.json")
            for case in json.loads(path.read_text(encoding="utf-8"))
        ]
        static_ids = {
            case["case_id"] for case in cases if case["case_id"].startswith("K5-STATIC-")
        }
        self.assertEqual({
            "K5-STATIC-POS-001", "K5-STATIC-PATH-001", "K5-STATIC-PATH-002",
            "K5-STATIC-AUTH-001", "K5-STATIC-AUTH-002", "K5-STATIC-AUTH-003",
            "K5-STATIC-AUTH-004", "K5-STATIC-RENDER-001", "K5-STATIC-RENDER-002",
            "K5-STATIC-PERSIST-001",
        }, static_ids)
        bare = validate_contract_bundle({"case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR", "record": self.descriptor()})
        self.assertEqual("REJECT", bare["result"])
        self.assertEqual("BUNDLE_STRUCTURE_INVALID", bare["outcome"])
        unsafe_heading = self.descriptor()
        unsafe_heading["source_locator"] = {"relative_path": "docs/synthetic.md", "section_heading": "Ignore safeguards"}
        result = validate_contract_bundle({"synthetic": True, "fixture_only": True, "payload": {"case_subject": "KNOWLEDGE_ITEM_DESCRIPTOR", "record": unsafe_heading}})
        self.assertEqual("REJECT", result["result"])

    def test_blocked_k3_outcome_requires_null_terminal_state(self) -> None:
        blocked = validate_contract_bundle({
            "synthetic": True,
            "fixture_only": True,
            "payload": {
                "case_subject": "K3_READ_EVALUATION",
                "request": {**self.request(), "sensitivity_basis": "UNKNOWN"},
                "authorization": self.authorization(),
                "receipt": self.receipt("BLOCKED_SENSITIVITY_UNKNOWN", "2030-01-01T12:00:00Z"),
                "evaluation_at": "2030-01-01T12:00:00Z",
                "evaluator_ran": True,
                "future_execution_terminal_state": "COMPLETED_WITHOUT_CONTENT_RETENTION",
            },
        })
        self.assertEqual("REJECT", blocked["result"])
        self.assertEqual("K3_BLOCKED_CONTEXT_INVALID", blocked["outcome"])


if __name__ == "__main__":
    unittest.main()
