from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecurityPolicyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    def test_supported_version_policy_is_current_and_bounded(self) -> None:
        self.assertIn("`main` / v0.6.x", self.security)
        self.assertIn("Current supported line", self.security)
        self.assertIn("v0.5.0", self.security)
        self.assertIn("Security-only until 2026-11-02", self.security)
        self.assertIn("v0.4.x and earlier", self.security)
        self.assertIn("Unsupported", self.security)
        self.assertNotIn("v0.4 release line", self.security)
        self.assertNotIn("upgrade to v0.4.0", self.security)

    def test_security_control_snapshot_is_dated_and_non_authorizing(self) -> None:
        normalized = " ".join(self.security.split())
        self.assertIn("Observed at: 2026-08-05.", normalized)
        self.assertIn("CodeQL default setup was `not-configured`", normalized)
        self.assertIn("Secret Scanning", normalized)
        self.assertIn("Push Protection", normalized)
        self.assertIn("passing CI does not establish their current state", normalized)
        self.assertIn("or a release is authorized", normalized)


if __name__ == "__main__":
    unittest.main()
