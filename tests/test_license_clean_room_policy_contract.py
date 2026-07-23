"""Contract checks for the Incubator's third-party adoption boundary."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "sandbox" / "skill-incubator" / "policy" / "license-and-clean-room.md"
README = ROOT / "sandbox" / "skill-incubator" / "README.md"


class LicenseCleanRoomPolicyContractTests(unittest.TestCase):
    def test_policy_preserves_non_import_default(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        normalized = " ".join(policy.split())

        for phrase in (
            "No third-party code, prompts, datasets, assets, or prose may be copied into stable skills.",
            "`methodology_only`",
            "`external_reference_only`",
            "`clean_room_candidate`",
            "Direct third-party code import into a stable skill is `DENY`.",
            "does not make third-party code \"our own code.\"",
            "AGPL candidates, including MiroFish, are clean-room methodology candidates only.",
        ):
            self.assertIn(" ".join(phrase.split()), normalized)

    def test_readme_links_to_the_policy(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("policy/license-and-clean-room.md", readme)
        self.assertIn(
            "does not turn third-party code into repository-owned code",
            " ".join(readme.split()),
        )


if __name__ == "__main__":
    unittest.main()
