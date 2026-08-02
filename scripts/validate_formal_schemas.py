#!/usr/bin/env python3
"""Validate the locked v0.3.0 Draft 2020-12 release gate."""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "requirements-release.txt"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
BOOTSTRAP_PARENT = "6f1f48381f465b460a9390643fc835b666604207"
BOOTSTRAP_COMMIT = "5f8540db1994839ad644b8fa3203642d82c1d581"
BOOTSTRAP_TREE = "9b13edb16d90db0d5f69a252bfebe69fa2c10d04"
TARGET_PYTHON = (3, 11)
TARGET_SYSTEM = "Linux"
TARGET_MACHINE = "x86_64"
REMEDIATION_BASELINE_REFERENCE = "cf74dd05fa805f2f369c563e3974bc942f29c7cc"
BOOTSTRAP_PATHS = (
    ".github/workflows/check-skill.yml",
    "docs/maintainers/release-checklist.md",
    "docs/releases/v0.3.0.md",
    "requirements-release.txt",
    "scripts/check_release_readiness.py",
    "scripts/validate_formal_schemas.py",
    "tests/test_formal_schema_validation.py",
    "tests/test_release_tooling.py",
)
APPROVED_METADATA_HOSTS = {"api.github.com", "api.osv.dev", "pypi.org"}
MAX_RECEIPT_AGE = timedelta(minutes=20)


@dataclass(frozen=True)
class Distribution:
    name: str
    version: str
    wheel: str
    sha256: str
    requires_python: str
    license_expression: str
    source_repo: str
    source_tag: str
    source_commit: str
    license_path: str
    license_blob: str
    publisher_repository: str
    publisher_workflow: str
    publisher_environment: str


DISTRIBUTIONS = (
    Distribution(
        "jsonschema",
        "4.26.0",
        "jsonschema-4.26.0-py3-none-any.whl",
        "d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce",
        ">=3.10",
        "MIT",
        "python-jsonschema/jsonschema",
        "v4.26.0",
        "a7277432b0f7bcd0551f6e589d30457017125df4",
        "COPYING",
        "af9cfbdb134f42e5205ecbad597421d778826481",
        "python-jsonschema/jsonschema",
        "ci.yml",
        "pypi",
    ),
    Distribution(
        "attrs",
        "26.1.0",
        "attrs-26.1.0-py3-none-any.whl",
        "c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309",
        ">=3.9",
        "MIT",
        "python-attrs/attrs",
        "26.1.0",
        "7bfc49e9b22d5ba25b6e429524c3d49fee27cb36",
        "LICENSE",
        "2bd6453d255e19b973f19b128596a8b6dd65b2c3",
        "python-attrs/attrs",
        "pypi-package.yml",
        "release-pypi",
    ),
    Distribution(
        "jsonschema-specifications",
        "2025.9.1",
        "jsonschema_specifications-2025.9.1-py3-none-any.whl",
        "98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe",
        ">=3.9",
        "MIT",
        "python-jsonschema/jsonschema-specifications",
        "v2025.9.1",
        "3b846010c34ce254d8ced23023451d1d64de37f5",
        "COPYING",
        "a9f853e43069b8e3f8a156a4af2b1198a004230d",
        "python-jsonschema/jsonschema-specifications",
        "ci.yml",
        "pypi",
    ),
    Distribution(
        "referencing",
        "0.37.0",
        "referencing-0.37.0-py3-none-any.whl",
        "381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231",
        ">=3.10",
        "MIT",
        "python-jsonschema/referencing",
        "v0.37.0",
        "944ed5a20bc5125f2349156cbdc365daac0e67e6",
        "COPYING",
        "a9f853e43069b8e3f8a156a4af2b1198a004230d",
        "python-jsonschema/referencing",
        "ci.yml",
        "pypi",
    ),
    Distribution(
        "rpds-py",
        "2026.6.3",
        "rpds_py-2026.6.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "9c1255b302953c86a486b81d330d5ee1d5bd937691ce271b6be0ef0e299eaab7",
        ">=3.11",
        "MIT",
        "crate-py/rpds",
        "v2026.6.3",
        "7277eb681f6efd67eca1bbaa32f78d78bdc044a5",
        "LICENSE",
        "119a1f205aa85f584e0dbc04d7b34deaebe9199d",
        "crate-py/rpds",
        "CI.yml",
        "pypi",
    ),
    Distribution(
        "typing-extensions",
        "4.16.0",
        "typing_extensions-4.16.0-py3-none-any.whl",
        "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
        ">=3.9",
        "PSF-2.0",
        "python/typing_extensions",
        "4.16.0",
        "f29cd28d8ed7642cafb1d18daf5aa41be6a5c0aa",
        "LICENSE",
        "f26bcf4d2de6eb136e31006ca3ab447d5e488adf",
        "python/typing_extensions",
        "publish.yml",
        "publish",
    ),
)

SCHEMA_INVENTORY = (
    "base-experiment-contract.schema.json",
    "candidate-pattern.schema.json",
    "candidate-state.schema.json",
    "capability-descriptor.schema.json",
    "capability-profile-doctor.schema.json",
    "capability-family.schema.json",
    "calculation-receipt.schema.json",
    "claim-record.schema.json",
    "decision-record.schema.json",
    "deduplication-record.schema.json",
    "evaluation-run.schema.json",
    "evidence-bound-multi-perspective-research.schema.json",
    "evidence-ledger.schema.json",
    "evidence-record.schema.json",
    "execution-receipt.schema.json",
    "experiment.schema.json",
    "gate-result.schema.json",
    "investment-decision-gate.schema.json",
    "local-capability-catalog.schema.json",
    "local-case-evidence-provider.schema.json",
    "monitoring-review.schema.json",
    "promotion.schema.json",
    "proposal-evidence.schema.json",
    "public-equity-data-freshness.schema.json",
    "public-equity-research-governance.schema.json",
    "public-equity-research-sandbox.schema.json",
    "registry.schema.json",
    "research-task-envelope.schema.json",
    "runtime-observation.schema.json",
    "result.schema.json",
    "task-grant-record.schema.json",
)
FIXTURE_VALIDATED_SCHEMAS = {
    "decision-record.schema.json",
    "evidence-bound-multi-perspective-research.schema.json",
    "gate-result.schema.json",
    "investment-decision-gate.schema.json",
    "promotion.schema.json",
    "public-equity-data-freshness.schema.json",
    "public-equity-research-governance.schema.json",
    "research-task-envelope.schema.json",
}
SYNTAX_ONLY_SCHEMAS = {
    name: (
        "No approved deterministic instance fixture is mapped in this release gate; "
        "Draft 2020-12 syntax, dialect, identity, and reference integrity are checked."
    )
    for name in SCHEMA_INVENTORY
    if name not in FIXTURE_VALIDATED_SCHEMAS
}
SYNTAX_ONLY_SCHEMAS["capability-profile-doctor.schema.json"] = (
    "Synthetic instances are validated by the capability profile contract's "
    "dependency-free fixtures; this formal gate checks Draft 2020-12 syntax, "
    "dialect, identity, and reference integrity."
)
SYNTAX_ONLY_SCHEMAS["local-capability-catalog.schema.json"] = (
    "Synthetic instances are validated by the local capability catalog's "
    "dependency-free contract tests; this formal gate checks Draft 2020-12 "
    "syntax, dialect, identity, and reference integrity."
)
SYNTAX_ONLY_SCHEMAS["local-case-evidence-provider.schema.json"] = (
    "Synthetic instances are validated by the local case evidence provider's "
    "dependency-free contract tests; this formal gate checks Draft 2020-12 "
    "syntax, dialect, identity, and reference integrity."
)
for _static_record_schema in (
    "capability-descriptor.schema.json",
    "runtime-observation.schema.json",
    "task-grant-record.schema.json",
    "execution-receipt.schema.json",
):
    SYNTAX_ONLY_SCHEMAS[_static_record_schema] = (
        "Synthetic static-record fixtures are checked by dependency-free contract "
        "tests; this formal gate checks Draft 2020-12 syntax, dialect, identity, "
        "and reference integrity."
    )
for _research_record_schema in (
    "evidence-record.schema.json",
    "claim-record.schema.json",
    "calculation-receipt.schema.json",
):
    SYNTAX_ONLY_SCHEMAS[_research_record_schema] = (
        "Synthetic research-record fixtures are checked by dependency-free contract "
        "tests; this formal gate checks Draft 2020-12 syntax, dialect, identity, "
        "and reference integrity."
    )
PYPI_ARTIFACT_HOSTS = {"files.pythonhosted.org"}

DIRECT_REQUIREMENTS = {
    "jsonschema": {
        "attrs>=22.2.0",
        "jsonschema-specifications>=2023.03.6",
        "referencing>=0.28.4",
        "rpds-py>=0.25.0",
    },
    "attrs": set(),
    "jsonschema-specifications": {"referencing>=0.31.0"},
    "referencing": {
        "attrs>=22.2.0",
        "rpds-py>=0.7.0",
        'typing-extensions>=4.4.0; python_version < "3.13"',
    },
    "rpds-py": set(),
    "typing-extensions": set(),
}


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_metadata_url(url: str) -> tuple[str, int | None]:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"metadata URL is invalid: {url!r}") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in APPROVED_METADATA_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(f"metadata URL is not an approved HTTPS source: {url!r}")
    return parsed.hostname, port


def bootstrap_identity() -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        commit = git_value("rev-parse", f"{BOOTSTRAP_COMMIT}^{{commit}}")
        tree = git_value("show", "-s", "--format=%T", BOOTSTRAP_COMMIT)
        parent = git_value("rev-parse", f"{BOOTSTRAP_COMMIT}^")
        paths_text = git_value(
            "diff",
            "--name-only",
            f"{BOOTSTRAP_PARENT}..{BOOTSTRAP_COMMIT}",
        )
    except RuntimeError as exc:
        return [f"formal gate bootstrap identity could not be verified: {exc}"], {}
    paths = sorted(path for path in paths_text.splitlines() if path)
    if commit != BOOTSTRAP_COMMIT or tree != BOOTSTRAP_TREE:
        errors.append("formal gate bootstrap commit or tree mismatch")
    if parent != BOOTSTRAP_PARENT:
        errors.append("formal gate bootstrap parent mismatch")
    if paths != sorted(BOOTSTRAP_PATHS):
        errors.append("formal gate bootstrap path inventory mismatch")
    return errors, {
        "commit": commit,
        "tree": tree,
        "parent": parent,
        "remediation_baseline_reference": REMEDIATION_BASELINE_REFERENCE,
        "paths": paths,
        "authority": "provenance-only",
    }


def candidate_binding(base_commit: str) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(base_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", base_commit
    ) or base_commit == "0" * 40:
        return ["formal candidate base must be a nonzero full commit SHA"], {}
    try:
        base = git_value("rev-parse", f"{base_commit}^{{commit}}")
        commit = git_value("rev-parse", "HEAD")
        tree = git_value("show", "-s", "--format=%T", "HEAD")
        parents_text = git_value("show", "-s", "--format=%P", "HEAD")
        merge_base = git_value("merge-base", base, commit)
        paths_text = git_value("diff", "--name-only", f"{base}..{commit}")
    except RuntimeError as exc:
        return [f"candidate identity could not be verified: {exc}"], {}
    parents = parents_text.split()
    paths = sorted(path for path in paths_text.splitlines() if path)
    if base != base_commit:
        errors.append("formal candidate base does not resolve to the supplied commit")
    if merge_base != base:
        errors.append("formal candidate base is not the candidate merge-base")
    if not paths:
        errors.append("formal candidate changed-path inventory must not be empty")
    diff = subprocess.run(
        ["git", "diff", "--binary", f"{base}..{commit}", "--"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if diff.returncode != 0:
        errors.append("formal candidate remediation diff could not be hashed")
        diff_sha256 = ""
    else:
        diff_sha256 = sha256_bytes(diff.stdout)
    return errors, {
        "binding_version": 1,
        "commit": commit,
        "tree": tree,
        "base_commit": base,
        "merge_base": merge_base,
        "parents": parents,
        "changed_paths": paths,
        "changed_paths_sha256": sha256_bytes(canonical_json_bytes(paths)),
        "diff_sha256": diff_sha256,
        "worktree_clean": not validate_clean_worktree(),
    }


def job_identity(
    run_id: str,
    run_attempt: str,
    workflow_ref: str,
    job_name: str,
) -> tuple[list[str], dict[str, str]]:
    values = {
        "run_id": run_id,
        "run_attempt": run_attempt,
        "workflow_ref": workflow_ref,
        "job_name": job_name,
    }
    errors = [
        f"job identity {name} is missing"
        for name, value in values.items()
        if not isinstance(value, str) or not value.strip()
    ]
    if run_id and not run_id.isdigit():
        errors.append("job identity run_id must be numeric")
    if run_attempt and not run_attempt.isdigit():
        errors.append("job identity run_attempt must be numeric")
    return errors, values


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        try:
            display_path = path.relative_to(ROOT)
        except ValueError:
            display_path = path
        raise ValueError(f"{display_path} is not valid JSON: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_clean_worktree() -> list[str]:
    try:
        status = git_value("status", "--porcelain=v1", "--untracked-files=all")
    except RuntimeError as exc:
        return [f"formal gate could not verify clean git state: {exc}"]
    if status:
        return [
            "formal gate requires a clean candidate worktree; "
            "staged, unstaged, and untracked paths are forbidden"
        ]
    return []


def artifact_identity() -> list[dict[str, str]]:
    return [
        {
            "name": canonical_name(item.name),
            "version": item.version,
            "wheel": item.wheel,
            "sha256": item.sha256,
        }
        for item in sorted(DISTRIBUTIONS, key=lambda value: canonical_name(value.name))
    ]


def validate_lock() -> list[str]:
    errors: list[str] = []
    try:
        text = LOCK_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"requirements-release.txt could not be read: {exc}"]
    logical = text.replace("\\\n", " ")
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in logical.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if lines[:2] != ["--only-binary=:all:", "--require-hashes"]:
        errors.append(
            "requirements-release.txt must begin with --only-binary=:all: "
            "and --require-hashes"
        )
    if any(
        token in text
        for token in ("--extra-index-url", "://", " @ ", "[", "-e ", "--editable")
    ):
        errors.append("requirements-release.txt contains a forbidden source or extra")
    requirement_lines = lines[2:]
    expected = {
        (
            f"{item.name}=={item.version} "
            f"--hash=sha256:{item.sha256}"
        )
        for item in DISTRIBUTIONS
    }
    if set(requirement_lines) != expected or len(requirement_lines) != len(expected):
        errors.append("requirements-release.txt does not match the six-package lock")
    return errors


def decode_statement(attestation: dict[str, Any]) -> dict[str, Any]:
    encoded = attestation.get("envelope", {}).get("statement")
    if not isinstance(encoded, str):
        raise ValueError("publish attestation statement is missing")
    padding = "=" * (-len(encoded) % 4)
    return json.loads(base64.b64decode(encoded + padding).decode("utf-8"))


class OnlineEvidenceSession:
    def __init__(self, evidence_dir: Path, github_token: str | None = None):
        self.evidence_dir = evidence_dir.resolve()
        if self.evidence_dir.exists():
            raise ValueError("acquisition evidence directory must not already exist")
        self.responses_dir = self.evidence_dir / "responses"
        self.responses_dir.mkdir(parents=True)
        self.entries: list[dict[str, Any]] = []
        self.request_keys: set[tuple[str, str, str]] = set()
        self.failed = False
        # This token is deliberately memory-only. Request headers are not
        # persisted in the raw-evidence manifest or acquisition receipt.
        self.github_token = github_token

    def request_json(
        self,
        method: str,
        url: str,
        payload: Any | None = None,
    ) -> Any:
        method = method.upper()
        if self.failed:
            raise RuntimeError("live metadata acquisition already failed")
        request_bytes = b"" if payload is None else canonical_json_bytes(payload)
        request_sha256 = sha256_bytes(request_bytes)
        key = (method, url, request_sha256)
        if key in self.request_keys:
            self.failed = True
            raise RuntimeError(f"duplicate live metadata request forbidden: {method} {url}")
        self.request_keys.add(key)
        try:
            source_host, _ = validate_metadata_url(url)
        except ValueError:
            self.failed = True
            raise
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "lhe-release-gate/0.3",
        }
        if source_host == "api.github.com" and self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        request = Request(
            url,
            data=request_bytes if method == "POST" else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)
                final_url = response.geturl()
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            self.failed = True
            raise RuntimeError(
                f"official metadata request failed for {url}: {exc}"
            ) from exc
        if status != 200:
            self.failed = True
            raise RuntimeError(f"official metadata request returned HTTP {status}: {url}")
        try:
            source_host, _ = validate_metadata_url(final_url)
        except ValueError:
            self.failed = True
            raise
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.failed = True
            raise RuntimeError(f"official metadata response is not JSON: {url}") from exc
        relative = Path("responses") / f"{len(self.entries) + 1:03d}.json"
        target = self.evidence_dir / relative
        target.write_bytes(raw)
        self.entries.append(
            {
                "method": method,
                "url": url,
                "final_url": final_url,
                "source_host": source_host,
                "status": status,
                "request_sha256": request_sha256,
                "response_path": relative.as_posix(),
                "response_sha256": sha256_bytes(raw),
            }
        )
        return parsed

    def get_json(self, url: str) -> Any:
        return self.request_json("GET", url)

    def post_json(self, url: str, payload: Any) -> Any:
        return self.request_json("POST", url, payload)

    def write_manifest(self) -> tuple[Path, str]:
        manifest = {
            "schema_version": 1,
            "entries": self.entries,
            "source_hosts": sorted({entry["source_host"] for entry in self.entries}),
        }
        path = self.evidence_dir / "manifest.json"
        path.write_bytes(canonical_json_bytes(manifest) + b"\n")
        return path, sha256_file(path)


class ReplayEvidenceSession:
    def __init__(self, evidence_dir: Path, manifest: dict[str, Any]):
        self.evidence_dir = evidence_dir.resolve()
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise ValueError("raw evidence manifest entries must be an array")
        self.entries = entries
        self.index = 0

    def request_json(
        self,
        method: str,
        url: str,
        payload: Any | None = None,
    ) -> Any:
        if self.index >= len(self.entries):
            raise ValueError("raw evidence is missing a required response")
        entry = self.entries[self.index]
        self.index += 1
        if not isinstance(entry, dict):
            raise ValueError("raw evidence manifest entry must be an object")
        request_bytes = b"" if payload is None else canonical_json_bytes(payload)
        expected = {
            "method": method.upper(),
            "url": url,
            "request_sha256": sha256_bytes(request_bytes),
        }
        for field, value in expected.items():
            if entry.get(field) != value:
                raise ValueError(f"raw evidence {field} mismatch")
        validate_metadata_url(url)
        final_url = entry.get("final_url")
        if not isinstance(final_url, str):
            raise ValueError("raw evidence final_url is missing")
        host, _ = validate_metadata_url(final_url)
        if entry.get("source_host") != host or entry.get("status") != 200:
            raise ValueError("raw evidence source host or status mismatch")
        relative = entry.get("response_path")
        if not isinstance(relative, str):
            raise ValueError("raw evidence response_path is missing")
        path = (self.evidence_dir / relative).resolve()
        try:
            path.relative_to(self.evidence_dir)
        except ValueError as exc:
            raise ValueError("raw evidence path escapes its directory") from exc
        if not path.is_file():
            raise ValueError(f"raw evidence response is missing: {relative}")
        raw = path.read_bytes()
        if sha256_bytes(raw) != entry.get("response_sha256"):
            raise ValueError(f"raw evidence response hash mismatch: {relative}")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"raw evidence response is not JSON: {relative}") from exc

    def get_json(self, url: str) -> Any:
        return self.request_json("GET", url)

    def post_json(self, url: str, payload: Any) -> Any:
        return self.request_json("POST", url, payload)

    def finish(self) -> None:
        if self.index != len(self.entries):
            raise ValueError("raw evidence contains unconsumed extra responses")


def peel_github_ref(session: Any, repo: str, tag: str) -> str:
    ref = session.get_json(f"https://api.github.com/repos/{repo}/git/ref/tags/{tag}")
    target = ref.get("object", {})
    if target.get("type") == "tag":
        target = session.get_json(target["url"]).get("object", {})
    if target.get("type") != "commit" or not isinstance(target.get("sha"), str):
        raise ValueError(f"{repo}@{tag} did not resolve to a commit")
    return target["sha"]


def verify_acquisition(session: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    evidence: dict[str, Any] = {"packages": []}
    osv_queries = []
    for item in DISTRIBUTIONS:
        package_evidence: dict[str, Any] = {
            "name": item.name,
            "version": item.version,
            "wheel": item.wheel,
            "sha256": item.sha256,
        }
        try:
            metadata_json = session.get_json(
                f"https://pypi.org/pypi/{item.name}/{item.version}/json"
            )
            info = metadata_json["info"]
            files = [
                candidate
                for candidate in metadata_json["urls"]
                if candidate.get("filename") == item.wheel
            ]
            if len(files) != 1:
                raise ValueError("selected wheel is missing or ambiguous")
            selected = files[0]
            if selected.get("digests", {}).get("sha256") != item.sha256:
                raise ValueError("selected wheel hash changed")
            if selected.get("yanked") is not False:
                raise ValueError("selected wheel is yanked")
            if selected.get("requires_python") != item.requires_python:
                raise ValueError("selected wheel Requires-Python changed")
            if info.get("license_expression") != item.license_expression:
                raise ValueError("license expression changed")
            actual_requires = set(info.get("requires_dist") or [])
            filtered_requires = {
                requirement
                for requirement in actual_requires
                if "extra ==" not in requirement
            }
            if filtered_requires != DIRECT_REQUIREMENTS[item.name]:
                raise ValueError("runtime dependency metadata changed")

            provenance = session.get_json(
                "https://pypi.org/integrity/"
                f"{item.name}/{item.version}/{item.wheel}/provenance"
            )
            bundles = provenance.get("attestation_bundles", [])
            if len(bundles) != 1:
                raise ValueError("publish attestation bundle is missing or ambiguous")
            bundle = bundles[0]
            publisher = bundle.get("publisher", {})
            if publisher.get("repository") != item.publisher_repository:
                raise ValueError("Trusted Publisher repository changed")
            if publisher.get("workflow") != item.publisher_workflow:
                raise ValueError("Trusted Publisher workflow changed")
            if publisher.get("environment") != item.publisher_environment:
                raise ValueError("Trusted Publisher environment changed")
            attestations = bundle.get("attestations", [])
            publish = [
                attestation
                for attestation in attestations
                if decode_statement(attestation).get("predicateType")
                == "https://docs.pypi.org/attestations/publish/v1"
            ]
            if len(publish) != 1:
                raise ValueError("exactly one PyPI publish attestation is required")
            statement = decode_statement(publish[0])
            if statement.get("subject") != [
                {"name": item.wheel, "digest": {"sha256": item.sha256}}
            ]:
                raise ValueError("publish attestation subject does not match the wheel")

            if peel_github_ref(session, item.source_repo, item.source_tag) != item.source_commit:
                raise ValueError("source tag commit changed")
            license_json = session.get_json(
                "https://api.github.com/repos/"
                f"{item.source_repo}/contents/{item.license_path}?ref={item.source_tag}"
            )
            if license_json.get("sha") != item.license_blob:
                raise ValueError("source license blob changed")
            package_evidence.update(
                {
                    "upload_time": selected.get("upload_time_iso_8601"),
                    "yanked": False,
                    "requires_python": item.requires_python,
                    "license_expression": item.license_expression,
                    "source_tag": item.source_tag,
                    "source_commit": item.source_commit,
                    "publish_attestation": "verified_metadata",
                    "slsa_build_provenance": "not_observed_exception",
                }
            )
            osv_queries.append(
                {
                    "package": {"ecosystem": "PyPI", "name": item.name},
                    "version": item.version,
                }
            )
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"{item.name}=={item.version}: {exc}")
        evidence["packages"].append(package_evidence)

    if not errors:
        try:
            osv = session.post_json(
                "https://api.osv.dev/v1/querybatch",
                {"queries": osv_queries},
            )
            results = osv.get("results")
            if not isinstance(results, list) or len(results) != len(DISTRIBUTIONS):
                raise ValueError("OSV result count does not match the locked closure")
            for item, result, package_evidence in zip(
                DISTRIBUTIONS, results, evidence["packages"]
            ):
                if result.get("vulns"):
                    errors.append(
                        f"{item.name}=={item.version}: OSV returned vulnerabilities"
                    )
                elif result.get("next_page_token"):
                    errors.append(
                        f"{item.name}=={item.version}: OSV response is paginated"
                    )
                else:
                    package_evidence["osv"] = "no_matching_records"
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"OSV query failed closed: {exc}")
    return errors, evidence


def validate_schema_inventory() -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    schema_root = ROOT / "sandbox/skill-incubator/schemas"
    actual = {path.name for path in schema_root.glob("*.schema.json")}
    expected = set(SCHEMA_INVENTORY)
    if actual != expected:
        errors.append(
            "schema inventory mismatch: "
            f"missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}"
        )
    schemas: dict[str, dict[str, Any]] = {}
    for name in SCHEMA_INVENTORY:
        path = schema_root / name
        payload = load_json(path)
        if not isinstance(payload, dict):
            errors.append(f"{name}: schema root must be an object")
            continue
        if payload.get("$schema") != DRAFT_2020_12:
            errors.append(f"{name}: unknown or unsupported schema dialect")
        if not isinstance(payload.get("$id"), str) or not payload["$id"]:
            errors.append(f"{name}: schema $id is missing")
        schemas[name] = payload
    ids = [schema.get("$id") for schema in schemas.values()]
    if len(ids) != len(set(ids)):
        errors.append("schema $id values must be unique")
    schemas_by_id = {
        schema["$id"]: schema
        for schema in schemas.values()
        if isinstance(schema.get("$id"), str)
    }
    classified = FIXTURE_VALIDATED_SCHEMAS | set(SYNTAX_ONLY_SCHEMAS)
    if classified != expected:
        errors.append(
            "schema coverage classification mismatch: "
            f"missing={sorted(expected - classified)} "
            f"unexpected={sorted(classified - expected)}"
        )
    overlap = FIXTURE_VALIDATED_SCHEMAS & set(SYNTAX_ONLY_SCHEMAS)
    if overlap:
        errors.append(f"schema coverage classification overlaps: {sorted(overlap)}")
    for name, reason in SYNTAX_ONLY_SCHEMAS.items():
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{name}: syntax-only classification requires a reason")

    def resolve_pointer(document: Any, fragment: str) -> None:
        if fragment in ("", "#"):
            return
        decoded = unquote(fragment[1:] if fragment.startswith("#") else fragment)
        if not decoded.startswith("/"):
            raise ValueError("fragment must be an absolute JSON Pointer")
        current = document
        for raw_part in decoded[1:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                if part not in current:
                    raise ValueError(f"missing object member {part!r}")
                current = current[part]
            elif isinstance(current, list):
                if not part.isdigit() or int(part) >= len(current):
                    raise ValueError(f"invalid array index {part!r}")
                current = current[int(part)]
            else:
                raise ValueError(f"cannot traverse through {type(current).__name__}")

    def visit(value: Any, owner: str) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"]
                if not isinstance(reference, str) or not reference:
                    errors.append(f"{owner}: $ref must be a non-empty string")
                    reference = None
            else:
                reference = None
            if reference is not None:
                base, separator, fragment = reference.partition("#")
                target = schemas[owner] if not base else schemas_by_id.get(base)
                if target is None:
                    errors.append(f"{owner}: unresolved external $ref {reference!r}")
                elif separator:
                    try:
                        resolve_pointer(target, f"#{fragment}")
                    except ValueError as exc:
                        errors.append(
                            f"{owner}: unresolved $ref {reference!r}: {exc}"
                        )
            for child in value.values():
                visit(child, owner)
        elif isinstance(value, list):
            for child in value:
                visit(child, owner)

    for name, schema in schemas.items():
        visit(schema, name)
    return errors, schemas


def schema_inventory_binding(schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema_root = ROOT / "sandbox/skill-incubator/schemas"
    files = [
        {
            "name": name,
            "sha256": sha256_file(schema_root / name),
            "validation": (
                "fixture-validated"
                if name in FIXTURE_VALIDATED_SCHEMAS
                else "syntax-only"
            ),
        }
        for name in sorted(schemas)
    ]
    return {
        "schema_count": len(files),
        "fixture_validated_schema_count": len(FIXTURE_VALIDATED_SCHEMAS),
        "syntax_only_schema_count": len(SYNTAX_ONLY_SCHEMAS),
        "files": files,
        "inventory_sha256": sha256_bytes(canonical_json_bytes(files)),
    }


def pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = pointer.lstrip("/").split("/")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def apply_mutations(base: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    record = deepcopy(base)
    for mutation in mutations:
        parent, leaf = pointer_parent(record, mutation["path"])
        operation = mutation["op"]
        if operation == "set":
            if isinstance(parent, list):
                parent[int(leaf)] = deepcopy(mutation["value"])
            else:
                parent[leaf] = deepcopy(mutation["value"])
        elif operation == "delete":
            if isinstance(parent, list):
                del parent[int(leaf)]
            else:
                del parent[leaf]
        elif operation == "append":
            target = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
            target.append(deepcopy(mutation["value"]))
        else:
            raise ValueError(f"unsupported fixture mutation {operation!r}")
    return record


def dotted_path(parts: Any) -> str:
    values = [str(part) for part in parts]
    return ".".join(values) if values else "<root>"


def materialized_fixture_cases() -> tuple[
    list[tuple[str, str, dict[str, Any]]],
    list[tuple[str, str, dict[str, Any], str]],
]:
    positives: list[tuple[str, str, dict[str, Any]]] = []
    negatives: list[tuple[str, str, dict[str, Any], str]] = []

    evidence = load_json(
        ROOT / "tests/fixtures/evidence-bound-multi-perspective-research/cases.json"
    )
    for case in evidence["positive_cases"]:
        positives.append(
            (
                "evidence-bound-multi-perspective-research.schema.json",
                case["case_id"],
                apply_mutations(evidence["base_record"], case.get("mutations", [])),
            )
        )
    malformed_evidence = deepcopy(evidence["base_record"])
    malformed_evidence["sources"][0] = 42
    negatives.append(
        (
            "evidence-bound-multi-perspective-research.schema.json",
            "formal-source-item-type",
            malformed_evidence,
            "sources.0",
        )
    )

    governance = load_json(
        ROOT / "tests/fixtures/public-equity-research-governance/cases.json"
    )
    for case in governance["cases"]:
        if case["expected_valid"]:
            positives.append(
                (
                    "public-equity-research-governance.schema.json",
                    case["case_id"],
                    apply_mutations(
                        governance["base_record"], case.get("mutations", [])
                    ),
                )
            )
    malformed_governance = deepcopy(governance["base_record"])
    del malformed_governance["sources"][0]["source_locator"]
    negatives.append(
        (
            "public-equity-research-governance.schema.json",
            "formal-source-locator-required",
            malformed_governance,
            "sources.0",
        )
    )

    investment = load_json(
        ROOT / "tests/fixtures/investment-decision-gate/cases.json"
    )
    for case in investment:
        positives.append(
            (
                "investment-decision-gate.schema.json",
                case["case_id"],
                case["record"],
            )
        )
    malformed_investment = deepcopy(investment[0]["record"])
    malformed_investment["human_decision"]["status"] = "approved"
    negatives.append(
        (
            "investment-decision-gate.schema.json",
            "formal-human-decision-enum",
            malformed_investment,
            "human_decision.status",
        )
    )

    freshness = load_json(
        ROOT / "tests/fixtures/public-equity-data-freshness/cases.json"
    )
    for case in freshness:
        positives.append(
            (
                "public-equity-data-freshness.schema.json",
                case["case_id"],
                case["record"],
            )
        )
    malformed_freshness = deepcopy(freshness[0]["record"])
    malformed_freshness["boundaries"]["network_action_performed"] = True
    negatives.append(
        (
            "public-equity-data-freshness.schema.json",
            "formal-network-boundary-const",
            malformed_freshness,
            "boundaries.network_action_performed",
        )
    )

    envelope = load_json(ROOT / "tests/fixtures/research-task-envelope/cases.json")
    for name, record in envelope["base_records"].items():
        positives.append(("research-task-envelope.schema.json", name, record))
    for case in envelope["negative_cases"]:
        negatives.append(
            (
                "research-task-envelope.schema.json",
                case["case_id"],
                apply_mutations(
                    envelope["base_records"][case["base"]],
                    [{key: value for key, value in case.items() if key in {"op", "path", "value"}}],
                ),
                case["expected_path"],
            )
        )

    authority = load_json(
        ROOT / "tests/fixtures/formal-authority-boundaries/cases.json"
    )
    for schema_case in authority["schemas"]:
        schema_name = schema_case["schema"]
        base_record = schema_case["base_record"]
        positives.append(
            (
                schema_name,
                schema_case["positive_case_id"],
                deepcopy(base_record),
            )
        )
        for case in schema_case["negative_cases"]:
            negatives.append(
                (
                    schema_name,
                    case["case_id"],
                    apply_mutations(base_record, case["mutations"]),
                    case["expected_path"],
                )
            )
    return positives, negatives


def validate_fixture_coverage(
    positives: list[tuple[str, str, dict[str, Any]]],
    negatives: list[tuple[str, str, dict[str, Any], str]],
) -> list[str]:
    errors: list[str] = []
    positive_schemas = {schema for schema, _, _ in positives}
    negative_schemas = {schema for schema, _, _, _ in negatives}
    for name in sorted(FIXTURE_VALIDATED_SCHEMAS):
        if name not in positive_schemas:
            errors.append(f"{name}: fixture-validated schema has no positive fixture")
        if name not in negative_schemas:
            errors.append(f"{name}: fixture-validated schema has no negative fixture")
    unexpected = (positive_schemas | negative_schemas) - FIXTURE_VALIDATED_SCHEMAS
    if unexpected:
        errors.append(
            f"syntax-only schemas unexpectedly have instance fixtures: {sorted(unexpected)}"
        )
    return errors


def validate_pip_report(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    errors: list[str] = []
    payload = load_json(path)
    installs = payload.get("install") if isinstance(payload, dict) else None
    if not isinstance(installs, list):
        return ["pip report does not contain an install list"], []
    actual: dict[str, dict[str, str]] = {}
    for entry in installs:
        try:
            name = canonical_name(entry["metadata"]["name"])
            version = entry["metadata"]["version"]
            url = entry["download_info"]["url"]
            parsed = urlparse(url)
            filename = Path(unquote(parsed.path)).name
            hashes = entry["download_info"]["archive_info"].get("hashes", {})
            sha256 = hashes.get("sha256")
            port = parsed.port
        except (AttributeError, KeyError, TypeError, ValueError):
            errors.append("pip report contains a malformed install record")
            continue
        if (
            parsed.scheme != "https"
            or parsed.hostname not in PYPI_ARTIFACT_HOSTS
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or entry.get("is_direct") is True
            or "vcs_info" in entry["download_info"]
            or "dir_info" in entry["download_info"]
        ):
            errors.append(
                f"pip report artifact source is not an approved PyPI HTTPS host for {name}"
            )
        if name in actual:
            errors.append(f"pip report contains duplicate package {name}")
        actual[name] = {
            "name": name,
            "version": version,
            "wheel": filename,
            "sha256": sha256,
        }
    expected_names = {canonical_name(item.name) for item in DISTRIBUTIONS}
    if set(actual) != expected_names:
        errors.append(
            "pip report closure mismatch: "
            f"missing={sorted(expected_names - set(actual))} "
            f"unexpected={sorted(set(actual) - expected_names)}"
        )
    for item in DISTRIBUTIONS:
        record = actual.get(canonical_name(item.name))
        expected = {
            "name": canonical_name(item.name),
            "version": item.version,
            "wheel": item.wheel,
            "sha256": item.sha256,
        }
        if record is not None and record != expected:
            errors.append(f"pip report artifact mismatch for {item.name}")
    return errors, [actual[name] for name in sorted(actual)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return parsed


def acquire_evidence(
    pip_report: Path,
    evidence_dir: Path,
    receipt_path: Path,
    identity: dict[str, str],
    candidate_base: str,
) -> tuple[list[str], dict[str, Any]]:
    errors = validate_clean_worktree()
    errors.extend(validate_lock())
    bootstrap_errors, bootstrap = bootstrap_identity()
    errors.extend(bootstrap_errors)
    inventory_errors, schemas = validate_schema_inventory()
    errors.extend(inventory_errors)
    report_errors, artifacts = validate_pip_report(pip_report)
    errors.extend(report_errors)
    candidate_errors, candidate = candidate_binding(candidate_base)
    errors.extend(candidate_errors)
    identity_errors, normalized_identity = job_identity(**identity)
    errors.extend(identity_errors)
    evidence_dir = evidence_dir.resolve()
    receipt_path = receipt_path.resolve()
    if receipt_path.parent != evidence_dir:
        errors.append("acquisition receipt must be created inside its evidence directory")
    if evidence_dir.exists():
        errors.append("acquisition evidence directory must not already exist")
    if errors:
        return errors, {"status": "FAIL", "gate": "formal-acquisition"}

    started = utc_now()
    session = OnlineEvidenceSession(
        evidence_dir, github_token=os.environ.get("GITHUB_TOKEN")
    )
    acquisition_errors, evidence = verify_acquisition(session)
    errors.extend(acquisition_errors)
    manifest_path, manifest_sha256 = session.write_manifest()
    completed = utc_now()
    receipt = {
        "schema_version": 2,
        "status": "PASS" if not errors else "FAIL",
        "gate": "formal-acquisition",
        "acquisition_started_at": iso_utc(started),
        "acquired_at": iso_utc(completed),
        "job_identity": normalized_identity,
        "bootstrap_identity": bootstrap,
        "candidate": candidate,
        "schema_inventory": schema_inventory_binding(schemas),
        "validator_sha256": sha256_file(Path(__file__).resolve()),
        "lock_sha256": sha256_file(LOCK_PATH),
        "pip_report_sha256": sha256_file(pip_report),
        "raw_evidence_manifest": manifest_path.name,
        "raw_evidence_manifest_sha256": manifest_sha256,
        "raw_evidence_count": len(session.entries),
        "source_hosts": sorted({entry["source_host"] for entry in session.entries}),
        "artifacts": artifacts,
        "packages": evidence["packages"],
        "limitations": [
            "Job-local evidence is not a cryptographic signature.",
            "PyPI publish attestations do not prove source-to-wheel provenance.",
            "Bootstrap identity records gate provenance only and grants no authority.",
        ],
        "approval_authority": "none",
        "next_stage_authorized": False,
    }
    write_json(receipt_path, receipt)
    return errors, receipt


def validate_raw_manifest(
    evidence_dir: Path,
    receipt_path: Path,
    expected_sha256: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    manifest_path = evidence_dir / "manifest.json"
    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        return [f"raw evidence manifest could not be validated: {exc}"], {}
    if not isinstance(manifest, dict):
        return ["raw evidence manifest must be an object"], {}
    expected_keys = {"schema_version", "entries", "source_hosts"}
    if set(manifest) != expected_keys or manifest.get("schema_version") != 1:
        errors.append("raw evidence manifest structure is not closed")
    if sha256_file(manifest_path) != expected_sha256:
        errors.append("raw evidence manifest hash mismatch")
    entries = manifest.get("entries")
    source_hosts = manifest.get("source_hosts")
    if not isinstance(entries, list) or not isinstance(source_hosts, list):
        errors.append("raw evidence manifest fields have invalid types")
        return errors, manifest
    expected_entry_keys = {
        "method",
        "url",
        "final_url",
        "source_host",
        "status",
        "request_sha256",
        "response_path",
        "response_sha256",
    }
    response_paths: list[str] = []
    actual_hosts: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != expected_entry_keys:
            errors.append("raw evidence manifest entry structure is not closed")
            continue
        try:
            requested_host, _ = validate_metadata_url(entry["url"])
            final_host, _ = validate_metadata_url(entry["final_url"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"raw evidence source URL is invalid: {exc}")
            continue
        if final_host != entry.get("source_host") or entry.get("status") != 200:
            errors.append("raw evidence host or HTTP status mismatch")
        if requested_host not in APPROVED_METADATA_HOSTS:
            errors.append("raw evidence request host is not approved")
        actual_hosts.add(final_host)
        relative = entry.get("response_path")
        if not isinstance(relative, str):
            errors.append("raw evidence response path is invalid")
            continue
        response_paths.append(relative)
        path = (evidence_dir / relative).resolve()
        try:
            path.relative_to(evidence_dir)
        except ValueError:
            errors.append("raw evidence response path escapes its directory")
            continue
        if not path.is_file():
            errors.append(f"raw evidence response is missing: {relative}")
        elif sha256_file(path) != entry.get("response_sha256"):
            errors.append(f"raw evidence response hash mismatch: {relative}")
    if source_hosts != sorted(actual_hosts):
        errors.append("raw evidence source host inventory mismatch")
    if len(response_paths) != len(set(response_paths)):
        errors.append("raw evidence response paths must be unique")
    try:
        receipt_relative = receipt_path.relative_to(evidence_dir).as_posix()
    except ValueError:
        errors.append("acquisition receipt is outside its evidence directory")
        receipt_relative = "__outside_receipt__"
    expected_files = {"manifest.json", receipt_relative, *response_paths}
    actual_files = {
        path.relative_to(evidence_dir).as_posix()
        for path in evidence_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        errors.append(
            "acquisition evidence file inventory mismatch: "
            f"missing={sorted(expected_files - actual_files)} "
            f"unexpected={sorted(actual_files - expected_files)}"
        )
    return errors, manifest


def validate_acquisition_receipt(
    path: Path,
    evidence_dir: Path,
    pip_report: Path,
    identity: dict[str, str],
    candidate_base: str,
) -> tuple[list[str], dict[str, Any], str]:
    errors: list[str] = []
    try:
        receipt = load_json(path)
    except ValueError as exc:
        return [f"acquisition receipt could not be validated: {exc}"], {}, ""
    if not isinstance(receipt, dict):
        return ["acquisition receipt must be an object"], {}, sha256_file(path)
    receipt_keys = {
        "schema_version",
        "status",
        "gate",
        "acquisition_started_at",
        "acquired_at",
        "job_identity",
        "bootstrap_identity",
        "candidate",
        "schema_inventory",
        "validator_sha256",
        "lock_sha256",
        "pip_report_sha256",
        "raw_evidence_manifest",
        "raw_evidence_manifest_sha256",
        "raw_evidence_count",
        "source_hosts",
        "artifacts",
        "packages",
        "limitations",
        "approval_authority",
        "next_stage_authorized",
    }
    if set(receipt) != receipt_keys:
        errors.append("acquisition receipt structure is not closed")
    if (
        receipt.get("schema_version") != 2
        or receipt.get("status") != "PASS"
        or receipt.get("gate") != "formal-acquisition"
    ):
        errors.append("acquisition receipt does not record valid PASS evidence")
    if (
        receipt.get("approval_authority") != "none"
        or receipt.get("next_stage_authorized") is not False
    ):
        errors.append("acquisition receipt must not grant approval or next-stage authority")
    identity_errors, normalized_identity = job_identity(**identity)
    errors.extend(identity_errors)
    if receipt.get("job_identity") != normalized_identity:
        errors.append("acquisition receipt job identity mismatch")
    bootstrap_errors, bootstrap = bootstrap_identity()
    errors.extend(bootstrap_errors)
    if receipt.get("bootstrap_identity") != bootstrap:
        errors.append("acquisition receipt bootstrap provenance mismatch")
    candidate_errors, candidate = candidate_binding(candidate_base)
    errors.extend(candidate_errors)
    if receipt.get("candidate") != candidate:
        errors.append("acquisition receipt candidate identity mismatch")
    inventory_errors, schemas = validate_schema_inventory()
    errors.extend(inventory_errors)
    if receipt.get("schema_inventory") != schema_inventory_binding(schemas):
        errors.append("acquisition receipt schema inventory mismatch")
    expected_hashes = {
        "validator_sha256": sha256_file(Path(__file__).resolve()),
        "lock_sha256": sha256_file(LOCK_PATH),
        "pip_report_sha256": sha256_file(pip_report),
    }
    for field, value in expected_hashes.items():
        if receipt.get(field) != value:
            errors.append(f"acquisition receipt {field} mismatch")
    if receipt.get("artifacts") != artifact_identity():
        errors.append("acquisition receipt does not match the six locked artifacts")
    try:
        started = parse_utc(receipt.get("acquisition_started_at"), "acquisition_started_at")
        acquired = parse_utc(receipt.get("acquired_at"), "acquired_at")
        now = utc_now()
        if acquired < started or acquired > now + timedelta(minutes=1):
            errors.append("acquisition receipt time interval is invalid")
        if now - acquired > MAX_RECEIPT_AGE:
            errors.append("acquisition receipt is stale")
    except ValueError as exc:
        errors.append(str(exc))
    evidence_dir = evidence_dir.resolve()
    path = path.resolve()
    try:
        path.relative_to(evidence_dir)
    except ValueError:
        errors.append("acquisition receipt is outside its evidence directory")
    manifest_name = receipt.get("raw_evidence_manifest")
    if manifest_name != "manifest.json":
        errors.append("acquisition receipt raw evidence manifest path is invalid")
    manifest_errors, manifest = validate_raw_manifest(
        evidence_dir,
        path,
        str(receipt.get("raw_evidence_manifest_sha256", "")),
    )
    errors.extend(manifest_errors)
    if receipt.get("raw_evidence_count") != len(manifest.get("entries", [])):
        errors.append("acquisition receipt raw evidence count mismatch")
    if receipt.get("source_hosts") != manifest.get("source_hosts"):
        errors.append("acquisition receipt source host inventory mismatch")
    if not errors:
        try:
            replay = ReplayEvidenceSession(evidence_dir, manifest)
            replay_errors, replayed = verify_acquisition(replay)
            replay.finish()
            errors.extend(replay_errors)
            if receipt.get("packages") != replayed.get("packages"):
                errors.append("acquisition receipt packages do not match raw evidence")
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"raw acquisition replay failed closed: {exc}")
    return errors, receipt, sha256_file(path)


def verify_runtime_versions() -> list[str]:
    errors: list[str] = []
    for item in DISTRIBUTIONS:
        try:
            actual = metadata.version(item.name)
        except metadata.PackageNotFoundError:
            errors.append(f"locked distribution is not installed: {item.name}")
            continue
        if actual != item.version:
            errors.append(
                f"installed {item.name} version {actual!r} does not match {item.version!r}"
            )
    return errors


def validate_formal(
    pip_report: Path,
    acquisition_result: Path,
    evidence_dir: Path,
    identity: dict[str, str],
    candidate_base: str,
) -> tuple[list[str], dict[str, Any]]:
    errors = validate_clean_worktree()
    errors.extend(validate_lock())
    inventory_errors, schemas = validate_schema_inventory()
    errors.extend(inventory_errors)
    if sys.version_info[:2] != TARGET_PYTHON:
        errors.append(
            f"formal gate requires CPython 3.11, got {platform.python_version()}"
        )
    if platform.system() != TARGET_SYSTEM or platform.machine() != TARGET_MACHINE:
        errors.append(
            "formal gate requires Linux x86_64, got "
            f"{platform.system()} {platform.machine()}"
        )
    errors.extend(verify_runtime_versions())
    report_errors, artifacts = validate_pip_report(pip_report)
    errors.extend(report_errors)
    acquisition_errors, receipt, acquisition_sha256 = validate_acquisition_receipt(
        acquisition_result,
        evidence_dir,
        pip_report,
        identity,
        candidate_base,
    )
    errors.extend(acquisition_errors)
    bootstrap_errors, bootstrap = bootstrap_identity()
    errors.extend(bootstrap_errors)
    candidate_errors, candidate = candidate_binding(candidate_base)
    errors.extend(candidate_errors)
    inventory_binding = schema_inventory_binding(schemas)

    positive_count = 0
    negative_count = 0
    if not errors:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
            from referencing import Registry, Resource

            for name, schema in schemas.items():
                try:
                    Draft202012Validator.check_schema(schema)
                except Exception as exc:
                    errors.append(f"{name}: schema check failed: {exc}")
            registry = Registry().with_resources(
                (schema["$id"], Resource.from_contents(schema))
                for schema in schemas.values()
            )
            positives, negatives = materialized_fixture_cases()
            errors.extend(validate_fixture_coverage(positives, negatives))
            for schema_name, case_id, record in positives:
                validator = Draft202012Validator(
                    schemas[schema_name],
                    registry=registry,
                    format_checker=FormatChecker(),
                )
                found = sorted(
                    validator.iter_errors(record),
                    key=lambda error: list(error.absolute_path),
                )
                if found:
                    errors.append(
                        f"{case_id}: positive fixture failed at "
                        f"{dotted_path(found[0].absolute_path)}: {found[0].message}"
                    )
                positive_count += 1
            for schema_name, case_id, record, expected_path in negatives:
                validator = Draft202012Validator(
                    schemas[schema_name],
                    registry=registry,
                    format_checker=FormatChecker(),
                )
                found = sorted(
                    validator.iter_errors(record),
                    key=lambda error: list(error.absolute_path),
                )
                actual_paths = {dotted_path(error.absolute_path) for error in found}
                if expected_path not in actual_paths:
                    errors.append(
                        f"{case_id}: expected formal error path {expected_path!r}; "
                        f"got {sorted(actual_paths)}"
                    )
                negative_count += 1
        except ImportError as exc:
            errors.append(f"formal Draft 2020-12 engine import failed: {exc}")
        except Exception as exc:
            errors.append(f"formal Draft 2020-12 validation raised an exception: {exc}")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "gate": "formal-draft-2020-12",
        "draft": DRAFT_2020_12,
        "candidate_commit": candidate.get("commit", "UNKNOWN"),
        "candidate_tree": candidate.get("tree", "UNKNOWN"),
        "candidate_base_commit": candidate.get("base_commit", "UNKNOWN"),
        "candidate_merge_base": candidate.get("merge_base", "UNKNOWN"),
        "candidate_parents": candidate.get("parents", []),
        "candidate_changed_paths": candidate.get("changed_paths", []),
        "candidate_changed_paths_sha256": candidate.get(
            "changed_paths_sha256", ""
        ),
        "candidate_diff_sha256": candidate.get("diff_sha256", ""),
        "candidate_worktree_clean": candidate.get("worktree_clean", False),
        "bootstrap_identity": bootstrap,
        "validator_sha256": sha256_file(Path(__file__).resolve()),
        "lock_sha256": sha256_file(LOCK_PATH),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "schema_count": len(schemas),
        "fixture_validated_schema_count": len(FIXTURE_VALIDATED_SCHEMAS),
        "syntax_only_schema_count": len(SYNTAX_ONLY_SCHEMAS),
        "schema_coverage": {
            "fixture_validated": sorted(FIXTURE_VALIDATED_SCHEMAS),
            "syntax_only": dict(sorted(SYNTAX_ONLY_SCHEMAS.items())),
        },
        "schema_inventory_binding": inventory_binding,
        "positive_fixture_count": positive_count,
        "negative_fixture_count": negative_count,
        "artifacts": artifacts,
        "acquisition_receipt_sha256": acquisition_sha256,
        "raw_evidence_manifest_sha256": receipt.get(
            "raw_evidence_manifest_sha256", ""
        ),
        "job_identity": receipt.get("job_identity", {}),
        "pip_report_sha256": sha256_file(pip_report),
        "limitations": [
            "PyPI publish attestations do not prove source-to-wheel provenance.",
            "This gate does not authorize tagging, release, installation, or runtime effects.",
            "Bootstrap identity records gate provenance only and cannot authorize descendants.",
        ],
        "approval_authority": "none",
        "next_stage_authorized": False,
    }
    return errors, result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-lock", action="store_true")
    mode.add_argument("--verify-acquisition", action="store_true")
    mode.add_argument("--formal", action="store_true")
    parser.add_argument("--pip-report", type=Path)
    parser.add_argument("--acquisition-result", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument(
        "--candidate-base",
        help="Full immutable base commit for the current descendant candidate.",
    )
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument(
        "--run-attempt",
        default=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    )
    parser.add_argument(
        "--workflow-ref",
        default=os.environ.get("GITHUB_WORKFLOW_REF", ""),
    )
    parser.add_argument("--job-name", default=os.environ.get("GITHUB_JOB", ""))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    identity = {
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "workflow_ref": args.workflow_ref,
        "job_name": args.job_name,
    }
    try:
        if args.check_lock:
            errors = validate_lock()
            inventory_errors, schemas = validate_schema_inventory()
            errors.extend(inventory_errors)
            positives, negatives = materialized_fixture_cases()
            errors.extend(validate_fixture_coverage(positives, negatives))
            payload = {
                "status": "PASS" if not errors else "FAIL",
                "locked_distributions": len(DISTRIBUTIONS),
                "schema_inventory": len(schemas),
                "fixture_validated_schema_count": len(FIXTURE_VALIDATED_SCHEMAS),
                "syntax_only_schema_count": len(SYNTAX_ONLY_SCHEMAS),
                "formal_execution": "PENDING",
            }
        elif args.verify_acquisition:
            missing = []
            if args.pip_report is None:
                missing.append("--pip-report")
            if args.evidence_dir is None:
                missing.append("--evidence-dir")
            if args.result is None:
                missing.append("--result")
            if args.candidate_base is None:
                missing.append("--candidate-base")
            if missing:
                errors = [f"--verify-acquisition requires {' and '.join(missing)}"]
                payload = {"status": "FAIL", "gate": "formal-acquisition"}
            else:
                errors, payload = acquire_evidence(
                    args.pip_report.resolve(),
                    args.evidence_dir.resolve(),
                    args.result.resolve(),
                    identity,
                    args.candidate_base,
                )
        else:
            missing = []
            if args.pip_report is None:
                missing.append("--pip-report")
            if args.acquisition_result is None:
                missing.append("--acquisition-result")
            if args.evidence_dir is None:
                missing.append("--evidence-dir")
            if args.candidate_base is None:
                missing.append("--candidate-base")
            if missing:
                errors = [f"--formal requires {' and '.join(missing)}"]
                payload = {"status": "FAIL", "gate": "formal-draft-2020-12"}
            else:
                errors, payload = validate_formal(
                    args.pip_report.resolve(),
                    args.acquisition_result.resolve(),
                    args.evidence_dir.resolve(),
                    identity,
                    args.candidate_base,
                )
    except Exception as exc:
        errors = [f"validator failed closed: {exc}"]
        payload = {"status": "FAIL"}
    if args.result is not None:
        write_json(args.result.resolve(), payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
