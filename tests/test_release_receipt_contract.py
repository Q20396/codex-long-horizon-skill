#!/usr/bin/env python3
"""Dependency-free contract tests for the immutable release receipt format."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_release_receipt.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_release_receipt", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = load_module()
SHA = "a" * 40
SHA256 = "b" * 64


def receipt(stage: str = "SOURCE_VALIDATED") -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": "1.0",
        "version": "0.4.1",
        "verified_stage": stage,
        "verified_at": "2026-08-01T00:00:00Z",
        "source": {"tag": "v0.4.1", "tag_object_sha": SHA, "peeled_commit_sha": SHA, "tree_sha": SHA},
        "formal_gate": {"acquisition_receipt_sha256": SHA256, "result_sha256": SHA256},
        "limitations": ["No authority."],
    }
    if stage in {"RELEASE_VERIFIED", "MARKETPLACE_VERIFIED", "INSTALL_VERIFIED"}:
        data["github_release"] = {"url": "https://example.test/release", "id": "1", "asset_sha256": []}
    if stage in {"MARKETPLACE_VERIFIED", "INSTALL_VERIFIED"}:
        data["marketplace"] = {"codex_cli_version": "0.0.0", "resolved_commit_sha": SHA}
    if stage == "INSTALL_VERIFIED":
        data["installed"] = {"verification_scope": "isolated temporary state", "customer_data_accessed": False}
    return data


class ReleaseReceiptContractTests(unittest.TestCase):
    def test_each_stage_with_its_required_evidence_is_valid(self) -> None:
        for stage in CHECKER.STAGES:
            with self.subTest(stage=stage):
                CHECKER.validate_receipt(receipt(stage))

    def test_later_stage_cannot_omit_its_evidence(self) -> None:
        data = receipt("MARKETPLACE_VERIFIED")
        del data["marketplace"]
        with self.assertRaisesRegex(CHECKER.ReceiptError, "marketplace"):
            CHECKER.validate_receipt(data)

    def test_marketplace_commit_must_bind_to_tagged_commit(self) -> None:
        data = receipt("MARKETPLACE_VERIFIED")
        data["marketplace"]["resolved_commit_sha"] = "c" * 40
        with self.assertRaisesRegex(CHECKER.ReceiptError, "peeled commit"):
            CHECKER.validate_receipt(data)

    def test_invalid_install_receipt_cannot_claim_customer_data_access(self) -> None:
        data = receipt("INSTALL_VERIFIED")
        data["installed"]["customer_data_accessed"] = True
        with self.assertRaisesRegex(CHECKER.ReceiptError, "customer_data_accessed"):
            CHECKER.validate_receipt(data)

    def test_template_is_deliberately_not_a_valid_receipt(self) -> None:
        template = json.loads((ROOT / "docs/maintainers/release-receipt-template.json").read_text(encoding="utf-8"))
        with self.assertRaises(CHECKER.ReceiptError):
            CHECKER.validate_receipt(template)


if __name__ == "__main__":
    unittest.main()
