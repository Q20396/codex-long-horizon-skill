from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "upgrade-audit-protocol.md"
TEMPLATE = LHE / "templates" / "UPGRADE_AUDIT_REPORT_TEMPLATE.md"


class UpgradeAuditProtocolContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def test_protocol_is_read_only_and_approval_gated(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Audit status: PROPOSAL_ONLY",
                "Repository write approval: NO",
                "Network access approval: NO",
                "Experiment execution: NO",
                "Changes applied: NO",
                "Do not create an audit directory",
                "or commit during Phase A",
                "The audit never applies fixes automatically, including P2 fixes.",
                "A user must explicitly authorize a named finding",
                "It is not a safety bypass and does not authorize execution.",
                "a user may explicitly approve one read-only online comparison.",
                "This approval expires after that comparison",
                "An update requires a separate user decision that names the approved target skills.",
                "Never schedule automatic checks or updates",
                "treat each external request and each state-changing action as a separate opt-in step.",
                "wait for an explicit customer decision for that exact step.",
                "Consent expires after one completed, failed, or cancelled step.",
                "For an update, require at least two separate decisions",
                "must not automatically",
                "rebase, force-push, push, merge, publish, tag, or release",
            ],
        )

    def test_protocol_preserves_privacy_and_evidence_boundaries(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "Do not read files from another worktree merely because it is registered.",
                "Do not scan home directories, cloud storage, mailboxes, browsers, credentials",
                "Do not store raw diffs, reflog output, command transcripts",
                "Network or GitHub review requires separate explicit approval.",
                "Distinguish implementation evidence from tests actually run",
            ],
        )

    def test_template_and_package_entrypoints_include_the_protocol(self) -> None:
        template = self.read(TEMPLATE)
        checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")
        index = self.read(LHE / "references" / "explicit-only-extensions.md")
        readme = self.read(ROOT / "README.md")
        self.assert_contains_all(
            template,
            [
                "Audit status: PROPOSAL_ONLY",
                "Repository write approval: NO",
                "Network access approval: NO",
                "Experiment execution: NO",
                "Changes applied: NO",
                "Activation status: LOCKED",
                "Experimental online comparison authorization expires after this run: YES",
                "## Stepwise Consent Log",
                "A read-only comparison and a named replacement require separate rows",
            ],
        )
        for text in (checker, doctor, index):
            self.assertIn("upgrade-audit-protocol.md", text)
        for text in (checker, doctor):
            self.assertIn("UPGRADE_AUDIT_REPORT_TEMPLATE.md", text)
        self.assert_contains_all(
            readme,
            [
                "## Time-Bounded Upgrade Audits",
                "starts read-only",
                "Any network check, durable report, repair, or quarantined experiment needs a separate user decision.",
                "never grants execution, installation, network, push, merge, or release permission.",
                "every network request and every update action must show its scope",
            ],
        )

    def test_trigger_fixtures_keep_audit_explicit_and_non_mutating(self) -> None:
        payload = json.loads((ROOT / "tests" / "expected-triggers.json").read_text())
        fixtures = {item["id"]: item for item in payload["cases"]}
        self.assertEqual(
            fixtures["explicit-lhe-time-bounded-upgrade-audit"]["expected_skill"],
            "long-horizon-engineering",
        )
        self.assertEqual(
            fixtures["none-implicit-auto-upgrade-audit-repair"]["expected_skill"],
            "none",
        )


if __name__ == "__main__":
    unittest.main()
