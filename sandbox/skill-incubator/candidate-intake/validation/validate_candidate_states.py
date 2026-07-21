#!/usr/bin/env python3
"""Validate authoritative, non-promotable state for candidates 012 through 014."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation_common import CANDIDATE_IDS, issue, repository_root


REQUIRED = {
    "status": "candidate_only",
    "registered_experiment": False,
    "recommendation_eligible": False,
    "execution_routing_allowed": False,
    "implementation_exists": False,
    "execution_authorized": False,
    "customer_decision": "not_approved",
    "network_authorized": False,
    "dependency_install_authorized": False,
    "external_service_authorized": False,
    "promotion_allowed": False,
    "authoritative_state": True,
}
ALLOWED = {"candidate_id", "name", "catalog_visible", "source_status"} | set(REQUIRED)
SOURCE_STATUSES = {"customer_provided_unverified", "verification_blocked", "ambiguous_source"}


def validate_payload(payload: dict, expected_id: str, relative: str) -> list[str]:
    errors: list[str] = []
    if set(payload) != ALLOWED:
        errors.append(issue(relative, "keys", sorted(ALLOWED), sorted(payload)))
    if payload.get("candidate_id") != expected_id:
        errors.append(issue(relative, "candidate_id", expected_id, payload.get("candidate_id")))
    for field, expected in REQUIRED.items():
        if payload.get(field) != expected:
            errors.append(issue(relative, field, expected, payload.get(field)))
    if not isinstance(payload.get("catalog_visible"), bool):
        errors.append(issue(relative, "catalog_visible", "boolean", payload.get("catalog_visible")))
    if payload.get("source_status") not in SOURCE_STATUSES:
        errors.append(issue(relative, "source_status", sorted(SOURCE_STATUSES), payload.get("source_status")))
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        errors.append(issue(relative, "name", "non-empty string", payload.get("name")))
    return errors


def validate_root(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "sandbox/skill-incubator/experiments/registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registered_ids = {entry.get("experiment_id") for entry in registry.get("experiments", [])}
    for candidate_id in sorted(CANDIDATE_IDS):
        relative = f"sandbox/skill-incubator/candidate-intake/candidate-states/{candidate_id}.json"
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(issue(relative, "state_file", "regular JSON file", "missing or symlink"))
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(issue(relative, "json", "valid JSON", exc.msg, exc.lineno))
            continue
        errors.extend(validate_payload(payload, candidate_id, relative))
        if candidate_id in registered_ids:
            errors.append(issue(relative, "registry", "not registered", candidate_id))
        markdown = root / f"sandbox/skill-incubator/candidate-intake/new-experiment-candidates/{candidate_id}-candidate.md"
        expected_note = f"candidate-intake/candidate-states/{candidate_id}.json"
        if not markdown.is_file() or expected_note not in markdown.read_text(encoding="utf-8"):
            errors.append(issue(str(markdown.relative_to(root)), "authoritative_state_path", expected_note, "missing"))
    unexpected = {path.stem for path in (root / "sandbox/skill-incubator/candidate-intake/candidate-states").glob("*.json")} - CANDIDATE_IDS
    if unexpected:
        errors.append(issue("candidate-states", "candidate_ids", sorted(CANDIDATE_IDS), sorted(unexpected)))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = validate_root(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: three candidate-only states are authoritative and non-executable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
