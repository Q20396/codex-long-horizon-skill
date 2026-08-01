from __future__ import annotations

import importlib.util
import json
from datetime import timedelta
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_formal_schemas.py"
WORKFLOW = ROOT / ".github" / "workflows" / "check-skill.yml"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "validate_formal_schemas_under_test", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module()


def synthetic_pip_report() -> dict:
    return {
        "version": "1",
        "install": [
            {
                "download_info": {
                    "url": f"https://files.pythonhosted.org/packages/{item.wheel}",
                    "archive_info": {"hashes": {"sha256": item.sha256}},
                },
                "metadata": {"name": item.name, "version": item.version},
            }
            for item in VALIDATOR.DISTRIBUTIONS
        ],
    }


JOB_IDENTITY = {
    "run_id": "12345",
    "run_attempt": "1",
    "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/pull/86/merge",
    "job_name": "formal-schema-gate",
}
CANDIDATE_BASE = "a" * 40


def synthetic_candidate() -> dict:
    return {
        "binding_version": 1,
        "commit": "1" * 40,
        "tree": "2" * 40,
        "base_commit": CANDIDATE_BASE,
        "merge_base": CANDIDATE_BASE,
        "parents": ["9" * 40],
        "changed_paths": ["candidate.txt"],
        "changed_paths_sha256": VALIDATOR.sha256_bytes(
            VALIDATOR.canonical_json_bytes(["candidate.txt"])
        ),
        "diff_sha256": "3" * 64,
        "worktree_clean": True,
    }


def synthetic_packages() -> list[dict[str, str]]:
    return [
        {
            "name": item.name,
            "version": item.version,
            "wheel": item.wheel,
            "sha256": item.sha256,
        }
        for item in VALIDATOR.DISTRIBUTIONS
    ]


def write_synthetic_evidence(
    root: Path,
    report: Path,
) -> tuple[Path, Path, dict]:
    evidence_dir = root / "evidence"
    evidence_dir.mkdir()
    manifest = {"schema_version": 1, "entries": [], "source_hosts": []}
    manifest_path = evidence_dir / "manifest.json"
    manifest_path.write_bytes(VALIDATOR.canonical_json_bytes(manifest) + b"\n")
    now = VALIDATOR.utc_now()
    receipt = {
        "schema_version": 2,
        "status": "PASS",
        "gate": "formal-acquisition",
        "acquisition_started_at": VALIDATOR.iso_utc(now - timedelta(seconds=1)),
        "acquired_at": VALIDATOR.iso_utc(now),
        "job_identity": dict(JOB_IDENTITY),
        "bootstrap_identity": {
            "commit": VALIDATOR.BOOTSTRAP_COMMIT,
            "tree": VALIDATOR.BOOTSTRAP_TREE,
            "parent": VALIDATOR.BOOTSTRAP_PARENT,
            "remediation_baseline_reference": (
                VALIDATOR.REMEDIATION_BASELINE_REFERENCE
            ),
            "paths": sorted(VALIDATOR.BOOTSTRAP_PATHS),
            "authority": "provenance-only",
        },
        "candidate": synthetic_candidate(),
        "schema_inventory": VALIDATOR.schema_inventory_binding(
            VALIDATOR.validate_schema_inventory()[1]
        ),
        "validator_sha256": VALIDATOR.sha256_file(SCRIPT_PATH),
        "lock_sha256": VALIDATOR.sha256_file(VALIDATOR.LOCK_PATH),
        "pip_report_sha256": VALIDATOR.sha256_file(report),
        "raw_evidence_manifest": "manifest.json",
        "raw_evidence_manifest_sha256": VALIDATOR.sha256_file(manifest_path),
        "raw_evidence_count": 0,
        "source_hosts": [],
        "artifacts": VALIDATOR.artifact_identity(),
        "packages": synthetic_packages(),
        "limitations": [
            "Job-local evidence is not a cryptographic signature.",
            "PyPI publish attestations do not prove source-to-wheel provenance.",
            "Bootstrap identity records gate provenance only and grants no authority.",
        ],
        "approval_authority": "none",
        "next_stage_authorized": False,
    }
    receipt_path = evidence_dir / "acquisition-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence_dir, receipt_path, receipt


class FormalSchemaStaticTests(unittest.TestCase):
    def test_lock_is_exact_and_dependency_free_to_check(self) -> None:
        self.assertEqual([], VALIDATOR.validate_lock())

    def test_schema_inventory_is_closed_and_draft_2020_12(self) -> None:
        errors, schemas = VALIDATOR.validate_schema_inventory()
        self.assertEqual([], errors)
        self.assertEqual(set(VALIDATOR.SCHEMA_INVENTORY), set(schemas))
        self.assertEqual(
            {VALIDATOR.DRAFT_2020_12},
            {schema["$schema"] for schema in schemas.values()},
        )
        self.assertEqual(
            set(VALIDATOR.SCHEMA_INVENTORY),
            VALIDATOR.FIXTURE_VALIDATED_SCHEMAS
            | set(VALIDATOR.SYNTAX_ONLY_SCHEMAS),
        )
        self.assertFalse(
            VALIDATOR.FIXTURE_VALIDATED_SCHEMAS
            & set(VALIDATOR.SYNTAX_ONLY_SCHEMAS)
        )
        self.assertIn(
            "dependency-free fixtures",
            VALIDATOR.SYNTAX_ONLY_SCHEMAS[
                "capability-profile-doctor.schema.json"
            ],
        )

    def test_authority_schemas_have_positive_and_negative_formal_fixtures(self) -> None:
        expected = {
            "decision-record.schema.json",
            "gate-result.schema.json",
            "promotion.schema.json",
        }
        positives, negatives = VALIDATOR.materialized_fixture_cases()
        positive_schemas = {schema for schema, _, _ in positives}
        negative_schemas = {schema for schema, _, _, _ in negatives}

        self.assertTrue(expected <= VALIDATOR.FIXTURE_VALIDATED_SCHEMAS)
        self.assertTrue(expected <= positive_schemas)
        self.assertTrue(expected <= negative_schemas)
        self.assertEqual([], VALIDATOR.validate_fixture_coverage(positives, negatives))
        for schema in expected:
            self.assertGreaterEqual(
                sum(1 for item in negatives if item[0] == schema),
                3,
            )

    def test_schema_inventory_rejects_missing_local_fragment(self) -> None:
        original = VALIDATOR.load_json

        def broken(path: Path):
            payload = original(path)
            if path.name == "evidence-bound-multi-perspective-research.schema.json":
                payload = json.loads(json.dumps(payload))
                payload["properties"]["record_id"]["$ref"] = "#/$defs/missing"
            return payload

        with mock.patch.object(VALIDATOR, "load_json", side_effect=broken):
            errors, _ = VALIDATOR.validate_schema_inventory()
        self.assertTrue(any("unresolved $ref" in error for error in errors), errors)

    def test_schema_inventory_rejects_non_string_ref(self) -> None:
        original = VALIDATOR.load_json

        def broken(path: Path):
            payload = original(path)
            if path.name == "evidence-bound-multi-perspective-research.schema.json":
                payload = json.loads(json.dumps(payload))
                payload["properties"]["record_id"]["$ref"] = 7
            return payload

        with mock.patch.object(VALIDATOR, "load_json", side_effect=broken):
            errors, _ = VALIDATOR.validate_schema_inventory()
        self.assertTrue(
            any("$ref must be a non-empty string" in error for error in errors),
            errors,
        )

    def test_formal_gate_requires_clean_worktree(self) -> None:
        with mock.patch.object(VALIDATOR, "git_value", return_value=""):
            self.assertEqual([], VALIDATOR.validate_clean_worktree())
        for status in (
            " M scripts/validate_formal_schemas.py",
            "M  scripts/validate_formal_schemas.py",
            "?? tests/untracked-formal-probe.py",
        ):
            with self.subTest(status=status):
                with mock.patch.object(VALIDATOR, "git_value", return_value=status):
                    errors = VALIDATOR.validate_clean_worktree()
                self.assertTrue(
                    any("clean candidate worktree" in error for error in errors)
                )

    def test_bootstrap_identity_is_provenance_only_and_exact(self) -> None:
        errors, identity = VALIDATOR.bootstrap_identity()
        self.assertEqual([], errors)
        self.assertEqual(VALIDATOR.BOOTSTRAP_COMMIT, identity["commit"])
        self.assertEqual(VALIDATOR.BOOTSTRAP_TREE, identity["tree"])
        self.assertEqual(VALIDATOR.BOOTSTRAP_PARENT, identity["parent"])
        self.assertEqual("provenance-only", identity["authority"])
        self.assertEqual(sorted(VALIDATOR.BOOTSTRAP_PATHS), identity["paths"])

    def test_candidate_binding_uses_current_base_merge_base_paths_and_diff(self) -> None:
        values = {
            ("rev-parse", f"{CANDIDATE_BASE}^{{commit}}"): CANDIDATE_BASE,
            ("rev-parse", "HEAD"): "1" * 40,
            ("show", "-s", "--format=%T", "HEAD"): "2" * 40,
            ("show", "-s", "--format=%P", "HEAD"): "9" * 40,
            ("merge-base", CANDIDATE_BASE, "1" * 40): CANDIDATE_BASE,
            ("diff", "--name-only", f"{CANDIDATE_BASE}..{'1' * 40}"): (
                "tests/new-contract.py\nsandbox/new-contract.json"
            ),
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }
        diff = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout=b"canonical remediation diff",
            stderr=b"",
        )
        with (
            mock.patch.object(
                VALIDATOR,
                "git_value",
                side_effect=lambda *args: values[args],
            ),
            mock.patch.object(VALIDATOR.subprocess, "run", return_value=diff),
        ):
            errors, binding = VALIDATOR.candidate_binding(CANDIDATE_BASE)
        self.assertEqual([], errors)
        self.assertEqual(
            ["sandbox/new-contract.json", "tests/new-contract.py"],
            binding["changed_paths"],
        )
        self.assertEqual(CANDIDATE_BASE, binding["base_commit"])
        self.assertEqual(CANDIDATE_BASE, binding["merge_base"])
        self.assertTrue(binding["worktree_clean"])
        self.assertEqual(
            VALIDATOR.sha256_bytes(diff.stdout),
            binding["diff_sha256"],
        )

        values[("merge-base", CANDIDATE_BASE, "1" * 40)] = "8" * 40
        with (
            mock.patch.object(
                VALIDATOR,
                "git_value",
                side_effect=lambda *args: values[args],
            ),
            mock.patch.object(VALIDATOR.subprocess, "run", return_value=diff),
        ):
            errors, _ = VALIDATOR.candidate_binding(CANDIDATE_BASE)
        self.assertTrue(any("merge-base" in error for error in errors))

    def test_candidate_binding_rejects_missing_zero_or_dirty_identity(self) -> None:
        for base in ("", "main", "0" * 40):
            with self.subTest(base=base):
                errors, _ = VALIDATOR.candidate_binding(base)
                self.assertTrue(any("nonzero full commit SHA" in error for error in errors))

    def test_fixture_coverage_rejects_unmapped_schema(self) -> None:
        positives, negatives = VALIDATOR.materialized_fixture_cases()
        missing = next(iter(VALIDATOR.FIXTURE_VALIDATED_SCHEMAS))
        positives = [case for case in positives if case[0] != missing]
        errors = VALIDATOR.validate_fixture_coverage(positives, negatives)
        self.assertTrue(any(missing in error for error in errors), errors)

    def test_acquisition_inventory_is_complete_and_matrix_specific(self) -> None:
        self.assertEqual(6, len(VALIDATOR.DISTRIBUTIONS))
        for item in VALIDATOR.DISTRIBUTIONS:
            self.assertRegex(item.sha256, r"^[0-9a-f]{64}$")
            self.assertRegex(item.source_commit, r"^[0-9a-f]{40}$")
            self.assertRegex(item.license_blob, r"^[0-9a-f]{40}$")
            self.assertTrue(item.publisher_repository)
            self.assertTrue(item.publisher_workflow)
            self.assertTrue(item.publisher_environment)
        native = next(
            item for item in VALIDATOR.DISTRIBUTIONS if item.name == "rpds-py"
        )
        self.assertIn("cp311-cp311", native.wheel)
        self.assertIn("manylinux_2_17_x86_64", native.wheel)
        for item in VALIDATOR.DISTRIBUTIONS:
            if item.name != "rpds-py":
                self.assertTrue(item.wheel.endswith("-py3-none-any.whl"))

    def test_pip_report_requires_exact_six_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
            path = Path(temp) / "report.json"
            path.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            errors, artifacts = VALIDATOR.validate_pip_report(path)
        self.assertEqual([], errors)
        self.assertEqual(6, len(artifacts))

    def test_pip_report_rejects_seventh_package(self) -> None:
        report = synthetic_pip_report()
        report["install"].append(
            {
                "download_info": {
                    "url": "https://files.pythonhosted.org/packages/seventh-1.0-py3-none-any.whl",
                    "archive_info": {"hashes": {"sha256": "0" * 64}},
                },
                "metadata": {"name": "seventh", "version": "1.0"},
            }
        )
        with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
            path = Path(temp) / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            errors, _ = VALIDATOR.validate_pip_report(path)
        self.assertTrue(any("closure mismatch" in error for error in errors))

    def test_pip_report_rejects_wrong_wheel_or_hash(self) -> None:
        report = synthetic_pip_report()
        report["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
            path = Path(temp) / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            errors, _ = VALIDATOR.validate_pip_report(path)
        self.assertTrue(any("artifact mismatch" in error for error in errors))

    def test_pip_report_rejects_nonofficial_or_local_sources(self) -> None:
        for url in (
            "https://attacker.example/jsonschema-4.26.0-py3-none-any.whl",
            "file:///private/tmp/jsonschema-4.26.0-py3-none-any.whl",
        ):
            with self.subTest(url=url):
                report = synthetic_pip_report()
                report["install"][0]["download_info"]["url"] = url
                with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
                    path = Path(temp) / "report.json"
                    path.write_text(json.dumps(report), encoding="utf-8")
                    errors, _ = VALIDATOR.validate_pip_report(path)
                self.assertTrue(
                    any("approved PyPI HTTPS host" in error for error in errors),
                    errors,
                )
        report = synthetic_pip_report()
        report["install"][0]["is_direct"] = True
        with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
            path = Path(temp) / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            errors, _ = VALIDATOR.validate_pip_report(path)
        self.assertTrue(
            any("approved PyPI HTTPS host" in error for error in errors), errors
        )
        for url, expected_valid in (
            (
                "https://files.pythonhosted.org:443/packages/"
                "jsonschema-4.26.0-py3-none-any.whl",
                True,
            ),
            (
                "https://files.pythonhosted.org:444/packages/"
                "jsonschema-4.26.0-py3-none-any.whl",
                False,
            ),
            (
                "https://files.pythonhosted.org:not-a-port/packages/"
                "jsonschema-4.26.0-py3-none-any.whl",
                False,
            ),
        ):
            with self.subTest(url=url):
                report = synthetic_pip_report()
                report["install"][0]["download_info"]["url"] = url
                with tempfile.TemporaryDirectory(prefix="formal-pip-report-") as temp:
                    path = Path(temp) / "report.json"
                    path.write_text(json.dumps(report), encoding="utf-8")
                    errors, _ = VALIDATOR.validate_pip_report(path)
                self.assertEqual(expected_valid, not errors, errors)

    def validate_synthetic_receipt(
        self,
        receipt_mutator=None,
        manifest_mutator=None,
    ) -> tuple[list[str], dict, str]:
        with tempfile.TemporaryDirectory(prefix="formal-acquisition-") as temp:
            root = Path(temp)
            report = root / "pip-report.json"
            report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            evidence_dir, receipt_path, receipt = write_synthetic_evidence(
                root, report
            )
            manifest_path = evidence_dir / "manifest.json"
            if manifest_mutator is not None:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_mutator(manifest)
                manifest_path.write_bytes(
                    VALIDATOR.canonical_json_bytes(manifest) + b"\n"
                )
                receipt["raw_evidence_manifest_sha256"] = VALIDATOR.sha256_file(
                    manifest_path
                )
            if receipt_mutator is not None:
                receipt_mutator(receipt)
            receipt_path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    VALIDATOR, "candidate_binding", return_value=([], synthetic_candidate())
                ),
                mock.patch.object(
                    VALIDATOR,
                    "verify_acquisition",
                    return_value=([], {"packages": synthetic_packages()}),
                ),
                mock.patch.object(
                    VALIDATOR,
                    "urlopen",
                    side_effect=AssertionError("offline replay attempted network"),
                ),
            ):
                return VALIDATOR.validate_acquisition_receipt(
                    receipt_path,
                    evidence_dir,
                    report,
                    JOB_IDENTITY,
                    CANDIDATE_BASE,
                )

    def test_acquisition_receipt_is_offline_replayed_and_bound(self) -> None:
        errors, _, receipt_hash = self.validate_synthetic_receipt()
        self.assertEqual([], errors)
        self.assertRegex(receipt_hash, r"^[0-9a-f]{64}$")

        errors, _, _ = self.validate_synthetic_receipt(
            lambda receipt: receipt["packages"][0].update({"sha256": "0" * 64})
        )
        self.assertTrue(
            any("packages do not match raw evidence" in error for error in errors),
            errors,
        )

    def test_acquisition_receipt_rejects_replay_and_artifact_tampering(self) -> None:
        cases = (
            (
                "foreign-job",
                lambda receipt: receipt["job_identity"].update({"run_id": "999"}),
                "job identity mismatch",
            ),
            (
                "foreign-candidate",
                lambda receipt: receipt["candidate"].update({"commit": "9" * 40}),
                "candidate identity mismatch",
            ),
            (
                "foreign-base",
                lambda receipt: receipt["candidate"].update({"base_commit": "8" * 40}),
                "candidate identity mismatch",
            ),
            (
                "foreign-tree",
                lambda receipt: receipt["candidate"].update({"tree": "8" * 40}),
                "candidate identity mismatch",
            ),
            (
                "foreign-diff",
                lambda receipt: receipt["candidate"].update(
                    {"diff_sha256": "8" * 64}
                ),
                "candidate identity mismatch",
            ),
            (
                "foreign-paths",
                lambda receipt: receipt["candidate"].update(
                    {"changed_paths": ["old-phase-b-path"]}
                ),
                "candidate identity mismatch",
            ),
            (
                "foreign-schema-inventory",
                lambda receipt: receipt["schema_inventory"].update(
                    {"inventory_sha256": "8" * 64}
                ),
                "schema inventory mismatch",
            ),
            (
                "bootstrap-as-authority",
                lambda receipt: receipt.update({"approval_authority": "bootstrap"}),
                "must not grant approval",
            ),
            (
                "next-stage",
                lambda receipt: receipt.update({"next_stage_authorized": True}),
                "must not grant approval",
            ),
            (
                "false-status",
                lambda receipt: receipt.update({"status": "FAIL"}),
                "valid PASS evidence",
            ),
            (
                "extra-artifact",
                lambda receipt: receipt["artifacts"].append(
                    {
                        "name": "seventh",
                        "version": "1.0",
                        "wheel": "seventh.whl",
                        "sha256": "0" * 64,
                    }
                ),
                "six locked artifacts",
            ),
            (
                "stale",
                lambda receipt: receipt.update(
                    {
                        "acquisition_started_at": VALIDATOR.iso_utc(
                            VALIDATOR.utc_now() - timedelta(hours=2, seconds=1)
                        ),
                        "acquired_at": VALIDATOR.iso_utc(
                            VALIDATOR.utc_now() - timedelta(hours=2)
                        ),
                    }
                ),
                "receipt is stale",
            ),
        )
        for name, mutator, expected in cases:
            with self.subTest(name=name):
                errors, _, _ = self.validate_synthetic_receipt(mutator)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_old_phase_b_receipt_cannot_authorize_descendant(self) -> None:
        def old_binding(receipt: dict) -> None:
            receipt["candidate"] = {
                "binding_version": 1,
                "commit": VALIDATOR.BOOTSTRAP_COMMIT,
                "tree": VALIDATOR.BOOTSTRAP_TREE,
                "base_commit": VALIDATOR.BOOTSTRAP_PARENT,
                "merge_base": VALIDATOR.BOOTSTRAP_PARENT,
                "parents": [VALIDATOR.BOOTSTRAP_PARENT],
                "changed_paths": sorted(VALIDATOR.BOOTSTRAP_PATHS),
                "changed_paths_sha256": "4" * 64,
                "diff_sha256": "5" * 64,
                "worktree_clean": True,
            }

        errors, _, _ = self.validate_synthetic_receipt(old_binding)
        self.assertTrue(
            any("candidate identity mismatch" in error for error in errors),
            errors,
        )

    def test_raw_evidence_manifest_rejects_foreign_host_and_extra_file(self) -> None:
        errors, _, _ = self.validate_synthetic_receipt(
            manifest_mutator=lambda manifest: manifest.update(
                {"source_hosts": ["attacker.example"]}
            )
        )
        self.assertTrue(
            any("source host inventory mismatch" in error for error in errors),
            errors,
        )

        with tempfile.TemporaryDirectory(prefix="formal-acquisition-") as temp:
            root = Path(temp)
            report = root / "pip-report.json"
            report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            evidence_dir, receipt_path, _ = write_synthetic_evidence(root, report)
            (evidence_dir / "unexpected.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(
                VALIDATOR, "candidate_binding", return_value=([], synthetic_candidate())
            ):
                errors, _, _ = VALIDATOR.validate_acquisition_receipt(
                    receipt_path,
                    evidence_dir,
                    report,
                    JOB_IDENTITY,
                    CANDIDATE_BASE,
                )
            self.assertTrue(
                any("file inventory mismatch" in error for error in errors), errors
            )

    def test_online_session_forbids_duplicate_calls_and_does_not_retry_403(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return "https://pypi.org/example"

            def read(self):
                return b'{"ok":true}'

        with tempfile.TemporaryDirectory(prefix="formal-online-session-") as temp:
            evidence = Path(temp) / "evidence"
            with mock.patch.object(VALIDATOR, "urlopen", return_value=Response()) as call:
                session = VALIDATOR.OnlineEvidenceSession(evidence)
                self.assertEqual({"ok": True}, session.get_json("https://pypi.org/example"))
                with self.assertRaisesRegex(RuntimeError, "duplicate live metadata request"):
                    session.get_json("https://pypi.org/example")
                with self.assertRaisesRegex(RuntimeError, "already failed"):
                    session.get_json("https://pypi.org/another")
                self.assertEqual(1, call.call_count)

        with tempfile.TemporaryDirectory(prefix="formal-online-session-") as temp:
            evidence = Path(temp) / "evidence"
            failure = HTTPError(
                "https://api.github.com/example", 403, "rate limited", {}, None
            )
            with mock.patch.object(VALIDATOR, "urlopen", side_effect=failure) as call:
                session = VALIDATOR.OnlineEvidenceSession(evidence)
                with self.assertRaisesRegex(RuntimeError, "request failed"):
                    session.get_json("https://api.github.com/example")
                with self.assertRaisesRegex(RuntimeError, "already failed"):
                    session.get_json("https://pypi.org/another")
                self.assertEqual(1, call.call_count)

    def test_replay_session_consumes_bound_raw_bytes_without_network(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-replay-session-") as temp:
            evidence = Path(temp)
            responses = evidence / "responses"
            responses.mkdir()
            raw = b'{"ok":true}'
            response_path = responses / "001.json"
            response_path.write_bytes(raw)
            url = "https://pypi.org/example"
            manifest = {
                "schema_version": 1,
                "source_hosts": ["pypi.org"],
                "entries": [
                    {
                        "method": "GET",
                        "url": url,
                        "final_url": url,
                        "source_host": "pypi.org",
                        "status": 200,
                        "request_sha256": VALIDATOR.sha256_bytes(b""),
                        "response_path": "responses/001.json",
                        "response_sha256": VALIDATOR.sha256_bytes(raw),
                    }
                ],
            }
            with mock.patch.object(
                VALIDATOR,
                "urlopen",
                side_effect=AssertionError("replay attempted network"),
            ):
                replay = VALIDATOR.ReplayEvidenceSession(evidence, manifest)
                self.assertEqual({"ok": True}, replay.get_json(url))
                replay.finish()

            response_path.write_bytes(b'{"ok":false}')
            replay = VALIDATOR.ReplayEvidenceSession(evidence, manifest)
            with self.assertRaisesRegex(ValueError, "response hash mismatch"):
                replay.get_json(url)

    def test_acquisition_receipt_missing_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-acquisition-") as temp:
            root = Path(temp)
            report = root / "pip-report.json"
            report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            path = evidence_dir / "missing.json"
            errors, _, receipt_hash = VALIDATOR.validate_acquisition_receipt(
                path,
                evidence_dir,
                report,
                JOB_IDENTITY,
                CANDIDATE_BASE,
            )
        self.assertTrue(any("could not be validated" in error for error in errors))
        self.assertEqual("", receipt_hash)

    def test_cli_lock_check_does_not_require_jsonschema(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check-lock"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual("PENDING", payload["formal_execution"])

    def test_formal_mode_fails_closed_without_pip_report(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--formal"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--formal requires --pip-report", result.stdout)
        self.assertIn("--candidate-base", result.stdout)

    def assert_formal_workflow_structure(self, text: str) -> None:
        lines = text.splitlines()
        job_start = lines.index("  formal-schema-gate:")
        job_end = next(
            (
                index
                for index in range(job_start + 1, len(lines))
                if lines[index].startswith("  ")
                and not lines[index].startswith("    ")
                and lines[index].endswith(":")
            ),
            len(lines),
        )
        formal_lines = lines[job_start:job_end]

        env_index = formal_lines.index("    env:")
        steps_index = formal_lines.index("    steps:")
        self.assertLess(env_index, steps_index)
        self.assertIn(
            '      PYTHONDONTWRITEBYTECODE: "1"',
            formal_lines[env_index + 1 : steps_index],
        )
        self.assertIn(
            "      FORMAL_CANDIDATE_BASE: "
            "${{ github.event.pull_request.base.sha || github.event.before }}",
            formal_lines[env_index + 1 : steps_index],
        )

        diagnostic_name = (
            "      - name: Report checkout status paths after formal gate failure"
        )
        self.assertEqual(1, formal_lines.count(diagnostic_name))
        diagnostic_index = formal_lines.index(diagnostic_name)
        diagnostic_end = next(
            (
                index
                for index in range(diagnostic_index + 1, len(formal_lines))
                if formal_lines[index].startswith("      - name:")
            ),
            len(formal_lines),
        )
        diagnostic_lines = formal_lines[diagnostic_index:diagnostic_end]
        self.assertEqual(1, diagnostic_lines.count("        if: failure()"))
        self.assertEqual(
            1,
            diagnostic_lines.count(
                "          git status --porcelain=v1 --untracked-files=all || true"
            ),
        )

    def assert_python_steps_inherit_bytecode_guard(
        self, text: str, job_name: str
    ) -> None:
        lines = text.splitlines()
        job_start = lines.index(f"  {job_name}:")
        job_end = next(
            (
                index
                for index in range(job_start + 1, len(lines))
                if lines[index].startswith("  ")
                and not lines[index].startswith("    ")
                and lines[index].endswith(":")
            ),
            len(lines),
        )
        job_lines = lines[job_start:job_end]
        env_index = job_lines.index("    env:")
        steps_index = job_lines.index("    steps:")
        self.assertLess(env_index, steps_index)
        self.assertEqual(
            1,
            job_lines[env_index + 1 : steps_index].count(
                '      PYTHONDONTWRITEBYTECODE: "1"'
            ),
        )

        step_starts = [
            index
            for index, line in enumerate(job_lines)
            if line.startswith("      - name:")
        ]
        python_steps = []
        for offset, step_start in enumerate(step_starts):
            step_end = (
                step_starts[offset + 1]
                if offset + 1 < len(step_starts)
                else len(job_lines)
            )
            step_lines = job_lines[step_start:step_end]
            if any("python3" in line or "/python\"" in line for line in step_lines):
                python_steps.append(step_lines[0].strip())
                self.assertFalse(
                    any("PYTHONDONTWRITEBYTECODE:" in line for line in step_lines),
                    step_lines[0],
                )
        self.assertTrue(python_steps)

    def test_check_skill_python_steps_inherit_job_bytecode_guard(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assert_python_steps_inherit_bytecode_guard(text, "check-skill")

        job_guard = (
            '    env:\n'
            '      PYTHONDONTWRITEBYTECODE: "1"\n'
            '    steps:\n'
        )
        step_local_guard = (
            '    steps:\n'
            '      - name: Check out repository\n'
            '        env:\n'
            '          PYTHONDONTWRITEBYTECODE: "1"\n'
        )
        mutated = text.replace(job_guard, step_local_guard, 1)
        with self.assertRaises((AssertionError, ValueError)):
            self.assert_python_steps_inherit_bytecode_guard(mutated, "check-skill")

        disabled_in_one_step = text.replace(
            "      - name: Run productized package checks\n",
            "      - name: Run productized package checks\n"
            "        env:\n"
            '          PYTHONDONTWRITEBYTECODE: "0"\n',
            1,
        )
        with self.assertRaises(AssertionError):
            self.assert_python_steps_inherit_bytecode_guard(
                disabled_in_one_step, "check-skill"
            )

    def test_workflow_has_read_only_isolated_formal_job(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assert_formal_workflow_structure(text)
        formal = text.split("  formal-schema-gate:", 1)[1]
        required = (
            "runs-on: ubuntu-24.04",
            "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
            "permissions:\n      contents: read",
            'python-version: "3.11"',
            'architecture: "x64"',
            "persist-credentials: false",
            "ref: ${{ github.event.pull_request.head.sha || github.sha }}",
            'PYTHONDONTWRITEBYTECODE: "1"',
            'PYTHONNOUSERSITE: "1"',
            'PIP_NO_INPUT: "1"',
            'PIP_NO_CACHE_DIR: "1"',
            "--verify-acquisition",
            "--isolated",
            "--index-url https://pypi.org/simple",
            "--only-binary=:all:",
            "--require-hashes",
            "--no-cache-dir",
            "--formal",
            "--formal-schema-result",
            "--formal-schema-pip-report",
            "--formal-schema-acquisition-result",
            "--formal-schema-evidence-dir",
            "--candidate-base \"$FORMAL_CANDIDATE_BASE\"",
            "--formal-schema-candidate-base \"$FORMAL_CANDIDATE_BASE\"",
            "--evidence-dir",
            "--allow-existing-tag",
            "if: failure()",
            "Report checkout status paths after formal gate failure",
            "git status --porcelain=v1 --untracked-files=all",
        )
        for fragment in required:
            self.assertIn(fragment, formal)
        forbidden = (
            "environment:",
            "secrets.",
            "git push",
            "gh release",
            "codex plugin",
            "update_installed_skill",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, formal)
        self.assertIn("            --allow-existing-tag \\\n", formal)
        self.assertNotIn("            --pre-tag \\\n", formal)
        self.assertNotIn(
            "scripts/validate_formal_schemas.py \\\n            --formal",
            formal,
        )
        self.assertEqual(1, formal.count("--verify-acquisition"))
        self.assertEqual(1, formal.count("--candidate-base \"$FORMAL_CANDIDATE_BASE\""))
        self.assertEqual(
            1,
            formal.count(
                "--formal-schema-candidate-base \"$FORMAL_CANDIDATE_BASE\""
            ),
        )
        self.assertLess(
            formal.index("- name: Acquire official evidence once"),
            formal.index("- name: Run formal Draft 2020-12 gate"),
        )
        formal_step = formal.split(
            "- name: Run formal Draft 2020-12 gate", 1
        )[1]
        self.assertNotIn("--verify-acquisition", formal_step)

    def test_workflow_pins_third_party_actions_to_reviewed_commits(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        action_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("uses: actions/")
        ]
        self.assertEqual(4, len(action_lines))
        for line in action_lines:
            reference = line.rsplit("@", 1)[-1]
            self.assertRegex(reference, r"^[0-9a-f]{40}$")
        self.assertEqual(
            2,
            action_lines.count(
                "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
            ),
        )
        self.assertEqual(
            2,
            action_lines.count(
                "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
            ),
        )

    def test_workflow_rejects_missing_or_step_local_candidate_base(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        job_level = (
            "      FORMAL_CANDIDATE_BASE: "
            "${{ github.event.pull_request.base.sha || github.event.before }}\n"
        )
        mutated = text.replace(job_level, "", 1).replace(
            "      - name: Acquire official evidence once\n",
            "      - name: Acquire official evidence once\n"
            "        env:\n"
            "          FORMAL_CANDIDATE_BASE: ${{ github.event.pull_request.base.sha }}\n",
            1,
        )
        with self.assertRaises(AssertionError):
            self.assert_formal_workflow_structure(mutated)

    def test_workflow_pins_checkout_and_python_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(
            2,
            text.count(
                "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
            ),
        )
        self.assertEqual(
            2,
            text.count(
                "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
            ),
        )
        self.assertEqual(2, text.count("persist-credentials: false"))

    def test_workflow_rejects_step_local_bytecode_guard(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        prefix, formal = text.split("  formal-schema-gate:", 1)
        mutated_formal = formal.replace(
            '      PYTHONDONTWRITEBYTECODE: "1"\n',
            "",
            1,
        ).replace(
            "      - name: Record isolated runner identity\n",
            "      - name: Record isolated runner identity\n"
            "        env:\n"
            '          PYTHONDONTWRITEBYTECODE: "1"\n',
            1,
        )
        mutated = prefix + "  formal-schema-gate:" + mutated_formal
        with self.assertRaises(AssertionError):
            self.assert_formal_workflow_structure(mutated)

    def test_workflow_rejects_duplicate_failure_diagnostic(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        lines = text.splitlines()
        diagnostic_name = (
            "      - name: Report checkout status paths after formal gate failure"
        )
        diagnostic_index = lines.index(diagnostic_name)
        diagnostic_end = next(
            (
                index
                for index in range(diagnostic_index + 1, len(lines))
                if lines[index].startswith("      - name:")
            ),
            len(lines),
        )
        diagnostic_lines = lines[diagnostic_index:diagnostic_end]
        mutated = "\n".join(
            lines[:diagnostic_end] + diagnostic_lines + lines[diagnostic_end:]
        )
        with self.assertRaises(AssertionError):
            self.assert_formal_workflow_structure(mutated)


@unittest.skipUnless(
    platform.system() == "Linux"
    and platform.machine() == "x86_64"
    and sys.version_info[:2] == (3, 11),
    "formal execution requires the approved Ubuntu x64 CPython 3.11 matrix",
)
class FormalSchemaEngineTests(unittest.TestCase):
    def test_formal_schema_inventory_and_fixtures(self) -> None:
        try:
            versions = {
                item.name: VALIDATOR.metadata.version(item.name)
                for item in VALIDATOR.DISTRIBUTIONS
            }
        except VALIDATOR.metadata.PackageNotFoundError:
            self.skipTest("locked formal dependencies are not installed")
        expected = {item.name: item.version for item in VALIDATOR.DISTRIBUTIONS}
        if versions != expected:
            self.skipTest("installed formal dependency versions do not match the lock")
        with tempfile.TemporaryDirectory(prefix="formal-schema-test-") as temp:
            root = Path(temp)
            report = root / "pip-report.json"
            report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            evidence_dir, acquisition, _ = write_synthetic_evidence(root, report)
            with (
                mock.patch.object(
                    VALIDATOR, "candidate_binding", return_value=([], synthetic_candidate())
                ),
                mock.patch.object(
                    VALIDATOR,
                    "verify_acquisition",
                    return_value=([], {"packages": synthetic_packages()}),
                ),
            ):
                errors, result = VALIDATOR.validate_formal(
                    report,
                    acquisition,
                    evidence_dir,
                    JOB_IDENTITY,
                    CANDIDATE_BASE,
                )
            self.assertEqual(
                VALIDATOR.sha256_file(report), result["pip_report_sha256"]
            )
            self.assertEqual(
                VALIDATOR.sha256_file(acquisition),
                result["acquisition_receipt_sha256"],
            )
        self.assertEqual([], errors)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(len(VALIDATOR.SCHEMA_INVENTORY), result["schema_count"])
        self.assertGreater(result["positive_fixture_count"], 0)
        self.assertGreater(result["negative_fixture_count"], 0)
        self.assertEqual(7, result["fixture_validated_schema_count"])
        self.assertEqual(16, result["syntax_only_schema_count"])


if __name__ == "__main__":
    unittest.main()
