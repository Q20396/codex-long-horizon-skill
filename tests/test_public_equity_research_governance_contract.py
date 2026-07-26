"""Static contract tests for clean-room public-equity research governance."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qsl, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
CONTRACT = INCUBATOR / "architecture" / "public-equity-research-governance.json"
GUIDE = INCUBATOR / "architecture" / "public-equity-research-governance.md"
SCHEMA = (
    INCUBATOR
    / "schemas"
    / "public-equity-research-governance.schema.json"
)
CASES = (
    ROOT
    / "tests"
    / "fixtures"
    / "public-equity-research-governance"
    / "cases.json"
)
PRIORITY = INCUBATOR / "architecture" / "implementation-priority.md"

OFFSET_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
DISPOSITIONS = {
    "accepted_for_monitoring",
    "request_more_evidence",
    "deferred",
    "rejected",
    "superseded",
}
RESEARCH_ACTIONS = {
    "source_review",
    "data_validation",
    "thesis_revision",
    "risk_review",
    "scenario_update",
    "request_customer_disposition",
}
BOUNDARY_FIELDS = {
    "network_action_performed",
    "provider_access_performed",
    "account_access_performed",
    "credential_access_performed",
    "customer_material_used",
    "customer_material_uploaded",
    "external_transfer_performed",
    "order_generated",
    "order_transmitted",
    "trade_executed",
    "automatic_rebalance_performed",
    "background_monitoring_started",
    "third_party_code_imported",
    "third_party_code_executed",
    "host_enforcement_claimed",
    "installed_runtime_enforcement_claimed",
}
ENTITY_ID_FIELDS = (
    ("sources", "source_id"),
    ("core_claims", "claim_id"),
    ("assumptions", "assumption_id"),
    ("scenarios", "scenario_id"),
    ("risks", "risk_id"),
    ("missing_evidence", "missing_evidence_id"),
    ("decision_log", "entry_id"),
)
SENSITIVE_LOCATOR_KEYS = {
    "account",
    "account_id",
    "accountid",
    "api_key",
    "apikey",
    "credential",
    "credentials",
    "password",
    "token",
}
FORBIDDEN_ACCOUNT_KEYS = {
    "account",
    "account_id",
    "api_key",
    "credential",
    "credentials",
    "password",
    "token",
}
FORBIDDEN_CUSTOMER_KEYS = {
    "customer_account",
    "customer_email",
    "customer_name",
    "customer_material",
    "real_customer_data",
}
FORBIDDEN_ENDPOINT_KEYS = {
    "broker_endpoint",
    "endpoint",
    "execution_endpoint",
}
RESEARCH_OUTPUT_EXECUTION_ACCOUNT_PATTERNS = (
    re.compile(r"\bbroker\s+payload\b"),
    re.compile(
        r"\b(?:submit|transmit|send|route|place|execute)\b"
        r".{0,40}\b(?:to\s+)?(?:a\s+)?broker\b",
    ),
    re.compile(
        r"\b(?:account|acct)\s+(?:id|identifier|number)\b",
    ),
    re.compile(
        r"\bcredential\s+(?:key|password|secret|token)\b",
    ),
    re.compile(
        r"\b(?:api|access|account|authentication|broker|execution|login)"
        r"\s+credentials?\b",
    ),
    re.compile(
        r"\bcredentials?\s+(?:for\s+)?"
        r"(?:account|broker|endpoint|login|token)\b",
    ),
    re.compile(
        r"\b(?:api\s+(?:key|token)|access\s+token|password)\b",
    ),
    re.compile(
        r"\b(?:broker|execution|order|trading)\s+endpoint\b",
    ),
    re.compile(
        r"\b(?:order|proposed|trade|position)\s+quantit(?:y|ies)\b",
    ),
)
AUTOMATED_EXECUTION_PATTERNS = (
    re.compile(
        r"\bautomatic\s+(?:trading|rebalancing)\b",
    ),
    re.compile(
        r"\bautomated\s+(?:trade|trading|rebalance|rebalancing)\b",
    ),
)
ACCOUNT_ACCESS_PATTERNS = (
    re.compile(
        r"\b(?:access|operate|use)\s+(?:the\s+|an?\s+)?"
        r"(?:brokerage\s+)?account\b",
    ),
    re.compile(
        r"\b(?:brokerage\s+)?account\s+(?:access|operations?)\b",
    ),
    re.compile(
        r"\bperform\s+(?:an?\s+)?(?:brokerage\s+)?account\s+operations?\b",
    ),
    re.compile(
        r"\b(?:use|using|with)\s+(?:an?\s+|the\s+)?"
        r"(?:credentials?|tokens?|password|api\s+key)\b"
        r".{0,40}\b(?:to\s+)?access\s+(?:the\s+|an?\s+)?"
        r"(?:brokerage\s+)?account\b",
    ),
)
LOCATOR_ACCOUNT_REFERENCE = re.compile(
    r"(?:^|[/#?&;._=-])accounts?"
    r"(?:[_-]?(?:id|number))?(?:[=:/#?&;._-]|$)",
    re.IGNORECASE,
)
LOCATOR_CREDENTIAL_REFERENCE = re.compile(
    r"(?:^|[/#?&;._=-])(?:api[_-]?(?:key|token)|access[_-]?token|"
    r"credentials?|password|token)(?:[=:/#?&;._-]|$)",
    re.IGNORECASE,
)
LOCATOR_EXECUTION_ENDPOINT_REFERENCE = re.compile(
    r"(?:^|[/#?&;._=-])(?:(?:broker|execution)[/#?&;._=-]*)?endpoint"
    r"(?:[=:/#?&;._-]|$)",
    re.IGNORECASE,
)
SEMANTIC_TOKEN_SEPARATORS = re.compile(r"[\s_./:\\-]+")
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
LOCATOR_DECODE_MAX_ROUNDS = 3


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


def parse_offset_datetime(value) -> datetime | None:
    if not isinstance(value, str) or not OFFSET_DATETIME.fullmatch(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        return parsed
    except ValueError:
        return None


def all_timestamp_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_at") or key == "research_as_of":
                yield child
            yield from all_timestamp_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_timestamp_values(child)


def has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_semantic_text(value: str) -> str:
    """Normalize only the bounded separator set declared by this contract."""

    return SEMANTIC_TOKEN_SEPARATORS.sub(" ", value.casefold()).strip()


def decode_locator_component(value: str) -> str | None:
    """Decode a URL component until stable, within a small fixed bound."""

    current = value
    for _ in range(LOCATOR_DECODE_MAX_ROUNDS):
        if INVALID_PERCENT_ESCAPE.search(current):
            return None
        decoded = unquote(current)
        if decoded == current:
            return current
        current = decoded
    if INVALID_PERCENT_ESCAPE.search(current) or unquote(current) != current:
        return None
    return current


def source_locator_issue(value) -> str | None:
    if not has_text(value):
        return "invalid"
    locator = value.strip()
    lower = locator.lower()
    if (
        lower.startswith(("file:", "/", "\\", "~/", "./", "../"))
        or re.match(r"^[a-z]:[\\/]", lower)
        or re.search(
            r"(?:^|[/?#&;])(?:api[_-]?key|token|password|credential|"
            r"account(?:[_-]?id)?)(?:[=:/]|$)",
            lower,
        )
    ):
        if re.search(
            r"(?:^|[/?#&;])accounts?(?:[_-]?id)?(?:[=:/]|$)",
            lower,
        ):
            return "account"
        return "sensitive"

    if lower.startswith("https://"):
        try:
            parsed = urlsplit(locator)
        except ValueError:
            return "sensitive"
        if "%" in parsed.netloc:
            return "authority_percent"
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return "sensitive"
        decoded_path = decode_locator_component(parsed.path)
        decoded_query = decode_locator_component(parsed.query)
        decoded_fragment = decode_locator_component(parsed.fragment)
        if None in (decoded_path, decoded_query, decoded_fragment):
            return "sensitive"
        query_keys = {
            normalized_key(key) for key, _ in parse_qsl(decoded_query)
        }
        decoded_components = (
            f"{decoded_path}?{decoded_query}#{decoded_fragment}"
        )
        if (
            query_keys & {"account", "account_id", "accountid"}
            or LOCATOR_ACCOUNT_REFERENCE.search(decoded_components)
        ):
            return "account"
        if (
            query_keys & SENSITIVE_LOCATOR_KEYS
            or LOCATOR_CREDENTIAL_REFERENCE.search(decoded_components)
            or LOCATOR_EXECUTION_ENDPOINT_REFERENCE.search(decoded_components)
        ):
            return "sensitive"
        return None

    if bool(
        re.fullmatch(r"urn:[A-Za-z0-9][A-Za-z0-9:._-]*", locator)
        or re.fullmatch(r"sha256:[A-Fa-f0-9]{64}", locator)
        or re.fullmatch(r"asx-announcement:[A-Za-z0-9._-]+", locator)
        or re.fullmatch(r"internal-document-id:[A-Za-z0-9._:-]+", locator)
    ):
        return None
    return "invalid"


def source_locator_is_safe(value) -> bool:
    return source_locator_issue(value) is None


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def walk_mapping(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield normalized_key(str(key)), child
            yield from walk_mapping(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_mapping(child)


def walk_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_text(child)


def research_output_text(record: dict):
    for field in (
        "core_claims",
        "assumptions",
        "scenarios",
        "risks",
        "missing_evidence",
        "recommendation",
        "decision_log",
    ):
        yield from walk_text(record.get(field, []))


def has_duplicate_entity_ids(record: dict) -> bool:
    for collection, id_field in ENTITY_ID_FIELDS:
        values = [
            item.get(id_field)
            for item in record.get(collection, [])
            if isinstance(item, dict)
        ]
        if len(values) != len(set(values)):
            return True
    return False


def structural_reason_codes(record: dict) -> list[str]:
    """Return stable rejection reasons without repairing the supplied record."""

    reasons: set[str] = set()
    sources = record.get("sources", [])
    for source in sources:
        if not has_text(source.get("source_locator")):
            reasons.add("EVIDENCE_LOCATOR_REQUIRED")
        else:
            locator_issue = source_locator_issue(source["source_locator"])
            if locator_issue == "account":
                reasons.add("LOCATOR_ACCOUNT_REFERENCE_FORBIDDEN")
            elif locator_issue == "authority_percent":
                reasons.add(
                    "LOCATOR_AUTHORITY_PERCENT_ENCODING_FORBIDDEN"
                )
            elif locator_issue is not None:
                reasons.add("SENSITIVE_ACCOUNT_OR_CREDENTIAL_FORBIDDEN")
        if not has_text(source.get("source_version")):
            reasons.add("EVIDENCE_VERSION_REQUIRED")

    for value in all_timestamp_values(record):
        if value is None:
            continue
        if parse_offset_datetime(value) is None:
            reasons.add("TIMESTAMP_OFFSET_REQUIRED")
    context = record.get("research_context", {})
    required_timestamps = (
        record.get("created_at"),
        context.get("research_as_of"),
        context.get("decision_at"),
    )
    if any(value is None for value in required_timestamps):
        reasons.add("TIMESTAMP_OFFSET_REQUIRED")
    for entry in record.get("decision_log", []):
        if entry.get("recorded_at") is None or entry.get("research_as_of") is None:
            reasons.add("TIMESTAMP_OFFSET_REQUIRED")

    status = record.get("point_in_time_status")
    block_reasons = set(record.get("point_in_time_block_reasons", []))
    imprecise = any(
        source.get("time_precision") != "exact_timestamp" for source in sources
    )
    missing_source_time = any(
        source.get(field) is None
        for source in sources
        for field in (
            "effective_at",
            "published_at",
            "available_at",
            "retrieved_at",
        )
    )
    precision_is_blocked = (
        status == "point_in_time_blocked"
        and bool(
            block_reasons
            & {
                "TIMESTAMP_MISSING",
                "TIMESTAMP_CONFLICT",
                "TIME_PRECISION_DATE_ONLY",
                "TIME_PRECISION_UNKNOWN",
            }
        )
    )
    if (imprecise or missing_source_time) and not precision_is_blocked:
        reasons.add("TIME_PRECISION_BLOCKED")

    decision_at = record.get("research_context", {}).get("decision_at")
    decision_time = parse_offset_datetime(decision_at)
    if decision_time is not None:
        available_after_decision = False
        for source in sources:
            available_time = parse_offset_datetime(source.get("available_at"))
            if available_time is not None and available_time > decision_time:
                available_after_decision = True
        violation_is_blocked = (
            status == "point_in_time_blocked"
            and "AVAILABLE_AFTER_DECISION" in block_reasons
        )
        if available_after_decision and not violation_is_blocked:
            reasons.add("POINT_IN_TIME_VIOLATION")

    required_claim_fields = (
        "claim",
        "bull_case",
        "bear_case",
        "supporting_evidence_ids",
        "disconfirming_evidence_ids",
        "falsification_condition",
        "data_to_verify",
    )
    for claim in record.get("core_claims", []):
        if any(
            not claim.get(field)
            or (isinstance(claim.get(field), str) and not claim[field].strip())
            for field in required_claim_fields
        ):
            reasons.add("CORE_CLAIM_COMPLETENESS_REQUIRED")

    if has_duplicate_entity_ids(record):
        reasons.add("ENTITY_ID_DUPLICATE")

    source_ids = {item.get("source_id") for item in sources}
    assumption_ids = {
        item.get("assumption_id") for item in record.get("assumptions", [])
    }
    scenario_ids = {
        item.get("scenario_id") for item in record.get("scenarios", [])
    }
    risk_ids = {item.get("risk_id") for item in record.get("risks", [])}
    missing_ids = {
        item.get("missing_evidence_id")
        for item in record.get("missing_evidence", [])
    }
    references_valid = True
    for claim in record.get("core_claims", []):
        references_valid &= set(claim.get("supporting_evidence_ids", [])).issubset(
            source_ids
        )
        references_valid &= set(
            claim.get("disconfirming_evidence_ids", [])
        ).issubset(source_ids)
    recommendation = record.get("recommendation", {})
    references_valid &= set(recommendation.get("risk_ids", [])).issubset(risk_ids)
    references_valid &= set(
        recommendation.get("missing_evidence_ids", [])
    ).issubset(missing_ids)
    for entry in record.get("decision_log", []):
        references_valid &= set(entry.get("source_ids", [])).issubset(source_ids)
        references_valid &= set(entry.get("assumption_ids", [])).issubset(
            assumption_ids
        )
        references_valid &= set(entry.get("scenario_ids", [])).issubset(
            scenario_ids
        )
        references_valid &= set(entry.get("risk_ids", [])).issubset(risk_ids)
        references_valid &= set(
            entry.get("missing_evidence_ids", [])
        ).issubset(missing_ids)
    if not references_valid:
        reasons.add("DECISION_REFERENCE_INVALID")

    prior_entries: set[str] = set()
    for index, entry in enumerate(record.get("decision_log", [])):
        entry_id = entry.get("entry_id")
        supersedes = entry.get("supersedes_entry_id")
        if index > 0 and not supersedes:
            reasons.add("DECISION_SUPERSESSION_REQUIRED")
        if supersedes is not None and supersedes not in prior_entries:
            reasons.add("DECISION_SUPERSESSION_REQUIRED")
        prior_entries.add(entry_id)
        disposition = entry.get("human_disposition")
        if disposition not in DISPOSITIONS:
            reasons.add("HUMAN_DISPOSITION_INVALID")
        if disposition in DISPOSITIONS and not has_text(entry.get("human_disposition_at")):
            reasons.add("HUMAN_DISPOSITION_TIMESTAMP_REQUIRED")

    if recommendation.get("human_disposition") not in DISPOSITIONS:
        reasons.add("HUMAN_DISPOSITION_INVALID")

    for key, _ in walk_mapping(recommendation):
        key_parts = set(key.split("_"))
        if "order" in key_parts:
            reasons.add("ORDER_FIELD_FORBIDDEN")
        if key_parts & {"quantity", "qty"}:
            reasons.add("QUANTITY_FIELD_FORBIDDEN")
        if "broker" in key_parts and "payload" in key_parts:
            reasons.add("BROKER_PAYLOAD_FORBIDDEN")
        if key in FORBIDDEN_ACCOUNT_KEYS or key_parts & FORBIDDEN_ACCOUNT_KEYS:
            reasons.add("SENSITIVE_ACCOUNT_OR_CREDENTIAL_FORBIDDEN")
        if key in FORBIDDEN_ENDPOINT_KEYS or "endpoint" in key_parts:
            reasons.add("REAL_ENDPOINT_FORBIDDEN")
        if key in FORBIDDEN_CUSTOMER_KEYS or (
            "customer" in key_parts
            and key_parts & {"account", "data", "email", "material", "name"}
        ):
            reasons.add("REAL_CUSTOMER_DATA_FORBIDDEN")

    next_action = recommendation.get("next_research_action", {})
    action_type = next_action.get("action_type")
    if action_type not in RESEARCH_ACTIONS:
        reasons.add("AUTOMATION_EXECUTION_FORBIDDEN")
    for output in research_output_text(record):
        output_text = output.lower()
        normalized_output = normalize_semantic_text(output)
        if any(
            pattern.search(normalized_output)
            for pattern in RESEARCH_OUTPUT_EXECUTION_ACCOUNT_PATTERNS
        ):
            reasons.add(
                "RESEARCH_OUTPUT_EXECUTION_OR_ACCOUNT_SEMANTICS_FORBIDDEN"
            )
        if any(
            pattern.search(normalized_output)
            for pattern in AUTOMATED_EXECUTION_PATTERNS
        ):
            reasons.add("AUTOMATED_EXECUTION_SEMANTICS_FORBIDDEN")
        if any(
            pattern.search(normalized_output)
            for pattern in ACCOUNT_ACCESS_PATTERNS
        ):
            reasons.add("ACCOUNT_ACCESS_SEMANTICS_FORBIDDEN")
        simulated_order = re.search(
            r"\b(?:simulat(?:e|ed|ing|ion)|paper[- ]?trade)"
            r".{0,40}(?:submit|place|transmit|send|execute)"
            r".{0,20}(?:order|trade)\b",
            output_text,
        )
        if simulated_order:
            reasons.add("SIMULATED_ORDER_SUBMISSION_FORBIDDEN")
        elif (
            re.search(
                r"\b(?:place|submit|transmit|send|execute)"
                r".{0,20}(?:order|trade|buy|sell)\b",
                output_text,
            )
            or re.search(
                r"\b(?:buy|sell)\s+(?:\d+(?:\.\d+)?\s+)?"
                r"(?:shares?|units?|stock|securities)\b",
                output_text,
            )
        ):
            reasons.add("ORDER_INSTRUCTION_FORBIDDEN")
        if re.search(
            r"\b(?:automatically|automatic|autonomously|autonomous)"
            r".{0,30}(?:trade|rebalance)\b",
            output_text,
        ):
            reasons.add("AUTOMATION_EXECUTION_FORBIDDEN")

    boundaries = record.get("boundaries", {})
    if boundaries.get("host_enforcement_claimed") is not False or boundaries.get(
        "installed_runtime_enforcement_claimed"
    ) is not False:
        reasons.add("HOST_ENFORCEMENT_CLAIM_FORBIDDEN")
    if any(
        boundaries.get(field) is not False
        for field in (
            "order_generated",
            "order_transmitted",
            "trade_executed",
            "automatic_rebalance_performed",
            "background_monitoring_started",
        )
    ):
        reasons.add("AUTOMATION_EXECUTION_FORBIDDEN")
    if any(
        boundaries.get(field) is not False
        for field in (
            "account_access_performed",
            "credential_access_performed",
        )
    ):
        reasons.add("SENSITIVE_ACCOUNT_OR_CREDENTIAL_FORBIDDEN")
    if any(
        boundaries.get(field) is not False
        for field in (
            "customer_material_used",
            "customer_material_uploaded",
        )
    ):
        reasons.add("REAL_CUSTOMER_DATA_FORBIDDEN")
    if any(
        boundaries.get(field) is not False
        for field in (
            "network_action_performed",
            "provider_access_performed",
            "external_transfer_performed",
            "third_party_code_imported",
            "third_party_code_executed",
        )
    ):
        reasons.add("BOUNDARY_ASSERTION_FORBIDDEN")
    if set(boundaries) != BOUNDARY_FIELDS:
        reasons.add("BOUNDARY_ASSERTION_FORBIDDEN")

    return sorted(reasons)


class PublicEquityResearchGovernanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_json(CONTRACT)
        cls.schema = load_json(SCHEMA)
        cls.fixtures = load_json(CASES)

    def materialize(self, case: dict) -> dict:
        return apply_mutations(
            self.fixtures["base_record"],
            case["mutations"],
        )

    def test_contract_is_locked_research_only_and_non_executable(self) -> None:
        self.assertEqual("candidate_only", self.contract["status"])
        self.assertFalse(self.contract["registered_skill"])
        self.assertFalse(self.contract["runtime_integration_exists"])
        self.assertTrue(self.contract["research_only"])
        self.assertTrue(self.contract["human_decision_required"])
        denied = [
            key
            for key in self.contract
            if key.endswith("_authorized")
            or key.endswith("_allowed")
            or key.endswith("_claimed")
        ]
        self.assertTrue(denied)
        for field in denied:
            self.assertIs(self.contract[field], False, field)

    def test_schema_is_closed_draft_2020_12(self) -> None:
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            self.schema["$schema"],
        )
        self.assertEqual(
            "urn:codex-long-horizon-skill:schema:"
            "public-equity-research-governance:1.0.0",
            self.schema["$id"],
        )
        self.assertFalse(self.schema["additionalProperties"])
        self.assertTrue(
            self.schema["$defs"]["source"]["properties"]["source_locator"][
                "x-lhe-decoded-locator-validation-required"
            ]
        )
        boundaries = self.schema["$defs"]["boundaries"]["properties"]
        for rule in boundaries.values():
            self.assertEqual({"const": False}, rule)
        self.assertEqual(BOUNDARY_FIELDS, set(boundaries))
        for collection, id_field in ENTITY_ID_FIELDS:
            self.assertEqual(
                id_field,
                self.schema["properties"][collection]["x-lhe-unique-key"],
            )

    def test_every_fixture_has_exact_stable_reason_codes(self) -> None:
        stable = set(self.contract["stable_reason_codes"])
        seen: set[str] = set()
        for case in self.fixtures["cases"]:
            record = self.materialize(case)
            actual = structural_reason_codes(record)
            self.assertEqual(
                case["expected_reason_codes"],
                actual,
                case["case_id"],
            )
            self.assertEqual(case["expected_valid"], not actual, case["case_id"])
            seen.update(actual)
        self.assertEqual(stable, seen)

    def test_formal_schema_validates_positive_fixtures_when_engine_available(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator, FormatChecker

        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(
            self.schema,
            format_checker=FormatChecker(),
        )
        for case in self.fixtures["cases"]:
            if not case["expected_valid"]:
                continue
            errors = list(validator.iter_errors(self.materialize(case)))
            self.assertEqual([], errors, case["case_id"])

    def test_formal_schema_rejects_structural_negative_fixtures(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator, FormatChecker

        validator = Draft202012Validator(
            self.schema,
            format_checker=FormatChecker(),
        )
        structural_cases = {
            "missing-evidence-locator",
            "missing-evidence-version",
            "credential-in-source-locator",
            "timestamp-without-offset",
            "missing-source-time-not-blocked",
            "human-disposition-time-missing",
            "human-disposition-invalid",
            "core-claim-bear-case-missing",
            "order-field-present",
            "quantity-field-present",
            "broker-payload-present",
            "credential-field-present",
            "execution-endpoint-present",
            "customer-data-present",
            "host-enforcement-claimed",
            "private-absolute-source-locator",
            "account-access-boundary-true",
            "external-transfer-boundary-true",
            "customer-material-boundary-true",
            "third-party-import-boundary-true",
            "nested-order-payload",
            "invalid-retrieved-month",
            "invalid-decision-month",
            "account-singular-path-locator",
            "account-plural-path-locator",
            "account-query-locator",
            "account-fragment-locator",
            "execution-endpoint-slash-locator",
        }
        cases = {
            case["case_id"]: case for case in self.fixtures["cases"]
        }
        for case_id in structural_cases:
            self.assertTrue(
                list(validator.iter_errors(self.materialize(cases[case_id]))),
                case_id,
            )

    def test_supersession_is_append_only_and_acyclic(self) -> None:
        case = next(
            case
            for case in self.fixtures["cases"]
            if case["case_id"] == "valid-append-only-supersession"
        )
        record = self.materialize(case)
        entries = record["decision_log"]
        self.assertEqual(["DECISION-001", "DECISION-002"], [
            entry["entry_id"] for entry in entries
        ])
        self.assertIsNone(entries[0]["supersedes_entry_id"])
        self.assertEqual("DECISION-001", entries[1]["supersedes_entry_id"])
        self.assertEqual([], structural_reason_codes(record))

    def test_independent_review_probes_fail_closed_without_jsonschema(self) -> None:
        case_ids = {
            "private-absolute-source-locator",
            "account-access-boundary-true",
            "external-transfer-boundary-true",
            "customer-material-boundary-true",
            "third-party-import-boundary-true",
            "order-in-conclusion",
            "nested-order-payload",
            "invalid-retrieved-month",
            "invalid-decision-month",
            "duplicate-source-id",
            "broker-payload-in-basis",
            "account-id-in-opposing-view",
            "credential-in-next-action",
            "execution-endpoint-in-conclusion",
            "proposed-quantity-in-basis",
            "submit-to-broker-in-next-action",
            "nested-broker-payload-value",
            "broker-payload-hyphen",
            "broker-payload-underscore",
            "broker-payload-slash",
            "broker-payload-dot",
            "broker-payload-colon",
            "account-id-dot",
            "account-number-slash",
            "execution-endpoint-dot",
            "execution-endpoint-slash",
            "proposed-quantity-colon",
            "order-quantity-slash",
            "nested-broker-payload-punctuation",
            "account-singular-path-locator",
            "account-plural-path-locator",
            "account-query-locator",
            "account-fragment-locator",
            "account-encoded-once-locator",
            "account-encoded-twice-locator",
            "account-encoded-query-locator",
            "execution-endpoint-slash-locator",
            "execution-endpoint-encoded-slash-locator",
            "invalid-percent-escape-locator",
            "decode-bound-exceeded-locator",
            "automatic-trading-in-conclusion",
            "automated-trading-punctuation",
            "automatic-rebalancing-in-next-action",
            "automated-rebalancing-punctuation",
            "access-account-in-basis",
            "account-access-in-opposing-view",
            "account-operation-in-next-action",
            "credential-access-account-in-conclusion",
            "api-key-access-account-in-basis",
            "authority-percent-encoding-locator",
        }
        cases = {
            case["case_id"]: case for case in self.fixtures["cases"]
        }
        self.assertEqual(case_ids, case_ids & set(cases))
        for case_id in case_ids:
            with self.subTest(case_id=case_id):
                actual = structural_reason_codes(
                    self.materialize(cases[case_id])
                )
                self.assertEqual(
                    cases[case_id]["expected_reason_codes"],
                    actual,
                )

    def test_legitimate_broker_research_language_remains_allowed(self) -> None:
        case_ids = {
            "valid-broker-research",
            "valid-broker-consensus",
            "valid-public-broker-source",
            "valid-analyst-credentials",
            "valid-professional-credentials",
            "valid-accounting-research",
            "valid-automated-valuation",
            "valid-automatic-data-cleaning",
        }
        cases = {
            case["case_id"]: case for case in self.fixtures["cases"]
        }
        self.assertEqual(case_ids, case_ids & set(cases))
        for case_id in case_ids:
            with self.subTest(case_id=case_id):
                self.assertEqual(
                    [],
                    structural_reason_codes(self.materialize(cases[case_id])),
                )

    def test_detection_is_bounded_and_locator_decoding_is_capped(self) -> None:
        self.assertEqual(3, LOCATOR_DECODE_MAX_ROUNDS)
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertIn("bounded static detection", guide)
        self.assertIn("not complete natural-language understanding", guide)
        self.assertIn("raw structural gate", guide)
        self.assertIn("Unicode confusables", guide)
        source_locator = self.schema["$defs"]["source"]["properties"][
            "source_locator"
        ]
        self.assertTrue(
            source_locator[
                "x-lhe-authority-percent-encoding-forbidden"
            ]
        )

    def test_every_boundary_field_fails_closed_without_jsonschema(self) -> None:
        base = self.fixtures["base_record"]
        for field in sorted(BOUNDARY_FIELDS):
            with self.subTest(field=field):
                record = deepcopy(base)
                record["boundaries"][field] = True
                self.assertTrue(structural_reason_codes(record))

    def test_every_entity_collection_rejects_duplicate_id(self) -> None:
        base = self.fixtures["base_record"]
        for collection, id_field in ENTITY_ID_FIELDS:
            with self.subTest(collection=collection):
                record = deepcopy(base)
                duplicate = deepcopy(record[collection][0])
                if collection == "decision_log":
                    duplicate["supersedes_entry_id"] = record[
                        "decision_log"
                    ][0]["entry_id"]
                record[collection].append(duplicate)
                self.assertIn(
                    "ENTITY_ID_DUPLICATE",
                    structural_reason_codes(record),
                )

    def test_blocked_time_precision_is_not_inferred_or_repaired(self) -> None:
        case = next(
            case
            for case in self.fixtures["cases"]
            if case["case_id"] == "valid-date-only-blocked"
        )
        record = self.materialize(case)
        self.assertEqual("date_only", record["sources"][0]["time_precision"])
        self.assertEqual(
            "point_in_time_blocked",
            record["point_in_time_status"],
        )
        self.assertIn(
            "TIME_PRECISION_DATE_ONLY",
            record["point_in_time_block_reasons"],
        )
        self.assertEqual([], structural_reason_codes(record))

    def test_recommendation_and_disposition_are_research_only(self) -> None:
        base = self.fixtures["base_record"]
        action = base["recommendation"]["next_research_action"]
        self.assertIn(action["action_type"], RESEARCH_ACTIONS)
        self.assertIn(
            base["recommendation"]["human_disposition"],
            DISPOSITIONS,
        )
        for entry in base["decision_log"]:
            self.assertIn(entry["human_disposition"], DISPOSITIONS)
        guide = GUIDE.read_text(encoding="utf-8")
        required = (
            "These are research dispositions.",
            "do not authorize an order",
            "does not create a schedule or permission",
            "do not constrain the currently installed Public Equity Investing runtime",
            "do not provide host-enforced isolation",
        )
        for phrase in required:
            self.assertIn(phrase, guide)

    def test_fixtures_use_only_synthetic_non_sensitive_material(self) -> None:
        text = CASES.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", text)
        self.assertNotIn("/home/", text)
        self.assertNotIn("TradingAgents", text)
        for match in re.findall(r"https://[^\"]+", text):
            self.assertIn(".example.test/", match)
        self.assertFalse(
            self.fixtures["base_record"]["boundaries"]["customer_material_used"]
        )

    def test_contract_does_not_register_or_promote_the_candidate(self) -> None:
        priority = PRIORITY.read_text(encoding="utf-8")
        self.assertIn(
            "outside the registered experiment and skill catalogs",
            priority,
        )
        self.assertIn("not permission", priority)
        self.assertFalse(self.contract["registered_skill"])
        self.assertFalse(self.contract["runtime_integration_exists"])

    def test_contract_tests_import_only_python_standard_library(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        imports = set(
            re.findall(
                r"^(?:from|import) ([a-zA-Z0-9_]+)",
                source,
                flags=re.MULTILINE,
            )
        )
        self.assertEqual(
            {
                "__future__",
                "copy",
                "datetime",
                "importlib",
                "json",
                "pathlib",
                "re",
                "unittest",
                "urllib",
            },
            imports,
        )


if __name__ == "__main__":
    unittest.main()
