"""Dependency-free contracts for local-first high-stakes capability designs."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
CATALOG = (
    ROOT
    / ".agents/skills/long-horizon-engineering/catalog/local-capability-catalog.json"
)
CATALOG_GUIDE = INCUBATOR / "architecture" / "local-capability-catalog.md"
CATALOG_SCHEMA = INCUBATOR / "schemas" / "local-capability-catalog.schema.json"
CATALOG_CASES = (
    ROOT / "tests" / "fixtures" / "local-capability-catalog" / "cases.json"
)
PROVIDER = INCUBATOR / "architecture" / "local-case-evidence-provider.json"
PROVIDER_GUIDE = INCUBATOR / "architecture" / "local-case-evidence-provider.md"
PROVIDER_SCHEMA = (
    INCUBATOR / "schemas" / "local-case-evidence-provider.schema.json"
)
PROVIDER_CASES = (
    ROOT / "tests" / "fixtures" / "local-case-evidence-provider" / "cases.json"
)
PROVIDER_PILOT = (
    ROOT
    / "tests"
    / "fixtures"
    / "local-case-evidence-provider"
    / "synthetic-pilot.json"
)
FEASIBILITY_REVIEW_PLAN = (
    ROOT / "docs" / "maintainers" / "local-first-feasibility-review-plan.md"
)
TRIGGER_VALIDATOR_PATH = (
    ROOT
    / ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py"
)
PRODUCT_LANGUAGE_FILES = (
    ROOT / "README.md",
    ROOT / ".agents/skills/long-horizon-engineering/SKILL.md",
    ROOT / ".codex-plugin/plugin.json",
    ROOT / ".agents/plugins/marketplace.json",
    ROOT / "INSTALL.md",
    ROOT / "UPGRADE_GUIDE.md",
    ROOT / "docs/plugin-install.md",
    ROOT / "docs/releases/v0.3.0.md",
    ROOT / "releases/latest.json",
    ROOT / "releases/long-horizon-engineering/latest.json",
    ROOT / "releases/ai-video-production/latest.json",
    CATALOG_GUIDE,
    PROVIDER_GUIDE,
    ROOT / "docs/high-stakes-customer-workflows.md",
)
SENSITIVE_BOUNDARY_FILES = (
    ROOT / ".agents/skills/long-horizon-engineering/references/client-privacy.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/external-app-runtime-boundary.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/capability-boundaries.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/external-search-protocol.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/external-source-scan.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/skill-authoring-methodology.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/industrial-skill-design-principles.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/disaster-monitoring-enablement.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/templates/disaster-alert-rule.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/references/approved-tool-contract-card.md",
    ROOT
    / ".agents/skills/long-horizon-engineering/templates/source-upload-consent-checklist.md",
)
TRANSFER_VERBS = (
    r"(?:upload(?:ed|ing)?|paste(?:d|ing)?|send|sent|sync(?:ed|ing)?|"
    r"transmit(?:ted|ting)?|share(?:d|ing)?|publish(?:ed|ing)?|push(?:ed|ing)?)"
)
SENSITIVE_TERMS = (
    r"(?:customer-sensitive|sensitive (?:data|content|information)|"
    r"client data|private (?:data|content|files)|legal evidence|"
    r"family information|financial records)"
)
APPROVAL_EXCEPTION = re.compile(
    rf"(?:{SENSITIVE_TERMS}.{{0,100}}(?:may|can|allowed|permitted).{{0,40}}"
    rf"{TRANSFER_VERBS}.{{0,80}}(?:approv|consent)|"
    rf"(?:approv|consent).{{0,80}}{SENSITIVE_TERMS}.{{0,80}}"
    rf"(?:may|can|allowed|permitted).{{0,40}}{TRANSFER_VERBS})",
    flags=re.IGNORECASE | re.DOTALL,
)
FALLBACK_VALIDATION_KEYWORDS = {
    "$ref",
    "additionalProperties",
    "const",
    "enum",
    "items",
    "maximum",
    "maxItems",
    "maxLength",
    "minimum",
    "minItems",
    "minLength",
    "pattern",
    "required",
    "type",
    "uniqueItems",
}
SCHEMA_METADATA_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "default",
    "examples",
}
SCHEMA_MAP_KEYWORDS = {"$defs", "properties"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pointer_parent(document, pointer: str):
    parts = pointer.lstrip("/").split("/")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def set_pointer(document: dict, pointer: str, value) -> None:
    parent, leaf = pointer_parent(document, pointer)
    if isinstance(parent, list):
        parent[int(leaf)] = deepcopy(value)
    else:
        parent[leaf] = deepcopy(value)


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
    raise AssertionError(f"Non-JSON value: {value!r}")


def matches_type(value, expected) -> bool:
    if isinstance(expected, list):
        return any(matches_type(value, item) for item in expected)
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: type(item) is bool,
        "integer": lambda item: type(item) is int,
        "null": lambda item: item is None,
    }
    return checks[expected](value)


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


def structural_reasons(instance, schema: dict, root_schema: dict):
    schema = resolve_schema(schema, root_schema)
    expected_type = schema.get("type")
    if expected_type is not None and not matches_type(instance, expected_type):
        yield "FIELD_TYPE_INVALID"
        return

    if "const" in schema:
        const_value = schema["const"]
        if type(instance) is not type(const_value) or instance != const_value:
            yield "FIELD_CONST_INVALID"
            return
    if "enum" in schema:
        if not any(type(instance) is type(item) for item in schema["enum"]):
            yield "FIELD_TYPE_INVALID"
            return
        if instance not in schema["enum"]:
            yield "FIELD_ENUM_INVALID"

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            yield "STRING_MIN_LENGTH_VIOLATION"
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            yield "STRING_MAX_LENGTH_VIOLATION"
        pattern = schema.get("pattern")
        if pattern is not None:
            try:
                compiled = re.compile(pattern)
            except (re.error, TypeError):
                yield "SCHEMA_PATTERN_INVALID"
            else:
                if compiled.search(instance) is None:
                    yield "STRING_PATTERN_VIOLATION"
    if isinstance(instance, int) and type(instance) is int:
        if "minimum" in schema and instance < schema["minimum"]:
            yield "NUMBER_MINIMUM_VIOLATION"
        if "maximum" in schema and instance > schema["maximum"]:
            yield "NUMBER_MAXIMUM_VIOLATION"
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            yield "ARRAY_MIN_ITEMS_VIOLATION"
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            yield "ARRAY_MAX_ITEMS_VIOLATION"
        if schema.get("uniqueItems") is True:
            values = [canonical_json_value(item) for item in instance]
            if len(values) != len(set(values)):
                yield "ARRAY_UNIQUE_ITEMS_VIOLATION"
        item_schema = schema.get("items")
        if item_schema is not None:
            for item in instance:
                yield from structural_reasons(item, item_schema, root_schema)
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        if any(key not in instance for key in schema.get("required", [])):
            yield "REQUIRED_FIELD_MISSING"
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    yield "UNKNOWN_FIELD"
        for key, value in instance.items():
            if key in properties:
                yield from structural_reasons(value, properties[key], root_schema)


def _present_wrong_type(mapping: dict, field: str, expected_type) -> bool:
    return field in mapping and not isinstance(mapping[field], expected_type)


def _present_wrong_exact_type(mapping: dict, field: str, expected_type) -> bool:
    return field in mapping and type(mapping[field]) is not expected_type


def catalog_semantic_reasons(catalog) -> set[str]:
    if not isinstance(catalog, dict):
        return {"FIELD_TYPE_INVALID"}

    reasons: set[str] = set()
    authority = catalog.get("authority")
    providers = catalog.get("providers")
    capabilities = catalog.get("capabilities")
    if authority is not None and not isinstance(authority, dict):
        return {"FIELD_TYPE_INVALID"}
    if providers is not None and not isinstance(providers, list):
        return {"FIELD_TYPE_INVALID"}
    if capabilities is not None and not isinstance(capabilities, list):
        return {"FIELD_TYPE_INVALID"}

    if isinstance(authority, dict) and any(
        _present_wrong_exact_type(authority, field, bool)
        for field in (
            "keyword_match_grants_authority",
            "auto_load_uninstalled_code",
            "auto_install",
            "auto_execute",
            "network_access",
            "account_access",
            "persistence",
            "customer_sensitive_data_upload",
            "model_memory",
            "telemetry",
        )
    ):
        return {"FIELD_TYPE_INVALID"}

    for provider in providers or []:
        if not isinstance(provider, dict):
            return {"FIELD_TYPE_INVALID"}
        if _present_wrong_type(provider, "provider_id", str):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_type(provider, field, str)
            for field in ("status", "synthetic_pilot_status")
        ):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_exact_type(provider, field, bool)
            for field in (
                "interface_only",
                "runtime_present",
                "connector_implementations_present",
                "network_access",
                "account_access",
                "credential_access",
                "persistence_authority",
                "customer_sensitive_data_upload",
                "model_memory",
                "telemetry",
            )
        ):
            return {"FIELD_TYPE_INVALID"}
        if "expires_at" in provider and provider["expires_at"] is not None:
            return {"FIELD_TYPE_INVALID"}

    for card in capabilities or []:
        if not isinstance(card, dict):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_type(card, field, str)
            for field in ("capability_id", "availability")
        ):
            return {"FIELD_TYPE_INVALID"}
        if _present_wrong_exact_type(card, "executable", bool):
            return {"FIELD_TYPE_INVALID"}
        required_provider = card.get("required_provider")
        if required_provider is not None and not isinstance(required_provider, str):
            return {"FIELD_TYPE_INVALID"}

    if not isinstance(authority, dict):
        return reasons
    if authority.get("keyword_match_grants_authority") is not False:
        reasons.add("KEYWORD_AUTHORITY_FORBIDDEN")
    if authority.get("auto_load_uninstalled_code") is not False:
        reasons.add("UNINSTALLED_AUTOLOAD_FORBIDDEN")
    if authority.get("customer_sensitive_data_upload") is not False:
        reasons.add("CUSTOMER_DATA_UPLOAD_FORBIDDEN")
    if not isinstance(providers, list):
        return reasons
    provider_ids: set[str] = set()
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("provider_id")
        if isinstance(provider_id, str):
            if provider_id in provider_ids:
                reasons.add("PROVIDER_REFERENCE_UNRESOLVED")
            provider_ids.add(provider_id)
        if (
            provider.get("status") != "declared-disabled"
            or provider.get("runtime_present") is not False
            or provider.get("connector_implementations_present") is not False
        ):
            reasons.add("PROVIDER_RUNTIME_UNIMPLEMENTED")
        if provider.get("synthetic_pilot_status") != "fixture-only":
            reasons.add("SYNTHETIC_PILOT_RUNTIME_FORBIDDEN")
        for field in (
            "network_access",
            "account_access",
            "credential_access",
            "persistence_authority",
            "customer_sensitive_data_upload",
            "model_memory",
            "telemetry",
        ):
            if provider.get(field) is not False:
                reasons.add("PROVIDER_EFFECT_FORBIDDEN")
    for card in capabilities or []:
        if card.get("executable") is not False:
            reasons.add("CAPABILITY_EXECUTION_FORBIDDEN")
        if card.get("availability") != "descriptor-only":
            reasons.add("CAPABILITY_DESCRIPTOR_ONLY")
        required_provider = card.get("required_provider")
        if (
            required_provider is not None
            and required_provider not in provider_ids
        ):
            reasons.add("PROVIDER_REFERENCE_UNRESOLVED")
    return reasons


def provider_semantic_reasons(record) -> set[str]:
    if not isinstance(record, dict):
        return {"FIELD_TYPE_INVALID"}

    if any(
        _present_wrong_exact_type(record, field, bool)
        for field in (
            "customer_data_upload",
            "raw_content_to_model",
            "model_memory",
            "telemetry",
        )
    ) or any(
        _present_wrong_type(record, field, str)
        for field in ("provider_status", "state")
    ):
        return {"FIELD_TYPE_INVALID"}

    connector = record.get("connector")
    handling = record.get("evidence_handling")
    cursor = record.get("cursor")
    retention = record.get("retention")
    for branch in (connector, handling, cursor, retention):
        if branch is not None and not isinstance(branch, dict):
            return {"FIELD_TYPE_INVALID"}

    if isinstance(connector, dict):
        if any(not isinstance(key, str) for key in connector):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_type(connector, field, str)
            for field in (
                "connector_type",
                "adapter_id",
                "execution_mode",
                "status",
            )
        ):
            return {"FIELD_TYPE_INVALID"}
        if _present_wrong_type(connector, "scopes", list):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_exact_type(connector, field, bool)
            for field in (
                "network_access",
                "account_access",
                "credentials_present",
                "automatic_reconnect",
            )
        ):
            return {"FIELD_TYPE_INVALID"}
    if isinstance(handling, dict) and any(
        _present_wrong_exact_type(handling, field, bool)
        for field in (
            "active_content_detected",
            "prompt_injection_detected",
            "raw_snapshot_retained",
            "raw_snapshot_approved",
        )
    ):
        return {"FIELD_TYPE_INVALID"}
    if isinstance(cursor, dict) and _present_wrong_type(cursor, "status", str):
        return {"FIELD_TYPE_INVALID"}
    if isinstance(retention, dict):
        if _present_wrong_type(retention, "legal_hold_status", str):
            return {"FIELD_TYPE_INVALID"}
        if any(
            _present_wrong_exact_type(retention, field, bool)
            for field in ("delete_authorized", "export_authorized")
        ):
            return {"FIELD_TYPE_INVALID"}

    reasons: set[str] = set()
    if record.get("customer_data_upload") is not False:
        reasons.add("CUSTOMER_DATA_UPLOAD_FORBIDDEN")
    if record.get("raw_content_to_model") is not False:
        reasons.add("RAW_CONTENT_TO_MODEL_FORBIDDEN")
    if record.get("provider_status") != "declared-disabled":
        reasons.add("PROVIDER_RUNTIME_UNIMPLEMENTED")

    if isinstance(connector, dict):
        if (
            connector.get("connector_type") != "synthetic-mailbox"
            or connector.get("adapter_id")
            != "synthetic-local-read-only-adapter"
            or connector.get("execution_mode") != "fixture-only"
        ):
            reasons.add("SYNTHETIC_PILOT_RUNTIME_FORBIDDEN")
        if connector.get("scopes") != []:
            reasons.add("CONNECTOR_SCOPE_FORBIDDEN")
        if connector.get("network_access") is not False:
            reasons.add("CONNECTOR_NETWORK_FORBIDDEN")
        if connector.get("account_access") is not False:
            reasons.add("CONNECTOR_ACCOUNT_ACCESS_FORBIDDEN")
        if connector.get("credentials_present") is not False:
            reasons.add("CREDENTIAL_FIELD_FORBIDDEN")
        if connector.get("automatic_reconnect") is not False:
            reasons.add("AUTOMATIC_RECONNECT_FORBIDDEN")
        if any(
            key.casefold() in {"credential", "credentials", "password", "secret", "token"}
            for key in connector
        ):
            reasons.add("CREDENTIAL_FIELD_FORBIDDEN")

    state = record.get("state")
    if isinstance(handling, dict):
        if handling.get("active_content_detected") is True and state != "QUARANTINED":
            reasons.add("ACTIVE_CONTENT_QUARANTINE_REQUIRED")
        if (
            handling.get("prompt_injection_detected") is True
            and state != "QUARANTINED"
        ):
            reasons.add("PROMPT_INJECTION_QUARANTINE_REQUIRED")
        if (
            handling.get("raw_snapshot_retained") is True
            and handling.get("raw_snapshot_approved") is not True
        ):
            reasons.add("RAW_SNAPSHOT_APPROVAL_REQUIRED")

    if (
        isinstance(cursor, dict)
        and cursor.get("status") in {"stale", "invalid"}
        and state not in {"BLOCKED", "APPROVAL_PENDING"}
    ):
        reasons.add("STALE_CURSOR_BLOCK_REQUIRED")

    if isinstance(retention, dict):
        if (
            retention.get("legal_hold_status") == "active"
            and retention.get("delete_authorized") is True
        ):
            reasons.add("LEGAL_HOLD_DELETE_FORBIDDEN")
        if retention.get("export_authorized") is True:
            reasons.add("EXPORT_APPROVAL_REQUIRED")
    return reasons


def validation_reasons(instance, schema: dict, semantic_helper) -> set[str]:
    structural = set(structural_reasons(instance, schema, schema))
    if "FIELD_TYPE_INVALID" in structural:
        return {"FIELD_TYPE_INVALID"}
    semantic = semantic_helper(instance)
    if "FIELD_TYPE_INVALID" in semantic:
        return {"FIELD_TYPE_INVALID"}
    return structural | semantic


def discover_capabilities(prompt: str, catalog: dict) -> list[str]:
    normalized = prompt.casefold()
    return sorted(
        card["capability_id"]
        for card in catalog["capabilities"]
        if any(keyword.casefold() in normalized for keyword in card["keywords"])
    )


class LocalFirstHighStakesContractTests(unittest.TestCase):
    def test_no_customer_sensitive_upload_exception_remains(self) -> None:
        for path in SENSITIVE_BOUNDARY_FILES:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(APPROVAL_EXCEPTION.search(text), path)
        combined = re.sub(r"\s+", " ", " ".join(
            path.read_text(encoding="utf-8") for path in SENSITIVE_BOUNDARY_FILES
        ))
        self.assertIn("Customer approval does not create an exception", combined)
        self.assertIn("Customer-sensitive information must never be uploaded", combined)

        permissive_mutations = (
            "Customer-sensitive information may be uploaded when approved.",
            "With customer consent, private files can be sent externally.",
        )
        for mutation in permissive_mutations:
            with self.subTest(mutation=mutation):
                self.assertIsNotNone(APPROVAL_EXCEPTION.search(mutation))

    def test_catalog_schema_and_fixed_authority_are_fail_closed(self) -> None:
        catalog = load_json(CATALOG)
        schema = load_json(CATALOG_SCHEMA)
        self.assertEqual(validation_reasons(catalog, schema, catalog_semantic_reasons), set())
        self.assertIn("FIELD_TYPE_INVALID", catalog["reason_codes"])
        self.assertEqual(catalog["profile_id"], "local-governance-core")
        [provider] = catalog["providers"]
        self.assertEqual(provider["status"], "declared-disabled")
        self.assertEqual(provider["synthetic_pilot_status"], "fixture-only")
        self.assertFalse(provider["runtime_present"])
        for card in catalog["capabilities"]:
            self.assertTrue((ROOT / card["descriptor_path"]).is_file())
            self.assertFalse(card["installed"])
            self.assertFalse(card["callable"])
            self.assertFalse(card["executable"])

    def test_keyword_cases_discover_only_local_descriptors(self) -> None:
        catalog = load_json(CATALOG)
        cases = load_json(CATALOG_CASES)
        for case in cases["positive_keyword_cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(
                    discover_capabilities(case["prompt"], catalog),
                    case["expected_capability_ids"],
                )
        self.assertIn("Discovery is not routing", CATALOG_GUIDE.read_text(encoding="utf-8"))

    def test_catalog_authority_mutations_are_rejected(self) -> None:
        catalog = load_json(CATALOG)
        cases = load_json(CATALOG_CASES)
        for case in cases["negative_mutations"]:
            with self.subTest(case=case["case_id"]):
                mutated = deepcopy(catalog)
                set_pointer(mutated, case["path"], case["value"])
                schema = load_json(CATALOG_SCHEMA)
                reasons = validation_reasons(
                    mutated,
                    schema,
                    catalog_semantic_reasons,
                )
                self.assertIn(case["expected_reason"], reasons)

    def test_provider_contract_is_declared_disabled(self) -> None:
        contract = load_json(PROVIDER)
        self.assertEqual(contract["provider_status"], "declared-disabled")
        self.assertFalse(contract["runtime_executable"])
        self.assertFalse(contract["connector_implementations_present"])
        self.assertTrue(all(value is False for value in contract["invariants"].values()))
        guide = re.sub(
            r"\s+",
            " ",
            PROVIDER_GUIDE.read_text(encoding="utf-8"),
        )
        for phrase in (
            "contains no Dropbox, Gmail, Outlook, Hotmail, or Google Drive implementation",
            "never raw customer material",
            "no automatic reconnection",
            "requires counsel direction",
        ):
            self.assertIn(phrase, guide)

    def test_provider_base_record_is_structurally_and_semantically_safe(self) -> None:
        cases = load_json(PROVIDER_CASES)
        schema = load_json(PROVIDER_SCHEMA)
        record = cases["base_record"]
        self.assertEqual(
            validation_reasons(record, schema, provider_semantic_reasons),
            set(),
        )
        self.assertIn(
            "FIELD_TYPE_INVALID",
            load_json(PROVIDER)["stable_reason_codes"],
        )
        self.assertEqual(
            {claim["classification"] for claim in record["claims"]},
            {"FACT", "INFERENCE", "UNKNOWN"},
        )

    def test_provider_threat_mutations_fail_closed(self) -> None:
        cases = load_json(PROVIDER_CASES)
        schema = load_json(PROVIDER_SCHEMA)
        for case in cases["negative_mutations"]:
            with self.subTest(case=case["case_id"]):
                record = deepcopy(cases["base_record"])
                for mutation in case["mutations"]:
                    set_pointer(record, mutation["path"], mutation["value"])
                reasons = validation_reasons(
                    record,
                    schema,
                    provider_semantic_reasons,
                )
                self.assertIn(case["expected_reason"], reasons)

    def test_fixture_only_pilot_models_incremental_delta_without_runtime(self) -> None:
        pilot = load_json(PROVIDER_PILOT)
        provider_schema = load_json(PROVIDER_SCHEMA)
        pilot_schema = {"$ref": "#/$defs/syntheticPilot"}
        self.assertEqual(
            list(structural_reasons(pilot, pilot_schema, provider_schema)),
            [],
        )
        self.assertTrue(pilot["synthetic_only"])
        self.assertFalse(pilot["customer_sensitive_data_present"])
        self.assertEqual(pilot["mode"], "fixture-only")
        self.assertEqual(pilot["provider_status"], "declared-disabled")
        for field in (
            "runtime_connector_present",
            "network_access",
            "account_access",
            "credentials_present",
            "encrypted_store_present",
            "os_credential_integration_present",
        ):
            self.assertFalse(pilot[field], field)

        first, second = pilot["checkpoints"]
        self.assertEqual(
            second["previous_checkpoint_sha256"],
            first["checkpoint_sha256"],
        )
        self.assertEqual(
            set(second["item_hashes"]) - set(first["item_hashes"]),
            set(second["delta_item_hashes"]),
        )
        outcome = pilot["customer_outcome"]
        self.assertEqual(
            set(outcome),
            {
                "FACT",
                "INFERENCE",
                "UNKNOWN",
                "status",
                "next_safe_action",
                "decision_authority",
            },
        )
        self.assertEqual(outcome["status"], "MORE_EVIDENCE_NEEDED")
        self.assertEqual(outcome["decision_authority"], "customer")
        self.assertTrue(outcome["next_safe_action"].strip())

    def test_fixture_only_pilot_rejects_unknown_runtime_aliases_recursively(self) -> None:
        provider_schema = load_json(PROVIDER_SCHEMA)
        pilot_schema = {"$ref": "#/$defs/syntheticPilot"}
        mutations = (
            ("/unexpected_runtime_alias", {"enabled": True}),
            ("/checkpoints/0/runtime", {"enabled": True}),
            ("/customer_outcome/automatic_approval", True),
        )
        for pointer, value in mutations:
            with self.subTest(pointer=pointer):
                pilot = load_json(PROVIDER_PILOT)
                set_pointer(pilot, pointer, value)
                self.assertIn(
                    "UNKNOWN_FIELD",
                    set(structural_reasons(pilot, pilot_schema, provider_schema)),
                )

    def test_semantic_type_errors_stop_dependent_traversal(self) -> None:
        catalog_schema = load_json(CATALOG_SCHEMA)
        provider_schema = load_json(PROVIDER_SCHEMA)
        catalog_mutations = (
            ("", []),
            ("/capabilities", "not-an-array"),
            ("/capabilities/0", []),
            ("/capabilities/0/required_provider", []),
            ("/providers/0/provider_id", []),
        )
        for pointer, value in catalog_mutations:
            with self.subTest(record="catalog", pointer=pointer):
                catalog = load_json(CATALOG)
                if pointer:
                    set_pointer(catalog, pointer, value)
                else:
                    catalog = value
                self.assertEqual(
                    {"FIELD_TYPE_INVALID"},
                    validation_reasons(
                        catalog,
                        catalog_schema,
                        catalog_semantic_reasons,
                    ),
                )

        provider_mutations = (
            ("", []),
            ("/connector", []),
            ("/cursor/status", []),
            ("/retention/delete_authorized", "false"),
            ("/claims/0", []),
        )
        for pointer, value in provider_mutations:
            with self.subTest(record="provider", pointer=pointer):
                provider = load_json(PROVIDER_CASES)["base_record"]
                if pointer:
                    set_pointer(provider, pointer, value)
                else:
                    provider = value
                self.assertEqual(
                    {"FIELD_TYPE_INVALID"},
                    validation_reasons(
                        provider,
                        provider_schema,
                        provider_semantic_reasons,
                    ),
                )

    def test_fallback_schema_keywords_are_closed_and_mutation_guarded(self) -> None:
        for path in (CATALOG_SCHEMA, PROVIDER_SCHEMA):
            with self.subTest(path=path):
                self.assertEqual(set(), unsupported_schema_keywords(load_json(path)))

        for keyword, value in (
            ("contains", {"type": "string"}),
            ("dependentRequired", {"status": ["provider_status"]}),
        ):
            with self.subTest(keyword=keyword):
                schema = load_json(PROVIDER_SCHEMA)
                schema["$defs"]["sourceRequest"][keyword] = value
                self.assertEqual({keyword}, unsupported_schema_keywords(schema))

        provider = load_json(PROVIDER_CASES)["base_record"]
        provider["source_request"]["maximum_items"] = 0
        schema = load_json(PROVIDER_SCHEMA)
        self.assertIn(
            "NUMBER_MINIMUM_VIOLATION",
            validation_reasons(provider, schema, provider_semantic_reasons),
        )

    def test_trigger_fixture_rejects_non_objects_and_discovery_escalation(self) -> None:
        module = load_module("lhe_trigger_validator_under_test", TRIGGER_VALIDATOR_PATH)
        payload = load_json(ROOT / "tests/expected-triggers.json")
        payload["cases"].append([])
        errors = module.validate_fixture(payload)
        self.assertTrue(
            any("must be an object" in error for error in errors),
            errors,
        )

        adversarial = [
            case
            for case in load_json(ROOT / "tests/expected-triggers.json")["cases"]
            if "discovery-escalation" in case.get("tags", [])
        ]
        self.assertGreaterEqual(len(adversarial), 2)
        for case in adversarial:
            self.assertEqual(case["expected_skill"], "none")
            self.assertEqual(case["category"], "no-skill-negative")
            self.assertEqual(
                module.validate_case(case, 0, module.skill_names()),
                [],
                case["id"],
            )
        malformed = deepcopy(adversarial[0])
        malformed["rationale"] = []
        malformed["expected_skill"] = {}
        errors = module.validate_case(malformed, 0, module.skill_names())
        self.assertTrue(any("rationale must be" in error for error in errors))
        self.assertTrue(any("invalid expected_skill" in error for error in errors))

        malformed_payload = load_json(ROOT / "tests/expected-triggers.json")
        malformed_payload["allowed_expected_skills"] = [{}]
        self.assertTrue(
            any(
                "allowed_expected_skills" in error
                for error in module.validate_fixture(malformed_payload)
            )
        )

    def test_product_language_never_claims_connector_or_provider_runtime(self) -> None:
        combined = " ".join(
            re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
            for path in PRODUCT_LANGUAGE_FILES
        )
        for required in (
            "declared-disabled",
            "fixture-only",
            "no connector implementation",
            "Customer-sensitive information",
        ):
            self.assertIn(required, combined)
        prohibited_claims = (
            r"(?i)\bLHE (?:connects|syncs|downloads|indexes) "
            r"(?:Dropbox|Gmail|Outlook|Hotmail|Google Drive)\b",
            r"(?i)\bsynthetic pilot (?:proves|verifies) "
            r"(?:encryption|connector|credential|runtime)\b",
            r"(?i)\bkeyword match (?:authorizes|installs|loads|executes)\b",
        )
        for pattern in prohibited_claims:
            self.assertNotRegex(combined, pattern)

    def test_all_records_and_descriptors_are_synthetic_or_static(self) -> None:
        fixture_text = (
            CATALOG_CASES.read_text(encoding="utf-8")
            + PROVIDER_CASES.read_text(encoding="utf-8")
            + PROVIDER_PILOT.read_text(encoding="utf-8")
        )
        self.assertNotRegex(
            fixture_text,
            r"(?i)(@[a-z0-9.-]+\.[a-z]{2,}|/Users/|C:\\|Bearer\s+|api[_-]?key)",
        )
        for path in INCUBATOR.glob("domain-packs/*/pack.json"):
            descriptor = load_json(path)
            self.assertEqual(descriptor["status"], "sandbox-only")
            self.assertTrue(descriptor["descriptor_only"])
            self.assertFalse(descriptor["installed"])
            self.assertFalse(descriptor["callable"])
            self.assertFalse(descriptor["executable"])

    def test_candidate_slice_manifest_is_exact_and_selectors_resolve(self) -> None:
        text = FEASIBILITY_REVIEW_PLAN.read_text(encoding="utf-8")
        self.assertIn("exact 74-path inventory", text)
        self.assertNotIn("exact 73-path inventory", text)
        manifest = text.split(
            "## Exact Candidate Slice Manifest",
            1,
        )[1].split("Mechanical review", 1)[0]
        base_match = re.search(
            r"^Candidate base: `([0-9a-f]{40})`\.$",
            manifest,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(base_match)
        base = base_match.group(1)
        candidate_match = re.search(
            r"^Candidate commit: `([0-9a-f]{40})`\.$",
            manifest,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(candidate_match)
        candidate = candidate_match.group(1)
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, candidate],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        # This is an archival candidate manifest. Later release commits may be
        # rebased or have unrelated history, so it must never be rebound to the
        # current HEAD merely to keep this historical review test passing.
        self.assertIn("not a current-HEAD assertion", " ".join(text.split()))

        rows = re.findall(
            r"^- \[([^]]+)\] `([^`]+)` - (.+)$",
            manifest,
            flags=re.MULTILINE,
        )
        manifest_paths = [path for _, path, _ in rows]
        tracked = subprocess.run(
            ["git", "diff", "--name-only", base, candidate],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        candidate_paths = sorted(set(tracked))

        self.assertEqual(len(rows), 74)
        self.assertEqual(len(set(manifest_paths)), 74)
        self.assertEqual(sorted(manifest_paths), candidate_paths)

        expected_slices = {f"S{index}" for index in range(1, 7)}
        covered_slices: set[str] = set()
        shared_rows = 0
        for slice_text, relative_path, description in rows:
            slices = slice_text.split("/")
            self.assertTrue(set(slices) <= expected_slices)
            covered_slices.update(slices)
            if len(slices) == 1:
                continue

            shared_rows += 1
            selectors = re.findall(r"(S[1-6])=`([^`]+)`", description)
            self.assertEqual(
                [slice_id for slice_id, _ in selectors],
                slices,
                relative_path,
            )
            target_text = subprocess.run(
                ["git", "show", f"{candidate}:{relative_path}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            for slice_id, selector in selectors:
                self.assertEqual(
                    target_text.count(selector),
                    1,
                    f"{relative_path} {slice_id} selector {selector!r}",
                )

        self.assertEqual(covered_slices, expected_slices)
        self.assertEqual(shared_rows, 8)


if __name__ == "__main__":
    unittest.main()
