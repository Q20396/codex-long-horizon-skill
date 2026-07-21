#!/usr/bin/env python3
"""Validate locked candidate-intake records without executing any candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PATTERN_HEADERS = [
    "pattern_id",
    "name",
    "group",
    "classification",
    "capability_family",
    "existing_experiment",
    "overlap_score",
    "overlap_type",
    "primary_gap_owner",
    "routing_allowed",
    "unique_gap",
    "proposed_action",
    "rationale",
    "evidence_contract",
    "evidence_strength",
    "source_status",
]

MAP_HEADERS = [
    "pattern_id",
    "name",
    "capability_family",
    "existing_experiment",
    "overlap_score",
    "overlap_type",
    "primary_gap_owner",
    "routing_allowed",
    "unique_gap",
    "proposed_action",
    "rationale",
    "evidence_contract",
    "evidence_strength",
    "source_status",
]

EVIDENCE_HEADERS = [
    "pattern_id",
    "name",
    "proposed_existing_experiment",
    "overlap_type",
    "primary_gap_owner",
    "routing_allowed",
    "experiment_contract_path",
    "proposal_path",
    "contract_sha256",
    "objective_overlap",
    "input_overlap",
    "output_overlap",
    "permission_overlap",
    "non_goal_conflict",
    "evidence_strength",
    "reviewer_notes",
]

GROUPS = {"team", "automation", "advanced_engineering", "foundation"}
FAMILIES = {f"FAMILY-{number:03d}" for number in range(1, 10)}
OVERLAP_TYPES = {"full", "partial", "adjacent", "none"}
EVIDENCE_STRENGTHS = {"strong", "moderate", "weak", "insufficient"}
PROPOSED_ACTIONS = {
    "map_to_existing_experiment",
    "candidate_extension",
    "candidate_new_experiment",
    "separate_skill",
    "rejected_pending_verification",
    "out_of_scope",
}
SOURCE_STATUSES = {
    "customer_provided_unverified",
    "verification_blocked",
    "ambiguous_source",
}
CANDIDATE_IDS = {
    "MAD-SKILL-012-candidate",
    "MAD-SKILL-013-candidate",
    "MAD-SKILL-014-candidate",
}


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def is_repo_relative(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def require_file(root: Path, relative: str, errors: list[str]) -> Path | None:
    if not is_repo_relative(relative):
        error(errors, f"unsafe repository-relative path: {relative}")
        return None
    candidate = root / relative
    if candidate.is_symlink():
        error(errors, f"symlink input is not allowed: {relative}")
        return None
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        error(errors, f"path escapes repository root: {relative}")
        return None
    if not candidate.is_file():
        error(errors, f"required file is missing: {relative}")
        return None
    return candidate


def incubator_relative_path(value: str) -> str:
    """Normalize an explicit incubator-relative path without allowing escape."""
    if value.startswith("sandbox/skill-incubator/"):
        return value
    return f"sandbox/skill-incubator/{value}"


def parse_tsv_text(text: str, expected_headers: list[str], label: str) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    rows = list(csv.reader(text.splitlines(), delimiter="\t"))
    if not rows:
        return [], [f"{label}: file is empty"]
    if rows[0] != expected_headers:
        return [], [f"{label}: unexpected header"]
    records: list[dict[str, str]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected_headers):
            error(errors, f"{label}:{line_number}: expected {len(expected_headers)} columns, found {len(row)}")
            continue
        # Column count was checked immediately above; avoid a Python-version-specific
        # zip(strict=...) dependency in this standalone validator.
        records.append(dict(zip(expected_headers, row)))
    return records, errors


def load_tsv(root: Path, relative: str, expected_headers: list[str], errors: list[str]) -> list[dict[str, str]]:
    path = require_file(root, relative, errors)
    if path is None:
        return []
    records, parse_errors = parse_tsv_text(path.read_text(encoding="utf-8"), expected_headers, relative)
    errors.extend(parse_errors)
    return records


def parse_boolean(value: str, label: str, errors: list[str]) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    error(errors, f"{label}: routing_allowed must be true or false")
    return None


def validate_pattern_rows(records: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    identifiers: set[str] = set()
    for row in records:
        label = row.get("pattern_id", "<missing pattern_id>")
        if label in identifiers:
            error(errors, f"{label}: duplicate pattern_id")
        identifiers.add(label)
        if not label.startswith("PAT-") or len(label) != 7 or not label[4:].isdigit():
            error(errors, f"{label}: invalid pattern_id")
        if row["group"] not in GROUPS:
            error(errors, f"{label}: invalid group {row['group']}")
        if row["classification"] != "customer_provided_capability_pattern":
            error(errors, f"{label}: invalid classification")
        if row["capability_family"] not in FAMILIES:
            error(errors, f"{label}: invalid capability family {row['capability_family']}")
        if row["proposed_action"] not in PROPOSED_ACTIONS:
            error(errors, f"{label}: invalid proposed action {row['proposed_action']}")
        if row["overlap_type"] not in OVERLAP_TYPES:
            error(errors, f"{label}: invalid overlap type {row['overlap_type']}")
        if row["evidence_strength"] not in EVIDENCE_STRENGTHS:
            error(errors, f"{label}: invalid evidence strength {row['evidence_strength']}")
        if row["source_status"] not in SOURCE_STATUSES:
            error(errors, f"{label}: invalid source status {row['source_status']}")
        try:
            score = int(row["overlap_score"])
        except ValueError:
            error(errors, f"{label}: overlap_score must be an integer")
            score = -1
        if not 0 <= score <= 100:
            error(errors, f"{label}: overlap_score must be in 0..100")
        routing_allowed = parse_boolean(row["routing_allowed"], label, errors)
        if row["overlap_type"] == "full" and row["evidence_strength"] != "strong":
            error(errors, f"{label}: full overlap requires strong evidence")
        if row["overlap_type"] != "full" and routing_allowed is True:
            error(errors, f"{label}: only full overlap may allow routing")
        if row["overlap_type"] == "full" and routing_allowed is not True:
            error(errors, f"{label}: full overlap must allow recommendation routing")
        if row["primary_gap_owner"] in CANDIDATE_IDS and routing_allowed is True:
            error(errors, f"{label}: candidate-only owner cannot be routing eligible")
        if not row["name"].strip() or not row["primary_gap_owner"].strip() or not row["unique_gap"].strip():
            error(errors, f"{label}: required descriptive field is empty")
    expected = {f"PAT-{number:03d}" for number in range(1, 41)}
    if identifiers != expected:
        error(errors, "candidate patterns must contain exactly PAT-001 through PAT-040")
    return errors


def validate_source_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = payload.get("sources")
    if payload.get("status") != "locked" or not isinstance(sources, list):
        return ["source candidate registry must be locked and contain a sources list"]
    blocked = 0
    ambiguous = 0
    for source in sources:
        source_id = source.get("source_id", "<missing source_id>")
        if source.get("status") != "locked":
            error(errors, f"{source_id}: source is not locked")
        verification_status = source.get("verification_status")
        if verification_status == "verification_blocked":
            blocked += 1
        elif verification_status == "ambiguous_source":
            ambiguous += 1
        else:
            error(errors, f"{source_id}: unexpected verification status {verification_status}")
        if source.get("full_commit_sha") is not None:
            error(errors, f"{source_id}: unverified source must not contain a full commit SHA")
        for capability in ("code_import_allowed", "runtime_execution_allowed", "network_execution_allowed"):
            if source.get(capability) is not False:
                error(errors, f"{source_id}: {capability} must be false")
    if blocked != 10 or ambiguous != 5:
        error(errors, f"source candidate counts must be 10 verification_blocked and 5 ambiguous_source, found {blocked} and {ambiguous}")
    return errors


def validate_candidate_only_state(candidate_texts: dict[str, str], registered_ids: set[str]) -> list[str]:
    errors: list[str] = []
    for candidate_id, text in candidate_texts.items():
        for required_line in (
            "status: `candidate_only`",
            "registered_experiment: `false`",
            "implementation_exists: `false`",
            "execution_authorized: `false`",
            "customer_decision: `not_approved`",
        ):
            if required_line not in text:
                error(errors, f"{candidate_id}: missing required candidate-only declaration {required_line}")
        if candidate_id.replace("-candidate", "") in registered_ids:
            error(errors, f"{candidate_id}: candidate-only ID is present in experiment registry")
    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_base_contracts(root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    contracts: dict[str, dict[str, Any]] = {}
    for number in range(1, 12):
        experiment_id = f"MAD-SKILL-{number:03d}"
        relative = f"sandbox/skill-incubator/candidate-intake/base-experiment-contracts/{experiment_id}.json"
        path = require_file(root, relative, errors)
        if path is None:
            continue
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            error(errors, f"{relative}: invalid JSON: {exc.msg}")
            continue
        contracts[experiment_id] = contract
        if contract.get("experiment_id") != experiment_id:
            error(errors, f"{relative}: experiment_id mismatch")
        if contract.get("status") != "locked":
            error(errors, f"{relative}: status must be locked")
        if contract.get("mapping_basis") != "design_mapping":
            error(errors, f"{relative}: mapping_basis must be design_mapping")
        if contract.get("coverage_validation") != "not_runtime_verified":
            error(errors, f"{relative}: coverage_validation must disclose no runtime verification")
        if contract.get("routing_eligible") is not False:
            error(errors, f"{relative}: routing_eligible must be false")
        proposal_relative = contract.get("source_proposal_path", "")
        proposal_path = require_file(root, proposal_relative, errors)
        if proposal_path is not None and contract.get("source_proposal_sha256") != sha256_file(proposal_path):
            error(errors, f"{relative}: source proposal SHA-256 mismatch")
    if len(contracts) != 11:
        error(errors, f"expected 11 base experiment contracts, found {len(contracts)}")
    return contracts, errors


def validate_paths_and_evidence(root: Path, records: list[dict[str, str]], contracts: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    contract_root = "sandbox/skill-incubator/candidate-intake/base-experiment-contracts/"
    for row in records:
        label = row["pattern_id"]
        evidence_path = row["evidence_contract"]
        if evidence_path == "not_applicable":
            if row["overlap_type"] not in {"adjacent", "none"}:
                error(errors, f"{label}: not_applicable evidence is only valid for adjacent or none")
            continue
        path = require_file(root, f"sandbox/skill-incubator/{evidence_path}", errors)
        if path is None:
            continue
        if not evidence_path.startswith("candidate-intake/base-experiment-contracts/"):
            error(errors, f"{label}: evidence contract must be a base experiment contract")
    return errors


def validate_map_consistency(patterns: list[dict[str, str]], mappings: list[dict[str, str]], evidence: list[dict[str, str]], root: Path) -> list[str]:
    errors: list[str] = []
    pattern_by_id = {row["pattern_id"]: row for row in patterns}
    for label, rows, experiment_field in (("existing-experiment-map", mappings, "existing_experiment"), ("deduplication-evidence", evidence, "proposed_existing_experiment")):
        by_id = {row["pattern_id"]: row for row in rows}
        if len(by_id) != len(rows):
            error(errors, f"{label}: duplicate pattern_id")
        if set(by_id) != set(pattern_by_id):
            error(errors, f"{label}: pattern IDs do not match capability-patterns.tsv")
            continue
        for pattern_id, pattern in pattern_by_id.items():
            row = by_id[pattern_id]
            for key in ("name", "overlap_type", "primary_gap_owner", "routing_allowed", "evidence_strength"):
                if row[key] != pattern[key]:
                    error(errors, f"{label}:{pattern_id}: {key} does not match capability-patterns.tsv")
            if row[experiment_field] != pattern["existing_experiment"]:
                error(errors, f"{label}:{pattern_id}: existing experiment does not match capability-patterns.tsv")
            if label == "deduplication-evidence":
                contract_path = row["experiment_contract_path"]
                if contract_path == "not_applicable":
                    if row["contract_sha256"] != "not_applicable":
                        error(errors, f"{label}:{pattern_id}: not_applicable contract needs not_applicable SHA")
                else:
                    contract = require_file(root, f"sandbox/skill-incubator/{contract_path}", errors)
                    if contract is not None and row["contract_sha256"] != sha256_file(contract):
                        error(errors, f"{label}:{pattern_id}: contract SHA-256 mismatch")
                proposal = require_file(root, incubator_relative_path(row["proposal_path"]), errors)
                if proposal is None:
                    error(errors, f"{label}:{pattern_id}: proposal path must be repository-bound")
    return errors


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    patterns = load_tsv(root, "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", PATTERN_HEADERS, errors)
    mappings = load_tsv(root, "sandbox/skill-incubator/candidate-intake/existing-experiment-map.tsv", MAP_HEADERS, errors)
    evidence = load_tsv(root, "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", EVIDENCE_HEADERS, errors)
    errors.extend(validate_pattern_rows(patterns))
    contracts, contract_errors = validate_base_contracts(root)
    errors.extend(contract_errors)
    errors.extend(validate_paths_and_evidence(root, patterns, contracts))
    errors.extend(validate_map_consistency(patterns, mappings, evidence, root))

    source_path = require_file(root, "sandbox/skill-incubator/candidate-intake/source-candidates.json", errors)
    if source_path is not None:
        try:
            errors.extend(validate_source_payload(json.loads(source_path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            error(errors, f"source-candidates.json: invalid JSON: {exc.msg}")

    registry_path = require_file(root, "sandbox/skill-incubator/experiments/registry.json", errors)
    if registry_path is not None:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registered_ids = {item["experiment_id"] for item in registry.get("experiments", [])}
        candidate_texts: dict[str, str] = {}
        for candidate_id in sorted(CANDIDATE_IDS):
            candidate_path = require_file(root, f"sandbox/skill-incubator/candidate-intake/new-experiment-candidates/{candidate_id}.md", errors)
            if candidate_path is not None:
                candidate_texts[candidate_id] = candidate_path.read_text(encoding="utf-8")
        errors.extend(validate_candidate_only_state(candidate_texts, registered_ids))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate locked incubator candidate-intake records.")
    parser.add_argument("--root", type=Path, default=repository_root(), help="repository root containing sandbox/skill-incubator")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = validate_root(root)
    if errors:
        for message in errors:
            print(f"ERROR: {message}")
        return 1
    print("PASS: validated 40 locked capability patterns, 11 base contracts, and 3 candidate-only extensions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
