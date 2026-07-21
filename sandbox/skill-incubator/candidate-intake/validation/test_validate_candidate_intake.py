"""Negative contract coverage for locked routing and evidence bindings."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import validate_candidate_intake as intake
import validate_candidate_states as states
import validate_capability_families as families
import validate_proposal_evidence as proposal
import validate_schema_declarations as schemas


ROOT = HERE.parents[3]


def cloned_root() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    shutil.copytree(ROOT / "sandbox", root / "sandbox")
    return temporary, root


def rewrite_tsv(path: Path, mutate) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    headers = list(rows[0])
    mutate(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class RoutingAndEvidenceContractTests(unittest.TestCase):
    def test_current_repository_validates(self) -> None:
        self.assertEqual([], intake.validate_root(ROOT))
        self.assertEqual([], states.validate_root(ROOT))
        self.assertEqual([], families.validate_root(ROOT))
        self.assertEqual([], proposal.validate_root(ROOT))
        self.assertEqual([], schemas.validate_root(ROOT))

    def test_fake_existing_experiment_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(existing_experiment="MAD-SKILL-999"))
        self.assertTrue(any("existing_experiment" in item for item in intake.validate_root(root)))

    def test_contract_filename_mismatch_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(evidence_contract="candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"))
        self.assertTrue(any("evidence_contract" in item for item in intake.validate_root(root)))

    def test_contract_internal_id_mismatch_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        payload = json.loads(path.read_text())
        payload["experiment_id"] = "MAD-SKILL-002"
        path.write_text(json.dumps(payload))
        self.assertTrue(any("experiment_id" in item for item in intake.validate_root(root)))

    def test_contract_proposal_path_mismatch_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        payload = json.loads(path.read_text())
        payload["source_proposal_path"] = "sandbox/skill-incubator/experiments/MAD-SKILL-002/proposal.md"
        path.write_text(json.dumps(payload))
        self.assertTrue(any("source_proposal_path" in item for item in intake.validate_root(root)))

    def test_contract_proposal_sha_mismatch_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        payload = json.loads(path.read_text())
        payload["source_proposal_sha256"] = "0" * 64
        path.write_text(json.dumps(payload))
        self.assertTrue(any("source_proposal_sha256" in item for item in intake.validate_root(root)))

    def test_contract_unsafe_network_permission_is_rejected_after_hash_recalculation(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        contract_path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        contract = json.loads(contract_path.read_text())
        contract["permissions"]["network"] = True
        contract_path.write_text(json.dumps(contract))
        digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        rewrite_tsv(
            root / "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv",
            lambda rows: [row.update(contract_sha256=digest) for row in rows if row["proposed_existing_experiment"] == "MAD-SKILL-001"],
        )
        self.assertTrue(any("permissions.network" in item for item in intake.validate_root(root)))

    def test_contract_permission_structure_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        payload = json.loads(path.read_text())
        payload["permissions"]["write"] = "not-a-list"
        path.write_text(json.dumps(payload))
        self.assertTrue(any("permissions.write" in item for item in intake.validate_root(root)))

    def test_contract_non_string_permission_path_is_rejected_without_crashing(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        payload = json.loads(path.read_text())
        payload["permissions"]["read"] = [{"unsafe": "shape"}]
        path.write_text(json.dumps(payload))
        self.assertTrue(any("permissions.read" in item for item in intake.validate_root(root)))

    def test_full_mapping_without_covered_pattern_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-008.json"
        payload = json.loads(path.read_text())
        payload["covered_patterns"] = []
        path.write_text(json.dumps(payload))
        self.assertTrue(any("covered_patterns" in item for item in intake.validate_root(root)))

    def test_full_mapping_requires_existing_experiment_and_map_action(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(
            root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv",
            lambda rows: next(row for row in rows if row["overlap_type"] == "full").update(existing_experiment="", proposed_action="candidate_extension"),
        )
        errors = intake.validate_root(root)
        self.assertTrue(any("base experiment for full overlap" in item for item in errors))
        self.assertTrue(any("map_to_existing_experiment for full overlap" in item for item in errors))

    def test_no_overlap_cannot_claim_existing_experiment(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(
            root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv",
            lambda rows: next(row for row in rows if row["overlap_type"] == "none").update(existing_experiment="MAD-SKILL-001"),
        )
        self.assertTrue(any("empty for no overlap" in item for item in intake.validate_root(root)))

    def test_proposed_action_relationships_are_rejected_when_inconsistent(self) -> None:
        cases = (
            ("candidate_extension", {"existing_experiment": ""}, "required for candidate_extension"),
            ("candidate_new_experiment", {"primary_gap_owner": "separate-skill"}, "candidate design owner or unresolved"),
            ("separate_skill", {"primary_gap_owner": "unresolved"}, "separate-skill for separate_skill action"),
        )
        for action, update, expected in cases:
            with self.subTest(action=action):
                temporary, root = cloned_root()
                self.addCleanup(temporary.cleanup)

                def mutate(rows: list[dict[str, str]]) -> None:
                    row = next(item for item in rows if item["proposed_action"] == action)
                    row.update(update)

                rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", mutate)
                self.assertTrue(any(expected in item for item in intake.validate_root(root)))

    def test_partial_mapping_without_owner_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(primary_gap_owner=""))
        self.assertTrue(any("primary_gap_owner" in item for item in intake.validate_root(root)))

    def test_candidate_design_owner_is_allowed_but_state_id_is_not(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)

        def set_owner(rows, owner: str) -> None:
            row = next(row for row in rows if row["overlap_type"] == "partial")
            row["primary_gap_owner"] = owner

        paths = (
            "capability-patterns.tsv",
            "existing-experiment-map.tsv",
            "deduplication-evidence.tsv",
        )
        for name in paths:
            rewrite_tsv(
                root / f"sandbox/skill-incubator/candidate-intake/{name}",
                lambda rows: set_owner(rows, "MAD-SKILL-012-candidate"),
            )
        self.assertEqual([], intake.validate_root(root))
        for name in paths:
            rewrite_tsv(
                root / f"sandbox/skill-incubator/candidate-intake/{name}",
                lambda rows: set_owner(rows, "MAD-SKILL-012"),
            )
        self.assertTrue(any("primary_gap_owner" in item for item in intake.validate_root(root)))

    def test_candidate_in_registry_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/experiments/registry.json"
        payload = json.loads(path.read_text())
        payload["experiments"].append({"experiment_id": "MAD-SKILL-012"})
        path.write_text(json.dumps(payload))
        self.assertTrue(any("registry" in item for item in states.validate_root(root)))

    def test_locked_routing_true_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(execution_routing_allowed="true"))
        self.assertTrue(any("execution_routing_allowed" in item for item in intake.validate_root(root)))

    def test_verification_blocked_recommendation_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        def mutate(rows):
            row = next(row for row in rows if row["source_status"] == "verification_blocked")
            row["recommendation_eligible"] = "true"
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", mutate)
        self.assertTrue(any("recommendation_eligible" in item for item in intake.validate_root(root)))

    def test_partial_overlap_execution_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        def mutate(rows):
            row = next(row for row in rows if row["overlap_type"] == "partial")
            row["execution_routing_allowed"] = "true"
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", mutate)
        self.assertTrue(any("execution_routing_allowed" in item for item in intake.validate_root(root)))

    def test_catalog_visibility_does_not_grant_routing(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(catalog_visible="false"))
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/existing-experiment-map.tsv", lambda rows: rows[0].update(catalog_visible="false"))
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", lambda rows: rows[0].update(catalog_visible="false"))
        self.assertEqual([], intake.validate_root(root))

    def test_candidate_recommendation_true_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/candidate-states/MAD-SKILL-012.json"
        payload = json.loads(path.read_text())
        payload["recommendation_eligible"] = True
        path.write_text(json.dumps(payload))
        self.assertTrue(any("recommendation_eligible" in item for item in states.validate_root(root)))

    def test_candidate_unknown_field_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/candidate-states/MAD-SKILL-012.json"
        payload = json.loads(path.read_text())
        payload["unexpected"] = True
        path.write_text(json.dumps(payload))
        self.assertTrue(any("keys" in item for item in states.validate_root(root)))

    def test_candidate_active_status_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/candidate-states/MAD-SKILL-012.json"
        payload = json.loads(path.read_text())
        payload["status"] = "active"
        path.write_text(json.dumps(payload))
        self.assertTrue(any("status" in item for item in states.validate_root(root)))

    def test_candidate_registered_execution_and_promotion_are_rejected(self) -> None:
        for field in ("registered_experiment", "execution_routing_allowed", "promotion_allowed"):
            with self.subTest(field=field):
                temporary, root = cloned_root()
                self.addCleanup(temporary.cleanup)
                path = root / "sandbox/skill-incubator/candidate-intake/candidate-states/MAD-SKILL-012.json"
                payload = json.loads(path.read_text())
                payload[field] = True
                path.write_text(json.dumps(payload))
                self.assertTrue(any(field in item for item in states.validate_root(root)))

    def test_candidate_customer_approval_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/candidate-intake/candidate-states/MAD-SKILL-012.json"
        payload = json.loads(path.read_text())
        payload["customer_decision"] = "approved"
        path.write_text(json.dumps(payload))
        self.assertTrue(any("customer_decision" in item for item in states.validate_root(root)))

    def test_family_execution_true_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        payload["families"][0]["execution_routing_allowed"] = True
        path.write_text(json.dumps(payload))
        self.assertTrue(any("execution_routing_allowed" in item for item in families.validate_root(root)))

    def test_family_schema_critical_types_and_enums_are_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        family = payload["families"][0]
        family["catalog_visible"] = "yes"
        family["recommended_layer"] = "unsupported-layer"
        family["execution_boundary"] = "anything"
        family["responsibilities"] = []
        path.write_text(json.dumps(payload))
        errors = families.validate_root(root)
        self.assertTrue(any("catalog_visible" in item for item in errors))
        self.assertTrue(any("recommended_layer" in item for item in errors))
        self.assertTrue(any("execution_boundary" in item for item in errors))
        self.assertTrue(any("responsibilities" in item for item in errors))

    def test_family_nested_values_are_rejected_without_crashing(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        family = payload["families"][0]
        family["included_patterns"] = [{"invalid": "shape"}]
        family["excluded_patterns"] = [{"invalid": "shape"}]
        family["current_experiments"] = [{"invalid": "shape"}]
        family["candidate_experiments"] = [{"invalid": "shape"}]
        path.write_text(json.dumps(payload))
        errors = families.validate_root(root)
        for field in ("included_patterns", "excluded_patterns", "current_experiments", "candidate_experiments"):
            self.assertTrue(any(field in item for item in errors))

    def test_family_current_experiment_mismatch_is_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        payload["families"][0]["current_experiments"] = ["MAD-SKILL-001"]
        path.write_text(json.dumps(payload))
        self.assertTrue(any("matrix.current_experiments" in item for item in families.validate_root(root)))

    def test_empty_family_experiment_lists_are_valid_when_authoritative(self) -> None:
        payload = json.loads((ROOT / "sandbox/skill-incubator/architecture/capability-families.json").read_text())
        indexed = {entry["family_id"]: entry for entry in payload["families"]}
        self.assertEqual([], indexed["FAMILY-008"]["current_experiments"])
        self.assertEqual([], indexed["FAMILY-009"]["current_experiments"])
        self.assertEqual([], families.validate_root(ROOT))

    def test_family_candidate_cannot_be_current_experiment(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        payload["families"][0]["current_experiments"] = ["MAD-SKILL-012"]
        path.write_text(json.dumps(payload))
        self.assertTrue(any("current_experiments" in item for item in families.validate_root(root)))

    def test_family_unknown_field_and_wrong_family_are_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        path = root / "sandbox/skill-incubator/architecture/capability-families.json"
        payload = json.loads(path.read_text())
        payload["families"][0]["unknown"] = True
        path.write_text(json.dumps(payload))
        self.assertTrue(any("keys" in item for item in families.validate_root(root)))
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", lambda rows: rows[0].update(capability_family="FAMILY-999"))
        self.assertTrue(any("capability_family" in item for item in intake.validate_root(root)))

    def test_proposal_evidence_wrong_sha_is_rejected(self) -> None:
        evidence = json.loads((ROOT / "sandbox/skill-incubator/candidate-intake/proposal-evidence/MAD-SKILL-001.json").read_text())
        evidence["proposal_sha256"] = "0" * 64
        proposal_bytes = (ROOT / "sandbox/skill-incubator/experiments/MAD-SKILL-001/proposal.md").read_bytes()
        self.assertTrue(any("proposal_sha256" in item for item in proposal.validate_evidence_payload(evidence, "fixture", proposal_bytes)))

    def test_proposal_evidence_bad_line_range_is_rejected(self) -> None:
        evidence = json.loads((ROOT / "sandbox/skill-incubator/candidate-intake/proposal-evidence/MAD-SKILL-001.json").read_text())
        evidence["sections"][0]["line_end"] = 9999
        proposal_bytes = (ROOT / "sandbox/skill-incubator/experiments/MAD-SKILL-001/proposal.md").read_bytes()
        self.assertTrue(any("line_range" in item for item in proposal.validate_evidence_payload(evidence, "fixture", proposal_bytes)))

    def test_proposal_evidence_experiment_and_excerpt_mismatches_are_rejected(self) -> None:
        evidence = json.loads((ROOT / "sandbox/skill-incubator/candidate-intake/proposal-evidence/MAD-SKILL-001.json").read_text())
        proposal_bytes = (ROOT / "sandbox/skill-incubator/experiments/MAD-SKILL-001/proposal.md").read_bytes()
        evidence["experiment_id"] = "MAD-SKILL-002"
        evidence["sections"][0]["normalized_excerpt_sha256"] = "0" * 64
        errors = proposal.validate_evidence_payload(evidence, "fixture", proposal_bytes, "MAD-SKILL-001")
        self.assertTrue(any("experiment_id" in item for item in errors))
        self.assertTrue(any("normalized_excerpt_sha256" in item for item in errors))

    def test_proposal_evidence_path_and_contract_binding_are_rejected(self) -> None:
        evidence = json.loads((ROOT / "sandbox/skill-incubator/candidate-intake/proposal-evidence/MAD-SKILL-001.json").read_text())
        evidence["proposal_path"] = "sandbox/skill-incubator/experiments/MAD-SKILL-002/proposal.md"
        proposal_bytes = (ROOT / "sandbox/skill-incubator/experiments/MAD-SKILL-002/proposal.md").read_bytes()
        evidence["proposal_sha256"] = proposal.sha256_bytes(proposal_bytes)
        errors = proposal.validate_evidence_payload(evidence, "fixture", proposal_bytes, "MAD-SKILL-001")
        self.assertTrue(any("proposal_path" in item for item in errors))
        contract = json.loads((ROOT / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json").read_text())
        self.assertTrue(any("source_proposal_path" in item for item in proposal.validate_contract_binding(contract, evidence, "MAD-SKILL-001")))

    def test_contract_and_dedup_missing_proposal_evidence_are_rejected(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        contract_path = root / "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/MAD-SKILL-001.json"
        contract = json.loads(contract_path.read_text())
        contract["proposal_evidence_ids"] = []
        contract_path.write_text(json.dumps(contract))
        self.assertTrue(any("proposal_evidence_ids" in item for item in intake.validate_root(root)))

        def mutate(rows):
            row = next(row for row in rows if row["overlap_type"] == "full")
            row["proposal_evidence_ids"] = "missing-evidence-id"
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", mutate)
        self.assertTrue(any("proposal_evidence_ids" in item for item in proposal.validate_root(root)))

    def test_partial_overlap_requires_candidate_gap_evidence(self) -> None:
        temporary, root = cloned_root()
        self.addCleanup(temporary.cleanup)
        def mutate(rows):
            row = next(row for row in rows if row["overlap_type"] == "partial" and row["proposed_existing_experiment"])
            row["proposal_evidence_ids"] = f"{row['proposed_existing_experiment']}-objective"
        rewrite_tsv(root / "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", mutate)
        self.assertTrue(any("partial_overlap_evidence" in item for item in proposal.validate_root(root)))


if __name__ == "__main__":
    unittest.main()
