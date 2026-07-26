from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "skill-routing-and-promotion-contract.md"
SCHEMA = LHE / "schemas" / "skill-routing-decision.schema.json"
SKILL = LHE / "SKILL.md"

EFFECTS = {
    "local-read",
    "local-write",
    "network-read",
    "network-write",
    "external-transfer",
    "account-session-access",
    "install",
    "execute",
    "publish",
    "merge",
    "release",
}
PROHIBITED_KEYS = {
    "account",
    "account_id",
    "account_number",
    "api_key",
    "access_token",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REFERENCE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")
LIFECYCLE_STATUSES = {
    "installed-skill-lifecycle": {"active", "frozen"},
    "incubator-experiment-lifecycle": {
        "locked",
        "proposed",
        "approved_for_design",
        "approved_for_isolated_build",
        "testing",
        "rejected",
        "retained_in_sandbox",
        "candidate_optional",
        "approved_optional",
        "candidate_core",
        "approved_core",
        "deprecated",
    },
    "source-lifecycle": {"locked"},
}
EXPECTED_KEYS = {
    "root": {
        "schema_version",
        "decision_id",
        "evaluated_at",
        "routing_input",
        "candidates",
        "routing_decision",
        "promotion_assessment",
        "contract_boundaries",
    },
    "routing_input": {
        "intent_id",
        "safety_gate",
        "explicit_target_id",
        "explicit_workflow_id",
        "granted_effects",
    },
    "candidate": {
        "route_id",
        "route_kind",
        "availability",
        "activation_policy",
        "intent_match",
        "exact_explicit_match",
        "executable",
        "required_effects",
    },
    "routing_decision": {
        "precedence_step",
        "outcome",
        "selected_route_id",
        "reason_code",
        "granted_effects_before",
        "granted_effects_after",
        "authority_expanded",
        "install_authorized_by_routing",
        "execution_authorized_by_routing",
        "promotion_authorized_by_routing",
    },
    "promotion_assessment": {
        "lifecycle_namespace",
        "lifecycle_status",
        "current_package_disposition",
        "proposed_package_disposition",
        "source_identity",
        "license_gate",
        "security_gate",
        "architecture_gate",
        "validation_gate",
        "eligibility",
        "promotion_state",
        "default_profile_change_requested",
        "assessment_actor",
        "approval_required",
        "human_disposition",
        "human_disposition_actor",
        "decision_reference",
        "next_stage_authorized",
        "automatic_promotion",
    },
    "source_identity": {
        "source_id",
        "immutable_ref",
        "mutable_ref_used",
    },
    "decision_reference": {
        "reference_id",
        "claim_status",
    },
    "contract_boundaries": {
        "static_contract",
        "schema_validated_only",
        "runtime_router",
        "host_enforced",
        "physical_package_migration",
        "third_party_material_included",
    },
}


def candidate(
    route_id: str,
    *,
    route_kind: str = "installed-skill",
    availability: str = "installed-callable",
    activation_policy: str = "implicit",
    intent_match: bool = True,
    exact_explicit_match: bool = False,
    executable: bool = True,
    required_effects: list[str] | None = None,
) -> dict:
    return {
        "route_id": route_id,
        "route_kind": route_kind,
        "availability": availability,
        "activation_policy": activation_policy,
        "intent_match": intent_match,
        "exact_explicit_match": exact_explicit_match,
        "executable": executable,
        "required_effects": required_effects or ["local-read"],
    }


def base_record() -> dict:
    return {
        "schema_version": "1.0",
        "decision_id": "ROUTE-SYNTHETIC-001",
        "evaluated_at": "2026-07-26T10:00:00+10:00",
        "routing_input": {
            "intent_id": "engineering.repository-review",
            "safety_gate": "pass",
            "explicit_target_id": None,
            "explicit_workflow_id": None,
            "granted_effects": ["local-read"],
        },
        "candidates": [candidate("long-horizon-engineering")],
        "routing_decision": {
            "precedence_step": "single-implicit-intent",
            "outcome": "selected",
            "selected_route_id": "long-horizon-engineering",
            "reason_code": "SINGLE_IMPLICIT_MATCH",
            "granted_effects_before": ["local-read"],
            "granted_effects_after": ["local-read"],
            "authority_expanded": False,
            "install_authorized_by_routing": False,
            "execution_authorized_by_routing": False,
            "promotion_authorized_by_routing": False,
        },
        "promotion_assessment": {
            "lifecycle_namespace": "incubator-experiment-lifecycle",
            "lifecycle_status": "locked",
            "current_package_disposition": "sandbox-only",
            "proposed_package_disposition": "bundled-optional",
            "source_identity": {
                "source_id": "synthetic-routing-method",
                "immutable_ref": "0123456789abcdef0123456789abcdef01234567",
                "mutable_ref_used": False,
            },
            "license_gate": "not-verified",
            "security_gate": "not-verified",
            "architecture_gate": "passed",
            "validation_gate": "passed",
            "eligibility": "ineligible",
            "promotion_state": "not-promoted",
            "default_profile_change_requested": False,
            "assessment_actor": "evaluator",
            "approval_required": True,
            "human_disposition": "pending",
            "human_disposition_actor": "none",
            "decision_reference": None,
            "next_stage_authorized": False,
            "automatic_promotion": False,
        },
        "contract_boundaries": {
            "static_contract": True,
            "schema_validated_only": True,
            "runtime_router": False,
            "host_enforced": False,
            "physical_package_migration": False,
            "third_party_material_included": False,
        },
    }


def expected_routing(record: dict) -> tuple[str, str, str | None, str]:
    routing_input = record["routing_input"]
    candidates = record["candidates"]

    if routing_input["safety_gate"] == "stop":
        return "safety-stop-gate", "blocked", None, "SAFETY_STOP"

    explicit_target = routing_input["explicit_target_id"]
    if explicit_target is not None:
        exact = [
            item
            for item in candidates
            if item["route_id"] == explicit_target
            and item["exact_explicit_match"] is True
        ]
        callable_exact = [
            item
            for item in exact
            if item["availability"] == "installed-callable"
            and item["executable"] is True
            and item["activation_policy"] not in {"proposal-only", "sandbox-only"}
        ]
        if len(callable_exact) == 1:
            return (
                "explicit-exact-installed-callable",
                "selected",
                explicit_target,
                "EXPLICIT_CALLABLE_SELECTED",
            )
        return (
            "explicit-unavailable",
            "unavailable",
            None,
            "EXPLICIT_TARGET_UNAVAILABLE",
        )

    explicit_workflow = routing_input["explicit_workflow_id"]
    if explicit_workflow is not None:
        workflows = [
            item
            for item in candidates
            if item["route_id"] == explicit_workflow
            and item["route_kind"] == "workflow"
            and item["availability"] == "installed-callable"
            and item["executable"] is True
            and item["activation_policy"] not in {"proposal-only", "sandbox-only"}
        ]
        if len(workflows) == 1:
            return (
                "explicit-workflow",
                "selected",
                explicit_workflow,
                "EXPLICIT_WORKFLOW_SELECTED",
            )
        return "no-match", "no-match", None, "NO_ELIGIBLE_MATCH"

    implicit = [
        item
        for item in candidates
        if item["intent_match"] is True
        and item["activation_policy"] == "implicit"
        and item["availability"] == "installed-callable"
        and item["executable"] is True
    ]
    if len(implicit) == 1:
        return (
            "single-implicit-intent",
            "selected",
            implicit[0]["route_id"],
            "SINGLE_IMPLICIT_MATCH",
        )
    if len(implicit) > 1:
        return (
            "ambiguity",
            "clarification-required",
            None,
            "AMBIGUOUS_IMPLICIT_MATCH",
        )
    return "no-match", "no-match", None, "NO_ELIGIBLE_MATCH"


def recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key.lower())
            keys.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def exact_keys(value: object, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def valid_effect_list(value: object) -> tuple[bool, bool]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return False, False
    return all(item in EFFECTS for item in value), len(value) == len(set(value))


def effect_set(value: object) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return set()
    return set(value)


def valid_unverified_decision_reference(value: object) -> bool:
    if not exact_keys(value, EXPECTED_KEYS["decision_reference"]):
        return False
    assert isinstance(value, dict)
    return (
        REFERENCE_ID.fullmatch(str(value.get("reference_id", ""))) is not None
        and value.get("claim_status") == "unverified_claim"
    )


def unverified_decision_reference(
    reference_id: str = "DECISION-UNVERIFIED-001",
) -> dict:
    return {
        "reference_id": reference_id,
        "claim_status": "unverified_claim",
    }


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []

    prohibited = recursive_keys(record) & PROHIBITED_KEYS
    if prohibited:
        errors.append("PROHIBITED_SENSITIVE_FIELD")

    if not exact_keys(record, EXPECTED_KEYS["root"]):
        errors.append("UNKNOWN_OR_MISSING_FIELD")
    for field in (
        "routing_input",
        "routing_decision",
        "promotion_assessment",
        "contract_boundaries",
    ):
        if not exact_keys(record.get(field), EXPECTED_KEYS[field]):
            errors.append("UNKNOWN_OR_MISSING_FIELD")

    candidates = record.get("candidates", [])
    if not isinstance(candidates, list):
        return sorted(set(errors + ["INVALID_CANDIDATE_COLLECTION"]))
    if any(not exact_keys(item, EXPECTED_KEYS["candidate"]) for item in candidates):
        errors.append("UNKNOWN_OR_MISSING_FIELD")

    promotion = record.get("promotion_assessment", {})
    source = (
        promotion.get("source_identity", {})
        if isinstance(promotion, dict)
        else {}
    )
    if not exact_keys(source, EXPECTED_KEYS["source_identity"]):
        errors.append("UNKNOWN_OR_MISSING_FIELD")
    decision_reference = (
        promotion.get("decision_reference")
        if isinstance(promotion, dict)
        else None
    )
    if decision_reference is not None and not exact_keys(
        decision_reference,
        EXPECTED_KEYS["decision_reference"],
    ):
        errors.append("UNKNOWN_OR_MISSING_FIELD")
        errors.append("UNVERIFIED_DECISION_REFERENCE_INVALID")

    if "UNKNOWN_OR_MISSING_FIELD" in errors:
        return sorted(set(errors))

    route_ids = [item.get("route_id") for item in candidates]
    if len(route_ids) != len(set(route_ids)):
        errors.append("DUPLICATE_ROUTE_ID")

    for item in candidates:
        route_kind = item.get("route_kind")
        activation = item.get("activation_policy")
        availability = item.get("availability")
        if (
            activation in {"proposal-only", "sandbox-only"}
            or availability in {"proposal-only", "sandbox-only"}
        ) and item.get("executable") is not False:
            errors.append("NON_EXECUTABLE_CANDIDATE_MARKED_EXECUTABLE")
        expected_non_executable = {
            "proposal": ("proposal-only", "proposal-only"),
            "sandbox-candidate": ("sandbox-only", "sandbox-only"),
        }
        if route_kind in expected_non_executable:
            expected_availability, expected_activation = expected_non_executable[
                route_kind
            ]
            if (
                availability != expected_availability
                or activation != expected_activation
                or item.get("executable") is not False
            ):
                errors.append("NON_EXECUTABLE_ROUTE_KIND_MISLABELED")
        required_effects_allowed, required_effects_unique = valid_effect_list(
            item.get("required_effects")
        )
        if not required_effects_allowed:
            errors.append("UNKNOWN_EFFECT_CLASS")
        if not required_effects_unique:
            errors.append("DUPLICATE_EFFECT_CLASS")

    routing_input = record.get("routing_input", {})
    decision = record.get("routing_decision", {})
    granted = routing_input.get("granted_effects", [])
    for effect_list in (
        granted,
        decision.get("granted_effects_before"),
        decision.get("granted_effects_after"),
    ):
        effects_allowed, effects_unique = valid_effect_list(effect_list)
        if not effects_allowed:
            errors.append("UNKNOWN_EFFECT_CLASS")
        if not effects_unique:
            errors.append("DUPLICATE_EFFECT_CLASS")
    if effect_set(decision.get("granted_effects_before")) != effect_set(granted):
        errors.append("AUTHORITY_INPUT_MISMATCH")
    if effect_set(decision.get("granted_effects_after")) != effect_set(granted):
        errors.append("AUTHORITY_EXPANDED")
    for field in (
        "authority_expanded",
        "install_authorized_by_routing",
        "execution_authorized_by_routing",
        "promotion_authorized_by_routing",
    ):
        if decision.get(field) is not False:
            errors.append("ROUTING_AUTHORIZATION_FORBIDDEN")

    expected = expected_routing(record)
    actual = (
        decision.get("precedence_step"),
        decision.get("outcome"),
        decision.get("selected_route_id"),
        decision.get("reason_code"),
    )
    if actual != expected:
        errors.append("ROUTING_PRECEDENCE_MISMATCH")

    selected_id = decision.get("selected_route_id")
    if selected_id is not None:
        selected = [item for item in candidates if item.get("route_id") == selected_id]
        if len(selected) != 1:
            errors.append("SELECTED_ROUTE_NOT_UNIQUE")
        else:
            item = selected[0]
            if not effect_set(item.get("required_effects")) <= effect_set(granted):
                errors.append("SELECTED_ROUTE_AUTHORITY_ESCALATION")
            if (
                decision.get("precedence_step") == "single-implicit-intent"
                and item.get("activation_policy") != "implicit"
            ):
                errors.append("EXPLICIT_ONLY_IMPLICIT_SELECTION")

    if not FULL_SHA.fullmatch(str(source.get("immutable_ref", ""))):
        errors.append("IMMUTABLE_SOURCE_IDENTITY_REQUIRED")
    if source.get("mutable_ref_used") is not False:
        errors.append("MUTABLE_SOURCE_REFERENCE_FORBIDDEN")

    lifecycle_namespace = promotion.get("lifecycle_namespace")
    allowed_statuses = LIFECYCLE_STATUSES.get(lifecycle_namespace)
    if (
        allowed_statuses is None
        or promotion.get("lifecycle_status") not in allowed_statuses
    ):
        errors.append("INVALID_AUTHORITATIVE_LIFECYCLE_STATUS")

    gates = [
        promotion.get("license_gate"),
        promotion.get("security_gate"),
        promotion.get("architecture_gate"),
        promotion.get("validation_gate"),
    ]
    all_gates_pass = all(value == "passed" for value in gates)
    eligibility = promotion.get("eligibility")
    if eligibility == "eligible" and not all_gates_pass:
        errors.append("ELIGIBLE_WITH_FAILED_GATE")
    if eligibility == "ineligible" and all_gates_pass:
        errors.append("INELIGIBLE_WITH_ALL_GATES_PASSED")

    if promotion.get("default_profile_change_requested") is not False:
        errors.append("DEFAULT_PROFILE_CHANGE_FORBIDDEN")
    if promotion.get("automatic_promotion") is not False:
        errors.append("AUTO_PROMOTION_FORBIDDEN")
    if promotion.get("approval_required") is not True:
        errors.append("STATIC_APPROVAL_REQUIRED")
    if (
        promotion.get("human_disposition") != "pending"
        or promotion.get("human_disposition_actor") != "none"
    ):
        errors.append("STATIC_HUMAN_DISPOSITION_MUST_REMAIN_PENDING")
    if decision_reference is not None and not valid_unverified_decision_reference(
        decision_reference
    ):
        errors.append("UNVERIFIED_DECISION_REFERENCE_INVALID")
    if promotion.get("next_stage_authorized") is not False:
        errors.append("STATIC_NEXT_STAGE_AUTHORIZATION_FORBIDDEN")
    if promotion.get("promotion_state") != "not-promoted":
        errors.append("STATIC_PROMOTION_FORBIDDEN")

    boundaries = record.get("contract_boundaries", {})
    expected_boundaries = {
        "static_contract": True,
        "schema_validated_only": True,
        "runtime_router": False,
        "host_enforced": False,
        "physical_package_migration": False,
        "third_party_material_included": False,
    }
    if boundaries != expected_boundaries:
        errors.append("STATIC_BOUNDARY_MISMATCH")
    return sorted(set(errors))


def apply_expected_routing(record: dict) -> None:
    step, outcome, selected, reason = expected_routing(record)
    decision = record["routing_decision"]
    decision["precedence_step"] = step
    decision["outcome"] = outcome
    decision["selected_route_id"] = selected
    decision["reason_code"] = reason


class SkillRoutingPromotionContractTests(unittest.TestCase):
    def assert_valid(self, record: dict) -> None:
        self.assertEqual(validate_record(record), [])

    def assert_rejected(self, record: dict, reason: str) -> None:
        self.assertIn(reason, validate_record(record))

    def test_contract_files_and_skill_route_exist(self) -> None:
        reference = REFERENCE.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Routing And Promotion Governance", skill)
        self.assertIn("skill-routing-and-promotion-contract.md", skill)
        for phrase in (
            "implement a runtime router",
            "Selection MUST preserve the authority",
            "`eligible` means only",
            "MUST NOT write an approved customer disposition",
            "MUST NOT invent or transition a parallel lifecycle",
            "unverified claim",
            "customer-controlled",
            "formal Draft 2020-12 engine result must be",
        ):
            self.assertIn(phrase, reference)

    def test_schema_is_draft_2020_12_and_closed(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["$defs"]["routingDecision"]["properties"][
                "authority_expanded"
            ]["const"]
        )
        self.assertFalse(
            schema["$defs"]["promotionAssessment"]["properties"][
                "automatic_promotion"
            ]["const"]
        )
        self.assertTrue(
            schema["$defs"]["promotionAssessment"]["properties"][
                "approval_required"
            ]["const"]
        )
        self.assertEqual(
            schema["$defs"]["promotionAssessment"]["properties"][
                "promotion_state"
            ]["const"],
            "not-promoted",
        )
        self.assertFalse(
            schema["$defs"]["promotionAssessment"]["properties"][
                "next_stage_authorized"
            ]["const"]
        )
        self.assertFalse(
            schema["$defs"]["contractBoundaries"]["properties"]["runtime_router"][
                "const"
            ]
        )
        self.assertIn(
            "decision_reference",
            schema["$defs"]["promotionAssessment"]["required"],
        )
        for section, field in (
            ("routingInput", "granted_effects"),
            ("routingDecision", "granted_effects_before"),
            ("routingDecision", "granted_effects_after"),
        ):
            definition = schema["$defs"][section]["properties"][field]
            self.assertTrue(definition["uniqueItems"])
            self.assertEqual(
                definition["items"]["$ref"],
                "#/$defs/effectClass",
            )
        decision_record = schema["$defs"]["decisionReference"]["oneOf"][1]
        for field in EXPECTED_KEYS["decision_reference"]:
            self.assertIn(field, decision_record["required"])
        self.assertEqual(
            decision_record["properties"]["claim_status"]["const"],
            "unverified_claim",
        )

    def test_fixed_precedence_safety_stop(self) -> None:
        record = base_record()
        record["routing_input"]["safety_gate"] = "stop"
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "safety-stop-gate",
        )
        self.assert_valid(record)

    def test_fixed_precedence_explicit_exact_installed_callable(self) -> None:
        record = base_record()
        record["routing_input"]["explicit_target_id"] = "exact-skill"
        record["candidates"] = [
            candidate(
                "exact-skill",
                activation_policy="explicit-only",
                exact_explicit_match=True,
            )
        ]
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "explicit-exact-installed-callable",
        )
        self.assert_valid(record)

    def test_fixed_precedence_explicit_unavailable(self) -> None:
        record = base_record()
        record["routing_input"]["explicit_target_id"] = "missing-skill"
        record["candidates"] = [
            candidate(
                "missing-skill",
                availability="not-installed",
                activation_policy="explicit-only",
                exact_explicit_match=True,
                executable=False,
            )
        ]
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "explicit-unavailable",
        )
        self.assert_valid(record)

    def test_fixed_precedence_explicit_workflow(self) -> None:
        record = base_record()
        record["routing_input"]["explicit_workflow_id"] = "review-workflow"
        record["candidates"] = [
            candidate(
                "review-workflow",
                route_kind="workflow",
                activation_policy="explicit-only",
            )
        ]
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "explicit-workflow",
        )
        self.assert_valid(record)

    def test_fixed_precedence_single_implicit(self) -> None:
        self.assert_valid(base_record())

    def test_fixed_precedence_ambiguity(self) -> None:
        record = base_record()
        record["candidates"].append(candidate("second-engineering-skill"))
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "ambiguity",
        )
        self.assert_valid(record)

    def test_fixed_precedence_no_match(self) -> None:
        record = base_record()
        record["candidates"][0]["intent_match"] = False
        apply_expected_routing(record)
        self.assertEqual(
            record["routing_decision"]["precedence_step"],
            "no-match",
        )
        self.assert_valid(record)

    def test_explicit_only_cannot_be_implicitly_selected(self) -> None:
        record = base_record()
        record["candidates"][0]["activation_policy"] = "explicit-only"
        self.assert_rejected(record, "ROUTING_PRECEDENCE_MISMATCH")

    def test_proposal_and_sandbox_candidates_are_never_executable_routes(self) -> None:
        for policy, availability, kind in (
            ("proposal-only", "proposal-only", "proposal"),
            ("sandbox-only", "sandbox-only", "sandbox-candidate"),
        ):
            with self.subTest(policy=policy):
                record = base_record()
                record["candidates"] = [
                    candidate(
                        f"{policy}-candidate",
                        route_kind=kind,
                        availability=availability,
                        activation_policy=policy,
                        executable=True,
                    )
                ]
                apply_expected_routing(record)
                self.assert_rejected(
                    record,
                    "NON_EXECUTABLE_CANDIDATE_MARKED_EXECUTABLE",
                )

    def test_proposal_and_sandbox_route_kinds_cannot_be_relabeled_callable(self) -> None:
        for route_kind in ("proposal", "sandbox-candidate"):
            with self.subTest(route_kind=route_kind):
                record = base_record()
                record["candidates"] = [
                    candidate(
                        f"{route_kind}-route",
                        route_kind=route_kind,
                        availability="installed-callable",
                        activation_policy="implicit",
                        executable=True,
                    )
                ]
                apply_expected_routing(record)
                self.assert_rejected(
                    record,
                    "NON_EXECUTABLE_ROUTE_KIND_MISLABELED",
                )

    def test_selected_route_cannot_expand_authority(self) -> None:
        record = base_record()
        record["candidates"][0]["required_effects"] = [
            "local-read",
            "network-read",
        ]
        self.assert_rejected(record, "SELECTED_ROUTE_AUTHORITY_ESCALATION")

        record = base_record()
        record["routing_decision"]["granted_effects_after"] = [
            "local-read",
            "local-write",
        ]
        self.assert_rejected(record, "AUTHORITY_EXPANDED")

    def test_effect_order_does_not_change_authority(self) -> None:
        record = base_record()
        record["routing_input"]["granted_effects"] = [
            "local-read",
            "local-write",
        ]
        record["routing_decision"]["granted_effects_before"] = [
            "local-write",
            "local-read",
        ]
        record["routing_decision"]["granted_effects_after"] = [
            "local-write",
            "local-read",
        ]
        self.assert_valid(record)

    def test_each_granted_effect_list_rejects_unknown_and_duplicate_effects(self) -> None:
        paths = (
            ("routing_input", "granted_effects"),
            ("routing_decision", "granted_effects_before"),
            ("routing_decision", "granted_effects_after"),
        )
        for section, field in paths:
            with self.subTest(section=section, field=field, case="unknown"):
                record = base_record()
                record[section][field] = ["local-read", "root-shell"]
                self.assert_rejected(record, "UNKNOWN_EFFECT_CLASS")

            with self.subTest(section=section, field=field, case="duplicate"):
                record = base_record()
                record[section][field] = ["local-read", "local-read"]
                self.assert_rejected(record, "DUPLICATE_EFFECT_CLASS")

            with self.subTest(section=section, field=field, case="non-string"):
                record = base_record()
                record[section][field] = ["local-read", {"effect": "root-shell"}]
                self.assert_rejected(record, "UNKNOWN_EFFECT_CLASS")

    def test_routing_cannot_authorize_install_execution_or_promotion(self) -> None:
        for field in (
            "authority_expanded",
            "install_authorized_by_routing",
            "execution_authorized_by_routing",
            "promotion_authorized_by_routing",
        ):
            with self.subTest(field=field):
                record = base_record()
                record["routing_decision"][field] = True
                self.assert_rejected(record, "ROUTING_AUTHORIZATION_FORBIDDEN")

    def test_promotion_requires_immutable_source_and_passed_gates(self) -> None:
        record = base_record()
        record["promotion_assessment"]["eligibility"] = "eligible"
        self.assert_rejected(record, "ELIGIBLE_WITH_FAILED_GATE")

        record = base_record()
        record["promotion_assessment"]["source_identity"]["immutable_ref"] = "main"
        self.assert_rejected(record, "IMMUTABLE_SOURCE_IDENTITY_REQUIRED")

        record = base_record()
        record["promotion_assessment"]["source_identity"][
            "mutable_ref_used"
        ] = True
        self.assert_rejected(record, "MUTABLE_SOURCE_REFERENCE_FORBIDDEN")

    def test_eligible_is_not_promoted_by_static_contract(self) -> None:
        record = base_record()
        promotion = record["promotion_assessment"]
        for field in (
            "license_gate",
            "security_gate",
            "architecture_gate",
            "validation_gate",
        ):
            promotion[field] = "passed"
        promotion["eligibility"] = "eligible"
        self.assert_valid(record)
        self.assertEqual(promotion["promotion_state"], "not-promoted")
        self.assertFalse(promotion["next_stage_authorized"])

        promotion["promotion_state"] = "promoted"
        self.assert_rejected(record, "STATIC_PROMOTION_FORBIDDEN")

    def test_static_contract_requires_pending_human_disposition(self) -> None:
        record = base_record()
        promotion = record["promotion_assessment"]
        promotion["human_disposition"] = "approved"
        promotion["human_disposition_actor"] = "customer"
        self.assert_rejected(
            record,
            "STATIC_HUMAN_DISPOSITION_MUST_REMAIN_PENDING",
        )

        record = base_record()
        record["promotion_assessment"]["approval_required"] = False
        self.assert_rejected(record, "STATIC_APPROVAL_REQUIRED")

    def test_unverified_decision_reference_cannot_authorize_promotion(self) -> None:
        record = base_record()
        promotion = record["promotion_assessment"]
        promotion["decision_reference"] = unverified_decision_reference(
            "DECISION-FAKE-999"
        )
        self.assert_valid(record)

        promotion["next_stage_authorized"] = True
        promotion["promotion_state"] = "promoted"
        self.assert_rejected(
            record,
            "STATIC_NEXT_STAGE_AUTHORIZATION_FORBIDDEN",
        )
        self.assert_rejected(record, "STATIC_PROMOTION_FORBIDDEN")
        for field in (
            "install_authorized_by_routing",
            "execution_authorized_by_routing",
            "promotion_authorized_by_routing",
        ):
            self.assertFalse(record["routing_decision"][field])

    def test_any_decision_or_audit_shape_remains_an_unverified_claim(self) -> None:
        for reference_id in (
            "DECISION-FAKE-999",
            "AUDIT-FAKE-999",
            "HASH-0123456789ABCDEF",
        ):
            with self.subTest(reference_id=reference_id):
                record = base_record()
                promotion = record["promotion_assessment"]
                promotion["decision_reference"] = unverified_decision_reference(
                    reference_id
                )
                self.assert_valid(record)
                self.assertEqual(promotion["human_disposition"], "pending")
                self.assertEqual(promotion["promotion_state"], "not-promoted")
                self.assertFalse(promotion["next_stage_authorized"])

    def test_decision_reference_cannot_claim_authority(self) -> None:
        mutations = (
            "APPROVED",
            {"reference_id": "DECISION-FAKE-999", "claim_status": "approved"},
            {
                "reference_id": "DECISION-FAKE-999",
                "claim_status": "unverified_claim",
                "authorized_action": "promote-package-disposition",
            },
        )
        for decision_reference in mutations:
            with self.subTest(decision_reference=decision_reference):
                record = base_record()
                record["promotion_assessment"][
                    "decision_reference"
                ] = decision_reference
                self.assert_rejected(
                    record,
                    "UNVERIFIED_DECISION_REFERENCE_INVALID",
                )

    def test_lifecycle_status_is_bound_to_authoritative_namespace(self) -> None:
        record = base_record()
        record["promotion_assessment"]["lifecycle_status"] = (
            "self-approved-runtime"
        )
        self.assert_rejected(record, "INVALID_AUTHORITATIVE_LIFECYCLE_STATUS")

        record = base_record()
        record["promotion_assessment"]["lifecycle_namespace"] = (
            "installed-skill-lifecycle"
        )
        record["promotion_assessment"]["lifecycle_status"] = "active"
        self.assert_valid(record)

        record["promotion_assessment"]["lifecycle_status"] = "locked"
        self.assert_rejected(record, "INVALID_AUTHORITATIVE_LIFECYCLE_STATUS")

    def test_auto_promotion_and_default_profile_change_are_rejected(self) -> None:
        record = base_record()
        record["promotion_assessment"]["automatic_promotion"] = True
        self.assert_rejected(record, "AUTO_PROMOTION_FORBIDDEN")

        record = base_record()
        record["promotion_assessment"]["default_profile_change_requested"] = True
        self.assert_rejected(record, "DEFAULT_PROFILE_CHANGE_FORBIDDEN")

    def test_sensitive_fields_are_rejected_anywhere(self) -> None:
        for field in (
            "secret",
            "credential",
            "account_id",
            "account_number",
            "api_key",
            "access_token",
            "client_secret",
        ):
            with self.subTest(field=field):
                record = base_record()
                record["promotion_assessment"]["source_identity"][field] = "x"
                self.assert_rejected(record, "PROHIBITED_SENSITIVE_FIELD")

    def test_unknown_fields_cannot_hide_authority(self) -> None:
        for field in ("auto_promote", "write_authorized", "external_effect"):
            with self.subTest(field=field):
                record = base_record()
                record["promotion_assessment"][field] = True
                self.assert_rejected(record, "UNKNOWN_OR_MISSING_FIELD")

    def test_missing_required_structure_fails_closed_without_exception(self) -> None:
        for path in (
            ("routing_input", "safety_gate"),
            ("routing_decision", "outcome"),
            ("promotion_assessment", "source_identity"),
        ):
            with self.subTest(path=path):
                record = base_record()
                del record[path[0]][path[1]]
                self.assertEqual(
                    validate_record(record),
                    ["UNKNOWN_OR_MISSING_FIELD"],
                )

    def test_static_boundaries_cannot_claim_runtime_or_host_enforcement(self) -> None:
        for field in ("runtime_router", "host_enforced", "physical_package_migration"):
            with self.subTest(field=field):
                record = base_record()
                record["contract_boundaries"][field] = True
                self.assert_rejected(record, "STATIC_BOUNDARY_MISMATCH")

    def test_synthetic_contract_is_deterministic(self) -> None:
        record = base_record()
        first = validate_record(deepcopy(record))
        second = validate_record(deepcopy(record))
        self.assertEqual(first, second)
        self.assertEqual(first, [])


if __name__ == "__main__":
    unittest.main()
