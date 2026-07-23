"""Contract checks for the locked public-equity research sandbox design."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCUBATOR = ROOT / "sandbox" / "skill-incubator"
CONTRACT = INCUBATOR / "architecture" / "public-equity-research-sandbox.json"
SCHEMA = INCUBATOR / "schemas" / "public-equity-research-sandbox.schema.json"
README = INCUBATOR / "README.md"
GUIDE = INCUBATOR / "architecture" / "public-equity-research-sandbox.md"
VALIDATION_SCRIPT = INCUBATOR / "candidate-intake" / "validation" / "validate_formal_schema_instances.py"


class PublicEquityResearchSandboxContractTests(unittest.TestCase):
    def assert_contains_all(self, text: str, phrases: tuple[str, ...]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def load_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_is_locked_and_non_executable(self) -> None:
        contract = self.load_json(CONTRACT)
        expected = {
            "status": "locked",
            "registered_experiment": False,
            "implementation_exists": False,
            "customer_decision": "not_approved",
            "research_only": True,
            "broker_access_authorized": False,
            "credential_access_authorized": False,
            "network_execution_authorized": False,
            "provider_access_authorized": False,
            "trade_execution_authorized": False,
            "investment_advice_provided": False,
            "code_import_allowed": False,
            "activation_policy": "contextual_explicit_only",
            "generic_review_behavior": "use_current_conversation_if_unambiguous_else_clarify",
            "conversation_context_only": True,
            "manual_input_only": True,
            "approved_path_required": True,
            "customer_material_local_processing_only": True,
            "customer_material_upload_authorized": False,
            "customer_material_external_transfer_authorized": False,
            "public_source_approval_required": True,
        }
        self.assertEqual("PUBLIC-EQUITY-RESEARCH-SANDBOX", contract["candidate_id"])
        for field, value in expected.items():
            if isinstance(value, bool):
                self.assertIs(contract[field], value)
            else:
                self.assertEqual(value, contract[field])
        self.assertEqual(["ASX", "US_LISTED_EQUITIES"], contract["markets"])

    def test_contract_prohibits_broker_and_execution_paths(self) -> None:
        contract = self.load_json(CONTRACT)
        prohibited = set(contract["prohibited_actions"])
        self.assertTrue(
            {
                "broker connection",
                "credential or API-key access",
                "customer-material upload",
                "customer-material external transfer or synchronization",
                "market-data download or scraping",
                "third-party code import",
                "order creation or submission",
                "copy trading",
                "wallet access",
                "portfolio rebalancing",
            }.issubset(prohibited)
        )

    def test_schema_and_docs_preserve_the_boundary(self) -> None:
        schema = self.load_json(SCHEMA)
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertEqual("locked", schema["properties"]["status"]["const"])
        self.assertFalse(schema["properties"]["trade_execution_authorized"]["const"])
        guide = GUIDE.read_text(encoding="utf-8")
        self.assert_contains_all(
            guide,
            (
                "Investment advice: `NOT PROVIDED`",
                "broker connection",
                "automatic signal generation",
                "order creation",
                "No permission is implied",
                "immutable 40-character commit pin",
                "A standalone `review` request may select this candidate only",
                "Before research, the response must state the exact market and supplied instruments it understood",
                "It must ask a clarifying question when the context is absent, mixed with another review subject",
                "review my ASX holdings",
                "exact-path approval",
                "must not scan broker accounts, email, cloud drives, wallets, browser history",
                "must not be uploaded, pasted, synchronized, summarized into an external service",
                "research-oriented analysis summaries and educational risk considerations",
                "must not provide personalized buy, sell, hold, allocation, or execution advice",
                "does not override the data-handling terms or organizational settings of the Codex platform",
                "approval to verify named public sources",
            ),
        )
        self.assertIn("public-equity-research-sandbox.md", README.read_text(encoding="utf-8"))
        self.assertIn("public-equity-research-sandbox.schema.json", VALIDATION_SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
