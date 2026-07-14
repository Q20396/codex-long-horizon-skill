from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
VIDEO = ROOT / ".agents" / "skills" / "ai-video-production"


class SafeContextRendererProtocolsContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_context_map_protocol_is_bounded_and_read_only(self) -> None:
        protocol = self.read(LHE / "references" / "safe-project-context-map.md")
        template = self.read(LHE / "templates" / "PROJECT_CONTEXT_MAP_TEMPLATE.md")
        skill = self.read(LHE / "SKILL.md")
        self.assert_contains_all(
            protocol,
            [
                "explicit path allowlist",
                "not a graph database",
                "Never include or index `.env` files",
                "stay plan-only and ask before reading it",
                "does not authorize edits, installation, push, merge, deployment, or publication",
            ],
        )
        self.assert_contains_all(
            template,
            [
                "Approved repository-relative paths",
                "Persistent storage approved: No / Yes",
                "Sensitive paths intentionally excluded",
                "Do not include secrets, API keys",
            ],
        )
        self.assertIn("safe-project-context-map.md", skill)

    def test_compute_intake_forbids_discovery_and_runtime_control(self) -> None:
        protocol = self.read(LHE / "references" / "local-compute-capability-intake.md")
        template = self.read(LHE / "templates" / "COMPUTE_CAPABILITY_INTAKE.md")
        self.assert_contains_all(
            protocol,
            [
                "manual requirements intake",
                "discover devices on a local network",
                "start services, download models, join a cluster",
                "requires separate explicit approval",
            ],
        )
        self.assert_contains_all(
            template,
            [
                "Do not discover devices, inspect the network",
                "Proposal status: PROPOSAL_ONLY",
                "Separate approval required",
            ],
        )

    def test_renderer_selection_requires_evidence_and_human_gate(self) -> None:
        protocol = self.read(VIDEO / "references" / "renderer-selection.md")
        template = self.read(VIDEO / "templates" / "RENDER_EVIDENCE_TEMPLATE.md")
        skill = self.read(VIDEO / "SKILL.md")
        self.assert_contains_all(
            protocol,
            [
                "does not install tools, run a renderer, call a provider",
                "deterministic timing and reproducibility",
                "Before a human considers rendering",
                "Final rendering, external upload, publication, and paid provider",
            ],
        )
        self.assert_contains_all(
            template,
            [
                "Final render requested: No",
                "External provider involved: No / Yes, separately approved",
                "Publication requested: No",
                "Explicit final-render approval recorded: No",
            ],
        )
        self.assertIn("renderer-selection.md", skill)
        self.assertIn("RENDER_EVIDENCE_TEMPLATE.md", skill)


if __name__ == "__main__":
    unittest.main()
