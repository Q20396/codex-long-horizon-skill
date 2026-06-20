from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "ai-video-production"
REFERENCE = SKILL / "references" / "text-to-visual-analysis.md"
TEMPLATE = SKILL / "templates" / "TEXT_TO_VISUAL_ANALYSIS_TEMPLATE.md"
FIXTURE = ROOT / "tests" / "expected-triggers.json"


class TextToVisualAnalysisContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_complete_text_analysis_precedes_visual_planning(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Read the complete supplied text before proposing visuals",
                "source meaning that must be preserved",
                "learning objective",
                "unsupported facts that must not be invented",
                "Do not generate prompts from isolated sentences",
            ],
        )

    def test_cognitive_anchors_and_selective_visualization_are_required(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Extract Cognitive Anchors",
                "core thesis",
                "process step",
                "system layer",
                "Use a small set of high-value anchors",
                "Do not visualize every paragraph by default",
                "Recommend text-only treatment",
            ],
        )

    def test_output_types_are_distinguished(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "diagrams for structure, process, systems, timelines, and relationships",
                "explanatory graphics for memorable concepts",
                "storyboard sequences for timed video beats",
                "image-prompt concepts for generated stills or seed frames",
                "text-only sections that should remain prose or narration",
                "Do not blur these categories",
            ],
        )

    def test_proposal_only_defaults_are_present(self) -> None:
        combined = self.read(REFERENCE) + "\n" + self.read(TEMPLATE)
        self.assert_contains_all(
            combined,
            [
                "Analysis status: PROPOSAL_ONLY",
                "User decision: PENDING",
                "Media generated: NO",
                "Media uploaded: NO",
                "Media published: NO",
                "External provider invoked: NO",
                "Credits or quota consumed: NO",
            ],
        )

    def test_sensitive_external_transfer_requires_explicit_approval(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "send sensitive material to an external provider",
                "separate explicit user approval",
                "privacy review",
                "cost or quota awareness",
                "Do not access private documents",
                "explicitly supplies or approves them",
            ],
        )

    def test_no_generation_upload_or_publication_runtime_is_added(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "must not generate images or video",
                "call an image or video model",
                "upload media",
                "publish media",
                "spend credits",
                "Stop at the analysis plan",
            ],
        )

    def test_template_contains_required_sections(self) -> None:
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "## 1. Analysis Status",
                "## 2. Source Scope",
                "## 3. Audience",
                "## 4. Learning Objective",
                "## 5. Full-Text Summary",
                "## 6. Cognitive Anchors",
                "## 7. Concept Relationships",
                "## 8. Visualization Candidates",
                "## 9. Text-Only Recommendations",
                "## 10. Diagram Concepts",
                "## 11. Explanatory Graphic Concepts",
                "## 12. Storyboard Concepts",
                "## 13. Image Prompt Concepts",
                "## 14. Visual Priority",
                "## 15. Visual Rationale",
                "## 16. Accuracy Constraints",
                "## 17. Privacy and Sensitive-Content Review",
                "## 18. Provider or Tool Requirements",
                "## 19. Estimated Generation Cost or Quota Impact",
                "## 20. User Decision",
                "## 21. Media Generated",
                "## 22. Media Uploaded or Published",
            ],
        )

    def test_skill_and_checker_reference_new_files(self) -> None:
        skill = self.read(SKILL / "SKILL.md")
        checker = self.read(
            ROOT
            / ".agents"
            / "skills"
            / "long-horizon-engineering"
            / "scripts"
            / "check_skill_package.py"
        )
        self.assert_contains_all(
            skill,
            [
                "references/text-to-visual-analysis.md",
                "templates/TEXT_TO_VISUAL_ANALYSIS_TEMPLATE.md",
            ],
        )
        self.assert_contains_all(
            checker,
            [
                ".agents/skills/ai-video-production/references/text-to-visual-analysis.md",
                ".agents/skills/ai-video-production/templates/TEXT_TO_VISUAL_ANALYSIS_TEMPLATE.md",
            ],
        )

    def test_expected_trigger_additions_cover_visual_explanation_contract(self) -> None:
        payload = json.loads(self.read(FIXTURE))
        cases = {case["id"]: case for case in payload["cases"]}
        self.assertEqual(
            cases["video-implicit-text-to-visual-analysis"]["expected_skill"],
            "ai-video-production",
        )
        self.assertEqual(
            cases["none-implicit-auto-sensitive-visual-generation"]["expected_skill"],
            "none",
        )
        self.assertEqual(
            cases["none-implicit-auto-sensitive-visual-generation"][
                "invocation_mode"
            ],
            "implicit",
        )


if __name__ == "__main__":
    unittest.main()
