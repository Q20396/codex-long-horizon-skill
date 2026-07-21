#!/usr/bin/env python3
"""Validate immutable proposal excerpts that support, but do not prove, mappings."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from validation_common import BASE_EXPERIMENT_IDS, issue, normalized_excerpt, repository_root, sha256_bytes
from validate_candidate_intake import EVIDENCE_HEADERS, PATTERN_HEADERS, load_tsv


PINNED_COMMIT = "418497b9918f8f0af1f3868af69f54a57773f586"
ALLOWED_SUPPORTS = {"objective", "non_goal", "input", "output", "permission", "execution_boundary", "candidate_gap"}


def _git_show(root: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{commit}:{path}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout if result.returncode == 0 else None


def validate_evidence_payload(
    payload: dict, relative: str, proposal_bytes: bytes | None, expected_experiment_id: str | None = None
) -> list[str]:
    errors: list[str] = []
    experiment_id = payload.get("experiment_id")
    expected = expected_experiment_id or sorted(BASE_EXPERIMENT_IDS)
    if expected_experiment_id is not None and experiment_id != expected_experiment_id:
        errors.append(issue(relative, "experiment_id", expected_experiment_id, experiment_id))
    elif expected_experiment_id is None and experiment_id not in BASE_EXPERIMENT_IDS:
        errors.append(issue(relative, "experiment_id", sorted(BASE_EXPERIMENT_IDS), experiment_id))
    if payload.get("proposal_commit") != PINNED_COMMIT:
        errors.append(issue(relative, "proposal_commit", PINNED_COMMIT, payload.get("proposal_commit")))
    if expected_experiment_id is not None:
        expected_path = f"sandbox/skill-incubator/experiments/{expected_experiment_id}/proposal.md"
        if payload.get("proposal_path") != expected_path:
            errors.append(issue(relative, "proposal_path", expected_path, payload.get("proposal_path")))
    if proposal_bytes is None:
        errors.append(issue(relative, "proposal", "readable pinned Git object", "unavailable"))
        return errors
    if payload.get("proposal_sha256") != sha256_bytes(proposal_bytes):
        errors.append(issue(relative, "proposal_sha256", sha256_bytes(proposal_bytes), payload.get("proposal_sha256")))
    lines = proposal_bytes.decode("utf-8").splitlines()
    section_ids: set[str] = set()
    for section in payload.get("sections", []):
        evidence_id = section.get("evidence_id", "<missing>")
        if evidence_id in section_ids:
            errors.append(issue(relative, "sections.evidence_id", "unique", evidence_id))
        section_ids.add(evidence_id)
        start, end = section.get("line_start"), section.get("line_end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > len(lines):
            errors.append(issue(relative, f"sections[{evidence_id}].line_range", f"1..{len(lines)}", (start, end)))
            continue
        actual = sha256_bytes(normalized_excerpt(lines, start, end).encode("utf-8"))
        if section.get("normalized_excerpt_sha256") != actual:
            errors.append(issue(relative, f"sections[{evidence_id}].normalized_excerpt_sha256", actual, section.get("normalized_excerpt_sha256")))
        supports = section.get("supports")
        if not isinstance(supports, list) or not supports or any(item not in ALLOWED_SUPPORTS for item in supports):
            errors.append(issue(relative, f"sections[{evidence_id}].supports", sorted(ALLOWED_SUPPORTS), supports))
    return errors


def validate_contract_binding(contract: dict, evidence: dict, experiment_id: str) -> list[str]:
    """Require contract and evidence to identify the same immutable proposal."""
    relative = f"base-experiment-contracts/{experiment_id}.json"
    expected_path = f"sandbox/skill-incubator/experiments/{experiment_id}/proposal.md"
    errors: list[str] = []
    if contract.get("source_proposal_path") != expected_path:
        errors.append(issue(relative, "source_proposal_path", expected_path, contract.get("source_proposal_path")))
    if evidence.get("proposal_path") != expected_path:
        errors.append(issue(f"proposal-evidence/{experiment_id}.json", "proposal_path", expected_path, evidence.get("proposal_path")))
    if contract.get("source_proposal_path") != evidence.get("proposal_path"):
        errors.append(issue(relative, "source_proposal_path", evidence.get("proposal_path"), contract.get("source_proposal_path")))
    return errors


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    evidence_root = root / "sandbox/skill-incubator/candidate-intake/proposal-evidence"
    evidence: dict[str, dict] = {}
    for experiment_id in sorted(BASE_EXPERIMENT_IDS):
        relative = f"sandbox/skill-incubator/candidate-intake/proposal-evidence/{experiment_id}.json"
        path = root / relative
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(issue(relative, "json", "valid JSON", str(exc)))
            continue
        evidence[experiment_id] = payload
        proposal_path = payload.get("proposal_path", "")
        proposal_bytes = _git_show(root, payload.get("proposal_commit", ""), proposal_path)
        errors.extend(validate_evidence_payload(payload, relative, proposal_bytes, experiment_id))
    if set(evidence) != BASE_EXPERIMENT_IDS:
        errors.append(issue("proposal-evidence", "experiment_ids", sorted(BASE_EXPERIMENT_IDS), sorted(evidence)))

    patterns = load_tsv(root, "sandbox/skill-incubator/candidate-intake/capability-patterns.tsv", PATTERN_HEADERS, errors)
    dedup = load_tsv(root, "sandbox/skill-incubator/candidate-intake/deduplication-evidence.tsv", EVIDENCE_HEADERS, errors)
    contracts: dict[str, dict] = {}
    for experiment_id in BASE_EXPERIMENT_IDS:
        contract_path = root / f"sandbox/skill-incubator/candidate-intake/base-experiment-contracts/{experiment_id}.json"
        contracts[experiment_id] = json.loads(contract_path.read_text(encoding="utf-8"))
    for contract_id, contract in contracts.items():
        errors.extend(validate_contract_binding(contract, evidence.get(contract_id, {}), contract_id))
        evidence_path = contract.get("proposal_evidence_path")
        expected_path = f"candidate-intake/proposal-evidence/{contract_id}.json"
        if evidence_path != expected_path:
            errors.append(issue(f"base-experiment-contracts/{contract_id}.json", "proposal_evidence_path", expected_path, evidence_path))
        sections = {entry.get("evidence_id"): set(entry.get("supports", [])) for entry in evidence.get(contract_id, {}).get("sections", [])}
        ids = contract.get("proposal_evidence_ids", [])
        if not isinstance(ids, list) or any(identifier not in sections for identifier in ids):
            errors.append(issue(f"base-experiment-contracts/{contract_id}.json", "proposal_evidence_ids", "existing evidence IDs", ids))
        supported = set().union(*(sections.get(identifier, set()) for identifier in ids)) if ids else set()
        if not {"objective"}.issubset(supported) or not ({"output", "permission"} & supported):
            errors.append(issue(f"base-experiment-contracts/{contract_id}.json", "proposal_evidence_supports", "objective plus output or permission", sorted(supported)))
    pattern_by_id = {row["pattern_id"]: row for row in patterns}
    for row in dedup:
        pattern = pattern_by_id.get(row["pattern_id"])
        if pattern is None or not row["proposed_existing_experiment"]:
            continue
        experiment_id = row["proposed_existing_experiment"]
        expected_path = f"candidate-intake/proposal-evidence/{experiment_id}.json"
        if row["proposal_evidence_path"] != expected_path:
            errors.append(issue(f"deduplication-evidence.tsv:{row['pattern_id']}", "proposal_evidence_path", expected_path, row["proposal_evidence_path"]))
            continue
        sections = {entry.get("evidence_id"): set(entry.get("supports", [])) for entry in evidence[experiment_id].get("sections", [])}
        ids = [item for item in row["proposal_evidence_ids"].split(";") if item]
        if any(identifier not in sections for identifier in ids):
            errors.append(issue(f"deduplication-evidence.tsv:{row['pattern_id']}", "proposal_evidence_ids", "existing evidence IDs", ids))
            continue
        supported = set().union(*(sections[identifier] for identifier in ids))
        if row["overlap_type"] == "full" and not ({"objective"}.issubset(supported) and ({"output", "permission"} & supported)):
            errors.append(issue(f"deduplication-evidence.tsv:{row['pattern_id']}", "full_overlap_evidence", "objective plus output or permission", sorted(supported)))
        if row["overlap_type"] == "partial" and not ({"objective", "candidate_gap"}.issubset(supported)):
            errors.append(issue(f"deduplication-evidence.tsv:{row['pattern_id']}", "partial_overlap_evidence", "objective plus candidate_gap", sorted(supported)))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: 11 pinned proposal evidence files bind excerpts, contracts, and deduplication claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
