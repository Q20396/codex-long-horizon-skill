#!/usr/bin/env python3
"""Validate the authoritative nine-family capability taxonomy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation_common import BASE_EXPERIMENT_IDS, CANDIDATE_IDS, FAMILY_IDS, issue, load_tsv, repository_root, split_ids
from validate_candidate_intake import PATTERN_HEADERS


MATRIX_HEADERS = [
    "family_id", "family_name", "patterns", "current_coverage", "uncovered_gap", "recommended_disposition",
    "overlap_type", "primary_gap_owner", "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
    "current_experiments", "candidate_experiments", "evidence_contract", "evidence_strength",
]
REQUIRED = {
    "family_id", "name", "objective", "responsibilities", "included_patterns", "excluded_patterns",
    "current_experiments", "candidate_experiments", "recommended_layer", "execution_boundary",
    "catalog_visible", "recommendation_eligible", "execution_routing_allowed",
}


def validate_payload(payload: dict, patterns: dict[str, dict[str, str]], matrix: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    families = payload.get("families")
    if not isinstance(families, list):
        return [issue("capability-families.json", "families", "list", type(families).__name__)]
    observed = {family.get("family_id") for family in families if isinstance(family, dict)}
    if observed != FAMILY_IDS or len(families) != len(FAMILY_IDS):
        errors.append(issue("capability-families.json", "family_ids", sorted(FAMILY_IDS), sorted(observed)))
    for family in families:
        if not isinstance(family, dict):
            errors.append(issue("capability-families.json", "family", "object", type(family).__name__))
            continue
        family_id = family.get("family_id", "<missing>")
        if set(family) != REQUIRED:
            errors.append(issue(family_id, "keys", sorted(REQUIRED), sorted(family)))
        if family.get("recommendation_eligible") is not False:
            errors.append(issue(family_id, "recommendation_eligible", False, family.get("recommendation_eligible")))
        if family.get("execution_routing_allowed") is not False:
            errors.append(issue(family_id, "execution_routing_allowed", False, family.get("execution_routing_allowed")))
        included = family.get("included_patterns", [])
        expected_patterns = sorted(identifier for identifier, row in patterns.items() if row["capability_family"] == family_id)
        if sorted(included) != expected_patterns:
            errors.append(issue(family_id, "included_patterns", expected_patterns, sorted(included)))
        current = family.get("current_experiments", [])
        candidates = family.get("candidate_experiments", [])
        if len(current) != len(set(current)) or any(identifier not in BASE_EXPERIMENT_IDS for identifier in current):
            errors.append(issue(family_id, "current_experiments", "unique base experiment IDs", current))
        if len(candidates) != len(set(candidates)) or any(identifier not in CANDIDATE_IDS for identifier in candidates):
            errors.append(issue(family_id, "candidate_experiments", "unique candidate IDs", candidates))
        matrix_row = matrix.get(family_id)
        if matrix_row is None:
            errors.append(issue(family_id, "deduplication_matrix", "matching row", "missing"))
        else:
            if matrix_row["family_name"] != family.get("name"):
                errors.append(issue(family_id, "matrix.family_name", family.get("name"), matrix_row["family_name"]))
            if split_ids(matrix_row["current_experiments"]) != current:
                errors.append(issue(family_id, "matrix.current_experiments", current, split_ids(matrix_row["current_experiments"])))
            if split_ids(matrix_row["candidate_experiments"]) != candidates:
                errors.append(issue(family_id, "matrix.candidate_experiments", candidates, split_ids(matrix_row["candidate_experiments"])))
    return errors


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    patterns = load_tsv(root, "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", PATTERN_HEADERS, errors)
    matrix_rows = load_tsv(root, "sandbox/skill-incubator/candidate-intake/deduplication-matrix.tsv", MATRIX_HEADERS, errors)
    matrix = {row["family_id"]: row for row in matrix_rows}
    path = root / "sandbox/skill-incubator/architecture/capability-families.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [issue("capability-families.json", "json", "valid JSON", str(exc))]
    errors.extend(validate_payload(payload, {row["pattern_id"]: row for row in patterns}, matrix))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: nine authoritative capability families match locked mappings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
