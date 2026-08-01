"""Contract checks for the static multi-perspective financial research workflow."""

from __future__ import annotations

import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "long-horizon-engineering"
WORKFLOW = SKILL / "references" / "multi-perspective-financial-research.md"
TEMPLATE = SKILL / "templates" / "MULTI_PERSPECTIVE_FINANCIAL_RESEARCH_REVIEW.md"
MANIFEST = SKILL / "package-manifest.json"
CONTRACT = SKILL / "references" / "multi-perspective-financial-research.contract.json"

EXPECTED_CONTRACT = {
    "schema_version": "1.0",
    "capability": "multi-perspective-financial-research",
    "mode": "static_research_packet",
    "activation": "explicit-only",
    "package_layer": "bundled-optional",
    "default_network": "disabled",
    "one_run_public_data_approval_required": True,
    "account_access": "forbidden",
    "credential_access": "forbidden",
    "customer_data_upload": "forbidden",
    "order_generation": "forbidden",
    "trade_execution": "forbidden",
    "background_monitoring": "forbidden",
    "external_notification": "forbidden",
    "persistent_memory": "forbidden",
    "human_decision_required": True,
}


class MultiPerspectiveFinancialResearchContractTests(unittest.TestCase):
    def test_workflow_preserves_research_only_boundaries(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8").casefold()
        for phrase in (
            "fundamentals",
            "market and valuation",
            "counter-case",
            "risk and backtest review",
            "fact",
            "inference",
            "unknown",
            "one-run network approval",
            "no account",
            "no order",
            "no trade",
            "no automatic",
            "no persistent memory",
            "not investment advice",
        ):
            self.assertIn(phrase, text)

    def test_template_has_reproducible_research_sections(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8").casefold()
        for heading in (
            "research question",
            "scope and authority",
            "evidence ledger",
            "four research views",
            "simulation or backtest plan",
            "falsifiers and evidence gaps",
            "customer decision",
        ):
            self.assertIn(heading, text)

    def test_new_static_assets_are_bundled_optional_only(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        core_paths = manifest["components"]["core"]["paths"]
        optional_paths = manifest["components"]["bundled-optional"]["paths"]
        expected = {
            ".agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.md",
            ".agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.contract.json",
            ".agents/skills/long-horizon-engineering/templates/MULTI_PERSPECTIVE_FINANCIAL_RESEARCH_REVIEW.md",
        }
        self.assertTrue(expected.isdisjoint(core_paths))
        self.assertTrue(expected.issubset(optional_paths))

    def test_machine_readable_contract_has_a_closed_safe_shape(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(set(EXPECTED_CONTRACT) | {"limitations"}, set(contract))
        for key, expected in EXPECTED_CONTRACT.items():
            with self.subTest(key=key):
                self.assertEqual(expected, contract[key])
        self.assertIsInstance(contract["limitations"], list)
        self.assertTrue(all(isinstance(item, str) and item for item in contract["limitations"]))

    def test_static_research_assets_do_not_introduce_runtime_surfaces(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        selected = {
            ".agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.md",
            ".agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.contract.json",
            ".agents/skills/long-horizon-engineering/templates/MULTI_PERSPECTIVE_FINANCIAL_RESEARCH_REVIEW.md",
        }
        bundled_optional = set(manifest["components"]["bundled-optional"]["paths"])
        self.assertTrue(selected.issubset(bundled_optional))
        self.assertTrue(all(not path.endswith(".py") for path in selected))


if __name__ == "__main__":
    unittest.main()
