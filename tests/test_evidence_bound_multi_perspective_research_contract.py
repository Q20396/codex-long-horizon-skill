"""Static tests for the evidence-bound multi-perspective research contract."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
GUIDE = (
    INCUBATOR
    / "architecture"
    / "evidence-bound-multi-perspective-research.md"
)
CONTRACT = (
    INCUBATOR
    / "architecture"
    / "evidence-bound-multi-perspective-research.json"
)
SCHEMA = (
    INCUBATOR
    / "schemas"
    / "evidence-bound-multi-perspective-research.schema.json"
)
CASES = (
    ROOT
    / "tests"
    / "fixtures"
    / "evidence-bound-multi-perspective-research"
    / "cases.json"
)

OFFSET_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SYNTHETIC_DOMAINS = {
    "example.invalid",
    "research.example.invalid",
    "market.example.invalid",
    "records.example.invalid",
}
ID_PATTERNS = {
    "contract": re.compile(r"^SYN-CONTRACT-[0-9]{3}$"),
    "entity": re.compile(r"^SYN-ENTITY-[0-9]{3}$"),
    "source": re.compile(r"^SYN-SOURCE-[0-9]{3}$"),
    "evidence": re.compile(r"^SYN-EVIDENCE-[0-9]{3}$"),
    "claim": re.compile(r"^SYN-CLAIM-[0-9]{3}$"),
    "lens": re.compile(r"^SYN-LENS-[0-9]{3}$"),
    "contradiction": re.compile(r"^SYN-CONTRADICTION-[0-9]{3}$"),
    "normalization": re.compile(r"^SYN-NORMALIZATION-[0-9]{3}$"),
}
CLAIM_KINDS = {
    "factual_statement",
    "analytical_inference",
    "research_question",
}
SOURCE_ORIGINS = {
    "primary",
    "authoritative_secondary",
    "secondary",
    "unverified",
}
VERIFIED_SOURCE_ORIGINS = SOURCE_ORIGINS - {"unverified"}
EXTERNAL_ACTION_KEYS = {
    "account_operation",
    "automatic_monitoring",
    "contact",
    "filing",
    "legal_opinion",
    "order",
    "publication",
    "representation",
    "submission",
}
BOUNDARY_FALSE_FIELDS = {
    "runtime_integration",
    "host_enforced",
    "network_access",
    "external_action",
    "private_material_access",
    "third_party_execution",
}


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
            raise AssertionError(f"Unsupported fixture mutation: {operation}")
    return record


def parse_offset_datetime(value) -> tuple[str, datetime | None]:
    if not isinstance(value, str) or not OFFSET_DATETIME.fullmatch(value):
        return "offset", None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "invalid", None
    if parsed.utcoffset() is None:
        return "offset", None
    return "valid", parsed


def walk_values(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)


def walk_items(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_items(child)


def resolve_schema(schema: dict, root_schema: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/$defs/"):
        raise AssertionError(f"Unexpected non-local schema reference: {ref}")
    return root_schema["$defs"][ref.removeprefix("#/$defs/")]


def unknown_fields(instance, schema: dict, root_schema: dict):
    schema = resolve_schema(schema, root_schema)
    if instance is None:
        return
    if isinstance(instance, dict):
        allowed = set(schema.get("properties", {}))
        for key in set(instance) - allowed:
            yield key
        for key, child in instance.items():
            child_schema = schema.get("properties", {}).get(key)
            if child_schema is not None:
                yield from unknown_fields(child, child_schema, root_schema)
    elif isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for child in instance:
                yield from unknown_fields(child, item_schema, root_schema)


def matches_json_type(value, expected_type: str) -> bool:
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: type(item) is bool,
        "null": lambda item: item is None,
        "integer": lambda item: type(item) is int,
        "number": lambda item: type(item) in {int, float},
    }
    check = type_checks.get(expected_type)
    if check is None:
        raise AssertionError(f"Unsupported JSON Schema type: {expected_type}")
    return check(value)


def required_and_type_issues(instance, schema: dict, root_schema: dict):
    schema = resolve_schema(schema, root_schema)
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        if not any(matches_json_type(instance, item) for item in expected_types):
            yield "FIELD_TYPE_INVALID"
            return

    enum_values = schema.get("enum")
    if enum_values is not None:
        if expected_type is None and not any(
            type(instance) is type(item) for item in enum_values
        ):
            yield "FIELD_TYPE_INVALID"
        if not any(
            type(instance) is type(item) and instance == item
            for item in enum_values
        ):
            yield "FIELD_ENUM_INVALID"

    if "const" in schema:
        const_value = schema["const"]
        if expected_type is None and type(instance) is not type(const_value):
            yield "FIELD_TYPE_INVALID"
        if type(instance) is not type(const_value) or instance != const_value:
            yield "FIELD_CONST_INVALID"

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if any(field not in instance for field in required):
            yield "REQUIRED_FIELD_MISSING"
        for key, child in instance.items():
            child_schema = schema.get("properties", {}).get(key)
            if child_schema is not None:
                yield from required_and_type_issues(
                    child, child_schema, root_schema
                )
    elif isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for child in instance:
                yield from required_and_type_issues(
                    child, item_schema, root_schema
                )


def iter_timestamp_values(record: dict):
    yield record.get("research_contract", {}).get("decision_at")
    yield record.get("research_contract", {}).get("as_of")
    for source in record.get("sources", []):
        for field in ("published_at", "available_at", "retrieved_at"):
            yield source.get(field)
    for evidence in record.get("evidence", []):
        yield evidence.get("as_of")
    for claim in record.get("claims", []):
        yield claim.get("as_of")
    for contradiction in record.get("contradictions", []):
        for boundary in contradiction.get("claim_boundaries", []):
            yield boundary.get("as_of")


def identifier_inventory(record: dict):
    inventory = {
        "contract": [record.get("record_id")],
        "entity": [item.get("entity_id") for item in record.get("entities", [])],
        "source": [item.get("source_id") for item in record.get("sources", [])],
        "evidence": [
            item.get("evidence_id") for item in record.get("evidence", [])
        ],
        "claim": [item.get("claim_id") for item in record.get("claims", [])],
        "lens": [item.get("lens_id") for item in record.get("lenses", [])],
        "contradiction": [
            item.get("contradiction_id")
            for item in record.get("contradictions", [])
        ],
        "normalization": [
            item["normalization"].get("normalization_id")
            for item in record.get("contradictions", [])
            if isinstance(item.get("normalization"), dict)
        ],
    }
    return inventory


def reference_issue(
    value,
    expected_namespace: str,
    namespace_ids: dict[str, set],
    all_ids: set,
) -> tuple[bool, bool]:
    unresolved = not isinstance(value, str) or value not in namespace_ids[
        expected_namespace
    ]
    wrong_type = isinstance(value, str) and value in all_ids and unresolved
    return unresolved, wrong_type


def iter_references(record: dict):
    for source in record.get("sources", []):
        if source.get("derivative_of") is not None:
            yield source.get("derivative_of"), "source"
    for evidence in record.get("evidence", []):
        yield evidence.get("source_id"), "source"
    for claim in record.get("claims", []):
        yield claim.get("entity_id"), "entity"
        for evidence_id in claim.get("evidence_ids", []):
            yield evidence_id, "evidence"
    for contradiction in record.get("contradictions", []):
        for boundary in contradiction.get("claim_boundaries", []):
            yield boundary.get("claim_id"), "claim"
            yield boundary.get("entity_id"), "entity"
        normalization = contradiction.get("normalization")
        if isinstance(normalization, dict):
            for evidence_id in normalization.get(
                "normalization_evidence_ids", []
            ):
                yield evidence_id, "evidence"
    deliverable = record.get("deliverable", {})
    for field in ("fact_claim_ids", "inference_claim_ids", "unknown_claim_ids"):
        for claim_id in deliverable.get(field, []):
            yield claim_id, "claim"
    for evidence_id in deliverable.get("evidence_ids", []):
        yield evidence_id, "evidence"
    for contradiction_id in deliverable.get("contradiction_ids", []):
        yield contradiction_id, "contradiction"
    for source_id in deliverable.get("references", []):
        yield source_id, "source"


def structural_reason_codes(record: dict, schema: dict) -> list[str]:
    """Return stable reasons without repairing or authorizing the record."""

    reasons: set[str] = set()

    if any(unknown_fields(record, schema, schema)):
        reasons.add("UNKNOWN_NESTED_FIELD")
    schema_issues = set(required_and_type_issues(record, schema, schema))
    reasons.update(schema_issues)

    for key, _value in walk_items(record):
        if key.casefold() in EXTERNAL_ACTION_KEYS:
            reasons.add("EXTERNAL_ACTION_FIELD_FORBIDDEN")

    if "FIELD_TYPE_INVALID" in schema_issues:
        return sorted(reasons)

    inventory = identifier_inventory(record)
    namespace_ids = {
        namespace: {value for value in values if isinstance(value, str)}
        for namespace, values in inventory.items()
    }
    all_values = [
        value
        for values in inventory.values()
        for value in values
        if isinstance(value, str)
    ]
    all_ids = set(all_values)

    for namespace, values in inventory.items():
        pattern = ID_PATTERNS[namespace]
        if any(not isinstance(value, str) or not pattern.fullmatch(value) for value in values):
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")
        strings = [value for value in values if isinstance(value, str)]
        if len(strings) != len(set(strings)):
            reasons.add("DUPLICATE_IDENTIFIER")

    owners: dict[str, set[str]] = {}
    for namespace, values in namespace_ids.items():
        for value in values:
            owners.setdefault(value, set()).add(namespace)
    if any(len(namespaces) > 1 for namespaces in owners.values()):
        reasons.add("CROSS_NAMESPACE_DUPLICATE_IDENTIFIER")

    for value, expected_namespace in iter_references(record):
        if (
            not isinstance(value, str)
            or not ID_PATTERNS[expected_namespace].fullmatch(value)
        ):
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")
        unresolved, wrong_type = reference_issue(
            value, expected_namespace, namespace_ids, all_ids
        )
        if unresolved:
            reasons.add("UNRESOLVED_EVIDENCE_REFERENCE")
        if wrong_type:
            reasons.add("REFERENCE_TARGET_TYPE_MISMATCH")

    for timestamp in iter_timestamp_values(record):
        status, _parsed = parse_offset_datetime(timestamp)
        if status == "offset":
            reasons.add("TIMESTAMP_OFFSET_REQUIRED")
        elif status == "invalid":
            reasons.add("TIMESTAMP_INVALID")

    decision_status, decision_at = parse_offset_datetime(
        record.get("research_contract", {}).get("decision_at")
    )
    if decision_status == "valid":
        for source in record.get("sources", []):
            available_status, available_at = parse_offset_datetime(
                source.get("available_at")
            )
            if available_status == "valid" and available_at > decision_at:
                reasons.add("LOOKAHEAD_EVIDENCE_FORBIDDEN")

    private = record.get("private_evidence", {})
    if private.get("private_evidence_mode") != "blocked":
        reasons.add("PRIVATE_EVIDENCE_LOCK_OVERRIDE")
    if private.get("private_materials_present") is not False:
        reasons.add("PRIVATE_MATERIAL_PRESENT_FORBIDDEN")

    candidate = record.get("candidate", {})
    if (
        candidate.get("package_disposition") != "sandbox-only"
        or candidate.get("activation") != "explicit-only"
        or candidate.get("runtime_executable") is not False
        or candidate.get("host_enforced") is not False
        or candidate.get("automatic_retrieval") is not False
        or candidate.get("third_party_material_included") is not False
    ):
        reasons.add("STATIC_CONTRACT_AUTHORITY_ESCALATION")

    boundaries = record.get("contract_boundaries", {})
    if (
        boundaries.get("static_contract") is not True
        or boundaries.get("schema_validated_only") is not True
        or any(boundaries.get(field) is not False for field in BOUNDARY_FALSE_FIELDS)
    ):
        reasons.add("STATIC_CONTRACT_AUTHORITY_ESCALATION")

    human = record.get("human_state", {})
    if (
        human.get("human_disposition") != "pending"
        or human.get("next_stage_authorized") is not False
        or human.get("promotion_state") != "not-promoted"
    ):
        reasons.add("HUMAN_STATE_OVERRIDE_FORBIDDEN")

    sources = {
        item.get("source_id"): item for item in record.get("sources", [])
    }
    evidence = {
        item.get("evidence_id"): item for item in record.get("evidence", [])
    }
    approved_origins = set(
        record.get("research_contract", {}).get(
            "approved_source_origins", []
        )
    )
    for source in record.get("sources", []):
        if source.get("source_origin") not in SOURCE_ORIGINS:
            reasons.add("SOURCE_ORIGIN_INVALID")
        elif source.get("source_origin") not in approved_origins:
            reasons.add("SOURCE_ORIGIN_NOT_APPROVED")
        parent_id = source.get("derivative_of")
        if parent_id is not None:
            parent = sources.get(parent_id)
            if (
                isinstance(parent, dict)
                and source.get("independence_group")
                != parent.get("independence_group")
            ):
                reasons.add("DERIVATIVE_INDEPENDENCE_GROUP_MISMATCH")
        locator = source.get("source_locator")
        if not isinstance(locator, str):
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")
            continue
        lower = locator.casefold()
        if lower.startswith(("file:", "/", "\\", "~/", "./", "../")) or re.match(
            r"^[a-z]:[\\/]", lower
        ):
            reasons.add("PRIVATE_LOCAL_PATH_FORBIDDEN")
            continue
        try:
            parsed = urlsplit(locator)
        except ValueError:
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")
            continue
        if (
            parsed.scheme != "https"
            or parsed.hostname not in SYNTHETIC_DOMAINS
            or parsed.username is not None
            or parsed.password is not None
        ):
            reasons.add("INVALID_SYNTHETIC_IDENTIFIER")

    for claim in record.get("claims", []):
        if claim.get("claim_kind") not in CLAIM_KINDS:
            reasons.add("CLAIM_KIND_INVALID")
        epistemic = claim.get("epistemic_status")
        certainty = claim.get("certainty_level")
        expected = {
            "FACT": "source_supported",
            "INFERENCE": "bounded",
            "UNKNOWN": "unresolved",
        }.get(epistemic)
        if expected is None or certainty != expected:
            reasons.add("CERTAINTY_LEVEL_INVALID")
        if epistemic in {"FACT", "INFERENCE"} and not claim.get("limitations"):
            reasons.add("LIMITATIONS_REQUIRED")

        claim_evidence = [
            evidence.get(value)
            for value in claim.get("evidence_ids", [])
            if value in evidence
        ]
        claim_sources = [
            sources.get(item.get("source_id"))
            for item in claim_evidence
            if isinstance(item, dict)
        ]
        origins = {
            item.get("source_origin")
            for item in claim_sources
            if isinstance(item, dict)
        }
        origins_are_valid = bool(origins) and origins <= SOURCE_ORIGINS
        if (
            epistemic == "FACT"
            and origins_are_valid
            and not (origins & VERIFIED_SOURCE_ORIGINS)
        ):
            reasons.add("UNVERIFIED_SOURCE_FACT_FORBIDDEN")
        if (
            epistemic == "INFERENCE"
            and origins_are_valid
            and "unverified" in origins
            and not (origins & VERIFIED_SOURCE_ORIGINS)
        ):
            reasons.add("UNVERIFIED_SOURCE_INFERENCE_UNBOUNDED")

        groups = [
            item.get("independence_group")
            for item in claim_sources
            if isinstance(item, dict)
        ]
        if any(count > 1 for count in Counter(groups).values()):
            reasons.add("DERIVATIVE_SOURCE_INDEPENDENCE_INFLATION")

    for lens in record.get("lenses", []):
        if lens.get("authority_claimed") is not False:
            reasons.add("LENS_AUTHORITY_CLAIM_FORBIDDEN")

    for contradiction in record.get("contradictions", []):
        boundaries_list = contradiction.get("claim_boundaries")
        if (
            not isinstance(boundaries_list, list)
            or len(boundaries_list) != 2
            or any(
                not isinstance(boundary, dict)
                or any(
                    not boundary.get(field)
                    for field in (
                        "claim_id",
                        "as_of",
                        "jurisdiction_or_market",
                        "entity_id",
                        "defined_terms",
                    )
                )
                for boundary in boundaries_list
            )
        ):
            reasons.add("CONTRADICTION_BOUNDARY_MISSING")

        if contradiction.get("consensus_treated_as_proof") is not False:
            reasons.add("CONSENSUS_TREATED_AS_PROOF")

        if contradiction.get("status") == "direct-conflict":
            if (
                isinstance(boundaries_list, list)
                and len(boundaries_list) == 2
                and all(isinstance(boundary, dict) for boundary in boundaries_list)
                and boundaries_list[0].get("claim_id")
                == boundaries_list[1].get("claim_id")
            ):
                reasons.add("DIRECT_CONFLICT_SAME_CLAIM_FORBIDDEN")
            normalization = contradiction.get("normalization")
            if not isinstance(normalization, dict) or not normalization.get(
                "normalization_basis"
            ):
                reasons.add("DIRECT_CONFLICT_NORMALIZATION_REQUIRED")
            else:
                scope = normalization.get("normalization_scope")
                if (
                    not isinstance(scope, dict)
                    or any(
                        not scope.get(field)
                        for field in (
                            "time",
                            "jurisdiction_or_market",
                            "subject",
                            "defined_terms",
                        )
                    )
                ):
                    reasons.add("DIRECT_CONFLICT_SCOPE_REQUIRED")
                evidence_ids = normalization.get("normalization_evidence_ids")
                if (
                    not isinstance(evidence_ids, list)
                    or not evidence_ids
                    or any(value not in namespace_ids["evidence"] for value in evidence_ids)
                ):
                    reasons.add("DIRECT_CONFLICT_EVIDENCE_REQUIRED")

    deliverable = record.get("deliverable", {})
    if deliverable.get("deliverable_kind") != "general_research_support":
        reasons.add("DELIVERABLE_KIND_INVALID")
    if (
        deliverable.get("self_critique", {}).get(
            "independent_review_claimed"
        )
        is not False
    ):
        reasons.add("SELF_CRITIQUE_AS_INDEPENDENT_REVIEW")

    return sorted(reasons)


def iter_object_schemas(schema: dict, root_schema: dict, seen=None):
    if seen is None:
        seen = set()
    schema = resolve_schema(schema, root_schema)
    marker = id(schema)
    if marker in seen:
        return
    seen.add(marker)
    schema_type = schema.get("type")
    if schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    ):
        yield schema
    for child in schema.get("properties", {}).values():
        yield from iter_object_schemas(child, root_schema, seen)
    if "items" in schema:
        yield from iter_object_schemas(schema["items"], root_schema, seen)
    for child in schema.get("$defs", {}).values():
        yield from iter_object_schemas(child, root_schema, seen)


class EvidenceBoundResearchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_json(CONTRACT)
        cls.schema = load_json(SCHEMA)
        cls.cases = load_json(CASES)
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def materialize(self, case: dict) -> dict:
        return apply_mutations(
            self.cases["base_record"], case.get("mutations", [])
        )

    def test_contract_files_and_candidate_boundaries(self) -> None:
        self.assertEqual("sandbox-only", self.contract["package_disposition"])
        self.assertEqual("explicit-only", self.contract["activation"])
        self.assertFalse(self.contract["runtime_executable"])
        self.assertFalse(self.contract["host_enforced"])
        self.assertFalse(self.contract["automatic_retrieval"])
        self.assertEqual("blocked", self.contract["private_evidence_mode"])
        self.assertFalse(self.contract["private_materials_present"])
        self.assertEqual("pending", self.contract["human_disposition"])
        self.assertFalse(self.contract["next_stage_authorized"])
        self.assertEqual("not-promoted", self.contract["promotion_state"])

    def test_schema_recursively_closes_every_modeled_object(self) -> None:
        objects = list(iter_object_schemas(self.schema, self.schema))
        self.assertGreater(len(objects), 10)
        for object_schema in objects:
            self.assertFalse(object_schema.get("additionalProperties"))
            self.assertFalse(object_schema.get("unevaluatedProperties"))

    def test_malformed_array_items_return_type_reason_without_exception(
        self,
    ) -> None:
        malformed_paths = (
            "/entities/0",
            "/sources/0",
            "/evidence/0",
            "/claims/0",
            "/lenses/0",
            "/contradictions/0",
            "/contradictions/0/claim_boundaries/0",
            "/deliverable/next_research_actions/0",
            "/deliverable/risks/0",
        )
        for path in malformed_paths:
            with self.subTest(path=path):
                record = apply_mutations(
                    self.cases["base_record"],
                    [{"op": "set", "path": path, "value": 42}],
                )
                self.assertIn(
                    "FIELD_TYPE_INVALID",
                    structural_reason_codes(record, self.schema),
                )

    def test_positive_fixtures_pass_dependency_free_validation(self) -> None:
        for case in self.cases["positive_cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(
                    case["expected_reason_codes"],
                    structural_reason_codes(
                        self.materialize(case), self.schema
                    ),
                )

    def test_negative_fixtures_have_exact_stable_reason_codes(self) -> None:
        for case in self.cases["negative_cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(
                    sorted(case["expected_reason_codes"]),
                    structural_reason_codes(
                        self.materialize(case), self.schema
                    ),
                )

    def test_every_stable_reason_has_an_independent_negative_fixture(self) -> None:
        stable = set(self.contract["stable_reason_codes"])
        covered = {
            reason
            for case in self.cases["negative_cases"]
            for reason in case["expected_reason_codes"]
        }
        self.assertEqual(stable, covered)
        case_ids = [case["case_id"] for case in self.cases["negative_cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_schema_accepts_positive_fixtures_when_engine_is_available(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator, FormatChecker

        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )
        for case in self.cases["positive_cases"]:
            with self.subTest(case=case["case_id"]):
                errors = list(validator.iter_errors(self.materialize(case)))
                self.assertEqual([], errors)

    def test_documentation_states_static_limits_without_runtime_claims(self) -> None:
        normalized_guide = " ".join(self.guide.split())
        required = (
            "`FACT` means a factual statement supported by a locatable source",
            "objective certainty",
            "not-directly-comparable",
            "private_evidence_mode: blocked",
            "general_research_support",
            "human_disposition: pending",
            "cannot prove",
            "host-enforced isolation",
        )
        for text in required:
            self.assertIn(text, normalized_guide)

    def test_base_fixture_contains_no_private_path_or_real_domain(self) -> None:
        serialized = json.dumps(self.cases["base_record"], sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("/private/", serialized)
        for source in self.cases["base_record"]["sources"]:
            self.assertIn(urlsplit(source["source_locator"]).hostname, SYNTHETIC_DOMAINS)


if __name__ == "__main__":
    unittest.main()
