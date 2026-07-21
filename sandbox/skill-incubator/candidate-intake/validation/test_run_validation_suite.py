"""Contract tests for external-only audit evidence records."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("run_validation_suite", HERE / "run_validation_suite.py")
assert SPEC is not None and SPEC.loader is not None
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


class AuditEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.audit_root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_record_is_complete_and_uses_actual_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            audit_root = Path(temporary) / "audit"
            record = suite.run([sys.executable, "-c", "print('ok')"], HERE, "fixture", audit_root, "a" * 40, ["fixture limitation"])
            self.assertEqual("passed", record["status"])
            self.assertEqual([sys.executable, "-c", "print('ok')"], record["command_argv"])
            self.assertNotIn("<", record["command_display"])
            for field in ("test_id", "command_argv", "command_display", "commit", "cwd", "started_at", "ended_at", "duration_ms", "exit_code", "status", "stdout_file", "stderr_file", "limitations"):
                self.assertIn(field, record)
            self.assertTrue(Path(record["stdout_file"]).is_file())
            self.assertTrue(Path(record["stderr_file"]).is_file())

    def test_empty_argv_is_rejected(self) -> None:
        record = self._record(command_argv=[])
        self.assertTrue(any("command_argv" in error for error in suite.validate_record(record)))

    def test_placeholder_display_is_rejected(self) -> None:
        record = self._record(command_display="python3 -c <...>")
        self.assertTrue(any("placeholder" in error for error in suite.validate_record(record)))

    def test_missing_output_file_is_rejected(self) -> None:
        record = self._record(stdout_file="/does/not/exist")
        self.assertTrue(any("stdout_file" in error for error in suite.validate_record(record)))

    def test_exit_status_mismatch_is_rejected(self) -> None:
        record = self._record(status="failed", exit_code=0)
        self.assertTrue(any("failed status" in error for error in suite.validate_record(record)))

    def test_blocked_limitation_cannot_be_passed(self) -> None:
        record = self._record(limitations=["blocked_not_installed"])
        self.assertTrue(any("blocked limitation" in error for error in suite.validate_record(record)))

    @mock.patch.object(suite.importlib.util, "find_spec", return_value=None)
    def test_formal_schema_probe_is_blocked_only_when_engine_is_unavailable(self, _find_spec) -> None:
        record = suite.formal_schema_probe(HERE, self.audit_root, "a" * 40)
        self.assertEqual("blocked_not_installed", record["status"])
        self.assertEqual(0, record["exit_code"])

    @mock.patch.object(suite, "run")
    @mock.patch.object(suite.importlib.util, "find_spec", return_value=object())
    def test_formal_schema_probe_runs_real_validator_when_engine_is_available(self, _find_spec, run) -> None:
        run.return_value = self._record()
        record = suite.formal_schema_probe(HERE, self.audit_root, "a" * 40)
        self.assertEqual("passed", record["status"])
        argv = run.call_args.args[0]
        self.assertIn("validate_formal_schema_instances.py", argv[1])

    def _record(self, **updates):
        stdout = self.audit_root / "stdout.txt"
        stderr = self.audit_root / "stderr.txt"
        stdout.write_text("", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        record = {
            "test_id": "fixture",
            "command_argv": [sys.executable, "-c", "print('ok')"],
            "command_display": "python3 -c \"print('ok')\"",
            "commit": "a" * 40,
            "cwd": str(HERE),
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:00:00Z",
            "duration_ms": 0,
            "exit_code": 0,
            "status": "passed",
            "stdout_file": str(stdout),
            "stderr_file": str(stderr),
            "limitations": [],
        }
        record.update(updates)
        return record


if __name__ == "__main__":
    unittest.main()
