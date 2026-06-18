#!/usr/bin/env python3
"""Check deterministic pre-release readiness gates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate deterministic release-readiness requirements.")
    parser.add_argument("--version", required=True, help="Release version, for example 0.1.0.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    version = args.version
    errors: list[str] = []

    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        errors.append(".codex-plugin/plugin.json missing")
        manifest = {}
    else:
        manifest = load_json(manifest_path)
        if manifest.get("version") != version:
            errors.append(f"plugin version {manifest.get('version')!r} does not match {version!r}")

    release_notes = ROOT / "docs" / "releases" / f"v{version}.md"
    if not release_notes.is_file():
        errors.append(f"release notes missing: docs/releases/v{version}.md")
    else:
        text = release_notes.read_text(encoding="utf-8")
        required_terms = [
            "long-horizon engineering",
            "AI video production",
            "Codex plugin",
            "repository marketplace",
            "not released",
        ]
        for term in required_terms:
            if term.lower() not in text.lower():
                errors.append(f"release notes missing expected topic: {term}")

    checklist = ROOT / "docs" / "maintainers" / "release-checklist.md"
    if not checklist.is_file():
        errors.append("release checklist missing: docs/maintainers/release-checklist.md")

    for path in [
        ROOT / "scripts" / "validate_plugin_package.py",
        ROOT / "scripts" / "test_fresh_install.py",
        ROOT / "scripts" / "full_skill_validation.py",
        ROOT / "tests" / "expected-triggers.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
    ]:
        if not path.is_file():
            errors.append(f"required release-readiness file missing: {path.relative_to(ROOT)}")

    tag = f"v{version}"
    tag_result = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"])
    if tag_result.returncode == 0:
        errors.append(f"tag already exists; this branch should prepare but not publish {tag}")

    if not re.match(r"^\d+\.\d+\.\d+$", version):
        errors.append("version must be plain semantic version syntax")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"Release readiness check passed for v{version}.")


if __name__ == "__main__":
    main()
