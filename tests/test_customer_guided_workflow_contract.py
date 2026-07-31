from __future__ import annotations

from copy import deepcopy
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/long-horizon-engineering/SKILL.md"
README = ROOT / "README.md"
WALKTHROUGH = ROOT / "docs/customer-guided-workflow.md"
CASES = ROOT / "tests/fixtures/customer-guided-workflow/cases.json"
CUSTOMER_PROMPT = ROOT / "prompts/customer-guided-decision.md"
EXAMPLE_ROOT = ROOT / "examples/customer-guided-decision"
OUTCOME_STATUSES = {
    "READY_FOR_CUSTOMER_DECISION",
    "MORE_EVIDENCE_NEEDED",
    "BLOCKED",
}
EVIDENCE_CLASSES = {"FACT", "INFERENCE", "UNKNOWN"}
OUTCOME_LAYERS = {
    "customer_layer",
    "operator_layer",
    "engineering_evidence_layer",
}
CUSTOMER_FIELDS = {
    "request_understood",
    "evidence",
    "status",
    "recommendation",
    "next_safe_action",
    "decision_needed",
}
OPERATOR_FIELDS = {
    "approved_read_scope",
    "allowed_effects",
    "forbidden_effects",
    "sensitive_data_handling",
    "stop_conditions",
    "work_not_performed",
    "customer_approval_required",
    "human_disposition",
    "next_stage_authorized",
}
ENGINEERING_FIELDS = {
    "claims",
    "validation_performed",
    "validation_not_performed",
    "known_limitations",
}
CUSTOMER_JARGON = {
    "schema",
    "receipt",
    "ci",
    "commit",
    "sha",
    "hash",
    "validator",
}


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def collect_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(key)
            keys.extend(collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(collect_keys(item))
    return keys


def outcome_contract_errors(brief: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(brief, dict) or set(brief) != OUTCOME_LAYERS:
        return ["outcome brief must contain exactly the three declared layers"]

    customer = brief["customer_layer"]
    operator = brief["operator_layer"]
    engineering = brief["engineering_evidence_layer"]
    if not isinstance(customer, dict) or set(customer) != CUSTOMER_FIELDS:
        errors.append("customer layer field mismatch")
    if not isinstance(operator, dict) or set(operator) != OPERATOR_FIELDS:
        errors.append("operator layer field mismatch")
    if not isinstance(engineering, dict) or set(engineering) != ENGINEERING_FIELDS:
        errors.append("engineering layer field mismatch")
    if errors:
        return errors

    evidence = customer["evidence"]
    if not isinstance(evidence, list) or not evidence:
        errors.append("customer evidence must be a non-empty list")
    else:
        malformed_evidence = any(
            not isinstance(item, dict)
            or set(item) != {"classification", "finding"}
            or not isinstance(item["classification"], str)
            or not isinstance(item["finding"], str)
            or not item["finding"].strip()
            for item in evidence
        )
        if malformed_evidence:
            errors.append("customer evidence item is malformed")
        elif {
            item["classification"] for item in evidence
        } != EVIDENCE_CLASSES:
            errors.append("customer evidence must cover FACT, INFERENCE, and UNKNOWN")
    for field in ("request_understood", "recommendation", "decision_needed"):
        if not isinstance(customer[field], str) or not customer[field].strip():
            errors.append(f"customer {field} must be a non-empty string")
    if (
        not isinstance(customer["status"], str)
        or customer["status"] not in OUTCOME_STATUSES
    ):
        errors.append("customer status is invalid")
    if (
        not isinstance(customer["next_safe_action"], str)
        or not customer["next_safe_action"].strip()
    ):
        errors.append("exactly one string next safe action is required")
    if (
        not isinstance(customer["decision_needed"], str)
        or not customer["decision_needed"].strip()
    ):
        errors.append("customer decision question is required")

    if operator["customer_approval_required"] is not True:
        errors.append("customer approval must remain required")
    if operator["human_disposition"] != "PENDING":
        errors.append("human disposition must remain pending")
    if operator["next_stage_authorized"] is not False:
        errors.append("next stage must remain unauthorized")
    for field in (
        "approved_read_scope",
        "allowed_effects",
        "forbidden_effects",
        "stop_conditions",
        "work_not_performed",
    ):
        value = operator[field]
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            errors.append(f"operator {field} must contain only strings")
    if (
        not isinstance(operator["sensitive_data_handling"], str)
        or not operator["sensitive_data_handling"].strip()
    ):
        errors.append("operator sensitive data handling is required")

    claims = engineering["claims"]
    if not isinstance(claims, list) or not claims:
        errors.append("engineering claims must be a non-empty list")
    else:
        malformed_claim = any(
            not isinstance(item, dict)
            or set(item)
            != {
                "claim_id",
                "classification",
                "source_locator",
                "verification_status",
            }
            or not all(isinstance(value, str) and value.strip() for value in item.values())
            for item in claims
        )
        if malformed_claim:
            errors.append("engineering claim is malformed")
        else:
            claim_ids = [item["claim_id"] for item in claims]
            if len(claim_ids) != len(set(claim_ids)):
                errors.append("engineering claim IDs must be unique")
            if {
                item["classification"] for item in claims
            } != EVIDENCE_CLASSES:
                errors.append("engineering claims must cover all evidence classes")
    for field in (
        "validation_performed",
        "validation_not_performed",
        "known_limitations",
    ):
        value = engineering[field]
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            errors.append(f"engineering {field} must contain non-empty strings")

    action_keys = [
        key
        for key in collect_keys(brief)
        if key in {"next_safe_action", "next_safe_actions"}
    ]
    if action_keys != ["next_safe_action"]:
        errors.append("only the customer layer may contain one next safe action")
    return errors


class CustomerGuidedWorkflowContractTests(unittest.TestCase):
    def test_skill_exposes_prompt_native_customer_entrypoint(self) -> None:
        text = normalized(SKILL)
        self.assertIn("## Guided Customer Workflow", text)
        self.assertIn("guided customer mode", text)
        self.assertIn("Start with a short intake", text)
        self.assertIn("Customer Outcome Brief", text)
        self.assertIn("### Layer 1: Customer outcome", text)
        self.assertIn("### Layer 2: Operator boundary", text)
        self.assertIn("### Layer 3: Engineering evidence", text)
        self.assertIn("customer_approval_required: true", text)
        self.assertIn("human_disposition: PENDING", text)
        self.assertIn("next_stage_authorized: false", text)
        self.assertIn("not a required installed dependency", text)
        self.assertIn("MORE_EVIDENCE_NEEDED", text)

    def test_outcome_contract_is_closed_and_advisory(self) -> None:
        text = normalized(SKILL)
        customer_text = text.split("### Layer 1: Customer outcome", 1)[1].split(
            "### Layer 2: Operator boundary", 1
        )[0]
        self.assertIn("READY_FOR_CUSTOMER_DECISION", customer_text)
        self.assertIn("MORE_EVIDENCE_NEEDED", customer_text)
        self.assertIn("BLOCKED", customer_text)
        self.assertIn("exactly one bounded action", customer_text)
        self.assertIn(
            "It is a proposal, not execution permission",
            text,
        )
        self.assertIn(
            "Never translate any status into a write, execution, merge, release",
            text,
        )

    def test_required_inputs_and_default_effects_are_visible(self) -> None:
        text = normalized(SKILL)
        for phrase in (
            "desired outcome",
            "decision the customer needs to make",
            "exact files, repositories, or supplied materials",
            "writes, network access, installation, or external action",
            "sensitive-data constraints",
            "Default to read-only analysis, no persistence, no network",
            "pasted non-sensitive excerpt",
            "attached synthetic artifact",
            "exact approved repository path",
            "Do not require an upload",
        ):
            self.assertIn(phrase, text)

    def test_readme_leads_with_customer_value_before_installation(self) -> None:
        text = README.read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        customer_index = text.index("## Customer Quick Start")
        install_index = text.index("## Installation Status")
        self.assertLess(customer_index, install_index)
        self.assertIn("docs/customer-guided-workflow.md", text)
        self.assertIn("prompts/customer-guided-decision.md", text)
        self.assertIn("Start with intake only", text)
        self.assertIn("The material I can provide is", text)
        self.assertIn("plain-language customer outcome", normalized_text)

    def test_walkthrough_covers_end_to_end_customer_journey(self) -> None:
        text = normalized(WALKTHROUGH)
        for heading in (
            "### Customer request",
            "### Guided intake",
            "### Example three-layer result",
            "#### Layer 1: Customer outcome",
            "##### Request understood",
            "##### What we found",
            "##### Status",
            "##### Recommendation",
            "##### Next safe action",
            "##### Decision needed from you",
            "#### Layer 2: Operator boundary",
            "#### Layer 3: Engineering evidence",
        ):
            self.assertIn(heading, text)
        self.assertIn("MORE_EVIDENCE_NEEDED", text)
        self.assertIn("customer_approval_required: true", text)
        self.assertIn("human_disposition: PENDING", text)
        self.assertIn("next_stage_authorized: false", text)

    def test_walkthrough_preserves_evidence_and_authority_boundaries(self) -> None:
        text = normalized(WALKTHROUGH).replace("`", "")
        self.assertIn("FACT means source-supported, not objective certainty", text)
        self.assertIn("INFERENCE is reasoning, not proof", text)
        self.assertIn("does not authorize writing, execution, merge, release", text)
        self.assertIn(
            "no source parser, production export, customer data",
            text.lower(),
        )

    def test_walkthrough_has_a_copy_paste_material_submission_form(self) -> None:
        text = normalized(WALKTHROUGH)
        for phrase in (
            "## How to submit material",
            "pasted non-sensitive text",
            "attached synthetic artifact",
            "exact approved path",
            "not provided",
            "locator:",
            "permitted use:",
        ):
            self.assertIn(phrase, text)
        self.assertIn("cannot represent that authorization as already satisfied", text)

    def test_customer_prompt_and_example_are_directly_usable(self) -> None:
        prompt = normalized(CUSTOMER_PROMPT)
        self.assertIn("Start with intake only", prompt)
        self.assertIn("plain-language customer outcome", prompt)
        self.assertIn("exactly one status", prompt)
        self.assertIn("exactly one next safe action", prompt)
        self.assertIn("human_disposition: PENDING", prompt)
        for name in ("prompt.md", "workflow.md", "expected-output.md"):
            self.assertTrue((EXAMPLE_ROOT / name).is_file(), name)
        expected = normalized(EXAMPLE_ROOT / "expected-output.md")
        self.assertIn("## Layer 1: Customer outcome", expected)
        self.assertIn("## Layer 2: Operator boundary", expected)
        self.assertIn("## Layer 3: Engineering evidence", expected)
        self.assertIn("Do you approve that exact read-only inspection?", expected)

    def test_simulated_customer_journeys_are_closed_and_usable(self) -> None:
        data = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertIs(data["synthetic_only"], True)
        cases = data["cases"]
        self.assertEqual(len(cases), 3)
        self.assertEqual(
            {
                case["outcome_brief"]["customer_layer"]["status"]
                for case in cases
            },
            OUTCOME_STATUSES,
        )

        for case in cases:
            submission = case["customer_submission"]
            brief = case["outcome_brief"]
            with self.subTest(case_id=case["case_id"]):
                for field in (
                    "desired_outcome",
                    "decision_question",
                    "audience",
                    "timing",
                    "success_criteria",
                    "materials",
                    "allowed_effects",
                    "forbidden_effects",
                    "stop_conditions",
                ):
                    self.assertIn(field, submission)
                self.assertGreaterEqual(len(submission["materials"]), 1)
                for material in submission["materials"]:
                    self.assertEqual(
                        set(material),
                        {
                            "locator",
                            "submission_form",
                            "sensitivity",
                            "permitted_use",
                            "availability",
                        },
                    )
                self.assertEqual(outcome_contract_errors(brief), [])
                operator = brief["operator_layer"]
                customer = brief["customer_layer"]
                engineering = brief["engineering_evidence_layer"]
                self.assertEqual(
                    set(operator["allowed_effects"]),
                    set(submission["allowed_effects"]),
                )
                self.assertEqual(
                    set(operator["forbidden_effects"]),
                    set(submission["forbidden_effects"]),
                )
                self.assertEqual(
                    len(customer["evidence"]),
                    len(engineering["claims"]),
                )
                words = set(
                    re.findall(
                        r"[a-z0-9_-]+",
                        json.dumps(customer).lower(),
                    )
                )
                self.assertTrue(CUSTOMER_JARGON.isdisjoint(words))

    def test_contract_mutations_fail_closed(self) -> None:
        brief = json.loads(CASES.read_text(encoding="utf-8"))["cases"][0][
            "outcome_brief"
        ]
        mutations = []

        invalid_status = deepcopy(brief)
        invalid_status["customer_layer"]["status"] = "IMPLEMENT_NOW"
        mutations.append(invalid_status)

        malformed_status = deepcopy(brief)
        malformed_status["customer_layer"]["status"] = []
        mutations.append(malformed_status)

        duplicate_action = deepcopy(brief)
        duplicate_action["engineering_evidence_layer"][
            "next_safe_action"
        ] = "Run it."
        mutations.append(duplicate_action)

        approved = deepcopy(brief)
        approved["operator_layer"]["human_disposition"] = "APPROVED"
        mutations.append(approved)

        authorized = deepcopy(brief)
        authorized["operator_layer"]["next_stage_authorized"] = True
        mutations.append(authorized)

        missing_unknown = deepcopy(brief)
        missing_unknown["customer_layer"]["evidence"] = [
            item
            for item in missing_unknown["customer_layer"]["evidence"]
            if item["classification"] != "UNKNOWN"
        ]
        mutations.append(missing_unknown)

        unhashable_classification = deepcopy(brief)
        unhashable_classification["customer_layer"]["evidence"][0][
            "classification"
        ] = []
        mutations.append(unhashable_classification)

        unhashable_claim_id = deepcopy(brief)
        unhashable_claim_id["engineering_evidence_layer"]["claims"][0][
            "claim_id"
        ] = []
        mutations.append(unhashable_claim_id)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(outcome_contract_errors(mutation))

    def test_blocked_case_never_turns_sensitive_material_into_authority(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
        blocked = next(
            case
            for case in cases
            if case["outcome_brief"]["customer_layer"]["status"] == "BLOCKED"
        )
        submission = blocked["customer_submission"]
        material = submission["materials"][0]
        self.assertEqual(material["sensitivity"], "restricted")
        self.assertEqual(material["permitted_use"], "none")
        self.assertEqual(material["availability"], "not_available")
        self.assertIn("network", submission["forbidden_effects"])
        self.assertIn("external_action", submission["forbidden_effects"])
        operator = blocked["outcome_brief"]["operator_layer"]
        self.assertEqual(operator["approved_read_scope"], [])
        self.assertIs(operator["customer_approval_required"], True)
        self.assertEqual(operator["human_disposition"], "PENDING")
        self.assertIs(operator["next_stage_authorized"], False)


if __name__ == "__main__":
    unittest.main()
