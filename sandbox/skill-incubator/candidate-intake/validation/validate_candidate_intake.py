#!/usr/bin/env python3
"""Validate locked capability mappings without recommending or executing them."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from validation_common import (
    BASE_EXPERIMENT_IDS,
    CANDIDATE_IDS,
    EVIDENCE_STRENGTHS,
    FAMILY_IDS,
    OVERLAP_TYPES,
    SOURCE_STATUSES,
    issue,
    load_json,
    load_tsv,
    parse_bool,
    repository_root,
    require_file,
    sha256_file,
)


PATTERN_HEADERS = [
    "pattern_id", "name", "group", "classification", "capability_family",
    "existing_experiment", "overlap_score", "overlap_type", "primary_gap_owner",
    "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
    "unique_gap", "proposed_action", "rationale", "evidence_contract",
    "evidence_strength", "source_status",
]
MAP_HEADERS = [
    "pattern_id", "name", "existing_experiment", "overlap_type", "primary_gap_owner",
    "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
    "evidence_contract", "evidence_strength", "proposed_action", "source_status",
]
EVIDENCE_HEADERS = [
    "pattern_id", "name", "proposed_existing_experiment", "overlap_type", "primary_gap_owner",
    "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
    "experiment_contract_path", "proposal_path", "contract_sha256", "proposal_evidence_path",
    "proposal_evidence_ids", "objective_overlap", "input_overlap", "output_overlap",
    "permission_overlap", "non_goal_conflict", "evidence_strength", "reviewer_notes",
]
GROUPS = {"team", "automation", "advanced_engineering", "foundation"}
PROPOSED_ACTIONS = {
    "map_to_existing_experiment", "candidate_extension", "candidate_new_experiment",
    "separate_skill", "rejected_pending_verification", "out_of_scope",
}
# Candidate state files use canonical IDs (for example, MAD-SKILL-012). A gap
# owner names the explanatory candidate design, which deliberately carries the
# -candidate suffix and is never a registered experiment ID.
ALLOWED_OWNERS = {f"{candidate_id}-candidate" for candidate_id in CANDIDATE_IDS} | {
    "unresolved", "separate-skill", "out-of-scope"
}
BASE_CONTRACT_FIELDS = {
    "experiment_id", "name", "status", "source_proposal_path", "source_proposal_sha256",
    "mapping_basis", "coverage_validation", "objective", "non_goals", "inputs", "outputs",
    "permissions", "covered_patterns", "excluded_patterns", "known_gaps", "recommended_layer",
    "routing_eligible", "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
    "proposal_evidence_path", "proposal_evidence_ids",
}
PERMISSION_FIELDS = {"read", "write", "network", "external_services"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _validate_string_list(
    payload: dict, field: str, relative: str, errors: list[str], *, minimum: int = 0, unique: bool = False
) -> None:
    value = payload.get(field)
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(issue(relative, field, f"list with at least {minimum} item(s)", value))
        return
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(issue(relative, field, "non-empty strings", value))
        return
    if unique and len(value) != len(set(value)):
        errors.append(issue(relative, field, "unique values", value))


def _validate_base_contract_shape(payload: object, experiment_id: str, relative: str, errors: list[str]) -> None:
    """Mirror security-critical schema constraints when no JSON Schema engine is installed."""
    if not isinstance(payload, dict):
        errors.append(issue(relative, "contract", "object", type(payload).__name__))
        return
    if set(payload) != BASE_CONTRACT_FIELDS:
        errors.append(issue(relative, "keys", sorted(BASE_CONTRACT_FIELDS), sorted(payload)))
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        errors.append(issue(relative, "name", "non-empty string", payload.get("name")))
    for field in ("objective", "non_goals", "inputs", "outputs", "known_gaps"):
        _validate_string_list(payload, field, relative, errors, minimum=1)
    _validate_string_list(payload, "excluded_patterns", relative, errors)
    _validate_string_list(payload, "proposal_evidence_ids", relative, errors, minimum=1, unique=True)

    permissions = payload.get("permissions")
    if not isinstance(permissions, dict) or set(permissions) != PERMISSION_FIELDS:
        errors.append(issue(relative, "permissions", sorted(PERMISSION_FIELDS), permissions))
    else:
        for field, minimum in (("read", 1), ("write", 0)):
            value = permissions.get(field)
            if not isinstance(value, list) or len(value) < minimum or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                errors.append(issue(relative, f"permissions.{field}", f"list with at least {minimum} non-empty string item(s)", value))
        for field in ("network", "external_services"):
            if permissions.get(field) is not False:
                errors.append(issue(relative, f"permissions.{field}", False, permissions.get(field)))

    covered = payload.get("covered_patterns")
    if not isinstance(covered, list) or any(
        not isinstance(item, str) or re.fullmatch(r"PAT-[0-9]{3}", item) is None for item in covered
    ) or len(covered) != len(set(covered)):
        errors.append(issue(relative, "covered_patterns", "unique PAT-### list", covered))
    if payload.get("mapping_basis") != "design_mapping":
        errors.append(issue(relative, "mapping_basis", "design_mapping", payload.get("mapping_basis")))
    if payload.get("coverage_validation") != "not_runtime_verified":
        errors.append(issue(relative, "coverage_validation", "not_runtime_verified", payload.get("coverage_validation")))
    if not isinstance(payload.get("recommended_layer"), str) or not payload["recommended_layer"].strip():
        errors.append(issue(relative, "recommended_layer", "non-empty string", payload.get("recommended_layer")))
    for field, expected in (("routing_eligible", False), ("recommendation_eligible", False), ("execution_routing_allowed", False)):
        if payload.get(field) is not expected:
            errors.append(issue(relative, field, expected, payload.get(field)))
    if not isinstance(payload.get("catalog_visible"), bool):
        errors.append(issue(relative, "catalog_visible", "boolean", payload.get("catalog_visible")))
    for field in ("source_proposal_sha256",):
        if not isinstance(payload.get(field), str) or SHA256_RE.fullmatch(payload[field]) is None:
            errors.append(issue(relative, field, "lowercase SHA-256", payload.get(field)))


def _validate_routing(row: dict[str, str], relative: str, line: int, errors: list[str]) -> None:
    for field in ("catalog_visible", "recommendation_eligible", "execution_routing_allowed"):
        value = parse_bool(row[field], relative, field, errors, line)
        if field in {"recommendation_eligible", "execution_routing_allowed"} and value is not False:
            errors.append(issue(relative, field, False, row[field], line))
    # Catalog display remains an independent state; never infer recommendation or execution.


def validate_pattern_rows(records: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for offset, row in enumerate(records, start=2):
        identifier = row.get("pattern_id", "")
        if identifier in seen:
            errors.append(issue("capability-patterns.tsv", "pattern_id", "unique", identifier, offset))
        seen.add(identifier)
        if identifier not in {f"PAT-{number:03d}" for number in range(1, 41)}:
            errors.append(issue("capability-patterns.tsv", "pattern_id", "PAT-001..PAT-040", identifier, offset))
        if row["group"] not in GROUPS:
            errors.append(issue(identifier, "group", sorted(GROUPS), row["group"]))
        if row["classification"] != "customer_provided_capability_pattern":
            errors.append(issue(identifier, "classification", "customer_provided_capability_pattern", row["classification"]))
        if row["capability_family"] not in FAMILY_IDS:
            errors.append(issue(identifier, "capability_family", sorted(FAMILY_IDS), row["capability_family"]))
        if row["existing_experiment"] and row["existing_experiment"] not in BASE_EXPERIMENT_IDS:
            errors.append(issue(identifier, "existing_experiment", sorted(BASE_EXPERIMENT_IDS), row["existing_experiment"]))
        if row["overlap_type"] not in OVERLAP_TYPES:
            errors.append(issue(identifier, "overlap_type", sorted(OVERLAP_TYPES), row["overlap_type"]))
        if row["evidence_strength"] not in EVIDENCE_STRENGTHS:
            errors.append(issue(identifier, "evidence_strength", sorted(EVIDENCE_STRENGTHS), row["evidence_strength"]))
        if row["source_status"] not in SOURCE_STATUSES:
            errors.append(issue(identifier, "source_status", sorted(SOURCE_STATUSES), row["source_status"]))
        if row["proposed_action"] not in PROPOSED_ACTIONS:
            errors.append(issue(identifier, "proposed_action", sorted(PROPOSED_ACTIONS), row["proposed_action"]))
        try:
            score = int(row["overlap_score"])
        except ValueError:
            score = -1
        if not 0 <= score <= 100:
            errors.append(issue(identifier, "overlap_score", "integer 0..100", row["overlap_score"]))
        _validate_routing(row, "capability-patterns.tsv", offset, errors)
        owner = row["primary_gap_owner"]
        if row["overlap_type"] == "full":
            if not row["existing_experiment"]:
                errors.append(issue(identifier, "existing_experiment", "base experiment for full overlap", row["existing_experiment"]))
            if owner:
                errors.append(issue(identifier, "primary_gap_owner", "empty for full overlap", owner))
            if row["evidence_strength"] != "strong":
                errors.append(issue(identifier, "evidence_strength", "strong for full overlap", row["evidence_strength"]))
            if row["proposed_action"] != "map_to_existing_experiment":
                errors.append(issue(identifier, "proposed_action", "map_to_existing_experiment for full overlap", row["proposed_action"]))
        else:
            if owner not in ALLOWED_OWNERS:
                errors.append(issue(identifier, "primary_gap_owner", sorted(ALLOWED_OWNERS), owner))
        if row["overlap_type"] == "none" and row["existing_experiment"]:
            errors.append(issue(identifier, "existing_experiment", "empty for no overlap", row["existing_experiment"]))
        if row["proposed_action"] == "map_to_existing_experiment" and not row["existing_experiment"]:
            errors.append(issue(identifier, "existing_experiment", "required for map_to_existing_experiment", row["existing_experiment"]))
        if row["proposed_action"] == "candidate_extension" and not row["existing_experiment"]:
            errors.append(issue(identifier, "existing_experiment", "required for candidate_extension", row["existing_experiment"]))
        if row["proposed_action"] == "candidate_new_experiment":
            allowed_candidate_owners = {f"{candidate_id}-candidate" for candidate_id in CANDIDATE_IDS} | {"unresolved"}
            if owner not in allowed_candidate_owners:
                errors.append(issue(identifier, "primary_gap_owner", "candidate design owner or unresolved for candidate_new_experiment", owner))
        if row["proposed_action"] == "separate_skill" and owner != "separate-skill":
            errors.append(issue(identifier, "primary_gap_owner", "separate-skill for separate_skill action", owner))
        if not row["name"].strip() or not row["unique_gap"].strip():
            errors.append(issue(identifier, "descriptive_fields", "non-empty", "empty"))
    expected = {f"PAT-{number:03d}" for number in range(1, 41)}
    if seen != expected:
        errors.append(issue("capability-patterns.tsv", "pattern_set", sorted(expected), sorted(seen)))
    return errors


def validate_base_contracts(root: Path) -> tuple[dict[str, dict], list[str]]:
    errors: list[str] = []
    contracts: dict[str, dict] = {}
    for experiment_id in sorted(BASE_EXPERIMENT_IDS):
        relative = f"sandbox/skill-incubator/candidate-intake/base-experiment-contracts/{experiment_id}.json"
        payload = load_json(root, relative, errors)
        if payload is None:
            continue
        if not isinstance(payload, dict):
            _validate_base_contract_shape(payload, experiment_id, relative, errors)
            continue
        contracts[experiment_id] = payload
        if payload.get("experiment_id") != experiment_id:
            errors.append(issue(relative, "experiment_id", experiment_id, payload.get("experiment_id")))
        _validate_base_contract_shape(payload, experiment_id, relative, errors)
        for field, expected in (("status", "locked"), ("routing_eligible", False), ("catalog_visible", True),
                                ("recommendation_eligible", False), ("execution_routing_allowed", False)):
            if payload.get(field) != expected:
                errors.append(issue(relative, field, expected, payload.get(field)))
        proposal = payload.get("source_proposal_path", "")
        expected_proposal = f"sandbox/skill-incubator/experiments/{experiment_id}/proposal.md"
        if proposal != expected_proposal:
            errors.append(issue(relative, "source_proposal_path", expected_proposal, proposal))
        proposal_path = require_file(root, proposal, errors)
        if proposal_path is not None and payload.get("source_proposal_sha256") != sha256_file(proposal_path):
            errors.append(issue(relative, "source_proposal_sha256", sha256_file(proposal_path), payload.get("source_proposal_sha256")))
        expected_evidence = f"candidate-intake/proposal-evidence/{experiment_id}.json"
        if payload.get("proposal_evidence_path") != expected_evidence:
            errors.append(issue(relative, "proposal_evidence_path", expected_evidence, payload.get("proposal_evidence_path")))
        ids = payload.get("proposal_evidence_ids")
        if not isinstance(ids, list) or not ids:
            errors.append(issue(relative, "proposal_evidence_ids", "non-empty list", ids))
    if set(contracts) != BASE_EXPERIMENT_IDS:
        errors.append(issue("base-experiment-contracts", "contract_ids", sorted(BASE_EXPERIMENT_IDS), sorted(contracts)))
    return contracts, errors


def validate_source_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    sources = payload.get("sources")
    if payload.get("status") != "locked" or not isinstance(sources, list):
        return [issue("source-candidates.json", "root", "locked source list", payload)]
    counts = {"verification_blocked": 0, "ambiguous_source": 0}
    for source in sources:
        status = source.get("verification_status")
        if status not in counts:
            errors.append(issue("source-candidates.json", "verification_status", sorted(counts), status))
        else:
            counts[status] += 1
        if source.get("status") != "locked":
            errors.append(issue(source.get("source_id", "source"), "status", "locked", source.get("status")))
        if source.get("full_commit_sha") is not None:
            errors.append(issue(source.get("source_id", "source"), "full_commit_sha", None, source.get("full_commit_sha")))
        for field in ("code_import_allowed", "runtime_execution_allowed", "network_execution_allowed"):
            if source.get(field) is not False:
                errors.append(issue(source.get("source_id", "source"), field, False, source.get(field)))
    if counts != {"verification_blocked": 10, "ambiguous_source": 5}:
        errors.append(issue("source-candidates.json", "source_counts", {"verification_blocked": 10, "ambiguous_source": 5}, counts))
    return errors


def validate_map_consistency(root: Path, patterns: list[dict[str, str]], contracts: dict[str, dict], errors: list[str]) -> None:
    pattern_by_id = {row["pattern_id"]: row for row in patterns}
    map_rows = load_tsv(root, "sandbox/skill-incubator/candidate-intake/existing-experiment-map.tsv", MAP_HEADERS, errors)
    evidence_rows = load_tsv(root, "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", EVIDENCE_HEADERS, errors)
    for label, rows, experiment_field in (("existing-experiment-map.tsv", map_rows, "existing_experiment"),
                                          ("deduplication-evidence.tsv", evidence_rows, "proposed_existing_experiment")):
        by_id = {row["pattern_id"]: row for row in rows}
        if set(by_id) != set(pattern_by_id) or len(by_id) != len(rows):
            errors.append(issue(label, "pattern_ids", sorted(pattern_by_id), sorted(by_id)))
            continue
        for identifier, pattern in pattern_by_id.items():
            row = by_id[identifier]
            for field in ("name", "overlap_type", "primary_gap_owner", "catalog_visible",
                          "recommendation_eligible", "execution_routing_allowed", "evidence_strength"):
                if row[field] != pattern[field]:
                    errors.append(issue(f"{label}:{identifier}", field, pattern[field], row[field]))
            if row[experiment_field] != pattern["existing_experiment"]:
                errors.append(issue(f"{label}:{identifier}", experiment_field, pattern["existing_experiment"], row[experiment_field]))
            if pattern["existing_experiment"]:
                expected_contract = f"candidate-intake/base-experiment-contracts/{pattern['existing_experiment']}.json"
                if pattern["evidence_contract"] != expected_contract:
                    errors.append(issue(f"capability-patterns.tsv:{identifier}", "evidence_contract", expected_contract, pattern["evidence_contract"]))
                if label == "existing-experiment-map.tsv" and row["evidence_contract"] != expected_contract:
                    errors.append(issue(f"{label}:{identifier}", "evidence_contract", expected_contract, row["evidence_contract"]))
                contract = contracts.get(pattern["existing_experiment"])
                if pattern["overlap_type"] == "full" and contract is not None and identifier not in contract.get("covered_patterns", []):
                    errors.append(issue(f"{label}:{identifier}", "covered_patterns", f"contains {identifier}", contract.get("covered_patterns")))
            if label == "deduplication-evidence.tsv":
                contract_path = row["experiment_contract_path"]
                if pattern["existing_experiment"]:
                    expected_contract = f"candidate-intake/base-experiment-contracts/{pattern['existing_experiment']}.json"
                    if contract_path != expected_contract:
                        errors.append(issue(f"{label}:{identifier}", "experiment_contract_path", expected_contract, contract_path))
                    contract = contracts.get(pattern["existing_experiment"])
                    if contract is not None and contract_path == expected_contract:
                        expected_sha = sha256_file(root / f"sandbox/skill-incubator/{contract_path}")
                        if row["contract_sha256"] != expected_sha:
                            errors.append(issue(f"{label}:{identifier}", "contract_sha256", expected_sha, row["contract_sha256"]))
                elif contract_path != "not_applicable" or row["contract_sha256"] != "not_applicable":
                    errors.append(issue(f"{label}:{identifier}", "contract", "not_applicable", (contract_path, row["contract_sha256"])))


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    patterns = load_tsv(root, "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", PATTERN_HEADERS, errors)
    errors.extend(validate_pattern_rows(patterns))
    contracts, contract_errors = validate_base_contracts(root)
    errors.extend(contract_errors)
    validate_map_consistency(root, patterns, contracts, errors)
    source = load_json(root, "sandbox/skill-incubator/candidate-intake/source-candidates.json", errors)
    if source is not None:
        errors.extend(validate_source_payload(source))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {entry}" for entry in errors))
        return 1
    print("PASS: 40 locked patterns, 11 evidence-bound base contracts, and no recommendation or execution routing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
