"""Dependency-free tests for the Capability Profile / Doctor sandbox contract."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
GUIDE = INCUBATOR / "architecture" / "capability-profile-doctor.md"
CONTRACT = INCUBATOR / "architecture" / "capability-profile-doctor.json"
SCHEMA = INCUBATOR / "schemas" / "capability-profile-doctor.schema.json"
CASES = ROOT / "tests" / "fixtures" / "capability-profile-doctor" / "cases.json"

ID_PATTERNS = {
    "profile": re.compile(r"^SYN-PROFILE-[0-9]{3}$"),
    "capability": re.compile(r"^SYN-CAP-[0-9]{3}$"),
    "evidence": re.compile(r"^SYN-EVIDENCE-[0-9]{3}$"),
    "diagnostic": re.compile(r"^SYN-DIAG-[0-9]{3}$"),
    "comparison": re.compile(r"^SYN-COMPARE-[0-9]{3}$"),
}
SYNTHETIC_LOCATOR = re.compile(r"^synthetic://[a-z0-9][a-z0-9./-]*$")
OFFSET_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SENSITIVE_KEYS = {
    "account",
    "account_id",
    "credential",
    "credentials",
    "installed_skill_path",
    "log_contents",
    "password",
    "private_material",
    "project_material",
    "secret",
    "token",
    "user_config",
}
BOUNDARY_FIELDS = {
    "installed_skill_read",
    "user_config_read",
    "account_read",
    "credential_read",
    "project_material_read",
    "log_read",
    "network_access",
    "subprocess_execution",
    "dependency_install",
    "default_profile_mutation",
    "routing_change",
    "capability_action",
}
FALLBACK_CONSTRAINT_KEYWORDS = {
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "pattern",
}
FALLBACK_VALIDATION_KEYWORDS = {
    "$ref",
    "additionalProperties",
    "const",
    "enum",
    "items",
    "maxItems",
    "maxLength",
    "minItems",
    "minLength",
    "pattern",
    "required",
    "type",
    "uniqueItems",
}
SCHEMA_METADATA_KEYWORDS = {"$schema", "$id", "title"}
SCHEMA_MAP_KEYWORDS = {"$defs", "properties"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pointer_parent(document, pointer: str):
    parts = pointer.lstrip("/").split("/")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def apply_mutations(base_record: dict, mutations: list[dict]) -> dict:
    record = deepcopy(base_record)
    for mutation in mutations:
        parent, leaf = pointer_parent(record, mutation["path"])
        operation = mutation["op"]
        if operation == "set":
            if isinstance(parent, list):
                parent[int(leaf)] = deepcopy(mutation["value"])
            else:
                parent[leaf] = deepcopy(mutation["value"])
        elif operation == "delete":
            if isinstance(parent, list):
                del parent[int(leaf)]
            else:
                del parent[leaf]
        elif operation == "append":
            target = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
            target.append(deepcopy(mutation["value"]))
        else:
            raise AssertionError(f"Unsupported mutation operation: {operation}")
    return record


def resolve_schema(schema: dict, root_schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        raise AssertionError(f"Unexpected schema reference: {ref!r}")
    name = ref.removeprefix("#/$defs/")
    if name not in root_schema.get("$defs", {}):
        raise AssertionError(f"Missing schema definition: {name}")
    return root_schema["$defs"][name]


def matches_type(value, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: type(item) is bool,
        "integer": lambda item: type(item) is int,
        "null": lambda item: item is None,
    }
    return checks[expected](value)


def canonical_json_value(value):
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is int:
        return ("integer", value)
    if type(value) is float:
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, list):
        return ("array", tuple(canonical_json_value(item) for item in value))
    if isinstance(value, dict):
        return (
            "object",
            tuple(
                (key, canonical_json_value(value[key]))
                for key in sorted(value)
            ),
        )
    raise AssertionError(f"Non-JSON value in structural validation: {value!r}")


def structural_reasons(instance, schema: dict, root_schema: dict):
    schema = resolve_schema(schema, root_schema)
    expected_type = schema.get("type")
    if expected_type is not None and not matches_type(instance, expected_type):
        yield "FIELD_TYPE_INVALID"
        return

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            yield "ARRAY_MIN_ITEMS_VIOLATION"
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            yield "ARRAY_MAX_ITEMS_VIOLATION"
        if schema.get("uniqueItems") is True:
            canonical_items = [canonical_json_value(item) for item in instance]
            if len(set(canonical_items)) != len(canonical_items):
                yield "ARRAY_UNIQUE_ITEMS_VIOLATION"

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            yield "STRING_MIN_LENGTH_VIOLATION"
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            yield "STRING_MAX_LENGTH_VIOLATION"
        if "pattern" in schema:
            try:
                pattern = re.compile(schema["pattern"])
            except (re.error, TypeError):
                yield "SCHEMA_PATTERN_INVALID"
            else:
                if pattern.search(instance) is None:
                    yield "STRING_PATTERN_VIOLATION"

    if "enum" in schema:
        enum_values = schema["enum"]
        if not any(type(instance) is type(item) for item in enum_values):
            yield "FIELD_TYPE_INVALID"
            return
        if not any(type(instance) is type(item) and instance == item for item in enum_values):
            yield "FIELD_ENUM_INVALID"

    if "const" in schema:
        const_value = schema["const"]
        if type(instance) is not type(const_value):
            yield "FIELD_TYPE_INVALID"
            return
        if instance != const_value:
            yield "FIELD_CONST_INVALID"

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        if any(key not in instance for key in schema.get("required", [])):
            yield "REQUIRED_FIELD_MISSING"
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    yield "UNKNOWN_FIELD"
        for key, value in instance.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                yield from structural_reasons(value, child_schema, root_schema)
    elif isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for item in instance:
                yield from structural_reasons(item, item_schema, root_schema)


def schema_validation_keywords(schema):
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key not in SCHEMA_METADATA_KEYWORDS | SCHEMA_MAP_KEYWORDS:
            yield key
        if key in SCHEMA_MAP_KEYWORDS and isinstance(value, dict):
            for child_schema in value.values():
                yield from schema_validation_keywords(child_schema)
        elif key in {"items", "additionalProperties"} and isinstance(value, dict):
            yield from schema_validation_keywords(value)


def unsupported_schema_keywords(schema) -> set[str]:
    return (
        set(schema_validation_keywords(schema))
        - FALLBACK_VALIDATION_KEYWORDS
    )


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def valid_offset_datetime(value) -> bool:
    if not isinstance(value, str) or not OFFSET_DATETIME.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def semantic_reasons(record) -> set[str]:
    reasons: set[str] = set()
    if not isinstance(record, dict):
        return reasons

    if any(key.casefold() in SENSITIVE_KEYS for key in walk_keys(record)):
        reasons.add("SENSITIVE_FIELD_FORBIDDEN")

    fixed_state = {
        "runtime_executable": False,
        "host_enforced": False,
        "human_disposition": "pending",
        "next_stage_authorized": False,
        "promotion_state": "not-promoted",
    }
    if any(
        type(record.get(key)) is type(value) and record.get(key) != value
        for key, value in fixed_state.items()
    ):
        reasons.add("STATIC_CAPABILITY_AUTHORITY_ESCALATION")

    boundaries = record.get("boundaries")
    if isinstance(boundaries, dict) and any(
        boundaries.get(field) is not False for field in BOUNDARY_FIELDS
    ):
        reasons.add("BOUNDARY_OVERRIDE_FORBIDDEN")

    capabilities = record.get("capabilities")
    evidence = record.get("evidence")
    diagnostics = record.get("diagnostics")
    comparisons = record.get("comparative_references")
    if not all(
        isinstance(value, list)
        for value in (capabilities, evidence, diagnostics, comparisons)
    ):
        return reasons

    identifiers: list[str] = []
    identifiers.append(record.get("profile_id"))
    for collection, field in (
        (capabilities, "capability_id"),
        (evidence, "evidence_id"),
        (diagnostics, "diagnostic_id"),
        (comparisons, "comparison_id"),
    ):
        for item in collection:
            if isinstance(item, dict):
                identifiers.append(item.get(field))
    if any(count > 1 for count in Counter(identifiers).values()):
        reasons.add("DUPLICATE_IDENTIFIER")

    invalid_identifiers = False
    id_fields = [
        ("profile", record.get("profile_id")),
        *[
            ("capability", item.get("capability_id"))
            for item in capabilities
            if isinstance(item, dict)
        ],
        *[
            ("evidence", item.get("evidence_id"))
            for item in evidence
            if isinstance(item, dict)
        ],
        *[
            ("diagnostic", item.get("diagnostic_id"))
            for item in diagnostics
            if isinstance(item, dict)
        ],
        *[
            ("comparison", item.get("comparison_id"))
            for item in comparisons
            if isinstance(item, dict)
        ],
    ]
    for namespace, value in id_fields:
        if isinstance(value, str) and not ID_PATTERNS[namespace].fullmatch(value):
            invalid_identifiers = True
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")

    evidence_by_id = {
        item.get("evidence_id"): item for item in evidence if isinstance(item, dict)
    }
    capability_by_id = {
        item.get("capability_id"): item
        for item in capabilities
        if isinstance(item, dict)
    }
    all_ids = set(identifiers)

    for item in evidence:
        if not isinstance(item, dict):
            continue
        locator = item.get("source_locator")
        if isinstance(locator, str) and not SYNTHETIC_LOCATOR.fullmatch(locator):
            reasons.add("NON_SYNTHETIC_FIXTURE_FORBIDDEN")
        observed_at = item.get("observed_at")
        if isinstance(observed_at, str) and not valid_offset_datetime(observed_at):
            reasons.add("OBSERVATION_TIMESTAMP_INVALID")

    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        refs = capability.get("evidence_ids")
        if not isinstance(refs, list):
            continue
        if any(
            not isinstance(ref, str) or not ID_PATTERNS["evidence"].fullmatch(ref)
            for ref in refs
        ):
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")
        missing_refs = [ref for ref in refs if ref not in evidence_by_id]
        if missing_refs:
            if any(ref in all_ids for ref in missing_refs):
                reasons.add("REFERENCE_TARGET_TYPE_MISMATCH")
            else:
                reasons.add("UNRESOLVED_EVIDENCE_REFERENCE")
        effects = capability.get("effects")
        if isinstance(effects, list) and effects:
            reasons.add("EXTERNAL_EFFECT_FORBIDDEN")
        if invalid_identifiers or missing_refs:
            continue
        cards = [evidence_by_id[ref] for ref in refs]
        status = capability.get("status")
        if status == "declared" and (
            not cards or any(card.get("evidence_kind") != "declaration" for card in cards)
        ):
            reasons.add("STATUS_EVIDENCE_MISMATCH")
        elif status == "locally_observed" and not any(
            card.get("evidence_kind") == "static_repository_observation"
            and card.get("source_origin") == "lhe_implementation"
            for card in cards
        ):
            reasons.add("STATUS_EVIDENCE_MISMATCH")

    diagnostics_by_capability: dict[str, list[dict]] = {}
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        capability_id = diagnostic.get("capability_id")
        diagnostics_by_capability.setdefault(capability_id, []).append(diagnostic)
        recovery = diagnostic.get("recovery_suggestion")
        if isinstance(recovery, str) and not recovery.strip():
            reasons.add("RECOVERY_SUGGESTION_REQUIRED")
        if (
            not invalid_identifiers
            and isinstance(capability_id, str)
            and capability_id not in capability_by_id
        ):
            reasons.add("REFERENCE_TARGET_TYPE_MISMATCH")

    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        related = diagnostics_by_capability.get(capability.get("capability_id"), [])
        if capability.get("status") == "unverified" and not any(
            item.get("reason_code") == "CAPABILITY_EVIDENCE_UNVERIFIED"
            for item in related
        ):
            reasons.add("STATUS_EVIDENCE_MISMATCH")
        if capability.get("status") == "blocked" and not any(
            item.get("reason_code") == "CAPABILITY_BLOCKED"
            and item.get("severity") == "blocking"
            for item in related
        ):
            reasons.add("STATUS_EVIDENCE_MISMATCH")

    for comparison in comparisons:
        if not isinstance(comparison, dict):
            continue
        if any(
            type(comparison.get(field)) is bool
            and comparison.get(field) is not False
            for field in (
                "automatic_dependency",
                "authority_granted",
                "implementation_equivalence_claimed",
            )
        ):
            reasons.add("EXTERNAL_COMPARISON_AUTHORITY_FORBIDDEN")
        external_id = comparison.get("external_statement_evidence_id")
        implementation_ids = comparison.get("lhe_implementation_evidence_ids")
        external_card = evidence_by_id.get(external_id)
        implementation_cards = (
            [evidence_by_id.get(item) for item in implementation_ids]
            if isinstance(implementation_ids, list)
            else []
        )
        missing = [
            item
            for item in [external_id, *(implementation_ids or [])]
            if item not in evidence_by_id
        ] if isinstance(implementation_ids, list) else [external_id]
        if missing:
            reasons.add("UNRESOLVED_EVIDENCE_REFERENCE")
            continue
        if (
            external_card.get("source_origin") != "external_source_statement"
            or any(
                card is None or card.get("source_origin") != "lhe_implementation"
                for card in implementation_cards
            )
        ):
            reasons.add(
                "EXTERNAL_STATEMENT_IMPLEMENTATION_EVIDENCE_CONFLATION"
            )

    return reasons


def validate_record(record: dict, schema: dict) -> list[str]:
    reasons = set(structural_reasons(record, schema, schema))
    if "FIELD_TYPE_INVALID" in reasons:
        return ["FIELD_TYPE_INVALID"]
    reasons.update(semantic_reasons(record))
    return sorted(reasons)


class CapabilityProfileDoctorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(SCHEMA)
        cls.contract = load_json(CONTRACT)
        cls.cases = load_json(CASES)

    def record_for(self, case: dict) -> dict:
        return apply_mutations(self.cases["base_record"], case["mutations"])

    def test_contract_files_and_static_boundaries(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        self.assertIn("Status: `sandbox-only`", text)
        self.assertIn("explicit-only", text)
        self.assertIn("not an installed doctor", text)
        self.assertIn("cannot use the network", text)
        self.assertIn("cannot prove capability availability", text)
        self.assertEqual("sandbox-only", self.contract["package_disposition"])
        self.assertEqual("explicit-only", self.contract["activation"])
        self.assertFalse(self.contract["runtime_executable"])
        self.assertFalse(self.contract["host_enforced"])

    def test_schema_is_closed_draft_2020_12(self) -> None:
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            self.schema["$schema"],
        )
        objects = [self.schema, *self.schema["$defs"].values()]
        for item in objects:
            if item.get("type") == "object":
                self.assertIs(item.get("additionalProperties"), False)

    def test_positive_status_fixtures_pass_dependency_free_validation(self) -> None:
        observed = set()
        for case in self.cases["positive_cases"]:
            record = self.record_for(case)
            self.assertEqual([], validate_record(record, self.schema), case["case_id"])
            observed.add(record["capabilities"][0]["status"])
        self.assertEqual(
            {"declared", "locally_observed", "unverified", "blocked"},
            observed,
        )

    def test_negative_fixtures_have_exact_stable_reasons(self) -> None:
        for case in self.cases["negative_cases"]:
            self.assertEqual(
                sorted(case["expected_reason_codes"]),
                validate_record(self.record_for(case), self.schema),
                case["case_id"],
            )

    def test_schema_keyword_fixtures_have_exact_stable_reasons(self) -> None:
        for case in self.cases["schema_keyword_cases"]:
            self.assertEqual(
                sorted(case["expected_reason_codes"]),
                sorted(
                    set(
                        structural_reasons(
                            case["instance"],
                            case["schema"],
                            case["schema"],
                        )
                    )
                ),
                case["case_id"],
            )

    def test_every_stable_reason_has_independent_fixture(self) -> None:
        covered = {
            reason
            for case in self.cases["negative_cases"]
            for reason in case["expected_reason_codes"]
        }
        covered.update(
            reason
            for case in self.cases["schema_keyword_cases"]
            for reason in case["expected_reason_codes"]
        )
        self.assertEqual(set(self.contract["stable_reason_codes"]), covered)
        self.assertEqual(
            len(self.cases["negative_cases"]),
            len({case["case_id"] for case in self.cases["negative_cases"]}),
        )

    def test_schema_constraint_keywords_are_covered_by_fallback(self) -> None:
        used = set(schema_validation_keywords(self.schema))
        self.assertEqual(set(), unsupported_schema_keywords(self.schema))
        self.assertEqual(
            {"minItems", "maxItems", "uniqueItems", "minLength", "pattern"},
            used & FALLBACK_CONSTRAINT_KEYWORDS,
        )
        self.assertTrue(
            {
                "minItems",
                "maxItems",
                "uniqueItems",
                "minLength",
                "maxLength",
                "pattern",
            }.issubset(FALLBACK_CONSTRAINT_KEYWORDS)
        )
        fixture_reasons = {
            reason
            for case in self.cases["schema_keyword_cases"]
            for reason in case["expected_reason_codes"]
        }
        self.assertTrue(
            {
                "ARRAY_MIN_ITEMS_VIOLATION",
                "ARRAY_MAX_ITEMS_VIOLATION",
                "ARRAY_UNIQUE_ITEMS_VIOLATION",
                "STRING_MIN_LENGTH_VIOLATION",
                "STRING_MAX_LENGTH_VIOLATION",
                "STRING_PATTERN_VIOLATION",
                "SCHEMA_PATTERN_INVALID",
            }.issubset(fixture_reasons)
        )

    def test_unsupported_schema_keywords_fail_closed(self) -> None:
        for keyword, value in (
            ("minimum", 0),
            ("contains", {"type": "string"}),
        ):
            with self.subTest(keyword=keyword):
                mutated = deepcopy(self.schema)
                mutated[keyword] = value
                self.assertEqual(
                    {keyword},
                    unsupported_schema_keywords(mutated),
                )

    def test_unique_items_uses_type_sensitive_deep_json_comparison(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertEqual(
            ["ARRAY_UNIQUE_ITEMS_VIOLATION"],
            list(structural_reasons([{"nested": [1]}] * 2, schema, schema)),
        )
        self.assertEqual(
            [],
            list(structural_reasons([1, True], schema, schema)),
        )

    def test_type_errors_stop_dependent_semantic_traversal(self) -> None:
        mutations = (
            ("/profile_id", 7),
            ("/human_disposition", 7),
            ("/capabilities/0/effects", "network"),
            ("/capabilities/0", []),
            ("/evidence/0/evidence_id", []),
            ("/evidence/0/evidence_id", {}),
            ("/evidence/0/evidence_kind", 7),
            ("/evidence/1/source_origin", {}),
            ("/evidence/0/source_locator", 7),
            ("/evidence/0/observed_at", 7),
            ("/evidence/0", []),
            ("/diagnostics/0/recovery_suggestion", 7),
            ("/comparative_references/0/authority_granted", "false"),
            (
                "/comparative_references/0/external_statement_evidence_id",
                [],
            ),
            (
                "/comparative_references/0/lhe_implementation_evidence_ids",
                [[]],
            ),
        )
        for path, value in mutations:
            with self.subTest(path=path):
                record = apply_mutations(
                    self.cases["base_record"],
                    [{"op": "set", "path": path, "value": value}],
                )
                self.assertEqual(
                    ["FIELD_TYPE_INVALID"],
                    validate_record(record, self.schema),
                )

    def test_fixture_content_is_synthetic_and_non_sensitive(self) -> None:
        text = CASES.read_text(encoding="utf-8")
        for prohibited in (
            "/Users/",
            "/private/",
            "file:",
            "CODEX_HOME",
            "api_key",
            "access_token",
        ):
            self.assertNotIn(prohibited, text)
        for tool_name in ("ecc", "graphify", "pwf"):
            self.assertNotIn(tool_name, text.casefold())

    def test_boundaries_are_fixed_false_and_effects_are_empty(self) -> None:
        record = self.cases["base_record"]
        self.assertEqual(BOUNDARY_FIELDS, set(record["boundaries"]))
        self.assertTrue(all(value is False for value in record["boundaries"].values()))
        self.assertTrue(all(not item["effects"] for item in record["capabilities"]))
        self.assertEqual("pending", record["human_disposition"])
        self.assertFalse(record["next_stage_authorized"])
        self.assertEqual("not-promoted", record["promotion_state"])

    def test_comparison_keeps_external_statement_separate(self) -> None:
        record = self.cases["base_record"]
        evidence = {item["evidence_id"]: item for item in record["evidence"]}
        for comparison in record["comparative_references"]:
            external = evidence[comparison["external_statement_evidence_id"]]
            implementation = [
                evidence[item]
                for item in comparison["lhe_implementation_evidence_ids"]
            ]
            self.assertEqual("external_source_statement", external["source_origin"])
            self.assertTrue(
                all(
                    item["source_origin"] == "lhe_implementation"
                    for item in implementation
                )
            )
            self.assertFalse(comparison["automatic_dependency"])
            self.assertFalse(comparison["authority_granted"])
            self.assertFalse(comparison["implementation_equivalence_claimed"])

    def test_formal_schema_accepts_positive_fixtures_when_available(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema)
        for case in self.cases["positive_cases"]:
            errors = list(validator.iter_errors(self.record_for(case)))
            self.assertEqual([], errors, case["case_id"])


if __name__ == "__main__":
    unittest.main()
