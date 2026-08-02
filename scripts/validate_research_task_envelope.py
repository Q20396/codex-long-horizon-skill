#!/usr/bin/env python3
"""Read-only semantic validation for one Research Task Envelope JSON file.

This tool validates a static request; it does not issue grants, call skills,
access financial data, or perform any external action.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA_VERSION = "1.1.0"
REQUESTABLE_EFFECTS = {
    "public_network_read",
    "local_public_material_read",
    "research_generation",
    "calculation_request",
}
FORBIDDEN_EFFECT_LIST = [
    "account_access", "credential_access", "customer_data_upload",
    "portfolio_data_access", "order_generation", "trade_instruction_generation",
    "trade_execution", "background_monitoring", "external_notification",
]
FORBIDDEN_EFFECTS = set(FORBIDDEN_EFFECT_LIST)
KNOWN_FIELDS = {
    "schema_version", "request_id", "task_type", "support_status", "as_of",
    "subjects", "requested_effects", "forbidden_effects", "not_requested_effects",
    "grant_requirement", "grant_ref", "authorization_state", "runtime_execution",
    "persistence", "financial_data_access", "external_action",
}
SUPPORTED_TASKS = {"single_security", "peer_set", "sector", "index", "etf", "strategy_research"}
TASK_SUBJECT_TYPE = {
    "single_security": "listed_security", "peer_set": "listed_security",
    "sector": "sector", "index": "index", "etf": "etf", "strategy_research": "strategy",
}


def issue(code: str, path: str) -> dict[str, str]:
    return {"code": code, "path": path}


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def timezone_aware_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def contract_errors(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        return [issue("SCHEMA_ROOT_NOT_OBJECT", "")]
    errors: list[dict[str, str]] = []
    for field in sorted(set(data) - KNOWN_FIELDS):
        errors.append(issue("SCHEMA_UNKNOWN_FIELD", f"/{field}"))
    required = KNOWN_FIELDS - {"as_of", "support_status"}
    for field in sorted(required - set(data)):
        errors.append(issue("SCHEMA_REQUIRED_FIELD_MISSING", f"/{field}"))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(issue("SCHEMA_VERSION_UNSUPPORTED", "/schema_version"))
    if "as_of" in data and data["as_of"] is not None and not timezone_aware_datetime(data["as_of"]):
        errors.append(issue("SCHEMA_AS_OF_INVALID", "/as_of"))
    task_type = data.get("task_type")
    if task_type not in SUPPORTED_TASKS | {"portfolio_research"}:
        errors.append(issue("SCHEMA_TASK_TYPE_INVALID", "/task_type"))
    for field in ("requested_effects", "not_requested_effects"):
        value = data.get(field)
        if not strings(value) or len(value) != len(set(value or [])):
            errors.append(issue("SCHEMA_EFFECT_LIST_INVALID", f"/{field}"))
        elif set(value) - REQUESTABLE_EFFECTS - FORBIDDEN_EFFECTS:
            errors.append(issue("SCHEMA_EFFECT_UNKNOWN", f"/{field}"))
    if data.get("forbidden_effects") != FORBIDDEN_EFFECT_LIST:
        errors.append(issue("SCHEMA_FORBIDDEN_EFFECTS_INVALID", "/forbidden_effects"))
    if data.get("grant_requirement") != "required_for_effect":
        errors.append(issue("SCHEMA_GRANT_REQUIREMENT_INVALID", "/grant_requirement"))
    if data.get("grant_ref") is not None:
        errors.append(issue("SCHEMA_GRANT_REF_INVALID", "/grant_ref"))
    if data.get("authorization_state") != "NOT_GRANTED":
        errors.append(issue("SCHEMA_AUTHORIZATION_STATE_INVALID", "/authorization_state"))
    if data.get("persistence") != "ephemeral":
        errors.append(issue("SCHEMA_PERSISTENCE_INVALID", "/persistence"))
    if data.get("financial_data_access") != "NOT_PERFORMED":
        errors.append(issue("SCHEMA_FINANCIAL_DATA_STATUS_INVALID", "/financial_data_access"))
    if data.get("external_action") != "NONE":
        errors.append(issue("SCHEMA_EXTERNAL_ACTION_INVALID", "/external_action"))
    subjects = data.get("subjects")
    if not isinstance(subjects, list):
        errors.append(issue("SCHEMA_SUBJECTS_INVALID", "/subjects"))
        return errors
    if task_type in SUPPORTED_TASKS:
        expected = TASK_SUBJECT_TYPE[task_type]
        if not subjects or (task_type == "single_security" and len(subjects) != 1) or (task_type == "peer_set" and len(subjects) < 2):
            errors.append(issue("SCHEMA_SUBJECT_COUNT_INVALID", "/subjects"))
        for index, subject in enumerate(subjects):
            if not isinstance(subject, dict) or subject.get("subject_type") != expected:
                errors.append(issue("SCHEMA_SUBJECT_TYPE_INVALID", f"/subjects/{index}/subject_type"))
            if expected == "listed_security":
                for field in ("ticker", "exchange", "mic"):
                    if not isinstance(subject, dict) or not isinstance(subject.get(field), str) or not subject[field]:
                        errors.append(issue("SUBJECT_IDENTITY_INCOMPLETE", f"/subjects/{index}/{field}"))
    if task_type == "portfolio_research":
        if data.get("support_status") != "DESCRIPTOR_ONLY" or subjects or data.get("requested_effects"):
            errors.append(issue("SCHEMA_PORTFOLIO_DESCRIPTOR_INVALID", "/"))
    return errors


def semantic_errors(data: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    requested = set(data.get("requested_effects", []))
    not_requested = set(data.get("not_requested_effects", []))
    forbidden = set(data.get("forbidden_effects", []))
    if requested & not_requested:
        errors.append(issue("EFFECT_CONFLICT", "/requested_effects"))
    if requested & forbidden:
        errors.append(issue("FORBIDDEN_EFFECT_REQUESTED", "/requested_effects"))
    identities = [
        (subject.get("ticker"), subject.get("exchange"), subject.get("mic"))
        for subject in data.get("subjects", [])
        if isinstance(subject, dict) and subject.get("subject_type") == "listed_security"
    ]
    if len(identities) != len(set(identities)):
        errors.append(issue("SUBJECT_IDENTITY_CONFLICT", "/subjects"))
    if data.get("task_type") == "portfolio_research":
        errors.append(issue("PORTFOLIO_RESEARCH_OUT_OF_SCOPE", "/task_type"))
    return errors


def result_for(data: Any, parse_error: bool = False) -> tuple[dict[str, Any], int]:
    contract = [issue("INPUT_JSON_INVALID", "")] if parse_error else contract_errors(data)
    semantic = [] if contract or not isinstance(data, dict) else semantic_errors(data)
    requested = set(data.get("requested_effects", [])) if isinstance(data, dict) else set()
    requirements = (
        [issue("NETWORK_EFFECT_REQUIRES_GRANT", "/requested_effects")]
        if "public_network_read" in requested
        else []
    )
    receipt = {
        "authorization_state": "NOT_GRANTED",
        "contract_validation": "PASS" if not contract else "FAIL",
        "errors": sorted(contract + semantic, key=lambda item: (item["code"], item["path"])),
        "external_action": "NONE",
        "financial_data_access": "NOT_PERFORMED",
        "grant_issued": False,
        "host_enforcement": "NOT_PROVEN",
        "network_effect_status": "REQUIRES_GRANT" if requirements else "NOT_REQUESTED",
        "planning_mode": "PLAN_ONLY" if isinstance(data, dict) and not data.get("as_of") else "AS_OF_DECLARED",
        "requirements": requirements,
        "runtime_execution": "NOT_IMPLEMENTED",
        "semantic_validation": "PASS" if not contract and not semantic else "FAIL",
    }
    return receipt, 0 if not contract and not semantic else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one local Research Task Envelope JSON file without side effects.")
    parser.add_argument("--input", required=True, type=Path, help="Explicit local JSON file to read")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        receipt, exit_code = result_for(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        receipt, exit_code = result_for(None, parse_error=True)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
