"""Contract tests for the explicit-only local voice tool sandbox."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "local-voice-tool-sandbox.md"
TEMPLATE = LHE / "templates" / "LOCAL_VOICE_TOOL_APPROVAL_CARD.md"


class LocalVoiceToolSandboxContractTests(unittest.TestCase):
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
                "does not install, update, download, start, configure, connect",
                "It does not create an MCP configuration",
            ],
        )

    def test_reference_requires_granular_approval_and_sensitive_audio_controls(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "One approval never covers another.",
                "Model download",
                "MCP connection",
                "Voice identity",
                "microphone or system-audio capture",
                "reading arbitrary `audio_path` values",
                "voice cloning, reference-audio enrollment, impersonation",
                "personality model before speech",
                "non-loopback bindings",
                "cloud login, synchronization, backup, telemetry",
                "Never assume that a tool is private merely because it is described as local.",
            ],
        )

    def test_template_defaults_to_no_voice_or_external_permission(self) -> None:
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "Invocation: EXPLICIT_ONLY",
                "Proposal status: PROPOSAL_ONLY",
                "User approval: PENDING",
                "Permission granted: NONE",
                "External tool invoked: NO",
                "Audio-path access: NO",
                "Capture or transcript-history access: NO",
                "Personality rewrite: NO",
                "Cloud sync, backup, telemetry, or account use: NO",
                "Speaker consent for a cloned or reference voice",
                "Separate Approval Gates",
            ],
        )

    def test_entrypoints_and_package_check_include_the_protocol(self) -> None:
        skill = self.read(LHE / "SKILL.md")
        index = self.read(LHE / "references" / "explicit-only-extensions.md")
        readme = self.read(ROOT / "README.md")
        package_checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")

        self.assertIn("local-voice-tool-sandbox.md", skill)
        self.assertIn("local-voice-tool-sandbox.md", index)
        self.assert_contains_all(
            readme,
            [
                "Optional Local Voice Tool Sandbox",
                "does not install, configure, start, or connect any voice tool",
                "separate approval gates",
            ],
        )
        self.assertIn("local-voice-tool-sandbox.md", package_checker)
        self.assertIn("LOCAL_VOICE_TOOL_APPROVAL_CARD.md", package_checker)
        self.assertIn("local-voice-tool-sandbox.md", doctor)
        self.assertIn("LOCAL_VOICE_TOOL_APPROVAL_CARD.md", doctor)


if __name__ == "__main__":
    unittest.main()
