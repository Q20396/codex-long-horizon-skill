from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "approved-tool-contract-card.md"
TEMPLATE = LHE / "templates" / "APPROVED_TOOL_CONTRACT_CARD.md"


class ApprovedToolContractCardTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_reference_preserves_review_gated_tool_boundaries(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "A completed card is still a proposal, not authorization.",
                "does not grant permission to install, update, download, run",
                "The exact command in a card is information for review",
                "local read, workspace write, network read, external transfer",
                "account or session access, and system or production action",
                "Use an immutable version, tag, checksum, or reviewed commit",
                "Do not use a contract card to bootstrap automatic installs",
                "Treat a changed command, version, source, input scope, or effect class",
                "Earlier approval does not carry over automatically.",
            ],
        )

    def test_template_defaults_to_no_permission(self) -> None:
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "Contract status: PROPOSAL_ONLY",
                "User approval: PENDING",
                "Permission granted: NONE",
                "must not run automatically",
                "No shell expansion, hidden command, secret, credential",
                "Exact approved input paths or public source classes",
                "Approval Gates",
                "Any changed command, version, source, input scope, or effect class requires a new review.",
            ],
        )

    def test_existing_protocol_and_entrypoints_link_the_card(self) -> None:
        protocol = self.read(LHE / "references" / "external-tool-provider-protocol.md")
        skill = self.read(LHE / "SKILL.md")
        readme = self.read(ROOT / "README.md")
        package_checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")
        self.assert_contains_all(
            protocol,
            [
                "The capability map compares candidates.",
                "A completed card is still proposal-only.",
                "Do not install, update, or run a provider automatically",
            ],
        )
        self.assertIn("approved-tool-contract-card.md", skill)
        self.assert_contains_all(
            readme,
            [
                "Approved External Tool Contracts",
                "The card is proposal-only",
                "does not add a tool hub, automatic discovery",
            ],
        )
        self.assertIn("approved-tool-contract-card.md", package_checker)
        self.assertIn("APPROVED_TOOL_CONTRACT_CARD.md", package_checker)
        self.assertIn("approved-tool-contract-card.md", doctor)
        self.assertIn("APPROVED_TOOL_CONTRACT_CARD.md", doctor)


if __name__ == "__main__":
    unittest.main()
