#!/usr/bin/env python3
"""Run locked incubator checks and persist reproducible evidence outside the repo."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_NAMES = [
    "validate_candidate_intake.py",
    "validate_candidate_states.py",
    "validate_capability_families.py",
    "validate_proposal_evidence.py",
    "check_source_status_counts.py",
    "check_prohibited_content.py",
    "check_internal_links.py",
    "validate_schema_declarations.py",
]
RECORD_FIELDS = {
    "test_id",
    "command_argv",
    "command_display",
    "commit",
    "cwd",
    "started_at",
    "ended_at",
    "duration_ms",
    "exit_code",
    "status",
    "stdout_file",
    "stderr_file",
    "limitations",
}
STATUSES = {"passed", "failed", "skipped", "blocked", "blocked_not_installed", "warning"}
TIMEOUT_SECONDS = 180


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def validate_record(record: dict[str, Any]) -> list[str]:
    """Validate evidence structure without treating it as an execution grant."""
    errors: list[str] = []
    if set(record) != RECORD_FIELDS:
        errors.append("record fields do not match the evidence contract")
    argv = record.get("command_argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        errors.append("command_argv must be a non-empty list of non-empty strings")
    display = record.get("command_display")
    if not isinstance(display, str) or not display or "<...>" in display:
        errors.append("command_display must be readable and contain no placeholder")
    for field in ("stdout_file", "stderr_file"):
        value = record.get(field)
        if not isinstance(value, str) or not Path(value).is_file():
            errors.append(f"{field} must name an existing evidence file")
    status = record.get("status")
    exit_code = record.get("exit_code")
    if status not in STATUSES:
        errors.append(f"unknown status: {status!r}")
    if status == "passed" and exit_code != 0:
        errors.append("passed status requires exit_code 0")
    if status == "failed" and exit_code == 0:
        errors.append("failed status must not have exit_code 0")
    if status == "passed" and any("blocked" in str(item).lower() for item in record.get("limitations", [])):
        errors.append("blocked limitation cannot be recorded as passed")
    if not isinstance(record.get("limitations"), list):
        errors.append("limitations must be a list")
    return errors


def run(
    argv: list[str], cwd: Path, test_id: str, audit_root: Path, commit: str, limitations: list[str]
) -> dict[str, Any]:
    tests_dir = audit_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    started = now()
    start_ns = time.monotonic_ns()
    status = "failed"
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
        exit_code = result.returncode
        stdout, stderr = result.stdout, result.stderr
        status = "passed" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = _text(exc.stdout), _text(exc.stderr)
        stderr += f"\nTimed out after {TIMEOUT_SECONDS} seconds."
        status = "blocked"
        limitations = [*limitations, f"Timed out after {TIMEOUT_SECONDS} seconds; command was stopped without retry."]
    except OSError as exc:
        stderr = f"Unable to start command: {exc}\n"
        limitations = [*limitations, "Command could not be started in the local environment."]
    duration_ms = (time.monotonic_ns() - start_ns) // 1_000_000
    stdout_path = tests_dir / f"{test_id}.stdout.txt"
    stderr_path = tests_dir / f"{test_id}.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return {
        "test_id": test_id,
        "command_argv": argv,
        "command_display": shlex.join(argv),
        "commit": commit,
        "cwd": str(cwd),
        "started_at": started,
        "ended_at": now(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "status": status,
        "stdout_file": str(stdout_path),
        "stderr_file": str(stderr_path),
        "limitations": limitations,
    }


def append_record(handle: Any, record: dict[str, Any]) -> None:
    errors = validate_record(record)
    if errors:
        raise ValueError("invalid audit record: " + "; ".join(errors))
    handle.write(json.dumps(record, sort_keys=True) + "\n")
    handle.flush()


def formal_schema_probe(cwd: Path, audit_root: Path, commit: str) -> dict[str, Any]:
    record = run(
        [
            sys.executable,
            "-c",
            "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('jsonschema') is None else 1)",
        ],
        cwd,
        "formal-json-schema-engine",
        audit_root,
        commit,
        ["Draft 2020-12 engine execution is intentionally not performed; this probe only checks whether jsonschema is absent."],
    )
    if record["exit_code"] == 0:
        record["status"] = "blocked_not_installed"
    else:
        record["limitations"].append("Expected absent jsonschema module was unexpectedly available; formal engine execution remains disabled by this protocol.")
    return record


def root_commands(root: Path) -> list[tuple[str, list[str], list[str]]]:
    validation = root / "sandbox/skill-incubator/candidate-intake/validation"
    ruby_yaml = (
        "require 'yaml'; Dir['sandbox/skill-incubator/experiments/{MAD-SKILL-*,template}/promotion.yaml'].sort.each "
        "do |path|; data = YAML.safe_load(File.read(path), permitted_classes: [], aliases: false); abort(\"invalid YAML: #{path}\") "
        "unless data.is_a?(Hash); expected = File.basename(File.dirname(path)); if expected != 'template'; abort(\"ID mismatch: #{path}\") "
        "unless data['experiment_id'] == expected; abort(\"unsafe promotion state: #{path}\") unless data['status'] == 'locked' && "
        "data['execution_authorized'] == false && data['automatic_transition'] == false && data['customer_decision'] == 'not_approved'; end; end; puts 'PASS: parsed locked promotion YAML'"
    )
    return [
        ("root-package-check", [sys.executable, str(root / ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py")], []),
        ("root-doctor", [sys.executable, str(root / ".agents/skills/long-horizon-engineering/scripts/doctor.py")], []),
        ("root-trigger-fixtures", [sys.executable, str(root / ".agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py")], ["Static fixtures do not prove live model routing."]),
        ("root-safety-audit", [sys.executable, str(root / ".agents/skills/long-horizon-engineering/scripts/audit_skill_safety.py")], []),
        ("root-description-audit", [sys.executable, str(root / ".agents/skills/long-horizon-engineering/scripts/audit_skill_descriptions.py")], []),
        ("root-unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-p", "test_*.py"], []),
        ("root-catalog-check", [sys.executable, str(root / "scripts/generate_skill_catalog.py"), "--check"], []),
        ("root-plugin-check", [sys.executable, str(root / "scripts/validate_plugin_package.py")], []),
        ("root-release-readiness", [sys.executable, str(root / "scripts/check_release_readiness.py"), "--version", "0.2.1", "--allow-existing-tag"], ["Checks existing release metadata only; no tag or release is created."]),
        ("root-json-parse", [sys.executable, "-c", "import json, pathlib; [json.loads(path.read_text(encoding='utf-8')) for path in pathlib.Path('sandbox/skill-incubator').rglob('*.json')]; print('PASS: parsed incubator JSON')"], []),
        ("root-yaml-semantic", ["ruby", "-e", ruby_yaml], ["Uses the operating system Ruby standard YAML library; no dependency is installed or added."]),
        ("root-full-skill-validation", [sys.executable, str(root / "scripts/full_skill_validation.py")], ["Optional scaffold warnings, if any, remain warnings and are recorded verbatim."]),
        ("root-diff-check", ["git", "-C", str(root), "diff", "--check"], []),
        ("incubator-executable-secret-installer-scan", [sys.executable, str(validation / "check_prohibited_content.py"), "--root", str(root)], ["Static scan checks the incubator only; it does not inspect customer worktrees."]),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True, help="Explicit external evidence directory; never defaults inside the repository.")
    parser.add_argument("--include-root", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    audit_root = args.audit_root.resolve()
    if root in audit_root.parents or audit_root == root:
        parser.error("--audit-root must be outside --root")
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    audit_root.mkdir(parents=True, exist_ok=True)
    validation = root / "sandbox/skill-incubator/candidate-intake/validation"
    commands = [
        (f"incubator-{script[:-3]}", [sys.executable, str(validation / script), "--root", str(root)], [])
        for script in SCRIPT_NAMES
    ]
    commands.append(("incubator-unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", str(validation), "-p", "test_*.py"], []))
    if args.include_root:
        commands.extend(root_commands(root))
    records: list[dict[str, Any]] = []
    with (audit_root / "test-runs.jsonl").open("w", encoding="utf-8") as handle:
        for test_id, command, limitations in commands:
            record = run(command, root, test_id, audit_root, commit, limitations)
            append_record(handle, record)
            records.append(record)
        formal = formal_schema_probe(root, audit_root, commit)
        append_record(handle, formal)
        records.append(formal)
    failures = [record for record in records if record["status"] == "failed"]
    blocked = [record for record in records if record["status"].startswith("blocked")]
    print(json.dumps({"passed": len(records) - len(failures) - len(blocked), "failed": len(failures), "blocked": len(blocked), "audit_root": str(audit_root)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
