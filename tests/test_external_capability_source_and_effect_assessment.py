"""Static-only tests for External Capability Source and Effect Assessment."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts.validate_external_capability_source_and_effect_assessment import (
    validate_static_assessment,
)


class ExternalCapabilitySourceEffectAssessmentTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    fixture_root = root / "tests/fixtures/external-capability-source-effect-assessment"
    schema_path = root / (
        "sandbox/skill-incubator/external-capability-source-effect-assessment/"
        "external-capability-source-effect-assessment.schema.json"
    )
    design_path = root / (
        "sandbox/skill-incubator/architecture/"
        "external-capability-source-and-effect-assessment.md"
    )

    def _fixture(self, category: str) -> dict[str, object]:
        return json.loads((self.fixture_root / category / "cases.json").read_text(encoding="utf-8"))

    def _baselines(self) -> dict[str, dict[str, object]]:
        return self._fixture("positive")["baselines"]  # type: ignore[return-value,index]

    def _cases(self, category: str) -> list[dict[str, object]]:
        return self._fixture(category)["cases"]  # type: ignore[return-value,index]

    @staticmethod
    def _matrix_literal(value: object, *, missing: bool = False) -> str:
        if missing:
            return "missing"
        if type(value) is list:
            return "[" + ",".join(str(item) for item in value) + "]"
        if type(value) is bool:
            return str(value).lower()
        return str(value)

    def _design_matrix(self) -> dict[str, dict[str, str]]:
        rows: dict[str, dict[str, str]] = {}
        in_matrix = False
        for line in self.design_path.read_text(encoding="utf-8").splitlines():
            if line == "| Future synthetic case | Baseline ID | Single field mutation | Before | After | Unique expected outcome | Unique reason category |":
                in_matrix = True
                continue
            if not in_matrix:
                continue
            if line.startswith("| ---"):
                continue
            if not line.startswith("|"):
                break
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            self.assertEqual(7, len(cells))
            rows[cells[0]] = {
                "baseline_id": cells[1],
                "field": cells[2],
                "before": cells[3].replace(" ", ""),
                "after": cells[4].replace(" ", ""),
                "outcome": cells[5],
                "reason": cells[6],
            }
        self.assertTrue(rows, "design fixture matrix not found")
        return rows

    @staticmethod
    def _value(record: dict[str, object], dotted: str) -> object:
        value: object = record
        for segment in dotted.split("."):
            value = value[segment]  # type: ignore[index]
        return value

    @staticmethod
    def _set_value(record: dict[str, object], dotted: str, value: object) -> None:
        parent: object = record
        segments = dotted.split(".")
        for segment in segments[:-1]:
            parent = parent[segment]  # type: ignore[index]
        parent[segments[-1]] = value  # type: ignore[index]

    @staticmethod
    def _remove_value(record: dict[str, object], dotted: str) -> None:
        parent: object = record
        segments = dotted.split(".")
        for segment in segments[:-1]:
            parent = parent[segment]  # type: ignore[index]
        del parent[segments[-1]]  # type: ignore[index]

    @classmethod
    def _changed_fields(cls, before: object, after: object, prefix: str = "") -> list[str]:
        if type(before) is not type(after):
            return [prefix]
        if type(before) is dict:
            fields: list[str] = []
            for key in sorted(set(before) | set(after)):  # type: ignore[arg-type]
                child = key if not prefix else f"{prefix}.{key}"
                if key not in before or key not in after:  # type: ignore[operator]
                    fields.append(child)
                else:
                    fields.extend(cls._changed_fields(before[key], after[key], child))  # type: ignore[index]
            return fields
        return [prefix] if before != after else []

    def _record_for(self, case: dict[str, object], *, include_result: bool = True) -> dict[str, object]:
        record = copy.deepcopy(self._baselines()[case["baseline_id"]])  # type: ignore[index]
        mutation = case["mutation"]  # type: ignore[index]
        if mutation is not None:
            field = mutation["field"]  # type: ignore[index]
            self.assertEqual(mutation["before"], self._value(record, field))  # type: ignore[index]
            if mutation["operation"] == "remove":  # type: ignore[index]
                self._remove_value(record, field)
            else:
                self._set_value(record, field, mutation["after"])  # type: ignore[index]
        declared_result = case["declared_result"]  # type: ignore[index]
        if include_result and declared_result is not None:
            record["planned_outcome"] = declared_result["planned_outcome"]  # type: ignore[index]
            record["reason_category"] = declared_result["reason_category"]  # type: ignore[index]
        return record

    def test_fixture_matrix_is_synthetic_complete_and_single_mutation(self) -> None:
        positive = self._cases("positive")
        negative = self._cases("negative")
        baselines = self._baselines()
        case_ids = [case["case_id"] for case in positive + negative]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(
            {
                "MISSING-SOURCE-REFERENCE", "UNKNOWN-SOURCE-CLASS", "UNKNOWN-DECLARED-EFFECT",
                "DUPLICATE-REQUESTED-EFFECT", "DECLARED-OBSERVED-CONFUSION",
                "OBSERVED-AUTHORIZED-CONFUSION", "UNKNOWN-STATIC-INDICATOR",
                "DUPLICATE-STATIC-INDICATOR", "HOST-ENFORCEMENT-MAP-MISMATCH",
                "INDICATOR-NON-ARRAY",
                "PLANNED-OUTCOME-MISMATCH", "REASON-CATEGORY-MISMATCH",
                "REQUESTED-EFFECT-BINDING-MISMATCH", "AUTHORIZED-NOT-REQUESTED",
                "EXPIRED-OPERATION-BINDING", "REVOKED-OPERATION-BINDING",
                "EFFECT-EXPANSION", "RENDERER-RETENTION-RISK",
                "HOST-REQUIRED-UNPROVEN", "HOST-REQUIRED-NOT-APPLICABLE",
            },
            {case["case_id"] for case in negative},
        )
        for case in positive + negative:
            self.assertIs(case["synthetic"], True)
            self.assertIs(case["fixture_only"], True)
            self.assertIn(case["baseline_id"], baselines)
        design_text = self.design_path.read_text(encoding="utf-8")
        self.assertIn("positive fixture `baselines` object", design_text)
        self.assertIn("immutable baseline authority", design_text)
        for baseline_id in baselines:
            self.assertIn(f"`{baseline_id}`", design_text)
        design_matrix = self._design_matrix()
        self.assertEqual(
            {case["case_id"].lower() for case in negative},
            set(design_matrix),
        )
        for case in positive:
            self.assertIsNone(case["mutation"])
            self.assertEqual(baselines[case["baseline_id"]], self._record_for(case, include_result=False))
        for case in negative:
            mutation = case["mutation"]  # type: ignore[index]
            self.assertIsNotNone(mutation)
            before = copy.deepcopy(baselines[case["baseline_id"]])
            after = self._record_for(case, include_result=False)
            field = mutation["field"]  # type: ignore[index]
            if mutation["operation"] == "remove":  # type: ignore[index]
                self.assertNotIn(field.split(".")[-1], after)
            else:
                self.assertEqual(mutation["after"], self._value(after, field))  # type: ignore[index]
            self.assertEqual([field], self._changed_fields(before, after))
            design_row = design_matrix[case["case_id"].lower()]
            self.assertEqual(case["baseline_id"], design_row["baseline_id"])
            self.assertEqual(field, design_row["field"])
            self.assertEqual(
                self._matrix_literal(mutation["before"]),  # type: ignore[index]
                design_row["before"],
            )
            self.assertEqual(
                self._matrix_literal(
                    mutation["after"],  # type: ignore[index]
                    missing=mutation["operation"] == "remove",  # type: ignore[index]
                ),
                design_row["after"],
            )
            self.assertEqual(case["expected_outcome"], design_row["outcome"])
            self.assertEqual(case["expected_reason_category"], design_row["reason"])

    def test_draft_2020_12_validates_every_materialized_synthetic_fixture_when_available(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ModuleNotFoundError:
            self.skipTest("BLOCKED_UNVERIFIED: jsonschema unavailable")
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for case in self._cases("positive") + self._cases("negative"):
            with self.subTest(case=case["case_id"]):
                errors = list(validator.iter_errors(self._record_for(case)))
                if case["expected_schema_valid"]:
                    self.assertEqual([], errors)
                else:
                    self.assertTrue(errors)

    def test_validator_matches_every_schema_valid_materialized_fixture(self) -> None:
        for case in self._cases("positive") + self._cases("negative"):
            result = validate_static_assessment(
                self._record_for(case), schema_gate_passed=case["expected_schema_valid"]
            )
            with self.subTest(case=case["case_id"]):
                self.assertEqual(case["expected_outcome"], result["outcome"])
                self.assertEqual(case["expected_reason_category"], result["reason_category"])
                self.assertEqual("NOT_IMPLEMENTED", result["runtime_execution"])
                self.assertEqual("NOT_IMPLEMENTED", result["governed_target_io"])
                self.assertEqual("NOT_IMPLEMENTED", result["network"])
                self.assertEqual("NOT_PROVEN", result["host_enforcement"])
                self.assertEqual("NONE", result["external_action"])

    def test_contradictory_evidence_is_priority_two_not_schema_failure(self) -> None:
        case = next(case for case in self._cases("negative") if case["case_id"] == "RENDERER-RETENTION-RISK")
        record = self._record_for(case)
        record["evidence_minimum"]["retention_classification"] = "CONTRADICTORY"  # type: ignore[index]
        record["planned_outcome"] = "BLOCKED"
        record["reason_category"] = "SOURCE_OR_SENSITIVITY_UNKNOWN"
        result = validate_static_assessment(record, schema_gate_passed=True)
        self.assertEqual(("BLOCKED", "SOURCE_OR_SENSITIVITY_UNKNOWN"), (result["outcome"], result["reason_category"]))

    def test_schema_gate_is_required(self) -> None:
        record = self._record_for(self._cases("positive")[0])
        result = validate_static_assessment(record, schema_gate_passed=False)
        self.assertEqual(("BLOCKED", "STRUCTURE_OR_REFERENCE_INVALID"), (result["outcome"], result["reason_category"]))


if __name__ == "__main__":
    unittest.main()
