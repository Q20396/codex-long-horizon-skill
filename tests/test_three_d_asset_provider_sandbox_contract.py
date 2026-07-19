"""Contract tests for the explicit-only 3D asset provider sandbox."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "three-d-asset-provider-sandbox.md"
TEMPLATE = LHE / "templates" / "THREE_D_ASSET_DELIVERY_APPROVAL_CARD.md"


class ThreeDAssetProviderSandboxContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_reference_is_explicit_only_and_non_runtime(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Invocation: `EXPLICIT_ONLY`",
                "Proposal status: `PROPOSAL_ONLY`",
                "Default permission: `NONE`",
                "Default network access: `DENY`",
                "Automatic skill installation: `NO`",
                "Automatic MCP configuration: `NO`",
                "Automatic sign-in or OAuth: `NO`",
                "Automatic asset inventory: `NO`",
                "Automatic reference upload: `NO`",
                "Automatic generation, credit spend, download, or workspace write: `NO`",
                "Automatic remote runtime, CDN, telemetry, or publication: `NO`",
                "does not install, update, configure, authenticate, invoke",
                "It does not add an MCP server to Codex.",
                "A proposal, public source review, copied command, installed skill, or prior approval",
            ],
        )

    def test_reference_requires_granular_approval_and_preserves_review_only_commands(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "One approval never covers another.",
                "MCP configuration",
                "Account connection",
                "Reference input",
                "Generation or revision",
                "Final generation approval",
                "Asset retrieval and project write",
                "Runtime use",
                "Sharing or publication",
                "npx skills add mintdotgg/mint-threejs-skills -a codex -g -y",
                "codex mcp add mint --url https://mcp.mint.gg/mcp",
                "not to be run automatically",
                "Do not copy its code, prompts, assets, or provider-specific prose.",
                "Treat unrecognized glTF/GLB extensions",
                "Do not silently fall back to a remote CDN",
            ],
        )

    def test_template_defaults_to_no_external_3d_permission(self) -> None:
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "Invocation: EXPLICIT_ONLY",
                "Proposal status: PROPOSAL_ONLY",
                "User approval: PENDING",
                "Permission granted: NONE",
                "External provider invoked: NO",
                "Automatic skill installation: NO",
                "Automatic MCP configuration: NO",
                "Automatic sign-in or OAuth: NO",
                "Automatic account, project, credit, or asset-inventory access: NO",
                "Automatic reference upload: NO",
                "Automatic generation, revision, or final approval: NO",
                "Automatic asset download, workspace write, remote runtime, telemetry, or publication: NO",
                "Separate Approval Gates",
                "Minimal Customer Approval Wording",
                "Do not install a skill, configure MCP, sign in, inspect my account, upload references, generate, download, write, or enable a remote runtime.",
            ],
        )

    def test_entrypoints_and_package_checks_include_the_protocol(self) -> None:
        skill = self.read(LHE / "SKILL.md")
        index = self.read(LHE / "references" / "explicit-only-extensions.md")
        readme = self.read(ROOT / "README.md")
        package_checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")

        self.assertIn("three-d-asset-provider-sandbox.md", skill)
        self.assertIn("three-d-asset-provider-sandbox.md", index)
        self.assert_contains_all(
            readme,
            [
                "Optional 3D Asset Provider Sandbox",
                "It does not install, configure, sign in, upload, generate, download, write, or enable a remote runtime.",
                "separate approval gates",
            ],
        )
        self.assertIn("three-d-asset-provider-sandbox.md", package_checker)
        self.assertIn("THREE_D_ASSET_DELIVERY_APPROVAL_CARD.md", package_checker)
        self.assertIn("three-d-asset-provider-sandbox.md", doctor)
        self.assertIn("THREE_D_ASSET_DELIVERY_APPROVAL_CARD.md", doctor)


if __name__ == "__main__":
    unittest.main()
