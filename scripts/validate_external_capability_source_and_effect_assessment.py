"""Pure static assessment for synthetic External Capability Source declarations.

This module has no file, network, provider, adapter, path, renderer, writer,
process, authorization-lookup, or host-enforcement interface.  Its caller must
run the Draft 2020-12 local-shape gate first.  This module then evaluates only
cross-field binding, time relations, ordered first-match routing, and supplied
outcome/reason consistency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

HOST_REQUIRED = {"TARGET_CONTENT_READ", "TARGET_CONTENT_WRITE", "PATH_RESOLUTION_OR_SYMLINK_INSPECTION", "RENDER_OR_RETENTION_PROCESSING", "HOST_CONTROL_OR_SCHEDULING", "subprocess_execution", "package_installation", "dynamic_import", "process_spawn"}
STATIC_EFFECTS = {"NO_EXTERNAL_EFFECT", "STATIC_CONTRACT_ANALYSIS"}


def _result(outcome: str, reason: str) -> dict[str, str]:
    return {
        "outcome": outcome,
        "reason_category": reason,
        "runtime_execution": "NOT_IMPLEMENTED",
        "governed_target_io": "NOT_IMPLEMENTED",
        "network": "NOT_IMPLEMENTED",
        "host_enforcement": "NOT_PROVEN",
        "external_action": "NONE",
    }


def _blocked(reason: str) -> dict[str, str]:
    return _result("BLOCKED", reason)


def _parse_time(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _derived(record: dict[str, Any]) -> tuple[str, str]:
    """Evaluate only after an external Draft Schema gate has accepted shape."""
    binding = record["operation_binding"]
    evidence = record["evidence_minimum"]
    requested = set(record["task_requested_effects"])
    authorized = set(record["task_authorized_effects"])
    host_required = bool(requested & HOST_REQUIRED)

    # Priority 1: remaining cross-field local consistency that cannot be
    # expressed as a single field (the Schema owns every local shape check).
    if not authorized <= requested or record["host_enforcement_required"] != host_required:
        return "BLOCKED", "STRUCTURE_OR_REFERENCE_INVALID"
    if host_required and record["host_enforcement_claim"] == "NOT_APPLICABLE":
        return "BLOCKED", "STRUCTURE_OR_REFERENCE_INVALID"
    # Priority 2.
    if any(value in {"UNKNOWN", "INCOMPLETE", "CONTRADICTORY", "PROTECTED_CONTENT"} for value in evidence.values()):
        return "BLOCKED", "SOURCE_OR_SENSITIVITY_UNKNOWN"
    # Priority 3.
    evaluation_at = _parse_time(binding["evaluation_at"])
    expires_at = _parse_time(binding["expires_at"])
    if (
        binding["task_requested_effects"] != record["task_requested_effects"]
        or binding["task_authorized_effects"] != record["task_authorized_effects"]
        or binding["revocation_state"] == "REVOKED"
        or evaluation_at is None or expires_at is None or expires_at <= evaluation_at
    ):
        return "BLOCKED", "BINDING_OR_DECISION_INVALID"
    # Priority 4.
    if requested - set(binding["prior_effect_scope"]):
        return "BLOCKED", "EFFECT_EXPANSION_BLOCKED"
    # Priority 5.
    if not host_required and requested - STATIC_EFFECTS:
        return "OUT_OF_SCOPE", "ACTUAL_CAPABILITY_NOT_AUTHORIZED"
    # Priority 6a / 6b.
    if host_required and record["host_enforcement_claim"] in {"FUTURE_VERIFIABLE", "NOT_AVAILABLE", "NOT_PROVEN", "CONFLICTING"}:
        return "OUT_OF_SCOPE", "HOST_ENFORCEMENT_NOT_PROVEN"
    if host_required:
        return "OUT_OF_SCOPE", "ACTUAL_CAPABILITY_NOT_AUTHORIZED"
    return "EXTERNAL_CAPABILITY_ASSESSMENT_DESIGNED_ONLY", "STATIC_DESIGN_ONLY"


def validate_static_assessment(record: Any, *, schema_gate_passed: bool) -> dict[str, str]:
    """Return a deterministic static result; never invokes a runtime seam."""
    if schema_gate_passed is not True or type(record) is not dict:
        return _blocked("STRUCTURE_OR_REFERENCE_INVALID")
    try:
        outcome, reason = _derived(record)
    except (KeyError, TypeError, ValueError):
        return _blocked("STRUCTURE_OR_REFERENCE_INVALID")
    supplied_outcome = record.get("planned_outcome")
    supplied_reason = record.get("reason_category")
    if supplied_outcome != outcome or supplied_reason != reason:
        return _blocked("STRUCTURE_OR_REFERENCE_INVALID")
    return _result(outcome, reason)
