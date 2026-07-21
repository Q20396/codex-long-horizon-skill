"""Small, dependency-free helpers for locked incubator validation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


BASE_EXPERIMENT_IDS = {f"MAD-SKILL-{number:03d}" for number in range(1, 12)}
CANDIDATE_IDS = {f"MAD-SKILL-{number:03d}" for number in range(12, 15)}
FAMILY_IDS = {f"FAMILY-{number:03d}" for number in range(1, 10)}
OVERLAP_TYPES = {"full", "partial", "adjacent", "none"}
EVIDENCE_STRENGTHS = {"strong", "moderate", "weak", "insufficient"}
SOURCE_STATUSES = {
    "customer_provided_unverified",
    "verification_blocked",
    "ambiguous_source",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalized_excerpt(lines: list[str], start: int, end: int) -> str:
    return "\n".join(line.rstrip() for line in lines[start - 1 : end]) + "\n"


def issue(relative: str, field: str, expected: object, actual: object, line: int | None = None) -> str:
    location = f"{relative}:{line}" if line is not None else relative
    return f"{location}: field={field} expected={expected!r} actual={actual!r}"


def safe_relative(value: str) -> bool:
    candidate = Path(value)
    return bool(value) and not candidate.is_absolute() and ".." not in candidate.parts


def require_file(root: Path, relative: str, errors: list[str]) -> Path | None:
    if not safe_relative(relative):
        errors.append(issue(relative, "path", "safe repository-relative file", relative))
        return None
    path = root / relative
    if path.is_symlink():
        errors.append(issue(relative, "path", "non-symlink file", "symlink"))
        return None
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        errors.append(issue(relative, "path", "within repository root", "outside repository root"))
        return None
    if not path.is_file():
        errors.append(issue(relative, "file", "existing regular file", "missing"))
        return None
    return path


def load_json(root: Path, relative: str, errors: list[str]) -> dict[str, Any] | None:
    path = require_file(root, relative, errors)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(issue(relative, "json", "valid JSON", exc.msg, exc.lineno))
        return None
    if not isinstance(payload, dict):
        errors.append(issue(relative, "json", "object", type(payload).__name__))
        return None
    return payload


def load_tsv(
    root: Path, relative: str, headers: list[str], errors: list[str]
) -> list[dict[str, str]]:
    path = require_file(root, relative, errors)
    if path is None:
        return []
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    if not rows:
        errors.append(issue(relative, "rows", "non-empty TSV", "empty"))
        return []
    if rows[0] != headers:
        errors.append(issue(relative, "header", headers, rows[0], 1))
        return []
    records: list[dict[str, str]] = []
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(headers):
            errors.append(issue(relative, "column_count", len(headers), len(row), number))
            continue
        records.append(dict(zip(headers, row)))
    return records


def parse_bool(value: object, relative: str, field: str, errors: list[str], line: int | None = None) -> bool | None:
    if value in (True, "true"):
        return True
    if value in (False, "false"):
        return False
    errors.append(issue(relative, field, "boolean", value, line))
    return None


def split_ids(value: str) -> list[str]:
    return [part for part in value.split(";") if part]
