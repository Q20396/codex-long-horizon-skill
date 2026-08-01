"""Contract checks for the static multi-perspective financial research workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "long-horizon-engineering"
WORKFLOW = SKILL / "references" / "multi-perspective-financial-research.md"
TEMPLATE = SKILL / "templates" / "MULTI_PERSPECTIVE_FINANCIAL_RESEARCH_REVIEW.md"
MANIFEST = SKILL / "package-manifest.json"


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
        import json

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        core_paths = manifest["components"]["core"]["paths"]
        optional_paths = manifest["components"]["bundled-optional"]["paths"]
        expected = {
            ".agents/skills/long-horizon-engineering/references/multi-perspective-financial-research.md",
            ".agents/skills/long-horizon-engineering/templates/MULTI_PERSPECTIVE_FINANCIAL_RESEARCH_REVIEW.md",
        }
        self.assertTrue(expected.isdisjoint(core_paths))
        self.assertTrue(expected.issubset(optional_paths))


if __name__ == "__main__":
    unittest.main()
