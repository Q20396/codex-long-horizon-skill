"""Static contract tests for clean-room public-equity research governance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from urllib.parse import parse_qsl, unquote, urlsplit

from scripts import validate_formal_schemas as formal_schemas
from scripts.validate_formal_schemas import validate_public_equity_timestamp_gate
from scripts.validate_public_equity_research_governance_contract import (
    TIMESTAMP_CALENDAR_INVALID,
    TIMESTAMP_CONTAINER_INVALID,
    TIMESTAMP_FIELD_INVENTORY,
    TIMESTAMP_LEXICAL_PROFILE_INVALID,
    TIMESTAMP_OFFSET_INVALID_OR_REQUIRED,
    TimestampFieldSpec,
    parse_offset_datetime,
    schema_semantic_digest,
    timestamp_inventory_alignment_errors,
    timestamp_inventory_manifest_digest,
    timestamp_manifest_errors,
    timestamp_manifest_semantic_digest,
    validate_timestamp_contract,
)


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
_TIMESTAMP_GATE_SCHEMA: object | None = None
_TIMESTAMP_GATE_MARKDOWN: str | None = None
_TIMESTAMP_GATE_DIGEST: str | None = None


def timestamp_contract_reason_codes(
    record: object,
    inventory: tuple[TimestampFieldSpec, ...] = TIMESTAMP_FIELD_INVENTORY,
) -> list[str]:
    """Test seam that always uses the public manifest-and-Schema gate."""

    return validate_timestamp_contract(
        schema=_TIMESTAMP_GATE_SCHEMA,
        markdown=_TIMESTAMP_GATE_MARKDOWN,
        record=record,
        inventory=inventory,
        expected_semantic_digest=_TIMESTAMP_GATE_DIGEST,
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


def _is_exact_json_value(value: object, active: set[int] | None = None) -> bool:
    """Admit only finite, acyclic, exact-builtin JSON values."""

    if value is None or type(value) in {str, bool, int}:
        return True
    if type(value) is float:
        return value == value and value not in (float("inf"), float("-inf"))
    if active is None:
        active = set()
    if type(value) is dict:
        identity = id(value)
        if identity in active:
            return False
        active.add(identity)
        try:
            return all(
                type(key) is str and _is_exact_json_value(child, active)
                for key, child in value.items()
            )
        finally:
            active.remove(identity)
    if type(value) is list:
        identity = id(value)
        if identity in active:
            return False
        active.add(identity)
        try:
            return all(_is_exact_json_value(child, active) for child in value)
        finally:
            active.remove(identity)
    return False


def _aggregate_traversal_shape_is_safe(record: object) -> bool:
    """Check only the bounded shapes this aggregate subsequently traverses."""

    def scalar(value: object) -> bool:
        return value is None or type(value) in {str, bool, int, float}

    def scalar_list(value: object) -> bool:
        return type(value) is list and all(scalar(item) for item in value)

    def records_with_scalar_fields(
        value: object,
        scalar_fields: tuple[str, ...],
        list_fields: tuple[str, ...] = (),
    ) -> bool:
        return type(value) is list and all(
            type(item) is dict
            and all(scalar(item.get(field)) for field in scalar_fields)
            and all(scalar_list(item.get(field)) for field in list_fields)
            for item in value
        )

    if type(record) is not dict:
        return False
    try:
        recommendation = record.get("recommendation")
        if (
            type(record.get("research_context")) is not dict
            or type(recommendation) is not dict
            or type(record.get("boundaries")) is not dict
            or type(recommendation.get("next_research_action")) is not dict
            or not all(
                scalar_list(recommendation.get(field))
                for field in ("risk_ids", "missing_evidence_ids")
            )
            or not scalar(recommendation.get("human_disposition"))
        ):
            return False
        return all(
            (
                records_with_scalar_fields(record.get("sources"), ("source_id",)),
                records_with_scalar_fields(
                    record.get("core_claims"),
                    ("claim_id",),
                    ("supporting_evidence_ids", "disconfirming_evidence_ids"),
                ),
                records_with_scalar_fields(record.get("assumptions"), ("assumption_id",)),
                records_with_scalar_fields(record.get("scenarios"), ("scenario_id",)),
                records_with_scalar_fields(record.get("risks"), ("risk_id",)),
                records_with_scalar_fields(
                    record.get("missing_evidence"), ("missing_evidence_id",)
                ),
                records_with_scalar_fields(
                    record.get("decision_log"),
                    ("entry_id", "supersedes_entry_id", "human_disposition"),
                    (
                        "source_ids",
                        "assumption_ids",
                        "scenario_ids",
                        "risk_ids",
                        "missing_evidence_ids",
                    ),
                ),
            )
        )
    except (RecursionError, TypeError, ValueError, AttributeError, KeyError):
        return False


def structural_reason_codes(record: object) -> list[str]:
    """Return stable rejection reasons without repairing the supplied record."""

    # The public gate owns all untrusted timestamp-container admission. It must
    # run before this aggregate reads any caller-controlled mapping.
    try:
        timestamp_codes = timestamp_contract_reason_codes(record)
    except Exception:
        return [TIMESTAMP_CONTAINER_INVALID]
    if TIMESTAMP_CONTAINER_INVALID in timestamp_codes:
        return sorted(set(timestamp_codes))
    try:
        if not _is_exact_json_value(record) or not _aggregate_traversal_shape_is_safe(record):
            return sorted(set(timestamp_codes) | {TIMESTAMP_CONTAINER_INVALID})
    except (RecursionError, TypeError, ValueError, AttributeError, KeyError):
        return sorted(set(timestamp_codes) | {TIMESTAMP_CONTAINER_INVALID})

    try:
        return _structural_reason_codes_after_admission(record, timestamp_codes)
    except (RecursionError, TypeError, ValueError, AttributeError, KeyError):
        return sorted(set(timestamp_codes) | {TIMESTAMP_CONTAINER_INVALID})


def _structural_reason_codes_after_admission(
    record: dict,
    timestamp_codes: list[str],
) -> list[str]:
    """Run aggregate semantics only after public and structural admission."""

    reasons: set[str] = set()
    sources = record["sources"]
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

    timestamp_reasons = set(timestamp_codes)

    status = record.get("point_in_time_status")
    if type(status) is not str:
        return sorted(reasons | {TIMESTAMP_CONTAINER_INVALID})
    raw_block_reasons = record.get("point_in_time_block_reasons", [])
    if type(raw_block_reasons) is not list or not all(
        type(reason) is str for reason in raw_block_reasons
    ):
        reasons.add(TIMESTAMP_CONTAINER_INVALID)
        block_reasons: set[str] = set()
    else:
        block_reasons = set(raw_block_reasons)
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
    reasons.update(timestamp_reasons)

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
        global _TIMESTAMP_GATE_DIGEST, _TIMESTAMP_GATE_MARKDOWN, _TIMESTAMP_GATE_SCHEMA
        cls.contract = load_json(CONTRACT)
        cls.schema = load_json(SCHEMA)
        cls.fixtures = load_json(CASES)
        _TIMESTAMP_GATE_SCHEMA = cls.schema
        _TIMESTAMP_GATE_MARKDOWN = GUIDE.read_text(encoding="utf-8")
        _TIMESTAMP_GATE_DIGEST = timestamp_manifest_semantic_digest(
            _TIMESTAMP_GATE_MARKDOWN
        )

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
        # Container totality is deliberately exercised by direct malformed
        # input regressions below so the fixed 109-fixture corpus can remain
        # stable.
        self.assertEqual(stable, seen | {TIMESTAMP_CONTAINER_INVALID})

    def test_fixture_corpus_is_fixed_and_case_ids_are_unique(self) -> None:
        case_ids = [case["case_id"] for case in self.fixtures["cases"]]
        self.assertEqual(109, len(case_ids))
        self.assertEqual(len(case_ids), len(set(case_ids)))

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

    def test_timestamp_profile_and_gregorian_calendar_gates_are_separate(self) -> None:
        cases = {case["case_id"]: case for case in self.fixtures["cases"]}
        lexical_schema_cases = {
            "invalid-retrieved-month",
            "invalid-decision-month",
            "invalid-lowercase-t-z",
            "invalid-leap-second",
            "invalid-trailing-newline",
            "invalid-fractional-second-7",
            "invalid-trailing-carriage-return",
            "invalid-trailing-line-separator",
            "invalid-trailing-paragraph-separator",
        }
        offset_cases = {
            "timestamp-without-offset",
            "invalid-negative-zero-offset",
            "invalid-offset-14-01",
        }
        calendar_only_cases = {
            "invalid-common-year-feb-29",
            "invalid-feb-30",
            "invalid-feb-31",
            "invalid-apr-31",
            "invalid-year-zero",
        }

        self.assertEqual([], structural_reason_codes(
            self.materialize(cases["valid-leap-year-feb-29"])
        ))
        for case_id in lexical_schema_cases:
            self.assertEqual(
                [TIMESTAMP_LEXICAL_PROFILE_INVALID],
                structural_reason_codes(self.materialize(cases[case_id])),
                case_id,
            )
        for case_id in calendar_only_cases:
            self.assertEqual(
                [TIMESTAMP_CALENDAR_INVALID],
                structural_reason_codes(self.materialize(cases[case_id])),
                case_id,
            )
        for case_id in offset_cases:
            self.assertEqual(
                [TIMESTAMP_OFFSET_INVALID_OR_REQUIRED],
                structural_reason_codes(self.materialize(cases[case_id])),
                case_id,
            )

        first = parse_offset_datetime("2026-07-26T09:00:00.123455Z")
        second = parse_offset_datetime("2026-07-26T09:00:00.123456Z")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertLess(first, second)

        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator

        validator = Draft202012Validator(self.schema)
        for case_id in lexical_schema_cases:
            self.assertTrue(
                list(validator.iter_errors(self.materialize(cases[case_id]))),
                case_id,
            )
        for case_id in offset_cases - {"timestamp-without-offset"}:
            self.assertTrue(
                list(validator.iter_errors(self.materialize(cases[case_id]))),
                case_id,
            )
        for case_id in calendar_only_cases:
            self.assertEqual(
                [],
                list(validator.iter_errors(self.materialize(cases[case_id]))),
                case_id,
            )

    def test_record_timestamp_verifier_covers_every_declared_path(self) -> None:
        def pointer(spec: TimestampFieldSpec) -> str:
            if spec.container_path == "record":
                return f"/{spec.field}"
            index = "/0" if spec.repeated else ""
            return f"/{spec.container_path}{index}/{spec.field}"

        invalid_values = (
            ("2026-07-26t09:00:00z", TIMESTAMP_LEXICAL_PROFILE_INVALID),
            ("2025-02-29T09:00:00+10:00", TIMESTAMP_CALENDAR_INVALID),
            ("2026-07-26T09:00:00+14:01", TIMESTAMP_OFFSET_INVALID_OR_REQUIRED),
        )
        for spec in (
            spec for spec in TIMESTAMP_FIELD_INVENTORY
            if spec.conditional_context == "always"
        ):
            for value, expected_reason in invalid_values:
                with self.subTest(path=spec.path, expected_reason=expected_reason):
                    record = apply_mutations(
                        self.fixtures["base_record"],
                        [{"op": "set", "path": pointer(spec), "value": value}],
                    )
                    self.assertEqual(
                        [expected_reason],
                        timestamp_contract_reason_codes(record),
                    )

    def test_schema_and_verifier_timestamp_inventories_match(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        inventory_manifests = re.findall(
            r"<!-- PUBLIC_EQUITY_TIMESTAMP_INVENTORY_MANIFEST\s+"
            r"sha256:([0-9a-f]{64})\s+"
            r"canonicalization:json-sort-keys-compact-separators\s+-->",
            guide,
        )
        semantic_manifests = re.findall(
            r"<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST\s+"
            r"sha256:([0-9a-f]{64})\s+"
            r"canonicalization:utf-8-json-sort-keys-compact-separators-array-order-preserved\s+"
            r"annotation_pointers:[^\n]+\s+"
            r"annotation_keys:title,description,\$comment\s+-->",
            guide,
        )
        self.assertEqual(1, len(inventory_manifests))
        self.assertEqual(1, len(semantic_manifests))
        inventory_manifest, semantic_manifest = inventory_manifests[0], semantic_manifests[0]
        self.assertEqual(inventory_manifest, timestamp_inventory_manifest_digest())
        self.assertEqual(semantic_manifest, schema_semantic_digest(self.schema))
        self.assertEqual([], timestamp_manifest_errors(guide, self.schema))
        self.assertEqual(
            [], timestamp_inventory_alignment_errors(self.schema, expected_semantic_digest=semantic_manifest)
        )
        for digest in (None, [], {}, "not-a-digest"):
            with self.subTest(missing_or_invalid_digest=digest):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(
                        self.schema, expected_semantic_digest=digest
                    ),
                )

        schema_mutations = []
        removed = deepcopy(self.schema)
        del removed["properties"]["created_at"]
        schema_mutations.append(removed)
        required_changed = deepcopy(self.schema)
        required_changed["$defs"]["source"]["required"].remove("available_at")
        schema_mutations.append(required_changed)
        nullable_changed = deepcopy(self.schema)
        nullable_changed["$defs"]["source"]["properties"]["available_at"] = {"$ref": "#/$defs/offsetDateTime"}
        schema_mutations.append(nullable_changed)
        min_items_changed = deepcopy(self.schema)
        min_items_changed["properties"]["sources"]["minItems"] = 0
        schema_mutations.append(min_items_changed)
        object_type_changed = deepcopy(self.schema)
        object_type_changed["properties"]["research_context"]["type"] = "array"
        schema_mutations.append(object_type_changed)
        items_ref_changed = deepcopy(self.schema)
        items_ref_changed["properties"]["sources"]["items"] = {"$ref": "#/$defs/decisionEntry"}
        schema_mutations.append(items_ref_changed)
        pattern_changed = deepcopy(self.schema)
        pattern_changed["$defs"]["offsetDateTime"]["pattern"] = "^different$"
        schema_mutations.append(pattern_changed)
        root_constraint = deepcopy(self.schema)
        root_constraint["not"] = {}
        schema_mutations.append(root_constraint)
        research_context_constraint = deepcopy(self.schema)
        research_context_constraint["properties"]["research_context"]["maxProperties"] = 1
        schema_mutations.append(research_context_constraint)
        source_constraint = deepcopy(self.schema)
        source_constraint["$defs"]["source"]["not"] = {}
        schema_mutations.append(source_constraint)
        decision_constraint = deepcopy(self.schema)
        decision_constraint["$defs"]["decisionEntry"]["not"] = {}
        schema_mutations.append(decision_constraint)
        source_max_items = deepcopy(self.schema)
        source_max_items["properties"]["sources"]["maxItems"] = 0
        schema_mutations.append(source_max_items)
        decision_max_items = deepcopy(self.schema)
        decision_max_items["properties"]["decision_log"]["maxItems"] = 0
        schema_mutations.append(decision_max_items)
        restrictive_sibling = deepcopy(self.schema)
        restrictive_sibling["$defs"]["source"]["properties"]["available_at"]["type"] = "string"
        schema_mutations.append(restrictive_sibling)
        unsupported_not = deepcopy(self.schema)
        unsupported_not["$defs"]["offsetDateTime"]["not"] = {"type": "null"}
        schema_mutations.append(unsupported_not)
        cyclic_ref = deepcopy(self.schema)
        cyclic_ref["$defs"]["offsetDateTime"] = {"$ref": "#/$defs/offsetDateTime"}
        schema_mutations.append(cyclic_ref)
        escaped_alias = deepcopy(self.schema)
        escaped_alias["$defs"]["offsetDateTimeAlias"] = deepcopy(escaped_alias["$defs"]["offsetDateTime"])
        escaped_alias["properties"]["created_at"] = {"$ref": "#/$defs/offsetDateTimeAlias"}
        schema_mutations.append(escaped_alias)
        duplicate_occurrence = deepcopy(self.schema)
        duplicate_occurrence["allOf"][0]["then"]["properties"]["sources"]["items"]["allOf"].append({"$ref": "#/$defs/source"})
        schema_mutations.append(duplicate_occurrence)
        conditional_changed = deepcopy(self.schema)
        conditional_changed["allOf"][0]["if"]["required"].append("created_at")
        schema_mutations.append(conditional_changed)
        ready_not = deepcopy(self.schema)
        ready_not["allOf"][0]["then"]["properties"]["sources"]["items"]["allOf"][1]["not"] = {}
        schema_mutations.append(ready_not)
        ready_min_items = deepcopy(self.schema)
        ready_min_items["allOf"][0]["then"]["properties"]["sources"]["items"]["allOf"][1]["minItems"] = 1
        schema_mutations.append(ready_min_items)
        missing_ready_descriptor = deepcopy(self.schema)
        del missing_ready_descriptor["allOf"][0]["then"]["properties"]["sources"]["items"]["allOf"][1]["properties"]["available_at"]
        schema_mutations.append(missing_ready_descriptor)
        else_constraint = deepcopy(self.schema)
        else_constraint["allOf"][0]["else"]["properties"]["sources"] = {"minItems": 2}
        schema_mutations.append(else_constraint)
        recursive_schema = deepcopy(self.schema)
        recursive_else = recursive_schema["allOf"][0]["else"]
        recursive_else["recursive"] = recursive_else
        schema_mutations.append(recursive_schema)
        for mutation in schema_mutations:
            with self.subTest(mutation=mutation):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(mutation, expected_semantic_digest=semantic_manifest),
                )

        annotations = deepcopy(self.schema)
        annotations["$comment"] = "non-semantic root annotation"
        annotations["$defs"]["offsetDateTime"]["title"] = "Timestamp"
        annotations["$defs"]["nullableOffsetDateTime"]["description"] = "Nullable timestamp"
        annotations["properties"]["sources"]["title"] = "Sources"
        annotations["allOf"][0]["then"]["properties"]["sources"]["items"]["allOf"][1]["$comment"] = "Ready-only source wrapper"
        self.assertEqual(
            [], timestamp_inventory_alignment_errors(annotations, expected_semantic_digest=semantic_manifest)
        )

        conditional_index = next(
            index for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            if spec.condition_id == "POINT_IN_TIME_READY"
        )
        decision_index = next(
            index for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            if spec.temporal_role == "decision_instant"
        )
        inventory_mutations = (
            tuple(spec for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY) if index != conditional_index),
            (*TIMESTAMP_FIELD_INVENTORY, TIMESTAMP_FIELD_INVENTORY[conditional_index]),
            tuple(
                replace(spec, condition_id="UNKNOWN", conditional_context="unknown")
                if index == conditional_index else spec
                for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            ),
            tuple(
                replace(spec, field="research_as_of") if index == decision_index else spec
                for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            ),
            tuple(
                replace(spec, path="research_context.research_as_of") if index == decision_index else spec
                for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            ),
            tuple(
                replace(spec, schema_pointer="/$defs/decisionEntry/properties/research_as_of") if index == decision_index else spec
                for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            ),
        )
        for inventory in inventory_mutations:
            with self.subTest(inventory=inventory):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(
                        self.schema, inventory, expected_semantic_digest=semantic_manifest
                    ),
                )
                with self.assertRaises(ValueError):
                    timestamp_inventory_manifest_digest(inventory)

    def test_schema_semantic_digest_is_annotation_scoped_and_total(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        marker = re.findall(
            r"<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST\s+sha256:([0-9a-f]{64})",
            guide,
        )
        self.assertEqual(1, len(marker))
        expected = marker[0]

        annotations = deepcopy(self.schema)
        annotations["title"] = "allowed root annotation"
        annotations["properties"]["sources"]["description"] = "allowed source annotation"
        self.assertEqual(expected, schema_semantic_digest(annotations))

        for path, value in (
            ("/properties/title", {"const": "validation property"}),
            ("/allOf/0/if/properties/title", {"const": "selector property"}),
            ("/properties/point_in_time_block_reasons/contains", {}),
            ("/properties/new_at", {"type": "string"}),
        ):
            with self.subTest(path=path):
                changed = apply_mutations(self.schema, [{"op": "set", "path": path, "value": value}])
                self.assertNotEqual(expected, schema_semantic_digest(changed))
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(changed, expected_semantic_digest=expected),
                )

        for pointer in ("/title", "/$defs/offsetDateTime/title"):
            with self.subTest(pointer=pointer):
                changed = apply_mutations(self.schema, [{"op": "set", "path": pointer, "value": 1}])
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(changed, expected_semantic_digest=expected),
                )

        duplicate = guide + "\n" + re.search(
            r"<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST.*?-->",
            guide,
            flags=re.DOTALL,
        ).group(0)
        self.assertEqual(
            [TIMESTAMP_CONTAINER_INVALID], timestamp_manifest_errors(duplicate, self.schema)
        )
        malformed_duplicate = guide + "\n<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST malformed -->"
        partial_duplicate = guide + "\n<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST\nsha256:bad\n-->"
        malformed_inventory_duplicate = guide + "\n<!-- PUBLIC_EQUITY_TIMESTAMP_INVENTORY_MANIFEST malformed -->"
        wrong_canonicalization = guide.replace(
            "canonicalization:utf-8-json-sort-keys-compact-separators-array-order-preserved",
            "canonicalization:wrong",
        )
        for document in (malformed_duplicate, partial_duplicate, malformed_inventory_duplicate, wrong_canonicalization):
            self.assertEqual(
                [TIMESTAMP_CONTAINER_INVALID], timestamp_manifest_errors(document, self.schema)
            )

        for document in (
            guide + "\nPUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST",
            guide + "\n<!--- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST malformed -->",
            guide + "\n<!-- malformed PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST sha256:bad -->",
            guide.replace("<!-- PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST", "<!--\u00a0PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST", 1),
        ):
            with self.subTest(marker_document=document[-100:]):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_manifest_errors(document, self.schema),
                )

        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(non_finite=value):
                changed = deepcopy(self.schema)
                changed["x-test-number"] = value
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(changed, expected_semantic_digest=expected),
                )

    def test_public_timestamp_gate_is_required_by_formal_public_equity_path(self) -> None:
        record = deepcopy(self.fixtures["base_record"])
        changed_schema = apply_mutations(
            self.schema,
            [{"op": "set", "path": "/$defs/offsetDateTime/pattern", "value": ".*"}],
        )
        self.assertEqual(
            [TIMESTAMP_CONTAINER_INVALID],
            validate_public_equity_timestamp_gate(changed_schema, record),
        )
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("jsonschema is not installed")
        from jsonschema import Draft202012Validator

        self.assertEqual([], list(Draft202012Validator(changed_schema).iter_errors(record)))

    def test_public_formal_gate_accepts_every_positive_synthetic_fixture(self) -> None:
        for case in self.fixtures["cases"]:
            if case["expected_valid"]:
                with self.subTest(case_id=case["case_id"]):
                    self.assertEqual(
                        [],
                        validate_public_equity_timestamp_gate(
                            self.schema, self.materialize(case)
                        ),
                    )
        with self.assertRaises(TypeError):
            validate_timestamp_contract(
                schema=self.schema,
                markdown=_TIMESTAMP_GATE_MARKDOWN,
                record=self.fixtures["base_record"],
                expected_semantic_digest=_TIMESTAMP_GATE_DIGEST,
            )

    def test_formal_aggregate_executes_public_equity_double_gate(self) -> None:
        """Exercise the actual formal aggregate wiring with in-memory seams."""

        positive = [
            (
                "public-equity-research-governance.schema.json",
                "aggregate-public-equity-positive",
                deepcopy(self.fixtures["base_record"]),
            )
        ]

        class Draft202012ValidatorStub:
            """Dependency-free seam; engine behavior is tested by formal-schema-gate."""

            @staticmethod
            def check_schema(schema: object) -> None:
                del schema

            def __init__(self, schema: object, **kwargs: object) -> None:
                del schema, kwargs

            def iter_errors(self, record: object) -> tuple[object, ...]:
                del record
                return ()

        class FormatCheckerStub:
            pass

        class RegistryStub:
            def with_resources(self, resources: object) -> "RegistryStub":
                tuple(resources)
                return self

        class ResourceStub:
            @staticmethod
            def from_contents(schema: object) -> object:
                return schema

        jsonschema_stub = ModuleType("jsonschema")
        jsonschema_stub.Draft202012Validator = Draft202012ValidatorStub
        jsonschema_stub.FormatChecker = FormatCheckerStub
        referencing_stub = ModuleType("referencing")
        referencing_stub.Registry = RegistryStub
        referencing_stub.Resource = ResourceStub

        def run(**gate_kwargs):
            gate_patch = patch.object(
                formal_schemas,
                "validate_public_equity_timestamp_gate",
                **gate_kwargs,
            )
            with (
                patch.dict(
                    sys.modules,
                    {"jsonschema": jsonschema_stub, "referencing": referencing_stub},
                ),
                patch.object(formal_schemas, "validate_clean_worktree", return_value=[]),
                patch.object(formal_schemas, "validate_lock", return_value=[]),
                patch.object(
                    formal_schemas,
                    "validate_schema_inventory",
                    return_value=(
                        [],
                        {"public-equity-research-governance.schema.json": self.schema},
                    ),
                ),
                patch.object(formal_schemas, "verify_runtime_versions", return_value=[]),
                patch.object(formal_schemas, "validate_pip_report", return_value=([], {})),
                patch.object(
                    formal_schemas,
                    "validate_acquisition_receipt",
                    return_value=([], {}, ""),
                ),
                patch.object(formal_schemas, "bootstrap_identity", return_value=([], {})),
                patch.object(formal_schemas, "candidate_binding", return_value=([], {})),
                patch.object(formal_schemas, "schema_inventory_binding", return_value={}),
                patch.object(formal_schemas, "validate_fixture_coverage", return_value=[]),
                patch.object(
                    formal_schemas,
                    "materialized_fixture_cases",
                    return_value=(positive, []),
                ),
                patch.object(
                    formal_schemas,
                    "TARGET_PYTHON",
                    formal_schemas.sys.version_info[:2],
                ),
                patch.object(formal_schemas, "TARGET_SYSTEM", formal_schemas.platform.system()),
                patch.object(formal_schemas, "TARGET_MACHINE", formal_schemas.platform.machine()),
                gate_patch as gate,
            ):
                errors, result = formal_schemas.validate_formal(
                    Path(__file__), Path(__file__), Path(__file__), {}, "synthetic-base"
                )
            return errors, result, gate

        errors, _, gate = run(wraps=validate_public_equity_timestamp_gate)
        self.assertEqual([], errors)
        gate.assert_called_once_with(self.schema, positive[0][2])

        errors, _, gate = run(return_value=[TIMESTAMP_CONTAINER_INVALID])
        gate.assert_called_once()
        self.assertTrue(
            any("public-equity timestamp gate failed" in error for error in errors)
        )

        errors, _, _ = run(side_effect=RuntimeError("public gate failure"))
        self.assertTrue(
            any("formal Draft 2020-12 validation raised" in error for error in errors)
        )

    def test_structural_aggregate_short_circuits_hostile_timestamp_selector(self) -> None:
        class HostileStatus(str):
            def __eq__(self, other: object) -> bool:
                raise RuntimeError("must not compare hostile status")

        record = deepcopy(self.fixtures["base_record"])
        record["point_in_time_status"] = HostileStatus("point_in_time_ready")
        self.assertIn(TIMESTAMP_CONTAINER_INVALID, structural_reason_codes(record))

    def test_public_timestamp_gate_rejects_hostile_or_non_string_mapping_keys(self) -> None:
        class HostileKey:
            def __hash__(self) -> int:
                return hash("synthetic-hostile-key")

            def __eq__(self, other: object) -> bool:
                raise RuntimeError("must not compare hostile key")

        targets = (
            ("root", lambda record: record),
            ("research_context", lambda record: record["research_context"]),
            ("sources", lambda record: record["sources"][0]),
            ("decision_log", lambda record: record["decision_log"][0]),
        )
        for name, target in targets:
            for key in (HostileKey(), 1):
                with self.subTest(container=name, key_type=type(key).__name__):
                    record = deepcopy(self.fixtures["base_record"])
                    target(record)[key] = "synthetic"
                    self.assertEqual(
                        [TIMESTAMP_CONTAINER_INVALID],
                        timestamp_contract_reason_codes(record),
                    )

    def test_structural_aggregate_short_circuits_hostile_mapping_keys(self) -> None:
        class CollisionKey:
            def __init__(self, target: str) -> None:
                self.target = target
                self.armed = False

            def __hash__(self) -> int:
                return hash(self.target)

            def __eq__(self, other: object) -> bool:
                if self.armed:
                    raise RuntimeError("must not compare hostile key")
                return False

        targets = (
            ("root", lambda record: record, 1),
            ("research_context", lambda record: record["research_context"], 1),
            ("sources", lambda record: record["sources"][0], 1),
            ("decision_log", lambda record: record["decision_log"][0], 1),
        )
        for name, target, key in targets:
            with self.subTest(container=name, kind="non-string"):
                record = deepcopy(self.fixtures["base_record"])
                target(record)[key] = "synthetic"
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(record)
                )

        for name, target, collision in (
            ("sources", lambda record: record, "sources"),
            ("source_locator", lambda record: record["sources"][0], "source_locator"),
            ("research_context", lambda record: record, "research_context"),
            ("decision_log", lambda record: record, "decision_log"),
        ):
            with self.subTest(container=name, kind="hostile-collision"):
                record = deepcopy(self.fixtures["base_record"])
                container = target(record)
                original = container.pop(collision)
                key = CollisionKey(collision)
                container[key] = original
                # This control proves that a pre-admission lookup would reach
                # the armed colliding key once the genuine string key is gone.
                key.armed = True
                with self.assertRaises(RuntimeError):
                    container.get(collision)
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(record)
                )

    def test_structural_aggregate_full_record_admission_is_total(self) -> None:
        class DictSubclass(dict):
            pass

        class ListSubclass(list):
            pass

        class StringSubclass(str):
            pass

        cases = (
            ("recommendation-dict-subclass", "/recommendation", DictSubclass()),
            ("core-claims-list-subclass", "/core_claims", ListSubclass()),
            ("boundaries-dict-subclass", "/boundaries", DictSubclass()),
            ("recommendation-string-subclass", "/recommendation/summary", StringSubclass("synthetic")),
            ("non-finite-float", "/recommendation/confidence", float("inf")),
        )
        for case_id, path, value in cases:
            with self.subTest(case_id=case_id):
                record = self.materialize({"mutations": [{"op": "set", "path": path, "value": value}]})
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(record)
                )

        cyclic = deepcopy(self.fixtures["base_record"])
        cyclic["recommendation"]["cycle"] = cyclic
        self.assertEqual([TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(cyclic))

        deep = deepcopy(self.fixtures["base_record"])
        nested: dict[str, object] = {}
        cursor = nested
        for _ in range(2_000):
            child: dict[str, object] = {}
            cursor["next"] = child
            cursor = child
        deep["recommendation"]["deep"] = nested
        self.assertEqual([TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(deep))

    def test_structural_aggregate_rejects_exact_json_wrong_shapes(self) -> None:
        malformed = (
            ("core-claims-scalar", "/core_claims", 1),
            ("core-claims-element", "/core_claims", [1]),
            ("recommendation-list", "/recommendation", []),
            ("boundaries-list", "/boundaries", []),
            ("research-context-list", "/research_context", []),
        )
        for field in (
            "assumptions",
            "scenarios",
            "risks",
            "missing_evidence",
            "decision_log",
        ):
            malformed += (
                (f"{field}-scalar", f"/{field}", 1),
                (f"{field}-object", f"/{field}", {}),
                (f"{field}-element", f"/{field}", [1]),
            )
        for case_id, path, value in malformed:
            with self.subTest(case_id=case_id):
                record = self.materialize(
                    {"mutations": [{"op": "set", "path": path, "value": value}]}
                )
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(record)
                )

    def test_structural_aggregate_rejects_nested_traversal_wrong_shapes(self) -> None:
        malformed = (
            ("next-action-list", "/recommendation/next_research_action", []),
            ("next-action-null", "/recommendation/next_research_action", None),
            ("next-action-scalar", "/recommendation/next_research_action", 1),
            ("claim-reference-object", "/core_claims/0/supporting_evidence_ids", [{}]),
            ("recommendation-risk-object", "/recommendation/risk_ids", [{}]),
            ("decision-reference-object", "/decision_log/0/source_ids", [{}]),
        )
        for case_id, path, value in malformed:
            with self.subTest(case_id=case_id):
                record = self.materialize(
                    {"mutations": [{"op": "set", "path": path, "value": value}]}
                )
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID], structural_reason_codes(record)
                )

    def test_structural_admission_preserves_public_timestamp_reasons(self) -> None:
        record = deepcopy(self.fixtures["base_record"])
        record["sources"][0].pop("available_at")
        record["recommendation"] = []
        self.assertCountEqual(
            [TIMESTAMP_OFFSET_INVALID_OR_REQUIRED, TIMESTAMP_CONTAINER_INVALID],
            structural_reason_codes(record),
        )

        nested = deepcopy(self.fixtures["base_record"])
        nested["sources"][0].pop("available_at")
        nested["recommendation"]["next_research_action"] = []
        self.assertCountEqual(
            [TIMESTAMP_OFFSET_INVALID_OR_REQUIRED, TIMESTAMP_CONTAINER_INVALID],
            structural_reason_codes(nested),
        )

    def test_structural_aggregate_fails_closed_when_public_gate_raises(self) -> None:
        original = timestamp_contract_reason_codes
        globals()["timestamp_contract_reason_codes"] = lambda record: (_ for _ in ()).throw(RuntimeError("gate failure"))
        try:
            self.assertEqual(
                [TIMESTAMP_CONTAINER_INVALID],
                structural_reason_codes(self.fixtures["base_record"]),
            )
        finally:
            globals()["timestamp_contract_reason_codes"] = original

    def test_inventory_rejects_strict_type_confusion(self) -> None:
        base = TIMESTAMP_FIELD_INVENTORY
        for field, value in (
            ("repeated", 0), ("nullable", 1), ("min_items", True),
            ("path", ["sources[].available_at"]), ("condition_id", {}),
        ):
            with self.subTest(field=field, value=value):
                changed = (replace(base[0], **{field: value}), *base[1:])
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(self.schema, changed, expected_semantic_digest=schema_semantic_digest(self.schema)),
                )

        class TupleSubclass(tuple):
            pass

        class WrongDescriptor:
            pass

        for changed in (TupleSubclass(TIMESTAMP_FIELD_INVENTORY), (WrongDescriptor(),)):
            with self.subTest(inventory=changed):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_inventory_alignment_errors(self.schema, changed, expected_semantic_digest=schema_semantic_digest(self.schema)),
                )

    def test_record_timestamp_verifier_is_total_for_malformed_containers(self) -> None:
        malformed_mutations = (
            {"op": "set", "path": "/sources", "value": None},
            {"op": "set", "path": "/sources", "value": []},
            {"op": "set", "path": "/sources", "value": {}},
            {"op": "set", "path": "/sources", "value": [[]]},
            {"op": "set", "path": "/sources", "value": [None]},
            {"op": "set", "path": "/decision_log", "value": None},
            {"op": "set", "path": "/decision_log", "value": []},
            {"op": "set", "path": "/decision_log", "value": {}},
            {"op": "set", "path": "/decision_log", "value": [[]]},
            {"op": "set", "path": "/decision_log", "value": [None]},
            {"op": "set", "path": "/point_in_time_block_reasons", "value": None},
            {"op": "set", "path": "/point_in_time_block_reasons", "value": {}},
            {"op": "set", "path": "/point_in_time_block_reasons", "value": [{}]},
            {"op": "set", "path": "/point_in_time_block_reasons", "value": [[]]},
        )
        for mutation in malformed_mutations:
            with self.subTest(mutation=mutation):
                record = apply_mutations(self.fixtures["base_record"], [mutation])
                self.assertIn(
                    TIMESTAMP_CONTAINER_INVALID,
                    timestamp_contract_reason_codes(record),
                )

        for value in (None, {}, [[]]):
            with self.subTest(structural_block_reasons=value):
                record = deepcopy(self.fixtures["base_record"])
                record["point_in_time_block_reasons"] = value
                self.assertIn(TIMESTAMP_CONTAINER_INVALID, structural_reason_codes(record))

        class HostileList(list):
            def __iter__(self):
                raise RuntimeError("must not iterate subclass")

        record = deepcopy(self.fixtures["base_record"])
        record["point_in_time_block_reasons"] = HostileList(["AVAILABLE_AFTER_DECISION"])
        self.assertIn(TIMESTAMP_CONTAINER_INVALID, timestamp_contract_reason_codes(record))

    def test_record_timestamp_verifier_is_total_for_untrusted_root_and_values(self) -> None:
        for root in (None, True, 1, "not-a-record", []):
            with self.subTest(root=root):
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_contract_reason_codes(root),
                )
        for value in (None, True, 1, "not-a-context", []):
            with self.subTest(research_context=value):
                record = deepcopy(self.fixtures["base_record"])
                record["research_context"] = value
                self.assertIn(
                    TIMESTAMP_CONTAINER_INVALID,
                    timestamp_contract_reason_codes(record),
                )
        for spec in (
            spec for spec in TIMESTAMP_FIELD_INVENTORY
            if spec.conditional_context == "always"
        ):
            path = (
                f"/{spec.field}" if spec.container_path == "record"
                else f"/{spec.container_path}{'/0' if spec.repeated else ''}/{spec.field}"
            )
            for value in ([], {}, 1, True):
                with self.subTest(path=path, value=value):
                    record = apply_mutations(
                        self.fixtures["base_record"],
                        [{"op": "set", "path": path, "value": value}],
                    )
                    self.assertIn(
                        TIMESTAMP_LEXICAL_PROFILE_INVALID,
                        timestamp_contract_reason_codes(record),
                    )

    def test_record_timestamp_verifier_distinguishes_missing_and_null(self) -> None:
        base_specs = tuple(
            spec for spec in TIMESTAMP_FIELD_INVENTORY
            if spec.conditional_context == "always"
        )
        def pointer(spec: TimestampFieldSpec) -> str:
            return f"/{spec.field}" if spec.container_path == "record" else f"/{spec.container_path}{'/0' if spec.repeated else ''}/{spec.field}"
        for spec in base_specs:
            path = pointer(spec)
            with self.subTest(path=path, mutation="delete"):
                record = apply_mutations(
                    self.fixtures["base_record"], [{"op": "delete", "path": path}]
                )
                self.assertIn(
                    TIMESTAMP_OFFSET_INVALID_OR_REQUIRED,
                    timestamp_contract_reason_codes(record),
                )
        for spec in (spec for spec in base_specs if not spec.nullable):
            path = pointer(spec)
            with self.subTest(path=path, mutation="null"):
                record = apply_mutations(
                    self.fixtures["base_record"], [{"op": "set", "path": path, "value": None}]
                )
                self.assertIn(
                    TIMESTAMP_OFFSET_INVALID_OR_REQUIRED,
                    timestamp_contract_reason_codes(record),
                )
        for spec in (spec for spec in base_specs if spec.nullable):
            path = pointer(spec)
            with self.subTest(path=path, mutation="source-null"):
                record = apply_mutations(
                    self.fixtures["base_record"], [
                        {"op": "set", "path": "/point_in_time_status", "value": "point_in_time_blocked"},
                        {"op": "set", "path": "/point_in_time_block_reasons", "value": ["TIMESTAMP_MISSING"]},
                        {"op": "set", "path": path, "value": None},
                    ]
                )
                self.assertEqual([], timestamp_contract_reason_codes(record))

    def test_record_timestamp_verifier_applies_ready_nullability_and_temporal_roles(self) -> None:
        source_fields = ("effective_at", "published_at", "available_at", "retrieved_at")
        for field in source_fields:
            with self.subTest(state="ready", field=field):
                record = apply_mutations(
                    self.fixtures["base_record"],
                    [{"op": "set", "path": f"/sources/0/{field}", "value": None}],
                )
                self.assertIn(
                    TIMESTAMP_OFFSET_INVALID_OR_REQUIRED,
                    timestamp_contract_reason_codes(record),
                )
            with self.subTest(state="blocked", field=field):
                record = apply_mutations(
                    self.fixtures["base_record"],
                    [
                        {"op": "set", "path": "/point_in_time_status", "value": "point_in_time_blocked"},
                        {"op": "set", "path": "/point_in_time_block_reasons", "value": ["TIMESTAMP_MISSING"]},
                        {"op": "set", "path": f"/sources/0/{field}", "value": None},
                    ],
                )
                self.assertEqual([], timestamp_contract_reason_codes(record))

        for invalid_status in (None, True, 1, [], {}, "UNKNOWN"):
            with self.subTest(invalid_status=invalid_status):
                record = apply_mutations(
                    self.fixtures["base_record"],
                    [
                        {"op": "set", "path": "/point_in_time_status", "value": invalid_status},
                        {"op": "set", "path": "/sources/0/available_at", "value": None},
                    ],
                )
                self.assertEqual(
                    [TIMESTAMP_CONTAINER_INVALID],
                    timestamp_contract_reason_codes(record),
                )

        decision_index = next(
            index for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            if spec.temporal_role == "decision_instant"
        )
        available_index = next(
            index for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
            if spec.temporal_role == "source_available_instant"
        )
        without_role = tuple(
            replace(spec, temporal_role="timestamp_only") if index == decision_index else spec
            for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
        )
        duplicate_role = (*TIMESTAMP_FIELD_INVENTORY, replace(TIMESTAMP_FIELD_INVENTORY[0], temporal_role="decision_instant"))
        redirected_role = tuple(
            replace(spec, temporal_role="source_available_instant") if spec.field == "published_at" and spec.condition_id == "ALWAYS" else
            replace(spec, temporal_role="timestamp_only") if index == available_index else spec
            for index, spec in enumerate(TIMESTAMP_FIELD_INVENTORY)
        )
        for inventory in (without_role, duplicate_role, redirected_role):
            with self.subTest(inventory=inventory):
                self.assertIn(
                    TIMESTAMP_CONTAINER_INVALID,
                    timestamp_contract_reason_codes(self.fixtures["base_record"], inventory),
                )

    def test_record_timestamp_verifier_compares_offset_aware_instants(self) -> None:
        cases = {case["case_id"]: case for case in self.fixtures["cases"]}
        self.assertEqual(
            [],
            timestamp_contract_reason_codes(
                self.materialize(cases["valid-offset-same-instant"])
            ),
        )

        one_microsecond_late = apply_mutations(
            self.fixtures["base_record"],
            [{
                "op": "set",
                "path": "/sources/0/available_at",
                "value": "2026-07-26T09:00:00.000001+10:00",
            }],
        )
        self.assertEqual(
            ["POINT_IN_TIME_VIOLATION"],
            timestamp_contract_reason_codes(one_microsecond_late),
        )
        self.assertEqual(
            ["POINT_IN_TIME_VIOLATION"],
            timestamp_contract_reason_codes(
                self.materialize(cases["invalid-offset-order-across-year"])
            ),
        )
        self.assertEqual(
            [],
            timestamp_contract_reason_codes(
                self.materialize(cases["valid-offset-order-across-year"])
            ),
        )

        same_utc = parse_offset_datetime("2026-07-26T00:00:00Z")
        same_offset = parse_offset_datetime("2026-07-26T10:00:00+10:00")
        self.assertEqual(same_utc, same_offset)

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

    def test_contract_tests_use_only_stdlib_and_the_formal_timestamp_verifier(self) -> None:
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
                "dataclasses",
                "importlib",
                "json",
                "pathlib",
                "re",
                "scripts",
                "sys",
                "types",
                "unittest",
                "urllib",
            },
            imports,
        )


if __name__ == "__main__":
    unittest.main()
