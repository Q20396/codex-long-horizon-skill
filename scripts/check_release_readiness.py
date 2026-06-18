#!/usr/bin/env python3
"""Check deterministic release-readiness gates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

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
    Path("scripts/validate_plugin_package.py"),
    Path("scripts/test_fresh_install.py"),
    Path("scripts/full_skill_validation.py"),
    Path("scripts/check_release_readiness.py"),
    Path("tests/test_release_tooling.py"),
    Path("tests/expected-triggers.json"),
    Path(".agents/plugins/marketplace.json"),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate deterministic release-readiness requirements. "
            "Default mode is --allow-existing-tag for post-release-safe routine CI."
        )
    )
    parser.add_argument("--version", required=True, help="Release version, for example 0.1.0.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--pre-tag",
        action="store_true",
        help="Final local gate before tagging; fails if refs/tags/vVERSION already exists.",
    )
    mode.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Routine CI mode; validates artifacts without caring whether the local tag exists.",
    )
    return parser.parse_args()


def release_notes_errors(version: str, errors: list[str]) -> None:
    release_notes = ROOT / "docs" / "releases" / f"v{version}.md"
    if not release_notes.is_file():
        errors.append(f"release notes missing: docs/releases/v{version}.md")
        return

    try:
        text = release_notes.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"release notes are not valid UTF-8: docs/releases/v{version}.md")
        return

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


def extract_markdown_section(text: str, heading: str) -> str | None:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def changelog_errors(version: str, errors: list[str]) -> None:
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        errors.append("CHANGELOG.md missing")
        return
    try:
        text = changelog.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("CHANGELOG.md is not valid UTF-8")
        return

    heading = f"{version} - 2026-06-18"
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


def package_errors(version: str, errors: list[str]) -> None:
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
        load_json(marketplace_path)

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


def validate(args: argparse.Namespace) -> list[str]:
    version = args.version
    errors: list[str] = []

    if not SEMVER_RE.match(version):
        errors.append("version must be plain semantic version syntax")
        return errors

    package_errors(version, errors)
    release_notes_errors(version, errors)
    changelog_errors(version, errors)
    tag_errors(version, args.pre_tag, errors)
    return errors


def main() -> int:
    args = parse_args()
    mode = "pre-tag" if args.pre_tag else "allow-existing-tag"
    try:
        errors = validate(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"Release readiness check passed for v{args.version} ({mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
