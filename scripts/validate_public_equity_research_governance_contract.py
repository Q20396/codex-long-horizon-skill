"""Dependency-free timestamp semantics for the public-equity contract.

The Draft 2020-12 Schema owns the timestamp lexical profile.  This module is
the reusable semantic complement: it classifies an already supplied timestamp
without I/O, network access, path resolution, or record mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import re


TIMESTAMP_LEXICAL_PROFILE_INVALID = "TIMESTAMP_LEXICAL_PROFILE_INVALID"
TIMESTAMP_CALENDAR_INVALID = "TIMESTAMP_CALENDAR_INVALID"
TIMESTAMP_OFFSET_INVALID_OR_REQUIRED = "TIMESTAMP_OFFSET_INVALID_OR_REQUIRED"
TIMESTAMP_CONTAINER_INVALID = "TIMESTAMP_CONTAINER_INVALID"
POINT_IN_TIME_VIOLATION = "POINT_IN_TIME_VIOLATION"

@dataclass(frozen=True)
class TimestampFieldSpec:
    """One Schema-owned timestamp path and its container/nullability shape."""

    path: str
    container_path: str
    container_type: str
    repeated: bool
    required: bool
    nullable: bool
    min_items: int | None
    conditional_context: str
    temporal_role: str
    field: str
    schema_pointer: str
    condition_id: str


# This is the verifier's only traversal inventory and the bounded mapping to
# Schema-owned local nodes. It is intentionally not a general JSON Schema
# interpreter; Draft 2020-12 remains the complete structural gate.
TIMESTAMP_FIELD_INVENTORY = (
    TimestampFieldSpec(
        "created_at", "record", "object", False, True, False, None,
        "always", "timestamp_only", "created_at", "/properties/created_at",
        "ALWAYS",
    ),
    TimestampFieldSpec(
        "research_context.research_as_of", "research_context", "object",
        False, True, False, None, "always", "timestamp_only",
        "research_as_of", "/properties/research_context/properties/research_as_of",
        "ALWAYS",
    ),
    TimestampFieldSpec(
        "research_context.decision_at", "research_context", "object", False,
        True, False, None, "always", "decision_instant", "decision_at",
        "/properties/research_context/properties/decision_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "sources[].effective_at", "sources", "array_item", True, True, True,
        1, "always", "timestamp_only", "effective_at",
        "/$defs/source/properties/effective_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "sources[].published_at", "sources", "array_item", True, True, True,
        1, "always", "timestamp_only", "published_at",
        "/$defs/source/properties/published_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "sources[].available_at", "sources", "array_item", True, True, True,
        1, "always", "source_available_instant", "available_at",
        "/$defs/source/properties/available_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "sources[].retrieved_at", "sources", "array_item", True, True, True,
        1, "always", "timestamp_only", "retrieved_at",
        "/$defs/source/properties/retrieved_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "sources[].effective_at", "sources", "array_item", True, True, False,
        1, "point_in_time_status=point_in_time_ready", "timestamp_only",
        "effective_at",
        "/allOf/0/then/properties/sources/items/allOf/1/properties/effective_at",
        "POINT_IN_TIME_READY",
    ),
    TimestampFieldSpec(
        "sources[].published_at", "sources", "array_item", True, True, False,
        1, "point_in_time_status=point_in_time_ready", "timestamp_only",
        "published_at",
        "/allOf/0/then/properties/sources/items/allOf/1/properties/published_at",
        "POINT_IN_TIME_READY",
    ),
    TimestampFieldSpec(
        "sources[].available_at", "sources", "array_item", True, True, False,
        1, "point_in_time_status=point_in_time_ready",
        "timestamp_only", "available_at",
        "/allOf/0/then/properties/sources/items/allOf/1/properties/available_at",
        "POINT_IN_TIME_READY",
    ),
    TimestampFieldSpec(
        "sources[].retrieved_at", "sources", "array_item", True, True, False,
        1, "point_in_time_status=point_in_time_ready", "timestamp_only",
        "retrieved_at",
        "/allOf/0/then/properties/sources/items/allOf/1/properties/retrieved_at",
        "POINT_IN_TIME_READY",
    ),
    TimestampFieldSpec(
        "decision_log[].recorded_at", "decision_log", "array_item", True,
        True, False, 1, "always", "timestamp_only", "recorded_at",
        "/$defs/decisionEntry/properties/recorded_at", "ALWAYS",
    ),
    TimestampFieldSpec(
        "decision_log[].research_as_of", "decision_log", "array_item", True,
        True, False, 1, "always", "timestamp_only", "research_as_of",
        "/$defs/decisionEntry/properties/research_as_of", "ALWAYS",
    ),
    TimestampFieldSpec(
        "decision_log[].human_disposition_at", "decision_log", "array_item",
        True, True, False, 1, "always", "timestamp_only",
        "human_disposition_at",
        "/$defs/decisionEntry/properties/human_disposition_at", "ALWAYS",
    ),
)

_CONDITION_COMBINATIONS = frozenset({
    ("ALWAYS", "always"),
    ("POINT_IN_TIME_READY", "point_in_time_status=point_in_time_ready"),
})
_TEMPORAL_ROLE_NAMES = frozenset({
    "timestamp_only", "decision_instant", "source_available_instant",
})
_ANNOTATION_KEYS = ("title", "description", "$comment")
_ANNOTATION_KEY_SET = frozenset(_ANNOTATION_KEYS)
_SEMANTIC_ANNOTATION_POINTERS = (
    "",
    "/$defs/offsetDateTime",
    "/$defs/nullableOffsetDateTime",
    "/properties/sources",
    "/allOf/0/then/properties/sources/items/allOf/1",
)
_SEMANTIC_ANNOTATION_POINTER_SET = frozenset(_SEMANTIC_ANNOTATION_POINTERS)
_INVENTORY_MARKER_IDENTIFIER = "PUBLIC_EQUITY_TIMESTAMP_INVENTORY_MANIFEST"
_SEMANTIC_MARKER_IDENTIFIER = "PUBLIC_EQUITY_TIMESTAMP_SCHEMA_SEMANTIC_DIGEST"
_ASCII_MARKER_GAP = r"[ \t\r\n]+"
_INVENTORY_MARKER_PATTERN = re.compile(
    r"<!--[ \t\r\n]+" + re.escape(_INVENTORY_MARKER_IDENTIFIER)
    + _ASCII_MARKER_GAP + r"sha256:([0-9a-f]{64})"
    + _ASCII_MARKER_GAP
    + r"canonicalization:json-sort-keys-compact-separators"
    + _ASCII_MARKER_GAP + r"-->",
)
_SEMANTIC_MARKER_PATTERN = re.compile(
    r"<!--[ \t\r\n]+" + re.escape(_SEMANTIC_MARKER_IDENTIFIER)
    + _ASCII_MARKER_GAP + r"sha256:([0-9a-f]{64})"
    + _ASCII_MARKER_GAP
    + r"canonicalization:utf-8-json-sort-keys-compact-separators-array-order-preserved"
    + _ASCII_MARKER_GAP + r"annotation_pointers:"
    + re.escape(",".join(
        "/" if pointer == "" else pointer
        for pointer in _SEMANTIC_ANNOTATION_POINTERS
    ))
    + _ASCII_MARKER_GAP + r"annotation_keys:"
    + re.escape(",".join(_ANNOTATION_KEYS))
    + _ASCII_MARKER_GAP + r"-->",
)
_MAX_SEMANTIC_DEPTH = 64


_PROFILE = re.compile(
    r"^(?![\s\S]*[\r\n\u2028\u2029])[0-9]{4}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:"
    r"[0-5][0-9](?:\.[0-9]{1,6})?(?:Z|(?:\+|-(?!00:00))"
    r"(?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))$"
)
_OFFSET_CANDIDATE = re.compile(
    r"^[0-9]{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?P<offset>Z|[+-].+)?$"
)
_VALID_OFFSET = re.compile(
    r"^(?:Z|(?:\+|-(?!00:00))"
    r"(?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))$"
)
_PARSE_PARTS = re.compile(
    r"^(?P<head>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?P<fraction>\.[0-9]{1,6})?(?P<offset>Z|[+-][0-9]{2}:[0-9]{2})$"
)


def _parse_profile_timestamp(value: str) -> datetime:
    """Parse the accepted profile without discarding declared precision."""

    match = _PARSE_PARTS.fullmatch(value)
    assert match is not None
    fraction = match.group("fraction")
    normalized_fraction = ""
    if fraction is not None:
        normalized_fraction = "." + fraction[1:].ljust(6, "0")
    normalized_offset = "+00:00" if match.group("offset") == "Z" else match.group("offset")
    return datetime.fromisoformat(
        match.group("head") + normalized_fraction + normalized_offset
    )


def timestamp_reason(value: object) -> str | None:
    """Return one stable reason, or ``None`` for a valid timestamp.

    Missing or malformed offsets are classified separately from an otherwise
    malformed lexical profile. Gregorian validity is deliberately evaluated
    only after the exact Schema-compatible lexical profile has passed.
    """

    if value is None:
        return TIMESTAMP_OFFSET_INVALID_OR_REQUIRED
    if type(value) is not str:
        return TIMESTAMP_LEXICAL_PROFILE_INVALID

    candidate = _OFFSET_CANDIDATE.fullmatch(value)
    if candidate is not None:
        offset = candidate.group("offset")
        if offset is None or _VALID_OFFSET.fullmatch(offset) is None:
            return TIMESTAMP_OFFSET_INVALID_OR_REQUIRED

    if _PROFILE.fullmatch(value) is None:
        return TIMESTAMP_LEXICAL_PROFILE_INVALID

    try:
        parsed = _parse_profile_timestamp(value)
    except ValueError:
        return TIMESTAMP_CALENDAR_INVALID
    if parsed.utcoffset() is None:
        return TIMESTAMP_OFFSET_INVALID_OR_REQUIRED
    return None


def parse_offset_datetime(value: object) -> datetime | None:
    """Return the parsed instant only after the complete contract gate passes."""

    if timestamp_reason(value) is not None:
        return None
    assert isinstance(value, str)
    return _parse_profile_timestamp(value)


def _pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _semantic_schema_tree(
    value: object,
    pointer: str = "",
    depth: int = 0,
    active: frozenset[int] = frozenset(),
) -> object:
    """Canonicalize the whole Schema without interpreting its keywords."""

    if depth > _MAX_SEMANTIC_DEPTH:
        raise ValueError("Schema exceeds semantic digest depth")
    if type(value) is dict:
        if id(value) in active or not all(type(key) is str for key in value):
            raise ValueError("cyclic or invalid Schema object")
        next_active = active | {id(value)}
        result: dict[str, object] = {}
        for key, child in value.items():
            if key in _ANNOTATION_KEY_SET and pointer in _SEMANTIC_ANNOTATION_POINTER_SET:
                if type(child) is not str:
                    raise ValueError("annotation must be a string")
                continue
            result[key] = _semantic_schema_tree(
                child, f"{pointer}/{_pointer_token(key)}", depth + 1, next_active
            )
        return result
    if type(value) is list:
        if id(value) in active:
            raise ValueError("cyclic Schema array")
        next_active = active | {id(value)}
        return [
            _semantic_schema_tree(item, f"{pointer}/{index}", depth + 1, next_active)
            for index, item in enumerate(value)
        ]
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite Schema number")
        return value
    raise TypeError("unsupported Schema value")


def schema_semantic_digest(schema: object) -> str:
    """Hash complete validation semantics, ignoring only approved annotations."""

    payload = _semantic_schema_tree(schema)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _validate_inventory_shape(
    inventory: tuple[TimestampFieldSpec, ...] = TIMESTAMP_FIELD_INVENTORY,
) -> list[str]:
    """Validate the exact formal inventory before any digest or traversal."""

    if type(inventory) is not tuple or len(inventory) != len(TIMESTAMP_FIELD_INVENTORY):
        return [TIMESTAMP_CONTAINER_INVALID]
    for spec, expected in zip(inventory, TIMESTAMP_FIELD_INVENTORY):
        if type(spec) is not TimestampFieldSpec:
            return [TIMESTAMP_CONTAINER_INVALID]
        string_fields = (
            "path", "container_path", "container_type", "conditional_context",
            "temporal_role", "field", "schema_pointer", "condition_id",
        )
        if any(type(getattr(spec, field)) is not str for field in string_fields):
            return [TIMESTAMP_CONTAINER_INVALID]
        if any(type(getattr(spec, field)) is not bool for field in ("repeated", "required", "nullable")):
            return [TIMESTAMP_CONTAINER_INVALID]
        if spec.min_items is not None and (type(spec.min_items) is not int or spec.min_items < 0):
            return [TIMESTAMP_CONTAINER_INVALID]
        if spec != expected or any(
            type(getattr(spec, field)) is not type(getattr(expected, field))
            for field in spec.__dataclass_fields__
        ):
            return [TIMESTAMP_CONTAINER_INVALID]
    return []


def timestamp_inventory_manifest_digest(
    inventory: tuple[TimestampFieldSpec, ...] = TIMESTAMP_FIELD_INVENTORY,
) -> str:
    """Return the canonical digest pinned independently in architecture text."""

    if _validate_inventory_shape(inventory):
        raise ValueError("invalid timestamp inventory")

    payload = [spec.__dict__ for spec in inventory]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def timestamp_manifest_errors(markdown: object, schema: object) -> list[str]:
    """Verify the two unique architecture identity markers without I/O."""

    if type(markdown) is not str:
        return [TIMESTAMP_CONTAINER_INVALID]
    # Count raw identifiers before accepting any comment grammar. This rejects
    # bare, malformed, partial, displaced, and conflicting duplicate markers.
    if (
        markdown.count(_INVENTORY_MARKER_IDENTIFIER) != 1
        or markdown.count(_SEMANTIC_MARKER_IDENTIFIER) != 1
    ):
        return [TIMESTAMP_CONTAINER_INVALID]
    inventory = _INVENTORY_MARKER_PATTERN.findall(markdown)
    semantic = _SEMANTIC_MARKER_PATTERN.findall(markdown)
    try:
        if (
            len(inventory) != 1
            or len(semantic) != 1
            or inventory[0] != timestamp_inventory_manifest_digest()
            or semantic[0] != schema_semantic_digest(schema)
        ):
            raise ValueError("manifest identity mismatch")
    except (TypeError, ValueError, RecursionError):
        return [TIMESTAMP_CONTAINER_INVALID]
    return []


def timestamp_manifest_semantic_digest(markdown: object) -> str | None:
    """Return the sole parsed semantic digest, or ``None`` for malformed text."""

    if type(markdown) is not str or markdown.count(_SEMANTIC_MARKER_IDENTIFIER) != 1:
        return None
    values = _SEMANTIC_MARKER_PATTERN.findall(markdown)
    return values[0] if len(values) == 1 else None


def _formal_inventory_errors(
    inventory: tuple[TimestampFieldSpec, ...],
) -> list[str]:
    """Reject a changed, incomplete, or internally inconsistent inventory."""

    if _validate_inventory_shape(inventory):
        return [TIMESTAMP_CONTAINER_INVALID]
    for spec, expected in zip(inventory, TIMESTAMP_FIELD_INVENTORY):
        expected_path = (
            spec.field if spec.container_path == "record"
            else f"{spec.container_path}{'[]' if spec.repeated else ''}.{spec.field}"
        )
        if (
            spec.path != expected_path
            or (spec.condition_id, spec.conditional_context)
            not in _CONDITION_COMBINATIONS
            or not spec.schema_pointer.endswith(f"/properties/{spec.field}")
        ):
            return [TIMESTAMP_CONTAINER_INVALID]
    role_specs = {role: [spec for spec in inventory if spec.temporal_role == role] for role in _TEMPORAL_ROLE_NAMES - {"timestamp_only"}}
    if any(len(specs) != 1 for specs in role_specs.values()):
        return [TIMESTAMP_CONTAINER_INVALID]
    if any(
        spec.condition_id != "ALWAYS" or spec.conditional_context != "always"
        for specs in role_specs.values() for spec in specs
    ):
        return [TIMESTAMP_CONTAINER_INVALID]
    return []


def timestamp_inventory_alignment_errors(
    schema: object,
    inventory: tuple[TimestampFieldSpec, ...] = TIMESTAMP_FIELD_INVENTORY,
    expected_semantic_digest: object = None,
) -> list[str]:
    """Verify immutable inventory and complete Schema semantic identity.

    This deliberately hashes the complete validation tree instead of partially
    interpreting JSON Schema applicators. The complete Draft engine remains the
    structural authority; this helper only validates the fixed identity chain.
    """

    if _formal_inventory_errors(inventory) or not isinstance(schema, dict):
        return [TIMESTAMP_CONTAINER_INVALID]
    try:
        if (
            type(expected_semantic_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_semantic_digest) is None
            or schema_semantic_digest(schema) != expected_semantic_digest
        ):
            raise ValueError("semantic Schema digest mismatch")
    except (TypeError, ValueError, RecursionError):
        return [TIMESTAMP_CONTAINER_INVALID]
    return []


def _record_timestamp_reason_codes_unchecked(
    record: object,
    inventory: tuple[TimestampFieldSpec, ...] = TIMESTAMP_FIELD_INVENTORY,
) -> list[str]:
    """Validate every declared record timestamp and point-in-time relation.

    This is a pure record-level contract gate. It explicitly enumerates the
    timestamp-bearing fields rather than discovering names recursively, so a
    future field is not silently admitted without a contract change.
    """

    if type(record) is not dict:
        return [TIMESTAMP_CONTAINER_INVALID]

    if _formal_inventory_errors(inventory):
        return [TIMESTAMP_CONTAINER_INVALID]

    reasons: set[str] = set()
    point_in_time_status = record.get("point_in_time_status")
    if type(point_in_time_status) is not str or point_in_time_status not in {
        "point_in_time_ready",
        "point_in_time_blocked",
    }:
        return [TIMESTAMP_CONTAINER_INVALID]

    def validate_field(container: dict[str, object], spec: TimestampFieldSpec) -> None:
        if spec.field not in container:
            reasons.add(TIMESTAMP_OFFSET_INVALID_OR_REQUIRED)
            return
        value = container[spec.field]
        if value is None and spec.nullable:
            return
        reason = timestamp_reason(value)
        if reason is not None:
            reasons.add(reason)

    def containers_for(spec: TimestampFieldSpec) -> tuple[dict[str, object], ...]:
        if spec.container_path == "record":
            return (record,)
        value = record.get(spec.container_path)
        if spec.repeated:
            if type(value) is not list:
                reasons.add(TIMESTAMP_CONTAINER_INVALID)
                return ()
            if len(value) < (spec.min_items or 0):
                reasons.add(TIMESTAMP_CONTAINER_INVALID)
                return ()
            containers = []
            for item in value:
                if type(item) is dict:
                    containers.append(item)
                else:
                    reasons.add(TIMESTAMP_CONTAINER_INVALID)
            return tuple(containers)
        if type(value) is not dict:
            reasons.add(TIMESTAMP_CONTAINER_INVALID)
            return ()
        return (value,)

    container_specs: dict[str, TimestampFieldSpec] = {}
    for spec in inventory:
        container_specs.setdefault(spec.container_path, spec)
    containers_by_name = {
        name: containers_for(spec) for name, spec in container_specs.items()
    }
    for spec in inventory:
        applies = spec.conditional_context == "always" or (
            spec.conditional_context == "point_in_time_status=point_in_time_ready"
            and point_in_time_status == "point_in_time_ready"
        )
        if applies:
            for container in containers_by_name[spec.container_path]:
                validate_field(container, spec)

    block_reasons = record.get("point_in_time_block_reasons")
    if type(block_reasons) is not list or not all(
        type(reason) is str for reason in block_reasons
    ):
        reasons.add(TIMESTAMP_CONTAINER_INVALID)
        block_reasons = []

    relation_specs = _temporal_relation_specs(inventory)
    if relation_specs is None:
        return [TIMESTAMP_CONTAINER_INVALID]
    decision_spec, available_spec = relation_specs
    contexts = containers_by_name.get(decision_spec.container_path, ())
    sources = containers_by_name.get(available_spec.container_path, ())
    decision_container = contexts[0] if len(contexts) == 1 else {}
    decision_at = parse_offset_datetime(decision_container.get(decision_spec.field))
    if decision_at is not None:
        available_after_decision = any(
            (available_at := parse_offset_datetime(source.get(available_spec.field)))
            is not None
            and available_at > decision_at
            for source in sources
            if type(source) is dict
        )
        blocked = (
            point_in_time_status == "point_in_time_blocked"
            and "AVAILABLE_AFTER_DECISION"
            in set(block_reasons)
        )
        if available_after_decision and not blocked:
            reasons.add(POINT_IN_TIME_VIOLATION)

    return sorted(reasons)


def _timestamp_container_keys_are_safe(record: object) -> bool:
    """Require exact string keys before any timestamp container field access.

    An exact builtin ``dict`` can still hold hostile non-string keys.  This
    admission check runs in the public gate before the unchecked walker uses
    ``get``, membership, or indexing on record-owned containers.
    """

    if type(record) is not dict or not all(type(key) is str for key in record):
        return False
    for field, repeated in (
        ("research_context", False),
        ("sources", True),
        ("decision_log", True),
    ):
        if field not in record:
            continue
        value = record[field]
        if repeated:
            if type(value) is list:
                for item in value:
                    if type(item) is dict and not all(
                        type(key) is str for key in item
                    ):
                        return False
        elif type(value) is dict and not all(type(key) is str for key in value):
            return False
    return True


def _temporal_relation_specs(
    inventory: tuple[TimestampFieldSpec, ...],
) -> tuple[TimestampFieldSpec, TimestampFieldSpec] | None:
    """Derive the sole relation participants from the formal role closure."""

    relational = [role for role in _TEMPORAL_ROLE_NAMES if role != "timestamp_only"]
    if len(relational) != 2:
        return None
    by_role = {role: [spec for spec in inventory if spec.temporal_role == role] for role in relational}
    if any(len(specs) != 1 for specs in by_role.values()):
        return None
    ordered = tuple(by_role[role][0] for role in sorted(relational))
    return ordered if len(ordered) == 2 else None


def validate_timestamp_contract(
    *,
    schema: object,
    markdown: object,
    record: object,
    inventory: tuple[TimestampFieldSpec, ...],
    expected_semantic_digest: object,
) -> list[str]:
    """Public timestamp gate: fixed manifest, Schema identity, then record."""

    if timestamp_manifest_errors(markdown, schema) or type(markdown) is not str:
        return [TIMESTAMP_CONTAINER_INVALID]
    semantic = timestamp_manifest_semantic_digest(markdown)
    if semantic is None or type(expected_semantic_digest) is not str or (
        expected_semantic_digest != semantic
    ) or timestamp_inventory_alignment_errors(
        schema, inventory, expected_semantic_digest=expected_semantic_digest
    ):
        return [TIMESTAMP_CONTAINER_INVALID]
    if not _timestamp_container_keys_are_safe(record):
        return [TIMESTAMP_CONTAINER_INVALID]
    return _record_timestamp_reason_codes_unchecked(record, inventory)
