from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = (
    ROOT
    / ".agents/skills/long-horizon-engineering/scripts/doctor.py"
)


def load_doctor_module():
    spec = importlib.util.spec_from_file_location("lhe_doctor", DOCTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DoctorCapabilityReportTests(unittest.TestCase):
    def test_lhe_required_inventory_is_derived_from_legacy_full_manifest(self) -> None:
        module = load_doctor_module()
        manifest = json.loads(module.PACKAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
        expected = []
        for component in manifest["profiles"]["legacy-full"]["components"]:
            expected.extend(manifest["components"][component]["paths"])
        self.assertEqual(expected, module.LHE_INSTALLED_REQUIRED_PATHS)

    def test_local_governance_profile_is_static_and_fail_closed(self) -> None:
        module = load_doctor_module()
        report, errors = module.capability_health_report(
            "local-governance-core"
        )
        self.assertEqual(errors, [])
        self.assertEqual(report["mode"], "static-read-only")
        self.assertEqual(report["active_profile"], "local-governance-core")
        self.assertFalse(report["profile_activation_verified"])
        self.assertFalse(report["capability_catalog"]["host_routing_verified"])
        self.assertEqual(len(report["capability_catalog"]["cards"]), 3)
        for card in report["capability_catalog"]["cards"]:
            self.assertEqual(card["status"], "descriptor-only")
            self.assertFalse(card["installed"])
            self.assertFalse(card["callable"])
            self.assertFalse(card["executable"])
        self.assertTrue(
            all(value is False for value in report["permission_effects"].values())
        )
        self.assertFalse(
            report["data_locality"]["customer_sensitive_data_upload"]
        )
        self.assertFalse(report["data_locality"]["model_memory"])
        self.assertFalse(report["data_locality"]["telemetry"])
        [provider] = report["declared_providers"]
        self.assertEqual(provider["status"], "declared-disabled")
        self.assertTrue(provider["interface_only"])
        self.assertFalse(provider["runtime_present"])
        self.assertFalse(provider["connector_implementations_present"])
        self.assertEqual(provider["synthetic_pilot_status"], "fixture-only")
        for field in (
            "network_access",
            "account_access",
            "credential_access",
            "persistence_authority",
            "customer_sensitive_data_upload",
            "model_memory",
            "telemetry",
        ):
            self.assertFalse(provider[field], field)

    def test_unknown_profile_fails_closed(self) -> None:
        module = load_doctor_module()
        _, errors = module.capability_health_report("unknown-profile")
        self.assertTrue(
            any("must name a declared package profile" in error for error in errors),
            errors,
        )

    def test_required_provider_rejects_non_string_non_null_values(self) -> None:
        module = load_doctor_module()
        catalog = json.loads(
            module.CAPABILITY_CATALOG_PATH.read_text(encoding="utf-8")
        )
        for value in ([], {}, 7, False):
            with self.subTest(value=value):
                mutated = json.loads(json.dumps(catalog))
                mutated["capabilities"][0]["required_provider"] = value
                with mock.patch.object(
                    module,
                    "load_object",
                    side_effect=lambda path, label: (
                        (mutated, [])
                        if path == module.CAPABILITY_CATALOG_PATH
                        else (
                            json.loads(path.read_text(encoding="utf-8")),
                            [],
                        )
                    ),
                ):
                    _, errors = module.capability_health_report(
                        "local-governance-core"
                    )
                self.assertTrue(
                    any(
                        "required_provider must be a string or null" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_cli_json_is_read_only_and_reports_static_limitations(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--json",
                "--profile",
                "local-governance-core",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        report = payload["capability_report"]
        self.assertIn(
            "It does not inspect user config",
            " ".join(report["limitations"]),
        )
        [provider] = report["declared_providers"]
        self.assertEqual(
            provider["provider_id"],
            "local-case-evidence-provider",
        )
        self.assertEqual(provider["synthetic_pilot_status"], "fixture-only")
        self.assertFalse(provider["runtime_present"])
        self.assertIsNone(provider["expires_at"])


if __name__ == "__main__":
    unittest.main()
