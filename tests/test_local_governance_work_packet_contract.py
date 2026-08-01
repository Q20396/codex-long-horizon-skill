from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".agents/skills/long-horizon-engineering/templates/LOCAL_GOVERNANCE_WORK_PACKET.md"
PROMPT = ROOT / "prompts/local-governance-work-packet.md"
GUIDE = ROOT / "docs/local-governance-work-packet.md"


class LocalGovernanceWorkPacketContractTests(unittest.TestCase):
    def test_packet_has_fixed_customer_safe_sections(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        for heading in (
            "## 1. Request and decision",
            "## 2. Approved material and privacy boundary",
            "## 3. Evidence ledger",
            "## 4. Bounded outcome",
            "## 5. Operator boundary",
            "## 6. Review record",
        ):
            self.assertIn(heading, text)
        self.assertIn("FACT / INFERENCE / UNKNOWN", text)
        self.assertIn("Exactly one next safe action", text)
        self.assertIn("customer_approval_required: true", text)
        self.assertIn("human_disposition: PENDING", text)
        self.assertIn("next_stage_authorized: false", text)

    def test_packet_refuses_sensitive_transfer_and_runtime_claims(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (TEMPLATE, PROMPT, GUIDE)
        ).lower()
        for phrase in (
            "do not paste, upload, log, or retain customer-sensitive content",
            "do not connect accounts",
            "does not access dropbox, gmail, outlook, google drive, brokerages",
            "does not replace a lawyer, adviser",
        ):
            self.assertIn(phrase, combined)

    def test_prompt_and_guide_link_to_the_template(self) -> None:
        self.assertIn("Local Governance Work Packet", PROMPT.read_text(encoding="utf-8"))
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertIn("LOCAL_GOVERNANCE_WORK_PACKET.md", guide)
        self.assertIn("local-governance-work-packet.md", guide)
