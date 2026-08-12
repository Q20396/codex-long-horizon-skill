"""Dependency-free validation for synthetic K0-K5 governance contracts.

The public seam accepts an explicitly supplied JSON value, then rejects any
envelope that is not marked synthetic and fixture-only before validation. It
returns a deterministic static disposition. It has no target-path reader,
path resolver, network client, authorization lookup, renderer, writer, logger,
or persistence interface. The command-line wrapper reads one caller-supplied
JSON file, validates its envelope after parsing, and writes its result only to
standard output.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable


RESULTS = {"ACCEPT", "REJECT", "BLOCKED", "NOT_AUTHORIZED", "OUT_OF_SCOPE"}
ID_PATTERNS = {
    "knowledge_item_id": re.compile(r"^KID-[A-Z2-7]{16}$"),
    "request_id": re.compile(r"^KRR-[A-Z2-7]{16}$"),
    "request_reference": re.compile(r"^KRR-[A-Z2-7]{16}$"),
    "source_request_reference": re.compile(r"^KRR-[A-Z2-7]{16}$"),
    "task_reference": re.compile(r"^KRT-[A-Z2-7]{16}$"),
    "authorization_reference": re.compile(r"^KRA-[A-Z2-7]{16}$"),
    "authorization_id": re.compile(r"^KRA-[A-Z2-7]{16}$"),
    "proposal_id": re.compile(r"^KWP-[A-Z2-7]{16}$"),
    "proposal_reference": re.compile(r"^KWP-[A-Z2-7]{16}$"),
    "disposition_id": re.compile(r"^KHD-[A-Z2-7]{16}$"),
}
KNOWLEDGE_KINDS = {
    "ARCHITECTURE_DECISION",
    "GOVERNANCE_BOUNDARY",
    "VERIFICATION_EVIDENCE",
    "GLOSSARY_ENTRY",
    "OPEN_QUESTION",
    "KNOWN_LIMITATION",
}
DESCRIPTOR_SENSITIVITY = {"HUMAN_DECLARED", "PROJECT_POLICY", "KNOWN_PATH_RULE"}
REQUEST_SENSITIVITY = DESCRIPTOR_SENSITIVITY | {"UNKNOWN"}
CLASSIFICATIONS = {"FACT", "INFERENCE", "UNKNOWN"}
CONTROL_DIRECTORIES = {".git", ".agents", ".codex"}
LINE_BREAK_CODEPOINTS = {0x0A, 0x0B, 0x0C, 0x0D, 0x85, 0x2028, 0x2029}
BIDI_CODEPOINTS = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
MARKUP_CHARACTERS = {"<", ">", "`", "[", "]", "*", "_"}
SENSITIVE_TEXT_MARKERS = {
    "ACCOUNT_NUMBER=",
    "BROKER_ACCOUNT=",
    "API_KEY=",
    "PASSWORD=",
    "/Users/",
    "ignore the contract",
    "ignore safeguards",
    "read all files",
}
SENSITIVE_TEXT_PATTERNS = tuple(
    re.compile(re.escape(marker), re.IGNORECASE | re.ASCII)
    for marker in SENSITIVE_TEXT_MARKERS
)
READ_EFFECT = "READ_ONE_DECLARED_NON_SENSITIVE_SECTION_ONLY"
READ_RANGE = "EXACT_DECLARED_SECTION_ONLY"
WRITE_EFFECT = "WRITE_ONE_DECLARED_PROJECT_RELATIVE_FILE_ONLY"
NOT_APPLICABLE = "NOT_APPLICABLE"

DESCRIPTOR_FIELDS = {
    "knowledge_item_id", "project_scope", "knowledge_kind", "statement",
    "classification", "source_locator", "sensitivity_basis", "observed_at",
    "review_by", "retention_status",
}
REQUEST_FIELDS = {
    "request_id", "task_reference", "authorization_reference", "sensitivity_basis",
    "target_locator", "requested_effect", "requested_read_range",
    "request_evaluated_at", "proposed_expires_at",
}
AUTHORIZATION_FIELDS = {
    "authorization_id", "request_reference", "task_reference", "effect",
    "target_locator", "requested_read_range", "expires_at",
    "authorization_status", "revoked_at",
}
RECEIPT_FIELDS = {
    "request_reference", "task_reference", "authorization_reference", "outcome",
    "recorded_at", "authorization_expiry_at", "revocation_checked_at",
    "revocation_checked_authorization_reference",
}
PROPOSAL_FIELDS = {
    "proposal_id", "task_reference", "source_request_reference",
    "proposed_target_path", "proposed_effect", "proposed_change_summary",
    "sensitivity_basis", "proposed_expires_at",
}
DISPOSITION_FIELDS = {
    "disposition_id", "proposal_reference", "task_reference", "allowed_effect",
    "approved_target_path", "disposition", "expires_at", "revoked_at",
}
K3_OUTCOMES = {
    "NOT_EXECUTED",
    "BLOCKED_SENSITIVITY_UNKNOWN",
    "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID",
    "BLOCKED_REQUEST_EXPIRED",
    "BLOCKED_AUTHORIZATION_EXPIRED",
    "BLOCKED_AUTHORIZATION_REVOKED",
    "FUTURE_READ_TARGET_UNAVAILABLE_OR_UNRESOLVED",
    "FUTURE_READ_HOST_DENIED",
    "FUTURE_READ_ABORTED_OR_INTERNAL_FAILURE",
    "FUTURE_READ_NOT_COMPLETED",
    "FUTURE_CONTENT_RETENTION_VIOLATION",
    "FUTURE_COMPLETED_WITHOUT_CONTENT_RETENTION",
}
FUTURE_TERMINAL_OUTCOMES = {
    "TARGET_UNAVAILABLE_OR_UNRESOLVED": "FUTURE_READ_TARGET_UNAVAILABLE_OR_UNRESOLVED",
    "HOST_DENIED": "FUTURE_READ_HOST_DENIED",
    "ABORTED_OR_INTERNAL_FAILURE": "FUTURE_READ_ABORTED_OR_INTERNAL_FAILURE",
    "READ_NOT_COMPLETED": "FUTURE_READ_NOT_COMPLETED",
    "CONTENT_RETENTION_VIOLATION": "FUTURE_CONTENT_RETENTION_VIOLATION",
    "COMPLETED_WITHOUT_CONTENT_RETENTION": "FUTURE_COMPLETED_WITHOUT_CONTENT_RETENTION",
}


def _result(result: str, outcome: str, label: str) -> dict[str, Any]:
    if result not in RESULTS:
        raise ValueError(f"unsupported result: {result}")
    return {
        "result": result,
        "outcome": outcome,
        "design_label": label,
        "runtime_execution": "NOT_IMPLEMENTED",
        "fixture_input_read": "CALLER_SUPPLIED_JSON_UNTRUSTED_UNTIL_ENVELOPE_VALIDATED",
        "governed_target_io": "NOT_IMPLEMENTED",
        "network": "NOT_IMPLEMENTED",
        "host_enforcement": "NOT_PROVEN",
        "external_action": "NONE",
    }


def _reject(outcome: str, label: str) -> dict[str, Any]:
    return _result("REJECT", outcome, label)


def _closed_object(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _valid_id(field: str, value: Any) -> bool:
    return isinstance(value, str) and ID_PATTERNS[field].fullmatch(value) is not None


def _is_single_line(value: Any, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and minimum <= len(value) <= maximum
        and not any(ord(character) in LINE_BREAK_CODEPOINTS for character in value)
    )


def _contains_sensitive_marker(value: str) -> bool:
    """Match exactly the Schema's ASCII case alternatives, never Unicode-fold."""

    return isinstance(value, str) and any(pattern.search(value) for pattern in SENSITIVE_TEXT_PATTERNS)


def _valid_plain_text_summary(value: Any) -> bool:
    if not _is_single_line(value, 1, 280):
        return False
    assert isinstance(value, str)
    if any(ord(character) <= 0x1F or 0x7F <= ord(character) <= 0x9F for character in value):
        return False
    if any(ord(character) in BIDI_CODEPOINTS for character in value):
        return False
    if any(character in MARKUP_CHARACTERS for character in value):
        return False
    return not _contains_sensitive_marker(value)


def _valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _valid_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.endswith("/") or "\\" in value or "//" in value:
        return False
    segments = value.split("/")
    return all(
        segment not in {"", ".", ".."}
        and segment not in CONTROL_DIRECTORIES
        and re.fullmatch(r"[A-Za-z0-9._-]+", segment) is not None
        for segment in segments
    )


def _valid_locator(value: Any) -> bool:
    return (
        _closed_object(value, {"relative_path", "section_heading"})
        and _valid_relative_path(value["relative_path"])
        and _is_single_line(value["section_heading"], 1, 120)
        and not _contains_sensitive_marker(value["section_heading"])
    )


def _validate_descriptor(record: Any) -> dict[str, Any]:
    if not _closed_object(record, DESCRIPTOR_FIELDS):
        return _reject("DESCRIPTOR_STRUCTURE_INVALID", "DESCRIPTOR_FIELDS_CLOSED")
    if not _valid_id("knowledge_item_id", record["knowledge_item_id"]):
        return _reject("DESCRIPTOR_ID_INVALID", "KNOWLEDGE_ITEM_ID_GRAMMAR_INVALID")
    if record["project_scope"] != "SINGLE_PROJECT_ONLY":
        return _reject("DESCRIPTOR_SCOPE_INVALID", "SINGLE_PROJECT_SCOPE_REQUIRED")
    if record["knowledge_kind"] not in KNOWLEDGE_KINDS:
        return _reject("DESCRIPTOR_KIND_INVALID", "CLOSED_ENUM_REQUIRED")
    if not _is_single_line(record["statement"], 1, 280) or _contains_sensitive_marker(record["statement"]):
        return _reject("DESCRIPTOR_STATEMENT_INVALID", "STATEMENT_BOUNDARY_OR_PROHIBITED_CONTENT")
    if record["classification"] not in CLASSIFICATIONS:
        return _reject("DESCRIPTOR_CLASSIFICATION_INVALID", "CLOSED_ENUM_REQUIRED")
    locator = record["source_locator"]
    if record["knowledge_kind"] == "OPEN_QUESTION":
        if locator is not None:
            return _reject("DESCRIPTOR_LOCATOR_INVALID", "OPEN_QUESTION_LOCATOR_MUST_BE_NULL")
    elif not _valid_locator(locator):
        return _reject("DESCRIPTOR_LOCATOR_INVALID", "LOCATOR_REQUIRED_FOR_SOURCED_KIND")
    if record["sensitivity_basis"] not in DESCRIPTOR_SENSITIVITY:
        return _reject("DESCRIPTOR_SENSITIVITY_INVALID", "CLOSED_ENUM_REQUIRED")
    if not _valid_utc_timestamp(record["observed_at"]) or not _valid_date(record["review_by"]):
        return _reject("DESCRIPTOR_TIME_INVALID", "FIXED_TIME_FORMAT_REQUIRED")
    if record["retention_status"] != "EPHEMERAL_ONLY":
        return _reject("DESCRIPTOR_RETENTION_INVALID", "UNAUTHORIZED_PERSISTENCE")
    return _result("ACCEPT", "DESCRIPTOR_STATICALLY_VALID", "SYNTHETIC_DESCRIPTOR_ACCEPTED")


def _validate_request(record: Any) -> dict[str, Any]:
    if not _closed_object(record, REQUEST_FIELDS):
        return _reject("READ_REQUEST_STRUCTURE_INVALID", "READ_REQUEST_FIELDS_CLOSED")
    for field in ("request_id", "task_reference", "authorization_reference"):
        if not _valid_id(field, record[field]):
            return _reject("READ_REQUEST_REFERENCE_INVALID", "TASK_LOCAL_REFERENCE_GRAMMAR_INVALID")
    if record["sensitivity_basis"] not in REQUEST_SENSITIVITY:
        return _reject("READ_REQUEST_SENSITIVITY_INVALID", "CLOSED_ENUM_REQUIRED")
    if not _valid_locator(record["target_locator"]):
        return _reject("READ_REQUEST_TARGET_INVALID", "PROJECT_RELATIVE_TARGET_REQUIRED")
    if record["requested_effect"] != READ_EFFECT or record["requested_read_range"] != READ_RANGE:
        return _reject("READ_REQUEST_EFFECT_INVALID", "DECLARED_READ_EFFECT_REQUIRED")
    if not _valid_utc_timestamp(record["request_evaluated_at"]) or not _valid_utc_timestamp(record["proposed_expires_at"]):
        return _reject("READ_REQUEST_TIME_INVALID", "FIXED_TIME_FORMAT_REQUIRED")
    if _parse_utc(record["proposed_expires_at"]) <= _parse_utc(record["request_evaluated_at"]):
        return _reject("READ_REQUEST_EXPIRY_INVALID", "REQUEST_EXPIRY_MUST_FOLLOW_EVALUATION")
    return _result("ACCEPT", "READ_REQUEST_STATICALLY_VALID", "SYNTHETIC_READ_REQUEST_ACCEPTED")


def _validate_authorization(record: Any) -> dict[str, Any]:
    if not _closed_object(record, AUTHORIZATION_FIELDS):
        return _reject("AUTHORIZATION_STRUCTURE_INVALID", "AUTHORIZATION_FIELDS_CLOSED")
    for field in ("authorization_id", "request_reference", "task_reference"):
        if not _valid_id(field, record[field]):
            return _reject("AUTHORIZATION_REFERENCE_INVALID", "TASK_LOCAL_REFERENCE_GRAMMAR_INVALID")
    if record["effect"] != READ_EFFECT or record["requested_read_range"] != READ_RANGE:
        return _reject("AUTHORIZATION_EFFECT_INVALID", "DECLARED_READ_EFFECT_REQUIRED")
    if not _valid_locator(record["target_locator"]):
        return _reject("AUTHORIZATION_TARGET_INVALID", "PROJECT_RELATIVE_TARGET_REQUIRED")
    if not _valid_utc_timestamp(record["expires_at"]):
        return _reject("AUTHORIZATION_TIME_INVALID", "FIXED_TIME_FORMAT_REQUIRED")
    status = record["authorization_status"]
    if status not in {"GRANTED", "REVOKED"}:
        return _reject("AUTHORIZATION_STATUS_INVALID", "CLOSED_ENUM_REQUIRED")
    if status == "GRANTED" and record["revoked_at"] is not None:
        return _reject("AUTHORIZATION_REVOCATION_COMBINATION_INVALID", "GRANTED_REQUIRES_NULL_REVOCATION")
    if status == "REVOKED" and not _valid_utc_timestamp(record["revoked_at"]):
        return _reject("AUTHORIZATION_REVOCATION_COMBINATION_INVALID", "REVOKED_REQUIRES_TIMESTAMP")
    return _result("ACCEPT", "AUTHORIZATION_STATICALLY_VALID", "SYNTHETIC_AUTHORIZATION_ACCEPTED")


def _validate_receipt_shape(record: Any) -> dict[str, Any]:
    if not _closed_object(record, RECEIPT_FIELDS):
        return _reject("READ_RECEIPT_STRUCTURE_INVALID", "READ_RECEIPT_FIELDS_CLOSED")
    for field in ("request_reference", "task_reference", "authorization_reference"):
        if not _valid_id(field, record[field]):
            return _reject("READ_RECEIPT_REFERENCE_INVALID", "TASK_LOCAL_REFERENCE_GRAMMAR_INVALID")
    if record["outcome"] not in K3_OUTCOMES or not _valid_utc_timestamp(record["recorded_at"]):
        return _reject("READ_RECEIPT_OUTCOME_INVALID", "RECEIPT_OUTCOME_OR_TIME_INVALID")
    expiry = record["authorization_expiry_at"]
    checked = record["revocation_checked_at"]
    checked_ref = record["revocation_checked_authorization_reference"]
    if expiry is not None and not _valid_utc_timestamp(expiry):
        return _reject("READ_RECEIPT_EXPIRY_INVALID", "RECEIPT_CONDITIONAL_FIELD_INVALID")
    if checked != NOT_APPLICABLE and not _valid_utc_timestamp(checked):
        return _reject("READ_RECEIPT_REVOCATION_CHECK_INVALID", "RECEIPT_CONDITIONAL_FIELD_INVALID")
    if checked_ref != NOT_APPLICABLE and not _valid_id("authorization_reference", checked_ref):
        return _reject("READ_RECEIPT_REVOCATION_REFERENCE_INVALID", "RECEIPT_CONDITIONAL_FIELD_INVALID")
    no_authorization_evidence = {
        "NOT_EXECUTED",
        "BLOCKED_SENSITIVITY_UNKNOWN",
        "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID",
    }
    if record["outcome"] in no_authorization_evidence:
        if not (
            expiry is None
            and checked == NOT_APPLICABLE
            and checked_ref == NOT_APPLICABLE
        ):
            return _reject(
                "READ_RECEIPT_CONDITIONAL_FIELDS_INVALID",
                "NO_FABRICATED_AUTHORIZATION_EVIDENCE",
            )
    elif record["outcome"] in {
        "BLOCKED_REQUEST_EXPIRED",
        "BLOCKED_AUTHORIZATION_EXPIRED",
    }:
        if not (
            _valid_utc_timestamp(expiry)
            and checked == NOT_APPLICABLE
            and checked_ref == NOT_APPLICABLE
        ):
            return _reject(
                "READ_RECEIPT_CONDITIONAL_FIELDS_INVALID",
                "NO_FABRICATED_REVOCATION_CHECK",
            )
    elif not (
        _valid_utc_timestamp(expiry)
        and _valid_utc_timestamp(checked)
        and _valid_id("authorization_reference", checked_ref)
    ):
        return _reject(
            "READ_RECEIPT_CONDITIONAL_FIELDS_INVALID",
            "RECEIPT_CONDITIONAL_FIELD_INVALID",
        )
    return _result("ACCEPT", "READ_RECEIPT_SHAPE_VALID", "SYNTHETIC_RECEIPT_ACCEPTED")


def _validate_proposal(record: Any) -> dict[str, Any]:
    if not _closed_object(record, PROPOSAL_FIELDS):
        return _reject("WRITE_PROPOSAL_STRUCTURE_INVALID", "WRITE_PROPOSAL_FIELDS_CLOSED")
    for field in ("proposal_id", "task_reference", "source_request_reference"):
        if not _valid_id(field, record[field]):
            return _reject("WRITE_PROPOSAL_REFERENCE_INVALID", "TASK_LOCAL_REFERENCE_GRAMMAR_INVALID")
    if not _valid_relative_path(record["proposed_target_path"]):
        return _reject("WRITE_PROPOSAL_TARGET_INVALID", "PROJECT_RELATIVE_TARGET_REQUIRED")
    if record["proposed_effect"] != WRITE_EFFECT:
        return _reject("WRITE_PROPOSAL_EFFECT_INVALID", "DECLARED_WRITE_EFFECT_REQUIRED")
    if not _valid_plain_text_summary(record["proposed_change_summary"]):
        return _reject("WRITE_PROPOSAL_SUMMARY_INVALID", "PLAIN_TEXT_LITERAL_SUMMARY_REQUIRED")
    if record["sensitivity_basis"] not in REQUEST_SENSITIVITY:
        return _reject("WRITE_PROPOSAL_SENSITIVITY_INVALID", "CLOSED_ENUM_REQUIRED")
    if not _valid_utc_timestamp(record["proposed_expires_at"]):
        return _reject("WRITE_PROPOSAL_TIME_INVALID", "FIXED_TIME_FORMAT_REQUIRED")
    return _result("ACCEPT", "WRITE_PROPOSAL_STATICALLY_VALID", "SYNTHETIC_WRITE_PROPOSAL_ACCEPTED")


def _validate_disposition(record: Any) -> dict[str, Any]:
    if not _closed_object(record, DISPOSITION_FIELDS):
        return _reject("HUMAN_DISPOSITION_STRUCTURE_INVALID", "HUMAN_DISPOSITION_FIELDS_CLOSED")
    for field in ("disposition_id", "proposal_reference", "task_reference"):
        if not _valid_id(field, record[field]):
            return _reject("HUMAN_DISPOSITION_REFERENCE_INVALID", "TASK_LOCAL_REFERENCE_GRAMMAR_INVALID")
    if record["allowed_effect"] != WRITE_EFFECT or not _valid_relative_path(record["approved_target_path"]):
        return _reject("HUMAN_DISPOSITION_SCOPE_INVALID", "DECLARED_WRITE_SCOPE_REQUIRED")
    if record["disposition"] not in {"APPROVE", "REJECT", "DEFER", "REVOKED"}:
        return _reject("HUMAN_DISPOSITION_STATUS_INVALID", "CLOSED_ENUM_REQUIRED")
    if not _valid_utc_timestamp(record["expires_at"]):
        return _reject("HUMAN_DISPOSITION_TIME_INVALID", "FIXED_TIME_FORMAT_REQUIRED")
    if record["disposition"] == "REVOKED":
        if not _valid_utc_timestamp(record["revoked_at"]):
            return _reject("HUMAN_DISPOSITION_REVOCATION_INVALID", "REVOKED_REQUIRES_TIMESTAMP")
    elif record["revoked_at"] is not None:
        return _reject("HUMAN_DISPOSITION_REVOCATION_INVALID", "NON_REVOKED_REQUIRES_NULL_REVOCATION")
    return _result("ACCEPT", "HUMAN_DISPOSITION_STATICALLY_VALID", "SYNTHETIC_HUMAN_DISPOSITION_ACCEPTED")


RECORD_VALIDATORS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "KNOWLEDGE_ITEM_DESCRIPTOR": _validate_descriptor,
    "KNOWLEDGE_READ_REQUEST": _validate_request,
    "AUTHORIZATION_RECORD": _validate_authorization,
    "KNOWLEDGE_READ_RECEIPT": _validate_receipt_shape,
    "WRITE_PROPOSAL": _validate_proposal,
    "HUMAN_DISPOSITION": _validate_disposition,
}


def _load_draft202012_validator() -> Any | None:
    """Load the candidate's local Schema gate when jsonschema is available.

    This optional import is intentionally deferred. Without it, record-local
    acceptance remains SCHEMA_UNVERIFIED rather than becoming a validator-only
    ACCEPT decision.
    """

    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ModuleNotFoundError:
        return None
    try:
        schema_path = Path(__file__).parent.parent / (
            "sandbox/skill-incubator/knowledge-governance-k6/"
            "knowledge-governance.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except (OSError, ValueError, TypeError):
        return None


def _schema_records_for_payload(payload: Any) -> list[Any]:
    """Return embedded K0-K4 records whose local acceptance is Schema-owned."""

    if not isinstance(payload, dict):
        return []
    subject = payload.get("case_subject")
    if subject in RECORD_VALIDATORS:
        return [payload.get("record")]
    if subject == "K3_READ_EVALUATION":
        return [payload.get("request"), payload.get("authorization"), payload.get("receipt")]
    if subject == "K4_WRITE_EVALUATION":
        return [
            payload.get("proposal"), payload.get("source_request"),
            payload.get("human_disposition"),
        ]
    if subject == "K5_STATIC_SECURITY_RELATION":
        return [payload.get("request"), payload.get("authorization")]
    return []


def _schema_gate(payload: Any) -> dict[str, Any] | None:
    """Apply the sole normative local-record acceptance gate when needed."""

    records = [record for record in _schema_records_for_payload(payload) if record is not None]
    if not records:
        return None
    validator = _load_draft202012_validator()
    if validator is None:
        return _result("BLOCKED", "SCHEMA_UNVERIFIED", "DRAFT202012_SCHEMA_GATE_REQUIRED")
    try:
        if any(any(validator.iter_errors(record)) for record in records):
            return _reject("SCHEMA_GATE_REJECTED", "DRAFT202012_LOCAL_CONTRACT_REJECTED")
    except (TypeError, ValueError, KeyError, AttributeError, OSError):
        return _reject("SCHEMA_GATE_INPUT_INVALID", "DRAFT202012_SCHEMA_GATE_FAIL_CLOSED")
    return None


def _authorization_bindings_hold(request: dict[str, Any], authorization: dict[str, Any]) -> bool:
    return (
        authorization["authorization_id"] == request["authorization_reference"]
        and authorization["request_reference"] == request["request_id"]
        and authorization["task_reference"] == request["task_reference"]
        and authorization["effect"] == request["requested_effect"]
        and authorization["target_locator"] == request["target_locator"]
        and authorization["requested_read_range"] == request["requested_read_range"]
        and _parse_utc(request["proposed_expires_at"]) <= _parse_utc(authorization["expires_at"])
    )


def _k3_authorization_first_match(
    request: dict[str, Any], authorization: dict[str, Any] | None, evaluation_at: str,
) -> tuple[str, str]:
    """The single K3/K5 authorization gate, in fixed first-match order."""

    evaluated = _parse_utc(evaluation_at)
    if evaluated < _parse_utc(request["request_evaluated_at"]):
        return "REJECT", "K3_EVALUATION_TIME_INVALID"
    if request["sensitivity_basis"] == "UNKNOWN":
        return "BLOCKED", "BLOCKED_SENSITIVITY_UNKNOWN"
    if authorization is None or not _authorization_bindings_hold(request, authorization):
        return "BLOCKED", "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID"
    if authorization["authorization_status"] == "REVOKED" and _parse_utc(authorization["revoked_at"]) > evaluated:
        return "BLOCKED", "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID"
    if _parse_utc(authorization["expires_at"]) <= evaluated:
        return "BLOCKED", "BLOCKED_AUTHORIZATION_EXPIRED"
    if _parse_utc(request["proposed_expires_at"]) <= evaluated:
        return "BLOCKED", "BLOCKED_REQUEST_EXPIRED"
    if authorization["authorization_status"] == "REVOKED":
        return "BLOCKED", "BLOCKED_AUTHORIZATION_REVOKED"
    return "ACCEPT", "K3_AUTHORIZATION_GATES_PASSED"


def _k3_first_match(payload: dict[str, Any]) -> tuple[str, str]:
    if not payload["evaluator_ran"]:
        return "NOT_AUTHORIZED", "NOT_EXECUTED"
    result, outcome = _k3_authorization_first_match(
        payload["request"], payload["authorization"], payload["evaluation_at"],
    )
    if result != "ACCEPT":
        return result, outcome
    terminal = payload["future_execution_terminal_state"]
    if terminal not in FUTURE_TERMINAL_OUTCOMES:
        return "REJECT", "FUTURE_TERMINAL_STATE_REQUIRED"
    return "OUT_OF_SCOPE", FUTURE_TERMINAL_OUTCOMES[terminal]


def _validate_receipt_relation(
    receipt: dict[str, Any],
    request: dict[str, Any],
    authorization: dict[str, Any] | None,
    evaluation_at: str,
    expected_outcome: str,
) -> dict[str, Any] | None:
    shape = _validate_receipt_shape(receipt)
    if shape["result"] != "ACCEPT":
        return shape
    if (
        receipt["request_reference"] != request["request_id"]
        or receipt["task_reference"] != request["task_reference"]
        or receipt["authorization_reference"] != request["authorization_reference"]
        or receipt["recorded_at"] != evaluation_at
        or receipt["outcome"] != expected_outcome
    ):
        return _reject("READ_RECEIPT_BINDING_INVALID", "RECEIPT_EXACT_BINDING_REQUIRED")
    no_authorization_evidence = {
        "NOT_EXECUTED", "BLOCKED_SENSITIVITY_UNKNOWN", "BLOCKED_AUTHORIZATION_MISSING_OR_INVALID"
    }
    if expected_outcome in no_authorization_evidence:
        if not (
            receipt["authorization_expiry_at"] is None
            and receipt["revocation_checked_at"] == NOT_APPLICABLE
            and receipt["revocation_checked_authorization_reference"] == NOT_APPLICABLE
        ):
            return _reject("READ_RECEIPT_CONDITIONAL_FIELDS_INVALID", "NO_FABRICATED_AUTHORIZATION_EVIDENCE")
        return None
    if authorization is None or receipt["authorization_expiry_at"] != authorization["expires_at"]:
        return _reject("READ_RECEIPT_EXPIRY_BINDING_INVALID", "AUTHORIZATION_EXPIRY_EXACT_BINDING_REQUIRED")
    no_revocation_check = {"BLOCKED_REQUEST_EXPIRED", "BLOCKED_AUTHORIZATION_EXPIRED"}
    if expected_outcome in no_revocation_check:
        if not (
            receipt["revocation_checked_at"] == NOT_APPLICABLE
            and receipt["revocation_checked_authorization_reference"] == NOT_APPLICABLE
        ):
            return _reject("READ_RECEIPT_REVOCATION_FIELDS_INVALID", "NO_FABRICATED_REVOCATION_CHECK")
        return None
    if not (
        receipt["revocation_checked_at"] == evaluation_at
        and receipt["revocation_checked_authorization_reference"] == authorization["authorization_id"]
    ):
        return _reject("READ_RECEIPT_REVOCATION_BINDING_INVALID", "FRESH_REVOCATION_CHECK_BINDING_REQUIRED")
    return None


def _validate_k3_evaluation(payload: Any) -> dict[str, Any]:
    fields = {
        "case_subject", "request", "authorization", "receipt", "evaluation_at",
        "evaluator_ran", "future_execution_terminal_state",
    }
    if not _closed_object(payload, fields) or payload["case_subject"] != "K3_READ_EVALUATION":
        return _reject("K3_EVALUATION_STRUCTURE_INVALID", "K3_EVALUATION_FIELDS_CLOSED")
    request_result = _validate_request(payload["request"])
    if request_result["result"] != "ACCEPT":
        return request_result
    if payload["authorization"] is not None:
        authorization_result = _validate_authorization(payload["authorization"])
        if authorization_result["result"] != "ACCEPT":
            return authorization_result
    if not _valid_utc_timestamp(payload["evaluation_at"]) or not isinstance(payload["evaluator_ran"], bool):
        return _reject("K3_EVALUATION_CONTEXT_INVALID", "FIXED_EVALUATION_CONTEXT_REQUIRED")
    if not payload["evaluator_ran"] and payload["future_execution_terminal_state"] is not None:
        return _reject("K3_NOT_EXECUTED_CONTEXT_INVALID", "NOT_EXECUTED_HAS_NO_TERMINAL_STATE")
    result_name, outcome = _k3_first_match(payload)
    if outcome.startswith("BLOCKED_") and payload["future_execution_terminal_state"] is not None:
        return _reject(
            "K3_BLOCKED_CONTEXT_INVALID",
            "BLOCKED_OUTCOME_REQUIRES_NULL_TERMINAL_STATE",
        )
    receipt_error = _validate_receipt_relation(
        payload["receipt"], payload["request"], payload["authorization"],
        payload["evaluation_at"], outcome,
    )
    if receipt_error is not None:
        return receipt_error
    return _result(result_name, outcome, "K3_ORDERED_FIRST_MATCH")


def _validate_k4_evaluation(payload: Any) -> dict[str, Any]:
    fields = {
        "case_subject", "proposal", "source_request", "human_disposition",
        "evaluation_at", "rendering_risk",
    }
    if not _closed_object(payload, fields) or payload["case_subject"] != "K4_WRITE_EVALUATION":
        return _reject("K4_EVALUATION_STRUCTURE_INVALID", "K4_EVALUATION_FIELDS_CLOSED")
    proposal_result = _validate_proposal(payload["proposal"])
    if proposal_result["result"] != "ACCEPT":
        return proposal_result
    if payload["source_request"] is not None:
        request_result = _validate_request(payload["source_request"])
        if request_result["result"] != "ACCEPT":
            return request_result
    if payload["human_disposition"] is not None:
        disposition_result = _validate_disposition(payload["human_disposition"])
        if disposition_result["result"] != "ACCEPT":
            return disposition_result
    if not _valid_utc_timestamp(payload["evaluation_at"]) or not isinstance(payload["rendering_risk"], bool):
        return _reject("K4_EVALUATION_CONTEXT_INVALID", "FIXED_EVALUATION_CONTEXT_REQUIRED")
    proposal = payload["proposal"]
    evaluation_at = _parse_utc(payload["evaluation_at"])
    if proposal["sensitivity_basis"] == "UNKNOWN":
        return _result("BLOCKED", "BLOCKED_SENSITIVITY_UNKNOWN", "K4_COMMON_READINESS_PRIORITY_1")
    if payload["rendering_risk"]:
        return _result("BLOCKED", "BLOCKED_RENDERING_RISK", "K4_COMMON_READINESS_PRIORITY_2")
    if _parse_utc(proposal["proposed_expires_at"]) <= evaluation_at:
        return _result("BLOCKED", "BLOCKED_PROPOSAL_EXPIRED", "K4_COMMON_READINESS_PRIORITY_3")
    request = payload["source_request"]
    if request is None or (
        proposal["source_request_reference"] != request["request_id"]
        or proposal["task_reference"] != request["task_reference"]
    ):
        return _result("BLOCKED", "BLOCKED_SOURCE_REQUEST_MISSING_OR_MISMATCH", "K4_COMMON_READINESS_PRIORITY_4")
    disposition = payload["human_disposition"]
    if disposition is None:
        return _result("ACCEPT", "PROPOSAL_READY_FOR_HUMAN_DISPOSITION", "WRITE_NOT_AUTHORIZED")
    if disposition["disposition"] == "REVOKED" and _parse_utc(disposition["revoked_at"]) > evaluation_at:
        return _result("BLOCKED", "BLOCKED_DISPOSITION_REVOCATION_TIME_INVALID", "K4_POST_DISPOSITION_PRIORITY_1")
    if disposition["disposition"] == "REVOKED":
        return _result("BLOCKED", "BLOCKED_DISPOSITION_REVOKED", "K4_POST_DISPOSITION_PRIORITY_2")
    if _parse_utc(disposition["expires_at"]) <= evaluation_at:
        return _result("BLOCKED", "BLOCKED_DISPOSITION_EXPIRED", "K4_POST_DISPOSITION_PRIORITY_3")
    if (
        disposition["proposal_reference"] != proposal["proposal_id"]
        or disposition["task_reference"] != proposal["task_reference"]
        or disposition["allowed_effect"] != proposal["proposed_effect"]
    ):
        return _result("BLOCKED", "BLOCKED_DISPOSITION_BINDING_MISMATCH", "K4_POST_DISPOSITION_PRIORITY_4")
    if disposition["approved_target_path"] != proposal["proposed_target_path"]:
        return _result("BLOCKED", "BLOCKED_TARGET_MISMATCH", "K4_POST_DISPOSITION_PRIORITY_5")
    if disposition["disposition"] != "APPROVE":
        return _result("BLOCKED", "HUMAN_DISPOSITION_NOT_APPROVED", "K4_POST_DISPOSITION_PRIORITY_6")
    return _result("ACCEPT", "HUMAN_DISPOSITION_RECORDED_NOT_EXECUTABLE", "APPROVE_DOES_NOT_EXECUTE")


def _validate_k5_capability(payload: Any) -> dict[str, Any]:
    fields = {"case_subject", "attempt", "requested_state"}
    if not _closed_object(payload, fields) or payload["case_subject"] != "K5_CAPABILITY_ATTEMPT":
        return _reject("K5_CAPABILITY_STRUCTURE_INVALID", "K5_CAPABILITY_FIELDS_CLOSED")
    forbidden = {
        "PERSISTENCE", "AUTOMATIC_MEMORY", "HOOK", "MCP", "SCHEDULER", "NETWORK"
    }
    if payload["attempt"] not in forbidden or payload["requested_state"] != "ENABLED":
        return _reject("K5_CAPABILITY_VALUE_INVALID", "K5_CAPABILITY_ENUM_CLOSED")
    return _result("NOT_AUTHORIZED", "CAPABILITY_EXPANSION_NOT_AUTHORIZED", payload["attempt"])


def _validate_k5_runtime(payload: Any) -> dict[str, Any]:
    fields = {
        "case_subject", "scenario", "design_disposition", "execution_status", "host_enforcement"
    }
    if not _closed_object(payload, fields) or payload["case_subject"] != "K5_RUNTIME_SCENARIO":
        return _reject("K5_RUNTIME_STRUCTURE_INVALID", "K5_RUNTIME_FIELDS_CLOSED")
    scenarios = {
        "AUTHORIZATION_LOOKUP", "SYMLINK_RESOLUTION", "DIRECTORY_CHECK",
        "RESOLVED_CONTAINMENT", "RENDERER_EXECUTION", "HOST_ENFORCEMENT",
        "CAPABILITY_EXPANSION_ACTIVATION",
    }
    if (
        payload["scenario"] not in scenarios
        or payload["design_disposition"] != "OUT_OF_SCOPE"
        or payload["execution_status"] != "NOT_EXECUTED"
        or payload["host_enforcement"] != "NOT_PROVEN"
    ):
        return _reject("K5_RUNTIME_BOUNDARY_INVALID", "FUTURE_RUNTIME_MARKERS_REQUIRED")
    return _result("OUT_OF_SCOPE", "FUTURE_RUNTIME_SCENARIO_NOT_EXECUTED", payload["scenario"])


def _validate_k5_static_relation(payload: Any) -> dict[str, Any]:
    fields = {"case_subject", "request", "authorization", "evaluation_at"}
    if not _closed_object(payload, fields) or payload["case_subject"] != "K5_STATIC_SECURITY_RELATION":
        return _reject("K5_STATIC_RELATION_STRUCTURE_INVALID", "K5_STATIC_RELATION_FIELDS_CLOSED")
    request_result = _validate_request(payload["request"])
    authorization_result = _validate_authorization(payload["authorization"])
    if request_result["result"] != "ACCEPT" or authorization_result["result"] != "ACCEPT":
        return _reject("K5_STATIC_RELATION_RECORD_INVALID", "K5_STATIC_BASELINE_RECORD_REQUIRED")
    if not _valid_utc_timestamp(payload["evaluation_at"]):
        return _reject("K5_STATIC_RELATION_TIME_INVALID", "K5_STATIC_EVALUATION_TIME_REQUIRED")
    result, outcome = _k3_authorization_first_match(
        payload["request"], payload["authorization"], payload["evaluation_at"],
    )
    if result == "ACCEPT":
        return _result("ACCEPT", "K5_STATIC_RELATION_VALID", "SYNTHETIC_STATIC_RELATION_VALID")
    return _result(result, outcome, "K5_REUSES_K3_AUTHORIZATION_FIRST_MATCH")


def _validate_k5_static_render_risk(payload: Any) -> dict[str, Any]:
    fields = {"case_subject", "protected_source_locator", "protected_sensitive_marker", "attempted_value"}
    if not _closed_object(payload, fields) or payload["case_subject"] != "K5_STATIC_RENDER_RISK":
        return _reject("K5_STATIC_RENDER_STRUCTURE_INVALID", "K5_STATIC_RENDER_FIELDS_CLOSED")
    attempted = payload["attempted_value"]
    locator = payload["protected_source_locator"]
    marker = payload["protected_sensitive_marker"]
    if (
        not isinstance(attempted, str)
        or locator is not None and not _valid_relative_path(locator)
        or marker is not None and (not isinstance(marker, str) or not _contains_sensitive_marker(marker))
        or locator is None and marker is None
    ):
        return _reject("K5_STATIC_RENDER_VALUE_INVALID", "K5_STATIC_RENDER_PROTECTION_REQUIRED")
    if locator is not None and locator in attempted:
        return _result("BLOCKED", "BLOCKED_RENDERING_RISK", "K5_SOURCE_LOCATOR_RENDERING_RISK")
    if marker is not None and marker in attempted and _contains_sensitive_marker(attempted):
        return _result("BLOCKED", "BLOCKED_RENDERING_RISK", "K5_SENSITIVE_CONTENT_RENDERING_RISK")
    return _reject("K5_STATIC_RENDER_RISK_NOT_DETECTED", "PROTECTED_VALUE_MUST_OCCUR_IN_ATTEMPT")


def _validate_payload(payload: Any) -> dict[str, Any]:
    """Validate one already-parsed synthetic payload without target I/O."""

    if not isinstance(payload, dict):
        return _reject("BUNDLE_STRUCTURE_INVALID", "BUNDLE_OBJECT_REQUIRED")
    subject = payload.get("case_subject")
    if subject in RECORD_VALIDATORS:
        if set(payload) != {"case_subject", "record"}:
            return _reject("BUNDLE_STRUCTURE_INVALID", "RECORD_BUNDLE_FIELDS_CLOSED")
        return RECORD_VALIDATORS[subject](payload["record"])
    if subject == "K3_READ_EVALUATION":
        return _validate_k3_evaluation(payload)
    if subject == "K4_WRITE_EVALUATION":
        return _validate_k4_evaluation(payload)
    if subject == "PRE_READ_SENSITIVITY_GATE":
        fields = {"case_subject", "project_scope", "sensitivity_basis", "proposed_source_locator"}
        if not _closed_object(payload, fields):
            return _reject("PRE_READ_GATE_STRUCTURE_INVALID", "PRE_READ_GATE_FIELDS_CLOSED")
        if payload["project_scope"] != "SINGLE_PROJECT_ONLY" or not _valid_relative_path(payload["proposed_source_locator"]):
            return _reject("PRE_READ_GATE_INPUT_INVALID", "PRE_READ_GATE_STATIC_INPUT_INVALID")
        if payload["sensitivity_basis"] == "UNKNOWN":
            return _result("BLOCKED", "BLOCKED_SENSITIVITY_UNKNOWN", "UNKNOWN_PRE_READ_SENSITIVITY_BLOCKED")
        if payload["sensitivity_basis"] in DESCRIPTOR_SENSITIVITY:
            return _result("ACCEPT", "PRE_READ_SENSITIVITY_CLASSIFIED", "PRE_READ_GATE_ACCEPTED")
        return _reject("PRE_READ_GATE_SENSITIVITY_INVALID", "CLOSED_ENUM_REQUIRED")
    if subject == "K5_CAPABILITY_ATTEMPT":
        return _validate_k5_capability(payload)
    if subject == "K5_RUNTIME_SCENARIO":
        return _validate_k5_runtime(payload)
    if subject == "K5_STATIC_SECURITY_RELATION":
        return _validate_k5_static_relation(payload)
    if subject == "K5_STATIC_RENDER_RISK":
        return _validate_k5_static_render_risk(payload)
    return _reject("CASE_SUBJECT_UNKNOWN", "CASE_SUBJECT_CLOSED")


def _validate_contract_bundle_unchecked(bundle: Any) -> dict[str, Any]:
    """Apply admission prechecks before the outer total/fail-closed wrapper."""

    fields = {"synthetic", "fixture_only", "payload"}
    if not _closed_object(bundle, fields):
        return _reject("BUNDLE_STRUCTURE_INVALID", "SYNTHETIC_BUNDLE_FIELDS_CLOSED")
    if bundle["synthetic"] is not True or bundle["fixture_only"] is not True:
        return _reject("BUNDLE_PROVENANCE_INVALID", "SYNTHETIC_FIXTURE_ONLY_REQUIRED")
    return _validate_payload(bundle["payload"])


def validate_contract_bundle(bundle: Any) -> dict[str, Any]:
    """Return a total, fail-closed disposition for an untrusted JSON bundle.

    The dependency-free precheck can reject unsafe local records, but never
    supplies their final acceptance. A result that would otherwise be ACCEPT
    must pass the local Draft 2020-12 Schema gate when it contains any of the
    six Schema-owned record types.
    """

    try:
        result = _validate_contract_bundle_unchecked(bundle)
        if result["result"] != "ACCEPT":
            return result
        payload = bundle["payload"]
        return _schema_gate(payload) or result
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        return _reject("UNTRUSTED_JSON_TYPE_INVALID", "TOTAL_FAIL_CLOSED")


def _validate_fixture_case_unchecked(case: Any) -> dict[str, Any]:
    """Validate a closed synthetic fixture wrapper and compare its expectation."""

    fields = {"case_id", "synthetic", "fixture_only", "expected_result", "expected_outcome", "payload"}
    if not _closed_object(case, fields):
        return _reject("FIXTURE_CASE_STRUCTURE_INVALID", "FIXTURE_CASE_FIELDS_CLOSED")
    if case["synthetic"] is not True or case["fixture_only"] is not True:
        return _reject("FIXTURE_PROVENANCE_INVALID", "SYNTHETIC_FIXTURE_ONLY_REQUIRED")
    if not isinstance(case["case_id"], str) or not case["case_id"]:
        return _reject("FIXTURE_CASE_ID_INVALID", "FIXTURE_CASE_ID_REQUIRED")
    if case["expected_result"] not in RESULTS or not isinstance(case["expected_outcome"], str):
        return _reject("FIXTURE_EXPECTATION_INVALID", "FIXTURE_EXPECTATION_CLOSED")
    actual = validate_contract_bundle({
        "synthetic": case["synthetic"],
        "fixture_only": case["fixture_only"],
        "payload": case["payload"],
    })
    actual["expectation_matches"] = (
        actual["result"] == case["expected_result"]
        and actual["outcome"] == case["expected_outcome"]
    )
    actual["case_id"] = case["case_id"]
    return actual


def validate_fixture_case(case: Any) -> dict[str, Any]:
    """Return a total, fail-closed fixture result for untrusted JSON data."""

    try:
        return _validate_fixture_case_unchecked(case)
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        return _reject("UNTRUSTED_JSON_TYPE_INVALID", "TOTAL_FAIL_CLOSED")


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate one synthetic K6 fixture JSON file")
    parser.add_argument("fixture", type=Path, help="explicit synthetic JSON fixture file")
    args = parser.parse_args()
    parsed = json.loads(args.fixture.read_text(encoding="utf-8"))
    cases = parsed if isinstance(parsed, list) else [parsed]
    results = [validate_fixture_case(case) for case in cases]
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if all(result.get("expectation_matches") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
