#!/usr/bin/env python3
"""Unit tests for the dependency-free candidate-intake validator."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


VALIDATOR_PATH = Path(__file__).with_name("validate_candidate_intake.py")
SPEC = importlib.util.spec_from_file_location("candidate_intake_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def valid_row(**changes: str) -> dict[str, str]:
    row = {
        "pattern_id": "PAT-001",
        "name": "Example",
        "group": "team",
        "classification": "customer_provided_capability_pattern",
        "capability_family": "FAMILY-001",
        "existing_experiment": "MAD-SKILL-008",
        "overlap_score": "90",
        "overlap_type": "full",
        "primary_gap_owner": "MAD-SKILL-008",
        "routing_allowed": "true",
        "unique_gap": "No identified design gap",
        "proposed_action": "map_to_existing_experiment",
        "rationale": "Test fixture",
        "evidence_contract": "candidate-intake/base-experiment-contracts/MAD-SKILL-008.json",
        "evidence_strength": "strong",
        "source_status": "customer_provided_unverified",
    }
    row.update(changes)
    return row


class CandidateIntakeValidatorTests(unittest.TestCase):
    def test_current_repository_data_validates(self) -> None:
        root = Path(__file__).resolve().parents[4]
        self.assertEqual([], validator.validate_root(root))

    def test_valid_row(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
        self.assertEqual([], validator.validate_pattern_rows(rows))

    def test_missing_column_is_rejected(self) -> None:
        text = "\t".join(validator.PATTERN_HEADERS[:-1]) + "\nvalue\n"
        _, errors = validator.parse_tsv_text(text, validator.PATTERN_HEADERS, "fixture")
        self.assertTrue(errors)

    def test_excess_column_is_rejected(self) -> None:
        text = "\t".join(validator.PATTERN_HEADERS) + "\n" + "\t".join(["x"] * (len(validator.PATTERN_HEADERS) + 1))
        _, errors = validator.parse_tsv_text(text, validator.PATTERN_HEADERS, "fixture")
        self.assertTrue(errors)

    def test_duplicate_pattern_id_is_rejected(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 40)] + [valid_row(pattern_id="PAT-001")]
        self.assertTrue(any("duplicate" in item for item in validator.validate_pattern_rows(rows)))

    def test_invalid_group_is_rejected(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
        rows[0]["group"] = "advanced"
        self.assertTrue(any("invalid group" in item for item in validator.validate_pattern_rows(rows)))

    def test_invalid_action_is_rejected(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
        rows[0]["proposed_action"] = "install_now"
        self.assertTrue(any("invalid proposed action" in item for item in validator.validate_pattern_rows(rows)))

    def test_invalid_overlap_type_is_rejected(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
        rows[0]["overlap_type"] = "mostly"
        self.assertTrue(any("invalid overlap type" in item for item in validator.validate_pattern_rows(rows)))

    def test_non_boolean_routing_is_rejected(self) -> None:
        rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
        rows[0]["routing_allowed"] = "yes"
        self.assertTrue(any("routing_allowed" in item for item in validator.validate_pattern_rows(rows)))

    def test_out_of_range_scores_are_rejected(self) -> None:
        for value in ("-1", "101"):
            rows = [valid_row(pattern_id=f"PAT-{number:03d}") for number in range(1, 41)]
            rows[0]["overlap_score"] = value
            self.assertTrue(any("0..100" in item for item in validator.validate_pattern_rows(rows)))

    def test_unverified_source_cannot_claim_sha(self) -> None:
        payload = {"status": "locked", "sources": []}
        for number in range(10):
            payload["sources"].append({"source_id": f"blocked-{number}", "status": "locked", "verification_status": "verification_blocked", "full_commit_sha": None, "code_import_allowed": False, "runtime_execution_allowed": False, "network_execution_allowed": False})
        for number in range(5):
            payload["sources"].append({"source_id": f"ambiguous-{number}", "status": "locked", "verification_status": "ambiguous_source", "full_commit_sha": None, "code_import_allowed": False, "runtime_execution_allowed": False, "network_execution_allowed": False})
        payload["sources"][0]["full_commit_sha"] = "a" * 40
        self.assertTrue(any("commit SHA" in item for item in validator.validate_source_payload(payload)))

    def test_candidate_only_registration_is_rejected(self) -> None:
        candidate_text = "\n".join(["status: `candidate_only`", "registered_experiment: `false`", "implementation_exists: `false`", "execution_authorized: `false`", "customer_decision: `not_approved`"])
        errors = validator.validate_candidate_only_state({"MAD-SKILL-012-candidate": candidate_text}, {"MAD-SKILL-012"})
        self.assertTrue(any("present in experiment registry" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
