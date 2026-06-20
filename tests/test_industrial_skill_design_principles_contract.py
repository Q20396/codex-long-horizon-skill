from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "industrial-skill-design-principles.md"


class IndustrialSkillDesignPrinciplesContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            normalized_phrase = " ".join(phrase.split())
            self.assertIn(normalized_phrase, normalized_text)

    def test_core_principles_are_documented(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Clear Trigger Boundary",
                "Minimal Tool Boundary",
                "Progressive Disclosure",
                "Match Workflow Depth To Task",
                "Test The Skill Contract",
                "Close The Evaluation Loop",
                "Router, Not Worker",
                "Invocation Permission Layers",
                "Shared Design Vocabulary",
                "trigger correctly",
                "controlled permissions",
                "verifiable results",
                "Borrow architecture ideas, not external implementation",
                "user problem before tool selection",
                "goals and non-goals",
                "narrow enough",
                "Definition of Done",
            ],
        )

    def test_progressive_disclosure_and_tool_boundaries_are_explicit(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Keep `SKILL.md` concise",
                "`references/` for long protocols",
                "`templates/` for reusable review",
                "`scripts/` for stable helper commands",
                "`assets/` for reusable static assets",
                "read-only exploration before mutation",
                "network access only after user approval",
                "human approval before install, update, render, publish, deploy, push, merge, or release",
                "minimum tools and permissions",
                "expensive, destructive, privacy-sensitive",
                "credential-bearing",
                "production-facing",
                "experimental",
                "broadly autonomous",
                "does not bypass approval",
                "separation of policy and executable behavior",
            ],
        )

    def test_validation_and_evaluation_loop_are_safety_preserving(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "positive prompts trigger the intended skill",
                "negative prompts do not trigger the skill",
                "Static trigger fixtures are a regression proxy",
                "do not prove live model routing",
                "deterministic contract tests",
                "package validation",
                "trigger failure",
                "permission-boundary failure",
                "privacy or safety failure",
                "output-quality failure",
                "false-positive analysis",
                "false-negative analysis",
                "Do not weaken safety, privacy, approval, or validation rules",
            ],
        )

    def test_controlled_evolution_boundaries_are_preserved(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Default mutation action: DENY",
                "Default exact-path write allowlist: EMPTY",
                "Exact-path approval required",
                "Mixed-trust directory wildcards forbidden",
                "Proposal is not write permission",
                "Write permission is not approval",
                "Approval is not promotion",
                "Do not describe `SKILL.md`, `references/**`, `templates/**`, or `scripts/**` as freely candidate-mutable",
                "GitHub Stars, popularity, and novelty are not evidence of safety",
                "evidence before capability expansion",
                "privacy by default",
                "compatibility and rollback",
            ],
        )

    def test_router_permission_layers_and_shared_vocabulary_are_safe(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "A router skill helps the user decide which existing skill",
                "style fits the task",
                "It should not perform the downstream work by itself",
                "install external skills",
                "invoke newly installed external skills automatically",
                "proposal-only until the user approves review, download, install, and use",
                "Human-invoked",
                "Model-selected",
                "Review-only",
                "Install-approved",
                "Use-approved",
                "High-impact-approved",
                "trigger boundary",
                "explicit-only extension",
                "approval gate",
                "route catalog",
                "exact reviewed commit",
                "Shared vocabulary should describe non-sensitive workflow concepts only",
                "Do not use it to store client facts",
            ],
        )

    def test_readme_and_index_reference_principles(self) -> None:
        readme = self.read(ROOT / "README.md")
        index = self.read(LHE / "references" / "explicit-only-extensions.md")
        self.assert_contains_all(
            readme,
            [
                "Industrial Skill Design Principles",
                "trigger accurately",
                "least privilege",
                "progressive disclosure",
                "router patterns",
                "invocation permission layers",
                "shared design vocabulary",
                "evaluation loop",
            ],
        )
        self.assert_contains_all(
            index,
            [
                "industrial-skill-design-principles.md",
                "trigger boundaries",
                "progressive disclosure",
            ],
        )


if __name__ == "__main__":
    unittest.main()
