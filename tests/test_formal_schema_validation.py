from __future__ import annotations

import importlib.util
import builtins
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import textwrap
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
FORMAL_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "formal-release-gate.yml"

APPROVED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
}


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


class SchemaIntegrationTests(unittest.TestCase):
    def step(self, name):
        text = WORKFLOW.read_text().split("  formal-schema-gate:", 1)[1]
        block = text.split("      - name: " + name + "\n", 1)[1].split("      - name:", 1)[0]
        return textwrap.dedent(block.split("        run: |\n", 1)[1])

    def require_engine(self):
        errors = VALIDATOR.verify_runtime_versions()
        if errors:
            self.skipTest("BLOCKED_REAL_ENGINE: " + "; ".join(errors))

    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            rc = VALIDATOR.main(argv)
        return rc, output.getvalue()

    def test_event_route_executes_real_shell(self):
        for event, ref, expected in [
            ("push", "refs/heads/main", 0),
            ("pull_request", "refs/pull/149/merge", 0),
            ("push", "refs/heads/other", 1),
            ("workflow_dispatch", "refs/heads/main", 1),
            ("", "", 1),
        ]:
            with self.subTest(event=event, ref=ref):
                p = subprocess.run(["bash", "-c", self.step("Validate CI event route")],
                                   env=dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_REF=ref),
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(expected, p.returncode, p.stderr)
                if event == "push" and expected == 0:
                    self.assertIn("controlled_formal_evidence: NOT_GENERATED", p.stdout)

    def test_schema_only_rejects_formal_or_unknown_arguments(self):
        for argv in [["--schema-only", "--formal"], ["--unknown-mode"],
                     ["--schema-only", "--result", "must-not-exist.json"],
                     ["--schema-only", "--event-target-sha", "f" * 40],
                     ["--schema-only", "--pip-report", "report.json"]]:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                VALIDATOR.main(argv)
            self.assertNotEqual(0, error.exception.code)

    def test_missing_engine_fails_without_acquisition_or_output(self):
        real_import = builtins.__import__
        def blocked(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("test: engine unavailable")
            return real_import(name, *args, **kwargs)
        # Isolate package metadata only; the real engine import must fail closed.
        with mock.patch.object(VALIDATOR, "verify_runtime_versions", return_value=[]), \
             mock.patch("builtins.__import__", side_effect=blocked), \
             mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, \
             mock.patch.object(VALIDATOR, "write_json") as write:
            rc, output = self.invoke(["--schema-only"])
        self.assertNotEqual(0, rc)
        self.assertIn("engine unavailable", output)
        self.assertIn('"controlled_formal_evidence": "NOT_GENERATED"', output)
        acquire.assert_not_called()
        write.assert_not_called()

    def test_real_engine_positive(self):
        self.require_engine()
        with mock.patch.object(VALIDATOR, "acquire_evidence") as acquire:
            rc, output = self.invoke(["--schema-only"])
        self.assertEqual(0, rc, output)
        self.assertGreater(json.loads(output)["positive_fixture_count"], 0)
        self.assertGreater(json.loads(output)["negative_fixture_count"], 0)
        acquire.assert_not_called()

    def test_real_engine_rejects_invalid_schema(self):
        self.require_engine()
        with mock.patch.object(VALIDATOR, "validate_schema_inventory", return_value=([], {"bad": {"$id": "urn:bad", "type": "not-a-type"}})):
            rc, output = self.invoke(["--schema-only"])
        self.assertNotEqual(0, rc, output)

    def test_real_engine_rejects_bad_positive_fixture(self):
        self.require_engine()
        positives, negatives = VALIDATOR.materialized_fixture_cases()
        name, case, _ = positives[0]
        with mock.patch.object(VALIDATOR, "materialized_fixture_cases", return_value=([(name, case, None), *positives[1:]], negatives)):
            rc, output = self.invoke(["--schema-only"])
        self.assertNotEqual(0, rc, output)

    def test_main_merge_shell_runs_schema_and_static_checks(self):
        self.require_engine()
        with tempfile.TemporaryDirectory(prefix="schema-main-") as temp:
            root = Path(temp)
            repo = root / "repo"
            shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                       GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                       RUNNER_TEMP=str(root), PYTHONDONTWRITEBYTECODE="1", SSH_AUTH_SOCK="")
            def git(*args, input=None):
                return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                                      cwd=repo, env=env, input=input, text=True, capture_output=True, check=True, timeout=30).stdout.strip()
            git("init", "-q")
            git("add", "--all")  # Test-only fixture, never the project candidate.
            tree = git("write-tree")
            base = git("commit-tree", tree, input="fixture base\n")
            side = git("commit-tree", tree, "-p", base, input="fixture side\n")
            merge = git("commit-tree", tree, "-p", base, "-p", side, input="fixture merge\n")
            git("update-ref", "HEAD", merge)
            self.assertEqual(3, len(git("rev-list", "--parents", "-n", "1", "HEAD").split()))
            # A symlink outside a venv loses pyvenv.cfg discovery; keep the original executable path.
            interpreter = sys.executable
            identity_code = (
                "import importlib.metadata as m,json,sys; "
                "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,"
                "'base_prefix':sys.base_prefix,'packages':"
                "{n:{'version':m.version(n),'location':str(m.distribution(n).locate_file(''))} "
                "for n in sys.argv[1:]}}))"
            )
            probe = subprocess.run([interpreter, "-B", "-c", identity_code,
                                    *[item.name for item in VALIDATOR.DISTRIBUTIONS]],
                                   cwd=repo, env=env, capture_output=True, text=True, check=True, timeout=30)
            child_identity = json.loads(probe.stdout)
            self.assertEqual(sys.executable, child_identity["executable"])
            self.assertEqual(sys.prefix, child_identity["prefix"])
            self.assertEqual(sys.base_prefix, child_identity["base_prefix"])
            self.assertEqual({item.name: item.version for item in VALIDATOR.DISTRIBUTIONS},
                             {name: value["version"] for name, value in child_identity["packages"].items()})
            print("MAIN_FIXTURE_CHILD_IDENTITY=" + json.dumps(child_identity, sort_keys=True))
            state = subprocess.run([sys.executable, "scripts/full_skill_validation.py", "--print-release-state"],
                                   cwd=repo, env=env, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
            script = self.step("Validate schema integration on main (not controlled evidence)").replace(
                "${{ steps.release-state.outputs.state }}", state)
            self.assertEqual(2, script.count('"$RUNNER_TEMP/lhe-formal-schema-venv/bin/python"'))
            script = script.replace('"$RUNNER_TEMP/lhe-formal-schema-venv/bin/python"', shlex.quote(interpreter))
            p = subprocess.run(["bash", "-x", "-c", script],
                               cwd=repo, env=env, capture_output=True, text=True, timeout=90)
            print("MAIN_FIXTURE_COMMAND=" + json.dumps({"cwd": str(repo), "command": ["bash", "-x", "-c", script]}))
            print(p.stderr)
            self.assertEqual(0, p.returncode, p.stdout + p.stderr)
            self.assertIn('"gate": "schema-integration"', p.stdout)
            self.assertIn("Final release-state consistency passed", p.stdout)
            self.assertFalse((root / "formal-schema-evidence").exists())
            self.assertFalse((root / "formal-schema-result.json").exists())

    def test_pr_route_keeps_formal_acquisition_and_readiness(self):
        text = WORKFLOW.read_text().split("  formal-schema-gate:", 1)[1]
        for name in ("Record formal runner identity", "Acquire official evidence once",
                     "Run formal Draft 2020-12 gate for pull request"):
            block = text.split("      - name: " + name + "\n", 1)[1].split("      - name:", 1)[0]
            self.assertIn("if: github.event_name == 'pull_request'", block)
        self.assertIn("--verify-acquisition", self.step("Acquire official evidence once"))
        self.assertIn("--formal-schema-result", self.step("Run formal Draft 2020-12 gate for pull request"))


class SchemaWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "schema_workflow_checker_under_test", ROOT / "scripts/full_skill_validation.py")
        cls.checker = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.checker
        spec.loader.exec_module(cls.checker)

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def errors(self, text):
        return (self.checker.release_gate_workflow_errors(text)
                + self.checker.check_skill_formal_evidence_workflow_errors(text))

    def replace_step(self, name, old, new):
        prefix, block = self.text.split("      - name: " + name + "\n", 1)
        step, separator, suffix = block.partition("      - name:")
        self.assertIn(old, step)
        return prefix + "      - name: " + name + "\n" + step.replace(old, new, 1) + separator + suffix

    def test_main_integration_and_pr_formal_contract_accepted(self):
        self.assertEqual([], self.errors(self.text))

    def test_main_rejects_missing_engine_static_gate_or_wrong_mode(self):
        mutations = [
            ("--schema-only", "--check-lock"),
            ("--schema-only", "--unknown-mode"),
            ("scripts/validate_formal_schemas.py --schema-only", "-c 'print(0)'"),
            ("scripts/check_release_readiness.py", "scripts/other.py"),
            ('--release-state "${{ steps.release-state.outputs.state }}"', "--release-state final"),
            ("--allow-existing-tag", ""),
            ("--schema-only", "--schema-only || true"),
            ("set -euo pipefail", "set +e"),
            ("--schema-only", "--schema-only --result /tmp/formal-result.json"),
        ]
        for old, new in mutations:
            with self.subTest(old=old, new=new):
                text = self.replace_step("Validate schema integration on main (not controlled evidence)", old, new)
                self.assertTrue(self.errors(text))

    def test_pr_provenance_remains_required(self):
        for fragment in (
            '--formal-schema-action-provenance-file "$RUNNER_TEMP/formal-schema-runner-identity.json"',
            '--formal-schema-workflow-sha256 "$WORKFLOW_SHA256"',
            '--formal-schema-event-target-sha "$FORMAL_EVENT_TARGET_SHA"',
        ):
            with self.subTest(fragment=fragment):
                self.assertTrue(self.errors(self.replace_step(
                    "Run formal Draft 2020-12 gate for pull request", fragment, "")))

    def test_formal_effects_cannot_leak_into_main(self):
        for name in ("Record formal runner identity", "Acquire official evidence once",
                     "Run formal Draft 2020-12 gate for pull request", "Upload formal schema CI evidence"):
            with self.subTest(name=name):
                self.assertTrue(self.errors(self.replace_step(name, "github.event_name == 'pull_request'", "true")))

    def test_event_route_must_fail_closed(self):
        for old, new in (("exit 1", "exit 0"), ("push:refs/heads/main)", "push:*)"),
                         ("controlled_formal_evidence: NOT_GENERATED", "controlled_formal_evidence: PASS")):
            with self.subTest(old=old):
                self.assertTrue(self.errors(self.replace_step("Validate CI event route", old, new)))
        self.assertTrue(self.errors(self.replace_step(
            "Validate schema integration on main (not controlled evidence)",
            "github.event_name == 'push' && github.ref == 'refs/heads/main'",
            "github.event_name == 'workflow_dispatch'")))

    def test_engine_installation_and_failure_propagation_remain_required(self):
        for old, new in (("--require-hashes", ""), ("-r requirements-release.txt", "jsonschema")):
            with self.subTest(old=old):
                self.assertTrue(self.errors(self.replace_step("Install exact wheels in a temporary virtual environment", old, new)))
        self.assertTrue(self.errors(self.replace_step("Validate CI event route", "shell: bash", "shell: bash\n        continue-on-error: true")))

    def test_explicit_release_gate_still_rejects_missing_production_contract(self):
        text = FORMAL_RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual([], self.checker.formal_release_evidence_workflow_errors(text))
        for old in ('--candidate-base "$CANDIDATE_BASE"', '--formal-schema-candidate-base "$CANDIDATE_BASE"',
                    'test "$(git merge-base "$candidate_base" "$release_commit")" = "$candidate_base"'):
            with self.subTest(old=old):
                self.assertIn(old, text)
                self.assertTrue(self.checker.formal_release_evidence_workflow_errors(text.replace(old, "", 1)))


class ExecutionWorkflowBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.path = ".github/workflows/formal-baseline.yml"
        self.content = (ROOT / self.path).read_bytes()
        self.env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                        GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        self.git("init", "-q")
        self.base = self.revision(self.content)
        self.head = self.revision(self.content, self.base)
        self.git("update-ref", "HEAD", self.head)
        (self.repo / self.path).parent.mkdir(parents=True)
        (self.repo / self.path).write_bytes(self.content)
        self.patch = mock.patch.object(VALIDATOR, "ROOT", self.repo)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def git(self, *args, input=None):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=self.repo,
                              env=self.env, input=input, text=True, capture_output=True,
                              check=True, timeout=10).stdout.strip()

    def revision(self, content, parent=None):
        blob = self.git("hash-object", "-w", "--stdin", input=content.decode())
        tree = self.git("mktree", input=f"100644 blob {blob}\tformal-baseline.yml\n")
        tree = self.git("mktree", input=f"040000 tree {tree}\tworkflows\n")
        tree = self.git("mktree", input=f"040000 tree {tree}\t.github\n")
        return self.git("commit-tree", tree, *(["-p", parent] if parent else []), input="fixture\n")

    def produce(self, revision):
        # Execute the checked-in producer, stopping before acquisition begins.
        text = self.content.decode()
        step = text.split("      - name: Record runner identity and acquire evidence", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1].split("          PY\n", 1)[0] + "          PY\n")
        (self.repo / "scripts").mkdir(exist_ok=True)
        shutil.copyfile(SCRIPT_PATH, self.repo / "scripts/validate_formal_schemas.py")
        interpreter = self.repo / "lhe-formal-venv/bin/python"
        interpreter.parent.mkdir(parents=True, exist_ok=True)
        if not interpreter.exists():
            interpreter.symlink_to(sys.executable)
        env = dict(self.env, RUNNER_TEMP=str(self.repo), TARGET_SHA=self.head,
                   ACTUAL_WORKFLOW_SHA=revision, GITHUB_WORKFLOW_SHA=revision,
                   GITHUB_RUN_ID="1", GITHUB_RUN_ATTEMPT="1", GITHUB_JOB="formal-baseline",
                   GITHUB_REPOSITORY=VALIDATOR.EXPECTED_REPOSITORY,
                   GITHUB_WORKFLOW_REF=f"{VALIDATOR.EXPECTED_REPOSITORY}/{self.path}@refs/heads/main")
        result = subprocess.run(["bash", "-c", script], cwd=self.repo, env=env,
                                stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads((self.repo / "formal-baseline-runner-identity.json").read_text())

    def consume(self, payload, revision):
        path = self.repo / "identity.json"
        path.write_text(json.dumps(payload))
        context = {key: payload[key] for key in ("github_run_id", "github_run_attempt", "workflow_ref", "job", "repository", "event_target_sha", "release_commit", "candidate_base")}
        context["workflow_sha"] = revision
        workflow = dict(payload["workflow_identity"], workflow_ref=payload["workflow_ref"])
        return VALIDATOR.load_action_provenance(path, workflow, context)[0]

    def test_real_producer_same_revision(self):
        self.assertEqual([], self.consume(self.produce(self.head), self.head))

    def test_real_producer_distinct_revision_same_blob(self):
        self.assertNotEqual(self.base, self.head)
        self.assertEqual([], self.consume(self.produce(self.base), self.base))

    def test_wrong_execution_blob_is_rejected(self):
        changed = self.revision(self.content + b"\n# different execution\n", self.head)
        payload = self.produce(self.head)
        payload["workflow_sha"] = changed
        self.assertTrue(self.consume(payload, changed))

    def test_payload_mutations_fail_closed(self):
        original = self.produce(self.head)
        for key, value in (("workflow_sha", "a" * 40), ("workflow_sha", None),
                           ("workflow_path", None), ("workflow_path", "../bad"),
                           ("workflow_file_sha256", None), ("workflow_file_sha256", "0" * 64),
                           ("release_commit", "a" * 40), ("github_run_id", 1)):
            with self.subTest(key=key, value=value):
                self.assertTrue(self.consume(dict(original, **{key: value}), self.head))
        payload = dict(original)
        del payload["workflow_sha"]
        self.assertTrue(self.consume(payload, self.head))
        self.assertTrue(self.consume(original, ""))
        self.assertTrue(self.consume(original, "a" * 40))

    def test_missing_blob_and_wrong_object_types(self):
        tree = self.git("mktree", input="")
        empty = self.git("commit-tree", tree, input="empty\n")
        blob = self.git("hash-object", "-w", "--stdin", input="blob")
        for sha, path in ((empty, self.path), (tree, self.path), (blob, self.path),
                          (self.head, ".github/workflows/absent.yml")):
            with self.subTest(sha=sha, path=path), self.assertRaises(ValueError):
                VALIDATOR.execution_workflow_blob_sha256(sha, path)

    def test_baseline_cannot_fall_back_to_legacy(self):
        payload = self.produce(self.head)
        for key in ("workflow_sha", "workflow_path", "workflow_file_sha256"):
            payload.pop(key)
        self.assertTrue(self.consume(payload, self.head))

    def test_execution_git_has_bounded_offline_io(self):
        with mock.patch.object(VALIDATOR.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 10)) as run:
            with self.assertRaises(ValueError):
                VALIDATOR.execution_workflow_blob_sha256(self.head, self.path)
            self.assertEqual(10, run.call_args.kwargs["timeout"])
            self.assertEqual(subprocess.DEVNULL, run.call_args.kwargs["stdin"])
            self.assertEqual("1", run.call_args.kwargs["env"]["GIT_NO_LAZY_FETCH"])
            self.assertEqual("", run.call_args.kwargs["env"]["GIT_ALLOW_PROTOCOL"])


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


class FormalBaselineArchiveLayoutTests(unittest.TestCase):
    workflow_name = "formal-baseline.yml"
    replay_step = "Offline formal replay and readiness audit"
    upload_step = "Upload formal evidence"
    raw_name = "formal-baseline-123-1"
    report_name = "pip-report.json"
    venv_name = "lhe-formal-venv"
    identity_name = "formal-baseline-runner-identity.json"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="formal-layout-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.report = self.root / self.report_name
        self.report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
        evidence, _, self.receipt = write_synthetic_evidence(self.root, self.report)
        self.raw = self.root / self.raw_name
        evidence.rename(self.raw)
        self.receipt_path = self.raw / "acquisition-receipt.json"
        response = self.raw / "responses/fixture.json"
        response.parent.mkdir()
        response.write_text('{"fixture_only": true}', encoding="utf-8")
        manifest = {
            "schema_version": 1, "source_hosts": ["pypi.org"],
            "entries": [{
                "method": "GET", "url": "https://pypi.org/pypi/fixture/json",
                "final_url": "https://pypi.org/pypi/fixture/json",
                "source_host": "pypi.org", "status": 200,
                "request_sha256": VALIDATOR.sha256_bytes(b""),
                "response_path": "responses/fixture.json",
                "response_sha256": VALIDATOR.sha256_file(response),
            }],
        }
        (self.raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.receipt["raw_evidence_manifest_sha256"] = VALIDATOR.sha256_file(self.raw / "manifest.json")
        self.receipt["raw_evidence_count"] = 1
        self.receipt["source_hosts"] = ["pypi.org"]
        self.receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")

    def inventory_errors(self, raw=None):
        raw = raw or self.raw
        return VALIDATOR.validate_raw_manifest(
            raw, raw / "acquisition-receipt.json",
            self.receipt["raw_evidence_manifest_sha256"],
        )[0]

    def test_legal_raw_fixture_passes_real_inventory(self):
        self.assertEqual(self.inventory_errors(), [])

    def test_workflow_output_and_upload_preserve_raw_inventory(self):
        workflow = (ROOT / ".github/workflows" / self.workflow_name).read_text()
        step = workflow.split(f"      - name: {self.replay_step}\n", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0])
        # Exercise the actual shell routing without formal execution or acquisition.
        # Only the CLI producer is a fixture; inventory checks use production code.
        python = self.root / self.venv_name / "bin/python"
        python.parent.mkdir(parents=True)
        python.write_text(
            f"#!{sys.executable}\n" + textwrap.dedent('''\
            import json, os, sys
            from pathlib import Path
            if sys.argv[1] == "-c":
                print("0" * 64)
            elif sys.argv[1] == "-m":
                assert sys.argv[1:] == ["-m", "unittest", "tests.test_formal_schema_validation", "-v"]
                Path(os.environ["FIXTURE_UNITTEST"]).write_text(json.dumps(sys.argv[1:]))
            else:
                args = sys.argv[1:]
                assert args[0] == "scripts/check_release_readiness.py"
                Path(os.environ["FIXTURE_ARGS"]).write_text(json.dumps(args))
                output = Path(args[args.index("--formal-schema-result") + 1])
                output.write_text(json.dumps({"fixture_only": True}))
            '''), encoding="utf-8",
        )
        python.chmod(0o700)
        identity = self.root / self.identity_name
        identity.write_text('{"fixture_only": true}', encoding="utf-8")
        env = dict(os.environ, RUNNER_TEMP=str(self.root), GITHUB_RUN_ID="123",
                   GITHUB_RUN_ATTEMPT="1", TARGET_SHA="a" * 40,
                   GITHUB_REPOSITORY="Q20396/codex-long-horizon-skill",
                   GITHUB_WORKFLOW_SHA="a" * 40, RUNNER_IDENTITY=str(identity),
                   FIXTURE_ARGS=str(self.root / "args.json"),
                   FIXTURE_UNITTEST=str(self.root / "unittest.json"),
                   RELEASE_VERSION="0.7.0", CANDIDATE_BASE="b" * 40,
                   FORMAL_EVENT_TARGET_SHA="a" * 40,
                   FORMAL_REPOSITORY="Q20396/codex-long-horizon-skill",
                   PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            ["bash", "-c", script], cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        args = json.loads((self.root / "args.json").read_text())
        value = lambda flag: args[args.index(flag) + 1]
        output = Path(value("--formal-schema-result"))
        self.assertTrue(output.is_file())
        self.assertEqual(self.inventory_errors(), [])
        self.assertFalse(output.is_relative_to(self.raw))
        self.assertEqual(Path(value("--formal-schema-evidence-dir")), self.raw)
        self.assertEqual(Path(value("--formal-schema-acquisition-result")), self.receipt_path)
        self.assertEqual(Path(value("--formal-schema-pip-report")), self.report)
        self.assertEqual(Path(value("--formal-schema-action-provenance-file")), identity)
        self.assertEqual(value("--formal-schema-event-target-sha"), "a" * 40)
        if self.workflow_name == "formal-release-gate.yml":
            self.assertEqual(value("--formal-schema-candidate-base"), "b" * 40)
            self.assertEqual(value("--formal-schema-workflow-path"), ".github/workflows/formal-release-gate.yml")
            self.assertEqual(value("--release-state"), "final")
            self.assertIn("--pre-tag", args)
            self.assertTrue((self.root / "unittest.json").is_file())

        upload = workflow.split(f"      - name: {self.upload_step}\n", 1)[1]
        paths = upload.split("          path: |\n", 1)[1].split("          if-no-files-found:", 1)[0]
        archive = self.root / "archive"
        archive.mkdir()
        for line in paths.strip().splitlines():
            source = Path(line.strip().replace("${{ runner.temp }}", str(self.root))
                          .replace("${{ github.run_id }}", "123")
                          .replace("${{ github.run_attempt }}", "1"))
            destination = archive / source.relative_to(self.root)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        for source in (output, self.report, identity, self.receipt_path):
            self.assertEqual((archive / source.relative_to(self.root)).read_bytes(), source.read_bytes())
        self.assertEqual(self.inventory_errors(archive / self.raw.name), [])

    def test_result_inside_raw_fixture_is_rejected(self):
        (self.raw / "formal-result.json").write_text('{"fixture_only": true}', encoding="utf-8")
        errors = self.inventory_errors()
        self.assertTrue(any("file inventory mismatch" in error and "formal-result.json" in error
                            for error in errors), errors)


class FormalReleaseGateArchiveLayoutTests(FormalBaselineArchiveLayoutTests):
    workflow_name = "formal-release-gate.yml"
    replay_step = "Run offline final formal replay"
    upload_step = "Upload retained formal evidence"
    raw_name = "formal-schema-evidence-123-1"
    report_name = "lhe-v0.7.0-formal-schema-pip-report.json"
    venv_name = "lhe-v0.7.0-formal-venv"
    identity_name = "lhe-v0.7.0-runner-identity.json"


class FormalSchemaStaticTests(unittest.TestCase):
    def _isolated_acquisition_fixture(self, root: Path, *, mismatch: bool = False):
        if shutil.which("git") is None:
            self.fail("BLOCKED: git is required for the topology fixture")
        repo = root / "repo"
        repo.mkdir()
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("GIT_") and key not in {"SSH_AUTH_SOCK", "SSH_AGENT_PID"}}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="",
                   GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                   GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_EMAIL="fixture@example.invalid")

        def git(*args, input=None):
            return subprocess.run(
                ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                cwd=repo, env=env, input=input, text=True, capture_output=True,
                check=True, timeout=15,
            ).stdout.strip()

        git("init", "-q")
        git("config", "commit.gpgsign", "false")
        git("config", "core.hooksPath", os.devnull)
        workflow_path = ".github/workflows/check-skill.yml"
        content = WORKFLOW.read_text(encoding="utf-8")
        blob = git("hash-object", "-w", "--stdin", input=content)
        tree = git("mktree", input=f"100644 blob {blob}\tcheck-skill.yml\n")
        tree = git("mktree", input=f"040000 tree {tree}\tworkflows\n")
        tree = git("mktree", input=f"040000 tree {tree}\t.github\n")
        base = git("commit-tree", tree, input="base\n")
        head = git("commit-tree", tree, "-p", base, input="head\n")
        candidate_base = git("commit-tree", tree, "-p", base, input="sibling\n") if mismatch else base
        git("update-ref", "HEAD", head)
        git("read-tree", "HEAD")
        workflow = repo / workflow_path
        workflow.parent.mkdir(parents=True)
        workflow.write_text(content, encoding="utf-8")
        self.assertEqual("", git("status", "--porcelain=v1"))
        self.assertEqual([head, base], git("rev-list", "--parents", "-n", "1", head).split())
        provenance, _, _ = self._write_main_provenance(root, fixture_repo=repo,
                                                       candidate_base=candidate_base)
        return repo, provenance, head, candidate_base

    def _synthetic_topology(self, root: Path) -> tuple[str, str, str]:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Synthetic Test"], cwd=root, check=True)
        (root / "marker").write_text("B\n", encoding="utf-8")
        subprocess.run(["git", "add", "marker"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "B"], cwd=root, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        for value in ("C", "D"):
            (root / "marker").write_text(value + "\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-qam", value], cwd=root, check=True)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=root, text=True).strip()
        return base, parent, head

    def _run_synthetic_verify(self, root: Path, workflow_path: str, job: str, base: str, head: str, provenance: Path):
        evidence = root / f"evidence-{job}"
        report = root / f"pip-{job}.json"
        report.write_text("{}", encoding="utf-8")
        receipt = evidence / "acquisition-receipt.json"
        argv = ["--verify-acquisition", "--pip-report", str(report), "--evidence-dir", str(evidence),
                "--result", str(receipt), "--candidate-base", base, "--run-id", "12345", "--run-attempt", "1",
                "--workflow-ref", f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main",
                "--job-name", job, "--workflow-sha256", VALIDATOR.sha256_file(root / workflow_path),
                "--workflow-path", workflow_path, "--action-provenance-file", str(provenance),
                "--event-target-sha", head, "--repository", "Q20396/codex-long-horizon-skill"]
        return argv, evidence, receipt

    def test_synthetic_ci_ancestor_topology_allows_multi_commit_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-topology-ci-") as temp:
            root = Path(temp)
            base, _parent, head = self._synthetic_topology(root)
            workflow_path = ".github/workflows/check-skill.yml"
            workflow = root / workflow_path
            workflow.parent.mkdir(parents=True)
            workflow.write_text((ROOT / workflow_path).read_text(encoding="utf-8"), encoding="utf-8")
            subprocess.run(["git", "add", workflow_path], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "workflow"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            provenance = root / "identity.json"
            workflow_ref = f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main"
            provenance.write_text(json.dumps({
                "github_run_id": "12345", "github_run_attempt": "1", "workflow_ref": workflow_ref,
                "job": "formal-schema-gate", "repository": "Q20396/codex-long-horizon-skill",
                "event_target_sha": head, "release_commit": head, "candidate_base": base,
                "workflow_identity": {"path": workflow_path, "sha256": VALIDATOR.sha256_file(workflow), "workflow_ref": workflow_ref},
                "actions": VALIDATOR.ACTION_PROVENANCE,
            }), encoding="utf-8")
            argv, evidence, receipt = self._run_synthetic_verify(root, workflow_path, "formal-schema-gate", base, head, provenance)
            real_run = VALIDATOR.subprocess.run
            def clean_status(*args, **kwargs):
                command = args[0] if args else kwargs.get("args", [])
                if command[:3] == ["git", "status", "--porcelain=v1"]:
                    return subprocess.CompletedProcess(command, 0, "", "")
                return real_run(*args, **kwargs)
            with mock.patch.object(VALIDATOR, "ROOT", root), mock.patch.object(VALIDATOR.subprocess, "run", side_effect=clean_status), mock.patch.object(VALIDATOR, "acquire_evidence", return_value=([], {"status": "PASS"})) as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                self.assertEqual(0, VALIDATOR.main(argv))
            acquire.assert_called_once()
            network.assert_not_called()
            self.assertEqual("ci_ancestor_base", acquire.call_args.kwargs["verified_context"]["topology_mode"])

    def test_synthetic_release_topology_requires_direct_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-topology-release-") as temp:
            root = Path(temp)
            base, parent, head = self._synthetic_topology(root)
            workflow_path = ".github/workflows/formal-release-gate.yml"
            workflow = root / workflow_path
            workflow.parent.mkdir(parents=True)
            workflow.write_text((ROOT / workflow_path).read_text(encoding="utf-8"), encoding="utf-8")
            subprocess.run(["git", "add", workflow_path], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "workflow"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=root, text=True).strip()
            workflow_ref = f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main"
            provenance = root / "identity.json"
            provenance.write_text(json.dumps({"github_run_id": "12345", "github_run_attempt": "1", "workflow_ref": workflow_ref,
                "job": "formal-release-gate", "repository": "Q20396/codex-long-horizon-skill", "event_target_sha": head,
                "release_commit": head, "candidate_base": base, "workflow_identity": {"path": workflow_path, "sha256": VALIDATOR.sha256_file(workflow), "workflow_ref": workflow_ref}, "actions": VALIDATOR.ACTION_PROVENANCE}), encoding="utf-8")
            argv, evidence, receipt = self._run_synthetic_verify(root, workflow_path, "formal-release-gate", base, head, provenance)
            with mock.patch.object(VALIDATOR, "ROOT", root), mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    self.assertNotEqual(0, VALIDATOR.main(argv))
            acquire.assert_not_called(); network.assert_not_called()
            self.assertFalse(evidence.exists()); self.assertFalse(receipt.exists())
            self.assertIn("unique parent", output.getvalue())

    def test_verify_acquisition_hits_merge_base_mismatch_without_other_binding_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-merge-base-mismatch-") as temp:
            root = Path(temp)
            repo, provenance, head, parent = self._isolated_acquisition_fixture(root, mismatch=True)
            argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent)
            with mock.patch.object(VALIDATOR, "ROOT", repo), mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    self.assertNotEqual(0, VALIDATOR.main(argv))
            acquire.assert_not_called(); network.assert_not_called()
            text = output.getvalue()
            self.assertIn("merge-base", text)
            self.assertEqual(["ERROR: preflight merge-base does not match candidate_base"], text.strip().splitlines())
            self.assertNotIn("exactly one parent", text)
            self.assertNotIn("unique parent", text)
            self.assertNotIn("must be a full lowercase commit SHA", text)
            self.assertNotIn("HEAD does not match", text)
            self.assertFalse(evidence.exists()); self.assertFalse(receipt.exists()); self.assertFalse(result.exists())

    def test_real_clean_synthetic_ci_ancestor_worktree_control(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-clean-topology-") as temp:
            root = Path(temp)
            base, _parent, head = self._synthetic_topology(root)
            with tempfile.TemporaryDirectory(prefix="formal-identity-") as external_temp:
                external = Path(external_temp)
                workflow_path = ".github/workflows/check-skill.yml"
                workflow = root / workflow_path
                workflow.parent.mkdir(parents=True)
                workflow.write_text((ROOT / workflow_path).read_text(encoding="utf-8"), encoding="utf-8")
                subprocess.run(["git", "add", workflow_path], cwd=root, check=True)
                subprocess.run(["git", "commit", "-qm", "workflow"], cwd=root, check=True)
                head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
                identity = external / "identity.json"
                identity.write_text(json.dumps({
                    "github_run_id": "12345", "github_run_attempt": "1",
                    "workflow_ref": f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main",
                    "job": "formal-schema-gate", "repository": "Q20396/codex-long-horizon-skill",
                    "event_target_sha": head, "release_commit": head, "candidate_base": base,
                    "workflow_identity": {"path": workflow_path, "sha256": VALIDATOR.sha256_file(WORKFLOW), "workflow_ref": f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main"},
                    "actions": VALIDATOR.ACTION_PROVENANCE,
                }), encoding="utf-8")
                errors, context = VALIDATOR.preflight_acquisition_context(
                    release_commit=head, candidate_base=base, event_target_sha=head,
                    repository="Q20396/codex-long-horizon-skill", workflow_sha256=VALIDATOR.sha256_file(WORKFLOW),
                    workflow_path=workflow_path, action_provenance_file=identity, runner_identity_file=identity,
                    worktree=root, evidence_dir=root / "new-evidence",
                    workflow_ref=f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main",
                    run_id="12345", run_attempt="1", job_name="formal-schema-gate",
                )
                self.assertEqual([], errors)
                self.assertEqual("ci_ancestor_base", context["topology_mode"])
                self.assertEqual(base, context["candidate_base_commit"])
                self.assertEqual(base, context["candidate_merge_base"])
    def _write_main_provenance(self, root: Path, *, fixture_repo: Path = ROOT, **changes: object) -> tuple[Path, str, str]:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo, text=True, timeout=15).strip()
        parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=fixture_repo, text=True, timeout=15).strip()
        workflow_path = ".github/workflows/check-skill.yml"
        workflow_ref = f"Q20396/codex-long-horizon-skill/{workflow_path}@refs/heads/main"
        payload = {
            "github_run_id": "12345", "github_run_attempt": "1",
            "workflow_ref": workflow_ref, "job": "formal-schema-gate",
            "repository": "Q20396/codex-long-horizon-skill",
            "event_target_sha": head, "release_commit": head,
            "candidate_base": parent,
            "workflow_identity": {"path": workflow_path, "sha256": VALIDATOR.sha256_file(ROOT / workflow_path), "workflow_ref": workflow_ref},
            "actions": VALIDATOR.ACTION_PROVENANCE,
        }
        payload.update(changes)
        path = root / "runner-identity.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, head, parent

    def _run_verify_acquisition(self, root: Path, provenance: Path, head: str, parent: str, evidence_exists: bool = False):
        evidence = root / "evidence"
        if evidence_exists:
            evidence.mkdir()
        receipt = evidence / "acquisition-receipt.json"
        result = root / "formal-result.json"
        report = root / "pip-report.json"
        report.write_text("{}", encoding="utf-8")
        argv = ["--verify-acquisition", "--pip-report", str(report), "--evidence-dir", str(evidence), "--result", str(receipt), "--candidate-base", parent, "--run-id", "12345", "--run-attempt", "1", "--workflow-ref", "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/heads/main", "--job-name", "formal-schema-gate", "--workflow-sha256", VALIDATOR.sha256_file(WORKFLOW), "--workflow-path", ".github/workflows/check-skill.yml", "--action-provenance-file", str(provenance), "--event-target-sha", head, "--repository", "Q20396/codex-long-horizon-skill"]
        return argv, evidence, receipt, result

    def test_verify_acquisition_preflight_failures_do_not_acquire(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-preflight-") as temp:
            root = Path(temp)
            provenance, head, parent = self._write_main_provenance(root)
            mutations = [
                ("candidate_base", "bad-base", "candidate_base"),
                ("provenance candidate base", {"candidate_base": "f" * 40}, "candidate_base"),
                ("event target", {"event_target_sha": "e" * 40}, "event_target_sha"),
                ("release commit", {"release_commit": "e" * 40}, "release_commit"),
                ("repository", {"repository": "foreign/repo"}, "repository"),
                ("workflow ref", {"workflow_ref": "foreign/ref"}, "workflow_ref"),
                ("job", {"job": "wrong-job"}, "job"),
            ]
            for label, mutation, field in mutations:
                with self.subTest(label=label), mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                    if isinstance(mutation, dict):
                        provenance, head, parent = self._write_main_provenance(root, **mutation)
                        argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent)
                    else:
                        argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, mutation)
                        argv[argv.index("--candidate-base") + 1] = mutation
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                        self.assertNotEqual(0, VALIDATOR.main(argv))
                    acquire.assert_not_called()
                    network.assert_not_called()
                    self.assertFalse(evidence.exists())
                    self.assertFalse(receipt.exists())
                    self.assertFalse(result.exists())
                    self.assertIn(field, output.getvalue())
                    self.assertNotIn('"status": "PASS"', output.getvalue())

    def test_verify_acquisition_rejects_invalid_event_and_foreign_workflow_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-preflight-context-") as temp:
            root = Path(temp)
            provenance, head, parent = self._write_main_provenance(root)
            cases = [
                ("invalid event target", {"event_target_sha": "not-a-sha"}, "event_target_sha"),
                ("foreign workflow path", {
                    "workflow_identity": {
                        "path": ".github/workflows/foreign.yml",
                        "sha256": VALIDATOR.sha256_file(WORKFLOW),
                        "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/foreign.yml@refs/heads/main",
                    },
                }, "workflow identity"),
            ]
            for label, mutation, field in cases:
                with self.subTest(label=label):
                    provenance, head, parent = self._write_main_provenance(root, **mutation)
                    argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent)
                    with mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                            self.assertNotEqual(0, VALIDATOR.main(argv))
                    acquire.assert_not_called(); network.assert_not_called()
                    self.assertFalse(evidence.exists()); self.assertFalse(receipt.exists()); self.assertFalse(result.exists())
                    self.assertIn(field, output.getvalue())

    def test_verify_acquisition_rejects_topology_binding_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-preflight-topology-") as temp:
            root = Path(temp)
            provenance, head, parent = self._write_main_provenance(root)
            argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent)
            real_run = subprocess.run

            def topology_run(*args, **kwargs):
                command = args[0] if args else kwargs.get("args", [])
                if command[:4] == ["git", "rev-list", "--parents", "-n"]:
                    return subprocess.CompletedProcess(command, 0, head, "")
                if command[:2] == ["git", "merge-base"]:
                    return subprocess.CompletedProcess(command, 0, "wrong" + "0" * 35, "")
                if command[:3] == ["git", "status", "--porcelain=v1"]:
                    return subprocess.CompletedProcess(command, 0, "", "")
                return real_run(*args, **kwargs)

            with mock.patch.object(VALIDATOR.subprocess, "run", side_effect=topology_run), mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    self.assertNotEqual(0, VALIDATOR.main(argv))
            acquire.assert_not_called(); network.assert_not_called()
            self.assertFalse(evidence.exists()); self.assertFalse(receipt.exists()); self.assertFalse(result.exists())
            self.assertIn("exactly one parent", output.getvalue())

    def test_verify_acquisition_preflight_success_passes_verified_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-preflight-success-") as temp:
            root = Path(temp)
            repo, provenance, head, parent = self._isolated_acquisition_fixture(root)
            argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent)
            with mock.patch.object(VALIDATOR, "ROOT", repo), mock.patch.object(VALIDATOR, "acquire_evidence", return_value=([], {"status": "PASS"})) as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                self.assertEqual(0, VALIDATOR.main(argv))
            acquire.assert_called_once()
            network.assert_not_called()
            context = acquire.call_args.kwargs["verified_context"]
            self.assertEqual(parent, context["candidate_base"])
            self.assertEqual(head, context["release_commit"])
            self.assertEqual(head, context["event_target_sha"])
            self.assertTrue(receipt.exists())
            self.assertFalse(result.exists())

    def test_real_merge_formal_target_rejected_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-merge-refusal-") as temp:
            root = Path(temp)
            repo, provenance, head, parent = self._isolated_acquisition_fixture(root)
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                       GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid")
            def git(*args, input=None):
                return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo,
                                      env=env, input=input, text=True, capture_output=True, check=True, timeout=10).stdout.strip()
            merge = git("commit-tree", git("rev-parse", "HEAD^{tree}"), "-p", parent, "-p", head, input="fixture merge\n")
            git("update-ref", "HEAD", merge)
            payload = json.loads(provenance.read_text())
            payload.update(event_target_sha=merge, release_commit=merge)
            provenance.write_text(json.dumps(payload))
            argv, evidence, receipt, _ = self._run_verify_acquisition(root, provenance, merge, parent)
            with mock.patch.object(VALIDATOR, "ROOT", repo), mock.patch.object(VALIDATOR, "acquire_evidence") as acquire:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertNotEqual(0, VALIDATOR.main(argv))
            self.assertIn("exactly one parent", output.getvalue())
            acquire.assert_not_called()
            self.assertFalse(evidence.exists())
            self.assertFalse(receipt.exists())

    def test_pr_acquisition_actual_shell_passes_fixture_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-pr-shell-") as temp:
            root = Path(temp)
            repo, provenance, head, parent = self._isolated_acquisition_fixture(root)
            shutil.copyfile(provenance, root / "formal-schema-runner-identity.json")
            report = root / "formal-schema-pip-report.json"
            report.write_text("{}")
            bridge = root / "bin/python3"
            bridge.parent.mkdir()
            # Only acquisition is replaced; execute the real CLI and Git preflight.
            bridge.write_text(f"#!{sys.executable}\n" + textwrap.dedent(f"""
                import importlib.util, json, sys
                from pathlib import Path
                spec = importlib.util.spec_from_file_location('validator_fixture', {str(SCRIPT_PATH)!r})
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                module.ROOT = Path({str(repo)!r})
                def acquire(*args, **kwargs):
                    Path({str(root / 'acquired.json')!r}).write_text(json.dumps(kwargs['verified_context']))
                    return [], {{'status':'PASS', 'fixture_only':True}}
                module.acquire_evidence = acquire
                raise SystemExit(module.main(sys.argv[2:]))
            """))
            bridge.chmod(0o700)
            env = dict(os.environ, PATH=str(bridge.parent) + os.pathsep + os.environ['PATH'],
                       RUNNER_TEMP=str(root), FORMAL_CANDIDATE_BASE=parent,
                       FORMAL_EVENT_TARGET_SHA=head, FORMAL_REPOSITORY=VALIDATOR.EXPECTED_REPOSITORY,
                       GITHUB_RUN_ID="12345", GITHUB_RUN_ATTEMPT="1", GITHUB_JOB="formal-schema-gate",
                       GITHUB_WORKFLOW_REF=VALIDATOR.EXPECTED_REPOSITORY + "/.github/workflows/check-skill.yml@refs/heads/main",
                       WORKFLOW_SHA256=VALIDATOR.sha256_file(WORKFLOW), PYTHONDONTWRITEBYTECODE="1")
            script = SchemaIntegrationTests().step("Acquire official evidence once")
            p = subprocess.run(["bash", "-e", "-c", script], cwd=repo, env=env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(0, p.returncode, p.stdout + p.stderr)
            acquired = json.loads((root / "acquired.json").read_text())
            self.assertEqual(head, acquired['release_commit'])
            self.assertEqual(parent, acquired['candidate_base'])

    def test_existing_evidence_directory_is_rejected_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="formal-preflight-existing-") as temp:
            root = Path(temp)
            provenance, head, parent = self._write_main_provenance(root)
            argv, evidence, receipt, result = self._run_verify_acquisition(root, provenance, head, parent, True)
            with mock.patch.object(VALIDATOR, "acquire_evidence") as acquire, mock.patch.object(VALIDATOR, "urlopen") as network:
                self.assertNotEqual(0, VALIDATOR.main(argv))
            acquire.assert_not_called(); network.assert_not_called(); self.assertTrue(evidence.exists()); self.assertFalse(receipt.exists()); self.assertFalse(result.exists())

    def test_workflow_identity_is_exact_and_fail_closed(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "formal-release-gate.yml"
        digest = VALIDATOR.sha256_file(workflow)
        identity = {
            "path": ".github/workflows/formal-release-gate.yml",
            "sha256": digest,
            "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/formal-release-gate.yml@refs/heads/main",
        }
        self.assertEqual([], VALIDATOR.validate_workflow_identity(identity))
        for field, value in (
            ("path", "wrong.yml"),
            ("sha256", "not-a-sha"),
            ("workflow_ref", ""),
        ):
            mutated = dict(identity)
            mutated[field] = value
            self.assertTrue(VALIDATOR.validate_workflow_identity(mutated))

    def test_action_provenance_file_is_closed_and_bound(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "formal-release-gate.yml"
        identity = {
            "path": ".github/workflows/formal-release-gate.yml",
            "sha256": VALIDATOR.sha256_file(workflow),
            "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/heads/main",
        }
        payload = {
            "github_run_id": "1", "github_run_attempt": "1", "workflow_ref": "workflow-ref",
            "job": "formal", "repository": "Q20396/codex-long-horizon-skill",
            "event_target_sha": "t", "release_commit": "c", "candidate_base": "b",
            "workflow_identity": identity, "actions": VALIDATOR.ACTION_PROVENANCE,
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runner-identity.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, actions, digest = VALIDATOR.load_action_provenance(path, identity)
            self.assertEqual([], errors)
            self.assertEqual(VALIDATOR.ACTION_PROVENANCE, actions)
            self.assertEqual(VALIDATOR.sha256_file(path), digest)
            for mutation in (
                {**payload, "actions": {"checkout": "x"}},
                {**payload, "actions": {**VALIDATOR.ACTION_PROVENANCE, "extra": "x"}},
                {**payload, "workflow_identity": {**identity, "sha256": "0" * 64}},
            ):
                path.write_text(json.dumps(mutation), encoding="utf-8")
                self.assertTrue(VALIDATOR.load_action_provenance(path, identity)[0])

    def test_action_provenance_binds_current_execution_context(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "check-skill.yml"
        identity = {
            "path": ".github/workflows/check-skill.yml",
            "sha256": VALIDATOR.sha256_file(workflow),
            "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/heads/main",
        }
        payload = {
            "github_run_id": "1", "github_run_attempt": "1",
            "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/heads/main", "job": "formal-schema-gate",
            "repository": "Q20396/codex-long-horizon-skill", "event_target_sha": "c" * 40,
            "release_commit": "c" * 40, "candidate_base": "b" * 40,
            "workflow_identity": identity, "actions": VALIDATOR.ACTION_PROVENANCE,
        }
        expected = {
            "github_run_id": "1", "github_run_attempt": "1",
            "workflow_ref": "Q20396/codex-long-horizon-skill/.github/workflows/check-skill.yml@refs/heads/main", "job": "formal-schema-gate",
            "repository": "Q20396/codex-long-horizon-skill", "event_target_sha": "c" * 40,
            "release_commit": "c" * 40, "candidate_base": "b" * 40,
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runner-identity.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(
                VALIDATOR.load_action_provenance(path, identity, expected)[0]
            )
            for field in expected:
                mutated = dict(expected)
                mutated[field] = "foreign"
                self.assertTrue(
                    VALIDATOR.load_action_provenance(path, identity, mutated)[0]
                )

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

    def test_online_session_uses_memory_only_token_for_github_api_only(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return "https://api.github.com/example"

            def read(self):
                return b'{"ok":true}'

        token = "unit-test-token-not-a-secret"
        with tempfile.TemporaryDirectory(prefix="formal-online-session-") as temp:
            evidence = Path(temp) / "evidence"
            with mock.patch.object(VALIDATOR, "urlopen", return_value=Response()) as call:
                session = VALIDATOR.OnlineEvidenceSession(evidence, github_token=token)
                self.assertEqual(
                    {"ok": True}, session.get_json("https://api.github.com/example")
                )
                request = call.call_args.args[0]
                self.assertEqual(f"Bearer {token}", request.get_header("Authorization"))
                manifest_path, _ = session.write_manifest()
                self.assertNotIn(token, manifest_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory(prefix="formal-online-session-") as temp:
            evidence = Path(temp) / "evidence"
            with mock.patch.object(VALIDATOR, "urlopen", return_value=Response()) as call:
                session = VALIDATOR.OnlineEvidenceSession(evidence, github_token=token)
                self.assertEqual({"ok": True}, session.get_json("https://pypi.org/example"))
                self.assertIsNone(call.call_args.args[0].get_header("Authorization"))

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
        for workflow_path in (WORKFLOW, FORMAL_RELEASE_WORKFLOW):
            text = workflow_path.read_text(encoding="utf-8")
            action_refs = []
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("uses: actions/"):
                    continue
                action, separator, reference = stripped[6:].partition("@")
                self.assertEqual("@", separator, workflow_path)
                self.assertIn(action, APPROVED_ACTIONS, workflow_path)
                self.assertRegex(reference, r"^[0-9a-f]{40}$", workflow_path)
                self.assertEqual(APPROVED_ACTIONS[action], reference, workflow_path)
                action_refs.append(action)

            self.assertEqual(
                set(APPROVED_ACTIONS), set(action_refs), workflow_path
            )
            for action in APPROVED_ACTIONS:
                self.assertGreaterEqual(action_refs.count(action), 1, workflow_path)

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
            repo = root / "repo"
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_") and key not in {"SSH_AUTH_SOCK", "SSH_AGENT_PID"}}
            env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_ALLOW_PROTOCOL="file", GIT_TERMINAL_PROMPT="0",
                       GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                       GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid")

            def git(*args, input=None):
                return subprocess.run(
                    ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                     "-c", f"safe.directory={ROOT}", *args],
                    cwd=repo if repo.exists() else root, env=env, input=input,
                    capture_output=True, text=True, check=True, timeout=30,
                ).stdout.strip()

            # Retain bootstrap objects, but commit current bytes only in this test-owned clone.
            git("clone", "--no-local", str(ROOT), str(repo))
            base = git("rev-parse", "HEAD")
            shutil.copytree(ROOT, repo, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.pyo"))
            (repo / "fixture-marker.txt").write_text("test-only schema fixture\n", encoding="utf-8")
            git("add", "--all")
            tree = git("write-tree")
            head = git("commit-tree", tree, "-p", base, input="test-only clean schema fixture\n")
            git("update-ref", "HEAD", head)
            self.assertEqual("", git("status", "--porcelain=v1"))
            self.assertEqual([head, base], git("rev-list", "--parents", "-n", "1", "HEAD").split())
            report = root / "pip-report.json"
            report.write_text(json.dumps(synthetic_pip_report()), encoding="utf-8")
            with (
                mock.patch.object(VALIDATOR, "ROOT", repo),
                mock.patch.object(VALIDATOR, "LOCK_PATH", repo / "requirements-release.txt"),
                mock.patch.object(
                    VALIDATOR,
                    "verify_acquisition",
                    return_value=([], {"packages": synthetic_packages()}),
                ),
            ):
                evidence_dir, acquisition, receipt = write_synthetic_evidence(root, report)
                binding_errors, binding = VALIDATOR.candidate_binding(base)
                self.assertEqual([], binding_errors)
                self.assertEqual(head, binding["commit"])
                receipt["candidate"] = binding
                acquisition.write_text(json.dumps(receipt), encoding="utf-8")
                errors, result = VALIDATOR.validate_formal(
                    report,
                    acquisition,
                    evidence_dir,
                    JOB_IDENTITY,
                    base,
                )
                self.assertEqual([], errors)
                self.assertEqual(head, result["candidate_commit"])
                self.assertTrue(result["candidate_worktree_clean"])
                self.assertEqual("", git("status", "--porcelain=v1"))
                print("FORMAL_ENGINE_CLEAN_FIXTURE=" + json.dumps({"head": head, "parent": base, "tree": tree, "clean": True}))
                (repo / "untracked-negative.txt").write_text("test-only dirty negative\n", encoding="utf-8")
                self.assertTrue(VALIDATOR.validate_clean_worktree())
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
        self.assertEqual(
            len(VALIDATOR.FIXTURE_VALIDATED_SCHEMAS),
            result["fixture_validated_schema_count"],
        )
        self.assertEqual(
            len(VALIDATOR.SYNTAX_ONLY_SCHEMAS),
            result["syntax_only_schema_count"],
        )


if __name__ == "__main__":
    unittest.main()
