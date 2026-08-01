#!/usr/bin/env python3
"""Validate one immutable LHE release-evidence receipt without network access.

The receipt is evidence metadata, not an authorization to tag, publish, install,
or update a skill. Live checks of the referenced systems remain separate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    "SOURCE_VALIDATED",
    "TAG_VERIFIED",
    "RELEASE_VERIFIED",
    "MARKETPLACE_VERIFIED",
    "INSTALL_VERIFIED",
)


class ReceiptError(ValueError):
    """A receipt is malformed or claims a stage without its evidence."""


def load_receipt(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReceiptError(f"receipt cannot be read: {error}") from error
    if not isinstance(value, dict):
        raise ReceiptError("receipt must be a JSON object")
    return value


def require_string(data: dict[str, object], key: str, pattern: re.Pattern[str] | None = None) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"{key} must be a non-empty string")
    if pattern is not None and not pattern.fullmatch(value):
        raise ReceiptError(f"{key} has an invalid format")
    return value


def require_object(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ReceiptError(f"{key} must be an object")
    return value


def validate_receipt(data: dict[str, object]) -> None:
    if data.get("schema_version") != "1.0":
        raise ReceiptError("schema_version must be '1.0'")
    require_string(data, "version", re.compile(r"^\d+\.\d+\.\d+$"))
    stage = require_string(data, "verified_stage")
    if stage not in STAGES:
        raise ReceiptError("verified_stage is not a known release stage")
    require_string(data, "verified_at")
    source = require_object(data, "source")
    tag = require_string(source, "tag")
    if tag != f"v{data['version']}":
        raise ReceiptError("source.tag must match version")
    for key in ("tag_object_sha", "peeled_commit_sha", "tree_sha"):
        require_string(source, key, SHA_RE)
    formal = require_object(data, "formal_gate")
    for key in ("acquisition_receipt_sha256", "result_sha256"):
        require_string(formal, key, SHA256_RE)
    stage_index = STAGES.index(stage)
    if stage_index >= STAGES.index("RELEASE_VERIFIED"):
        release = require_object(data, "github_release")
        require_string(release, "url")
        require_string(release, "id")
        if not isinstance(release.get("asset_sha256"), list):
            raise ReceiptError("github_release.asset_sha256 must be a list")
    if stage_index >= STAGES.index("MARKETPLACE_VERIFIED"):
        marketplace = require_object(data, "marketplace")
        require_string(marketplace, "codex_cli_version")
        require_string(marketplace, "resolved_commit_sha", SHA_RE)
        if marketplace.get("resolved_commit_sha") != source["peeled_commit_sha"]:
            raise ReceiptError("marketplace resolved commit must match source peeled commit")
    if stage_index >= STAGES.index("INSTALL_VERIFIED"):
        installed = require_object(data, "installed")
        require_string(installed, "verification_scope")
        if installed.get("customer_data_accessed") is not False:
            raise ReceiptError("installed receipt must declare customer_data_accessed false")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise ReceiptError("limitations must be a list of strings")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = load_receipt(args.receipt)
        validate_receipt(receipt)
    except ReceiptError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"receipt": str(args.receipt), "verified_stage": receipt["verified_stage"], "valid": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
