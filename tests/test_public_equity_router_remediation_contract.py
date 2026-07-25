"""Ensure the observed Public Equity router defect remains explicit and unclaimed."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "sandbox"
    / "skill-incubator"
    / "architecture"
    / "investment-decision-gate.json"
)


class PublicEquityRouterRemediationContractTests(unittest.TestCase):
    def test_missing_test_skill_is_recorded_as_unapplied_upstream_remediation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        observation = contract["router_observation"]
        self.assertEqual("public-equity-investing@0.1.31", observation["package"])
        self.assertEqual(
            "test-public-equity-investing-workflows",
            observation["missing_skill_id"],
        )
        self.assertTrue(observation["router_declares_skill"])
        self.assertFalse(observation["skill_directory_present"])
        self.assertEqual(1, observation["observed_occurrence_count"])
        self.assertEqual(
            "read_only_installed_package_inventory",
            observation["verification_method"],
        )
        self.assertEqual(
            "remove_stale_user_visible_route",
            observation["recommended_action"],
        )
        self.assertFalse(observation["remediation_applied"])
        self.assertEqual(
            "package_level_contract_and_regression_tests",
            observation["replacement"],
        )


if __name__ == "__main__":
    unittest.main()
