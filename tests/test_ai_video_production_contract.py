from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / ".agents" / "skills" / "ai-video-production"


class AIVideoProductionContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        path = VIDEO / relative
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_remotion_contract_tracks_reproducible_render_inputs(self) -> None:
        text = self.read("references/remotion-patterns.md")
        self.assert_contains_all(
            text,
            [
                "composition ID",
                "width and height",
                "fps",
                "duration in frames",
                "props file or serialized props",
                "JSON-serializable",
                "schema or validation status",
                "Do not run final render automatically",
                "Important sample frames render correctly",
            ],
        )

    def test_hyperframes_contract_tracks_preview_and_lint_gate(self) -> None:
        text = self.read("references/hyperframes-patterns.md")
        self.assert_contains_all(
            text,
            [
                "`index.html` path",
                "composition ID or stage ID",
                "animation adapter or timeline mechanism",
                "lint or inspect result",
                "preview URL or local preview command",
                "Non-seekable or wall-clock-only animation",
                "final render remains approval-gated",
                "Node, FFmpeg, browser automation, or Docker",
            ],
        )

    def test_imagegen_contract_tracks_provider_output_and_provenance(self) -> None:
        text = self.read("references/imagegen-patterns.md")
        self.assert_contains_all(
            text,
            [
                "Image generation from a prompt",
                "Image edits from existing images or masks",
                "responses-style workflow",
                "size or aspect ratio",
                "quality level",
                "file format",
                "compression",
                "background or transparency needs",
                "Private inputs used",
                "moderation or safety-review status",
            ],
        )

    def test_asset_manifest_template_captures_generation_settings(self) -> None:
        text = self.read("templates/ASSET_MANIFEST_TEMPLATE.md")
        self.assert_contains_all(
            text,
            [
                "## Generation Settings",
                "Generation / Edit Mode",
                "Input Assets",
                "Size / Aspect Ratio",
                "Quality",
                "Output Format",
                "Compression",
                "Background / Alpha",
                "Moderation / Safety Status",
                "Private inputs used: No / Yes",
                "External upload approved: No / Yes / Not applicable",
            ],
        )

    def test_render_handoff_template_captures_tool_specific_gates(self) -> None:
        text = self.read("templates/RENDER_HANDOFF_TEMPLATE.md")
        self.assert_contains_all(
            text,
            [
                "Preview type: Browser / Still frames / Segment preview / Full local preview",
                "Lint or inspect result",
                "Sample frames reviewed",
                "## Remotion-Style Contract",
                "Entry point or serve URL",
                "Props are JSON-serializable",
                "Schema or validation status",
                "## HyperFrames-Style Contract",
                "`index.html` path",
                "Stage or composition ID",
                "Animation adapter or timeline mechanism",
                "Final render approved",
            ],
        )


if __name__ == "__main__":
    unittest.main()
