#!/usr/bin/env python3
"""Check deterministic release-readiness gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
STABLE_RELEASE_VERSION = "0.6.0"
RELEASE_DATE_RE = re.compile(r"^Release date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
RELEASE_STATE_CONTRACTS = {
    "candidate": {
        "marketplace_installation": "NOT_AVAILABLE",
        "update_channel": "candidate",
        "channel": "candidate",
        "released": False,
        "risk": "not-assessed",
    },
    "final": {
        "marketplace_installation": "AVAILABLE",
        "update_channel": "stable",
        "channel": "stable",
        "released": True,
        "risk": "reviewed",
    },
}

STALE_RELEASE_MARKERS = [
    "prepared, not released",
    "not yet released",
    "no git tag has been published",
    "no tag has been created",
    "no github release has been published",
    "release should happen only after",
    "do not publish yet",
    "ready for a future release",
]

REQUIRED_RELEASE_FILES = [
    Path("requirements-release.txt"),
    Path("scripts/validate_formal_schemas.py"),
    Path("scripts/validate_plugin_package.py"),
    Path("scripts/test_fresh_install.py"),
    Path("scripts/full_skill_validation.py"),
    Path("scripts/check_release_readiness.py"),
    Path("tests/test_release_tooling.py"),
    Path("tests/test_formal_schema_validation.py"),
    Path("tests/expected-triggers.json"),
    Path(".agents/plugins/marketplace.json"),
]
FORMAL_SCHEMA_ARTIFACTS = [
    {
        "name": "attrs",
        "version": "26.1.0",
        "wheel": "attrs-26.1.0-py3-none-any.whl",
        "sha256": "c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309",
    },
    {
        "name": "jsonschema",
        "version": "4.26.0",
        "wheel": "jsonschema-4.26.0-py3-none-any.whl",
        "sha256": "d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce",
    },
    {
        "name": "jsonschema-specifications",
        "version": "2025.9.1",
        "wheel": "jsonschema_specifications-2025.9.1-py3-none-any.whl",
        "sha256": "98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe",
    },
    {
        "name": "referencing",
        "version": "0.37.0",
        "wheel": "referencing-0.37.0-py3-none-any.whl",
        "sha256": "381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231",
    },
    {
        "name": "rpds-py",
        "version": "2026.6.3",
        "wheel": "rpds_py-2026.6.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "sha256": "9c1255b302953c86a486b81d330d5ee1d5bd937691ce271b6be0ef0e299eaab7",
    },
    {
        "name": "typing-extensions",
        "version": "4.16.0",
        "wheel": "typing_extensions-4.16.0-py3-none-any.whl",
        "sha256": "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
    },
]
FORMAL_BOOTSTRAP_PARENT = "6f1f48381f465b460a9390643fc835b666604207"
FORMAL_BOOTSTRAP_COMMIT = "5f8540db1994839ad644b8fa3203642d82c1d581"
FORMAL_BOOTSTRAP_TREE = "9b13edb16d90db0d5f69a252bfebe69fa2c10d04"
FORMAL_REMEDIATION_BASELINE_REFERENCE = "cf74dd05fa805f2f369c563e3974bc942f29c7cc"
FORMAL_BOOTSTRAP_PATHS = [
    ".github/workflows/check-skill.yml",
    "docs/maintainers/release-checklist.md",
    "docs/releases/v0.3.0.md",
    "requirements-release.txt",
    "scripts/check_release_readiness.py",
    "scripts/validate_formal_schemas.py",
    "tests/test_formal_schema_validation.py",
    "tests/test_release_tooling.py",
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.relative_to(ROOT)} is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate deterministic release-readiness requirements. "
            "Default mode is --allow-existing-tag for post-release-safe routine CI."
        )
    )
    parser.add_argument("--version", required=True, help="Release version, for example 0.1.0.")
    parser.add_argument(
        "--release-state",
        choices=sorted(RELEASE_STATE_CONTRACTS),
        default="candidate",
        help=(
            "Expected release metadata state. 'candidate' is required for "
            "--pre-tag-static; 'final' is checked only as static consistency "
            "unless controlled formal inputs are also supplied."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--pre-tag-static",
        action="store_true",
        help=(
            "Phase A local/no-network gate; validates static candidate evidence "
            "but leaves formal Draft 2020-12 validation UNVERIFIED."
        ),
    )
    mode.add_argument(
        "--pre-tag",
        action="store_true",
        help=(
            "Reserved Phase B gate before tagging; requires separately approved "
            "formal Draft 2020-12 validation."
        ),
    )
    mode.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Routine CI mode; validates artifacts without caring whether the local tag exists.",
    )
    parser.add_argument(
        "--formal-schema-result",
        type=Path,
        help=(
            "New temporary output path for a controlled validate_formal_schemas.py "
            "execution. A pre-existing receipt is rejected."
        ),
    )
    parser.add_argument(
        "--formal-schema-pip-report",
        type=Path,
        help="Temporary pip --report input for the controlled formal execution.",
    )
    parser.add_argument(
        "--formal-schema-acquisition-result",
        type=Path,
        help=(
            "Job-local acquisition receipt replayed by the formal validator "
            "without a second network acquisition."
        ),
    )
    parser.add_argument(
        "--formal-schema-evidence-dir",
        type=Path,
        help="Job-local raw evidence directory for offline formal validation.",
    )
    parser.add_argument(
        "--formal-schema-candidate-base",
        help="Full immutable base commit for the current descendant candidate.",
    )
    parser.add_argument(
        "--release-hygiene-base",
        help=(
            "Full immutable local origin/main commit for an isolated, clean "
            "release-preparation worktree. Valid only with --pre-tag-static."
        ),
    )
    return parser.parse_args()


def release_notes_errors(
    version: str,
    release_state: str,
    errors: list[str],
) -> str | None:
    release_notes = ROOT / "docs" / "releases" / f"v{version}.md"
    if not release_notes.is_file():
        errors.append(f"release notes missing: docs/releases/v{version}.md")
        return None

    try:
        text = release_notes.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"release notes are not valid UTF-8: docs/releases/v{version}.md")
        return None

    lowered = text.lower()
    required_any = [
        ("requested version", [version, f"v{version}"]),
        ("long-horizon engineering", ["long-horizon-engineering", "long-horizon engineering"]),
        ("AI video production", ["ai-video-production", "ai video production"]),
        ("Codex plugin", ["codex plugin"]),
        ("repository marketplace", ["repository marketplace", "git-backed marketplace"]),
        ("validation or installation verification", ["validation", "installation", "install gate"]),
    ]
    for label, options in required_any:
        if not any(option.lower() in lowered for option in options):
            errors.append(f"release notes missing expected topic: {label}")

    for marker in STALE_RELEASE_MARKERS:
        if marker in lowered:
            errors.append(f"release notes contain stale preparation marker: {marker}")

    state_match = re.search(
        r"^Release state:\s*(candidate|final)\s*$",
        text,
        re.MULTILINE,
    )
    if not state_match:
        errors.append("release notes missing Release state: candidate|final")
    elif state_match.group(1) != release_state:
        errors.append(
            f"release notes state {state_match.group(1)!r} does not match "
            f"{release_state!r}"
        )

    match = RELEASE_DATE_RE.search(text)
    if not match:
        errors.append("release notes missing Release date: YYYY-MM-DD")
        return None
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        errors.append("release notes have invalid Release date: YYYY-MM-DD")
        return None
    return match.group(1)


def extract_markdown_section(text: str, heading: str) -> str | None:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def changelog_errors(version: str, release_date: str | None, errors: list[str]) -> None:
    if release_date is None:
        return
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        errors.append("CHANGELOG.md missing")
        return
    try:
        text = changelog.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("CHANGELOG.md is not valid UTF-8")
        return

    heading = f"{version} - {release_date}"
    versioned = extract_markdown_section(text, heading)
    if versioned is None:
        errors.append(f"CHANGELOG missing dated version section: ## {heading}")
        return
    if not versioned.strip():
        errors.append(f"CHANGELOG version section is empty: ## {heading}")

    unreleased = extract_markdown_section(text, "Unreleased") or ""
    unreleased_lines = {
        line.strip()
        for line in unreleased.splitlines()
        if line.strip()
        and line.strip().lower() != "no unreleased changes."
        and len(line.strip()) > 20
    }
    versioned_lines = {
        line.strip()
        for line in versioned.splitlines()
        if line.strip() and len(line.strip()) > 20
    }
    duplicated = sorted(unreleased_lines & versioned_lines)
    if duplicated:
        errors.append(
            "CHANGELOG duplicates release content under Unreleased: "
            + "; ".join(duplicated[:3])
        )


def skill_version(path: Path, errors: list[str]) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path.relative_to(ROOT)} could not be read: {exc}")
        return None
    match = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
    if not match:
        errors.append(f"{path.relative_to(ROOT)} is missing version metadata")
        return None
    return match.group(1)


def package_errors(
    version: str,
    release_date: str | None,
    release_state: str,
    errors: list[str],
) -> None:
    expected_state = RELEASE_STATE_CONTRACTS[release_state]
    selector_version = STABLE_RELEASE_VERSION if release_state == "candidate" else version
    selector_state = (
        RELEASE_STATE_CONTRACTS["final"]
        if release_state == "candidate"
        else expected_state
    )
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        errors.append(".codex-plugin/plugin.json missing")
    else:
        manifest = load_json(manifest_path)
        if manifest.get("version") != version:
            errors.append(f"plugin version {manifest.get('version')!r} does not match {version!r}")

    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    if not marketplace_path.is_file():
        errors.append(".agents/plugins/marketplace.json missing")
    else:
        marketplace = load_json(marketplace_path)
        plugins = marketplace.get("plugins")
        ref = None
        if isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict):
            source = plugins[0].get("source")
            if isinstance(source, dict):
                ref = source.get("ref")
            policy = plugins[0].get("policy")
            installation = (
                policy.get("installation") if isinstance(policy, dict) else None
            )
            expected_installation = selector_state["marketplace_installation"]
            if installation != expected_installation:
                errors.append(
                    "marketplace policy.installation "
                    f"must be {expected_installation!r} for release state "
                    f"{release_state!r}"
                )
        expected_ref = f"v{selector_version}"
        if ref != expected_ref:
            errors.append(
                f"marketplace source ref {ref!r} does not match "
                f"immutable release tag {expected_ref!r}"
            )

    for skill_name in ["long-horizon-engineering", "ai-video-production"]:
        path = ROOT / ".agents" / "skills" / skill_name / "SKILL.md"
        actual = skill_version(path, errors)
        if actual is not None and actual != version:
            errors.append(
                f"{skill_name}/SKILL.md version {actual!r} does not match {version!r}"
            )
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        expected_channel = expected_state["update_channel"]
        if not re.search(
            rf"^update_channel:\s*{re.escape(str(expected_channel))}\s*$",
            text,
            re.MULTILINE,
        ):
            errors.append(
                f"{skill_name}/SKILL.md must declare update_channel: "
                f"{expected_channel} for release state {release_state!r}"
            )

    release_manifests = [
        ROOT / "releases" / "long-horizon-engineering" / "latest.json",
        ROOT / "releases" / "ai-video-production" / "latest.json",
    ]
    for path in release_manifests:
        data = load_json(path)
        relative = path.relative_to(ROOT)
        if data.get("version") != selector_version:
            errors.append(
                f"{relative} version {data.get('version')!r} does not match {selector_version!r}"
            )
        if release_state == "final" and release_date is not None and data.get("release_date") != release_date:
            errors.append(
                f"{relative} release_date {data.get('release_date')!r} "
                f"does not match {release_date!r}"
            )
        if (
            data.get("channel") != selector_state["channel"]
            or data.get("released") is not selector_state["released"]
        ):
            errors.append(
                f"{relative} must describe release state {release_state!r} "
                f"with channel {selector_state['channel']!r} and released "
                f"{selector_state['released']!r}"
            )
        if data.get("risk") != selector_state["risk"]:
            errors.append(
                f"{relative} risk must be {selector_state['risk']!r} for "
                f"release state {release_state!r}"
            )

    latest = load_json(ROOT / "releases" / "latest.json")
    if (
        latest.get("channel") != selector_state["channel"]
        or latest.get("released") is not selector_state["released"]
    ):
        errors.append(
            "releases/latest.json must describe release state "
            f"{release_state!r} with channel {selector_state['channel']!r} "
            f"and released {selector_state['released']!r}"
        )
    if release_state == "final" and release_date is not None and latest.get("updated_at") != release_date:
        errors.append(
            f"releases/latest.json updated_at {latest.get('updated_at')!r} "
            f"does not match {release_date!r}"
        )
    skills = latest.get("skills")
    if not isinstance(skills, dict):
        errors.append("releases/latest.json skills must be an object")
    else:
        for skill_name in ["long-horizon-engineering", "ai-video-production"]:
            entry = skills.get(skill_name)
            actual = entry.get("version") if isinstance(entry, dict) else None
            if actual != selector_version:
                errors.append(
                    f"releases/latest.json {skill_name} version {actual!r} "
                    f"does not match {selector_version!r}"
                )

    for path in REQUIRED_RELEASE_FILES:
        if not (ROOT / path).is_file():
            errors.append(f"required release-readiness file missing: {path}")

    validator = run(["python3", "scripts/validate_plugin_package.py"])
    if validator.returncode != 0:
        output = (validator.stdout + validator.stderr).strip()
        if "Traceback" in output:
            output = "validator returned an internal error; inspect malformed release inputs"
        errors.append("plugin package validation failed: " + output)


def tag_errors(version: str, pre_tag: bool, errors: list[str]) -> None:
    if not pre_tag:
        return
    tag = f"v{version}"
    tag_result = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"])
    if tag_result.returncode == 0:
        errors.append(f"local tag already exists; cannot run pre-tag gate for {tag}")


def formal_worktree_errors(errors: list[str]) -> None:
    status = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if status.returncode != 0:
        errors.append("formal gate could not verify clean candidate git state")
    elif status.stdout.strip():
        errors.append(
            "formal gate requires a clean candidate worktree; "
            "staged, unstaged, and untracked paths are forbidden"
        )


def release_history_errors(errors: list[str]) -> None:
    """Require archival evidence objects for a formal release-grade gate."""
    environment = os.environ.copy()
    environment["LHE_HISTORY_VALIDATION_MODE"] = "release"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_local_first_high_stakes_contracts."
            "LocalFirstHighStakesContractTests."
            "test_candidate_slice_manifest_is_exact_and_selectors_resolve",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        errors.append(
            "release-grade historical validation failed: "
            + (output or "HISTORY_UNAVAILABLE")
        )


def release_hygiene_errors(expected_base: str | None, errors: list[str]) -> None:
    if expected_base is None:
        return
    if not re.fullmatch(r"[0-9a-f]{40}", expected_base):
        errors.append("release hygiene base must be a full commit SHA")
        return

    commands = {
        "base": ["git", "rev-parse", f"{expected_base}^{{commit}}"],
        "origin_main": [
            "git",
            "rev-parse",
            "refs/remotes/origin/main^{commit}",
        ],
        "merge_base": ["git", "merge-base", expected_base, "HEAD"],
        "status": ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        "git_dir": [
            "git",
            "rev-parse",
            "--path-format=absolute",
            "--git-dir",
        ],
        "common_dir": [
            "git",
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
    }
    results = {name: run(command) for name, command in commands.items()}
    if any(result.returncode != 0 for result in results.values()):
        errors.append("release hygiene could not verify repository identity")
        return
    if results["base"].stdout.strip() != expected_base:
        errors.append("release hygiene base does not resolve to the expected commit")
    if results["origin_main"].stdout.strip() != expected_base:
        errors.append("release hygiene base does not match local origin/main")
    if results["merge_base"].stdout.strip() != expected_base:
        errors.append("release candidate is not based on the recorded origin/main commit")
    if results["status"].stdout.strip():
        errors.append(
            "release hygiene requires a clean worktree; staged, unstaged, "
            "and untracked paths are forbidden"
        )
    if results["git_dir"].stdout.strip() == results["common_dir"].stdout.strip():
        errors.append("release hygiene requires an isolated linked worktree")


def formal_schema_errors(args: argparse.Namespace, errors: list[str]) -> None:
    paths = {
        "--formal-schema-result": args.formal_schema_result,
        "--formal-schema-pip-report": args.formal_schema_pip_report,
        "--formal-schema-acquisition-result": args.formal_schema_acquisition_result,
        "--formal-schema-evidence-dir": args.formal_schema_evidence_dir,
        "--formal-schema-candidate-base": args.formal_schema_candidate_base,
    }
    supplied = {name for name, value in paths.items() if value is not None}
    if args.pre_tag_static:
        if supplied:
            errors.append("formal schema inputs are forbidden with --pre-tag-static")
        return
    if not supplied and not args.pre_tag:
        return
    missing = [name for name, value in paths.items() if value is None]
    if missing:
        errors.append(
            "formal Draft 2020-12 schema gate is UNVERIFIED; "
            f"controlled formal execution requires {', '.join(missing)}"
        )
        return
    if not re.fullmatch(r"[0-9a-f]{40}", args.formal_schema_candidate_base):
        errors.append("formal schema candidate base must be a full commit SHA")
        return
    formal_worktree_errors(errors)
    if errors:
        return
    path = args.formal_schema_result.resolve()
    if path.exists():
        errors.append(
            "formal schema result output already exists; prewritten PASS receipts "
            "are not accepted"
        )
        return
    release_history_errors(errors)
    if errors:
        return
    command = [
        sys.executable,
        "scripts/validate_formal_schemas.py",
        "--formal",
        "--pip-report",
        str(args.formal_schema_pip_report.resolve()),
        "--acquisition-result",
        str(args.formal_schema_acquisition_result.resolve()),
        "--evidence-dir",
        str(args.formal_schema_evidence_dir.resolve()),
        "--candidate-base",
        args.formal_schema_candidate_base,
        "--run-id",
        os.environ.get("GITHUB_RUN_ID", ""),
        "--run-attempt",
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "--workflow-ref",
        os.environ.get("GITHUB_WORKFLOW_REF", ""),
        "--job-name",
        os.environ.get("GITHUB_JOB", ""),
        "--result",
        str(path),
    ]
    execution = run(command)
    if execution.returncode != 0:
        output = (execution.stdout + execution.stderr).strip()
        errors.append(
            "controlled formal Draft 2020-12 execution failed: "
            + (output or "validator returned no diagnostic")
        )
        return
    try:
        result = load_json(path)
    except (OSError, ValueError) as exc:
        errors.append(f"formal schema result could not be validated: {exc}")
        return
    expected = {
        "status": "PASS",
        "gate": "formal-draft-2020-12",
        "draft": "https://json-schema.org/draft/2020-12/schema",
        "system": "Linux",
        "machine": "x86_64",
        "candidate_worktree_clean": True,
        "candidate_base_commit": args.formal_schema_candidate_base,
        "candidate_merge_base": args.formal_schema_candidate_base,
        "approval_authority": "none",
        "next_stage_authorized": False,
        "bootstrap_identity": {
            "commit": FORMAL_BOOTSTRAP_COMMIT,
            "tree": FORMAL_BOOTSTRAP_TREE,
            "parent": FORMAL_BOOTSTRAP_PARENT,
            "remediation_baseline_reference": FORMAL_REMEDIATION_BASELINE_REFERENCE,
            "paths": sorted(FORMAL_BOOTSTRAP_PATHS),
            "authority": "provenance-only",
        },
    }
    for field, value in expected.items():
        if result.get(field) != value:
            errors.append(
                f"formal schema result {field} {result.get(field)!r} "
                f"does not match {value!r}"
            )
    python_version = result.get("python_version")
    if not isinstance(python_version, str) or not python_version.startswith("3.11."):
        errors.append("formal schema result must record an exact CPython 3.11 patch")
    artifacts = result.get("artifacts")
    if artifacts != FORMAL_SCHEMA_ARTIFACTS:
        errors.append("formal schema result does not match the six locked artifacts")
    expected_hashes = {
        "validator_sha256": sha256_file(ROOT / "scripts/validate_formal_schemas.py"),
        "lock_sha256": sha256_file(ROOT / "requirements-release.txt"),
        "pip_report_sha256": sha256_file(args.formal_schema_pip_report.resolve()),
        "acquisition_receipt_sha256": sha256_file(
            args.formal_schema_acquisition_result.resolve()
        ),
        "raw_evidence_manifest_sha256": sha256_file(
            args.formal_schema_evidence_dir.resolve() / "manifest.json"
        ),
    }
    for field, value in expected_hashes.items():
        if result.get(field) != value:
            errors.append(f"formal schema result {field} does not match candidate files")
    schema_binding = result.get("schema_inventory_binding")
    schema_root = ROOT / "sandbox" / "skill-incubator" / "schemas"
    schema_files = sorted(schema_root.glob("*.schema.json"))
    if not isinstance(schema_binding, dict):
        errors.append("formal schema result schema inventory binding is missing")
    else:
        recorded_files = schema_binding.get("files")
        if not isinstance(recorded_files, list):
            errors.append("formal schema result schema inventory files are invalid")
        else:
            actual_schema_files = [
                {
                    "name": schema_path.name,
                    "sha256": sha256_file(schema_path),
                    "validation": next(
                        (
                            item.get("validation")
                            for item in recorded_files
                            if isinstance(item, dict)
                            and item.get("name") == schema_path.name
                        ),
                        None,
                    ),
                }
                for schema_path in schema_files
            ]
            if recorded_files != actual_schema_files:
                errors.append("formal schema result schema inventory file binding mismatch")
            validation_values = [
                item.get("validation")
                for item in actual_schema_files
                if isinstance(item, dict)
            ]
            if any(
                value not in {"fixture-validated", "syntax-only"}
                for value in validation_values
            ):
                errors.append("formal schema result schema classification is invalid")
            fixture_count = validation_values.count("fixture-validated")
            syntax_count = validation_values.count("syntax-only")
            if (
                result.get("schema_count") != len(actual_schema_files)
                or result.get("fixture_validated_schema_count") != fixture_count
                or result.get("syntax_only_schema_count") != syntax_count
                or schema_binding.get("schema_count") != len(actual_schema_files)
                or schema_binding.get("fixture_validated_schema_count") != fixture_count
                or schema_binding.get("syntax_only_schema_count") != syntax_count
            ):
                errors.append("formal schema result schema classification counts mismatch")
            inventory_sha256 = hashlib.sha256(
                json.dumps(
                    actual_schema_files,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            if schema_binding.get("inventory_sha256") != inventory_sha256:
                errors.append("formal schema result schema inventory hash mismatch")
    try:
        head = run(["git", "rev-parse", "HEAD"])
        tree = run(["git", "show", "-s", "--format=%T", "HEAD"])
    except OSError as exc:
        errors.append(f"could not bind formal schema result to git state: {exc}")
        return
    if head.returncode != 0 or tree.returncode != 0:
        errors.append("could not bind formal schema result to git state")
        return
    if result.get("candidate_commit") != head.stdout.strip():
        errors.append("formal schema result candidate_commit does not match HEAD")
    if result.get("candidate_tree") != tree.stdout.strip():
        errors.append("formal schema result candidate_tree does not match HEAD tree")
    bootstrap_commit = run(["git", "rev-parse", f"{FORMAL_BOOTSTRAP_COMMIT}^{{commit}}"])
    bootstrap_tree = run(
        ["git", "show", "-s", "--format=%T", FORMAL_BOOTSTRAP_COMMIT]
    )
    bootstrap_parent = run(["git", "rev-parse", f"{FORMAL_BOOTSTRAP_COMMIT}^"])
    bootstrap_paths = run(
        [
            "git",
            "diff",
            "--name-only",
            f"{FORMAL_BOOTSTRAP_PARENT}..{FORMAL_BOOTSTRAP_COMMIT}",
        ]
    )
    if (
        bootstrap_commit.returncode != 0
        or bootstrap_commit.stdout.strip() != FORMAL_BOOTSTRAP_COMMIT
        or bootstrap_tree.returncode != 0
        or bootstrap_tree.stdout.strip() != FORMAL_BOOTSTRAP_TREE
        or bootstrap_parent.returncode != 0
        or bootstrap_parent.stdout.strip() != FORMAL_BOOTSTRAP_PARENT
        or bootstrap_paths.returncode != 0
        or sorted(bootstrap_paths.stdout.splitlines())
        != sorted(FORMAL_BOOTSTRAP_PATHS)
    ):
        errors.append("formal schema bootstrap provenance mismatch")
    base = run(
        [
            "git",
            "rev-parse",
            f"{args.formal_schema_candidate_base}^{{commit}}",
        ]
    )
    merge_base = run(
        ["git", "merge-base", args.formal_schema_candidate_base, "HEAD"]
    )
    parents = run(["git", "show", "-s", "--format=%P", "HEAD"])
    paths_result = run(
        [
            "git",
            "diff",
            "--name-only",
            f"{args.formal_schema_candidate_base}..HEAD",
        ]
    )
    diff_result = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            f"{args.formal_schema_candidate_base}..HEAD",
            "--",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if (
        base.returncode != 0
        or base.stdout.strip() != args.formal_schema_candidate_base
        or merge_base.returncode != 0
        or merge_base.stdout.strip() != args.formal_schema_candidate_base
    ):
        errors.append("formal schema result candidate base or merge-base mismatch")
    actual_paths = sorted(path for path in paths_result.stdout.splitlines() if path)
    if paths_result.returncode != 0 or not actual_paths:
        errors.append("formal schema result changed-path inventory is invalid")
    if result.get("candidate_changed_paths") != actual_paths:
        errors.append("formal schema result changed-path inventory mismatch")
    actual_paths_sha256 = hashlib.sha256(
        json.dumps(
            actual_paths,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if result.get("candidate_changed_paths_sha256") != actual_paths_sha256:
        errors.append("formal schema result changed-path hash mismatch")
    actual_parents = parents.stdout.split()
    if parents.returncode != 0 or result.get("candidate_parents") != actual_parents:
        errors.append("formal schema result candidate parents mismatch")
    actual_diff_sha256 = hashlib.sha256(diff_result.stdout).hexdigest()
    if (
        diff_result.returncode != 0
        or result.get("candidate_diff_sha256") != actual_diff_sha256
    ):
        errors.append("formal schema result candidate diff hash mismatch")
    expected_job_identity = {
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF", ""),
        "job_name": os.environ.get("GITHUB_JOB", ""),
    }
    if result.get("job_identity") != expected_job_identity:
        errors.append("formal schema result job identity mismatch")
    formal_worktree_errors(errors)


def validate(args: argparse.Namespace) -> list[str]:
    version = args.version
    errors: list[str] = []

    if not SEMVER_RE.match(version):
        errors.append("version must be plain semantic version syntax")
        return errors

    release_date = release_notes_errors(version, args.release_state, errors)
    package_errors(version, release_date, args.release_state, errors)
    changelog_errors(version, release_date, errors)
    tag_errors(version, args.pre_tag, errors)
    if args.release_state == "final" and args.pre_tag_static:
        errors.append(
            "final release state is forbidden with --pre-tag-static; "
            "controlled formal or post-tag-safe validation is required"
        )
    if args.release_hygiene_base is not None and not args.pre_tag_static:
        errors.append("release hygiene base is valid only with --pre-tag-static")
    else:
        release_hygiene_errors(args.release_hygiene_base, errors)
    formal_schema_errors(args, errors)
    return errors


def main() -> int:
    args = parse_args()
    if args.pre_tag_static:
        mode = "pre-tag-static"
    elif args.pre_tag:
        mode = "pre-tag"
    else:
        mode = "allow-existing-tag"
    try:
        errors = validate(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.pre_tag_static:
        print(
            f"Static candidate check passed for v{args.version} ({mode}); "
            "formal Draft 2020-12 schema validation is UNVERIFIED and "
            "this result is not release-ready."
        )
    elif (
        args.release_state == "final"
        and not args.formal_schema_result
        and not args.formal_schema_pip_report
        and not args.formal_schema_acquisition_result
        and not args.formal_schema_evidence_dir
        and not args.formal_schema_candidate_base
    ):
        print(
            f"Final release-state consistency passed for v{args.version} ({mode}); "
            "formal and post-tag evidence remain required and this result alone "
            "is not release-ready."
        )
    else:
        print(
            f"Release readiness check passed for v{args.version} ({mode}, "
            f"release-state={args.release_state})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
