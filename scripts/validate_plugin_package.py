#!/usr/bin/env python3
"""Validate Codex plugin packaging for this repository."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
EXPECTED_NAME = "codex-long-horizon-skill"
EXPECTED_VERSION = "0.2.2"
EXPECTED_REPOSITORY = "https://github.com/Q20396/codex-long-horizon-skill"
EXPECTED_LICENSE = "MIT"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"missing file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_plugin_path(relative_path: str) -> Path:
    if not relative_path.startswith("./"):
        raise ValueError(f"plugin path must start with ./, got {relative_path!r}")
    resolved = (ROOT / relative_path).resolve()
    if not inside(resolved, ROOT):
        raise ValueError(f"plugin path escapes repository: {relative_path}")
    return resolved


def relative(path: Path, root: Path = ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_skill_frontmatter(path: Path, root: Path = ROOT) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{relative(path, root)} bundled skill is not valid UTF-8") from exc

    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0] != "---":
        raise ValueError(f"{relative(path, root)} bundled skill front matter is missing opening delimiter")

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError(f"{relative(path, root)} bundled skill front matter is missing closing delimiter")

    data: dict[str, str] = {}
    for raw_line in lines[1:closing_index]:
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")

    if "name" not in data:
        raise ValueError(f"{relative(path, root)} bundled skill front matter is missing name")
    if not data["name"].strip():
        raise ValueError(f"{relative(path, root)} bundled skill front matter name is empty")
    return data


def bundled_skill_names(skills_root: Path, errors: list[str], root: Path = ROOT) -> list[str]:
    skill_names = []
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"bundled skill missing SKILL.md: {relative(skill_dir, root)}")
            continue
        try:
            metadata = parse_skill_frontmatter(skill_md, root)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        skill_names.append(metadata["name"].strip())
    duplicates = sorted(name for name in set(skill_names) if skill_names.count(name) > 1)
    if duplicates:
        errors.append(f"duplicate bundled skill name: {', '.join(duplicates)}")
    return skill_names


def validate_manifest(errors: list[str]) -> dict:
    try:
        manifest = load_json(MANIFEST)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f".codex-plugin/plugin.json: {exc}")
        return {}

    for field in ["name", "version", "description", "repository", "license", "skills"]:
        if field not in manifest:
            errors.append(f"plugin.json missing required field: {field}")

    name = manifest.get("name", "")
    version = manifest.get("version", "")
    description = manifest.get("description", "")
    if name != EXPECTED_NAME:
        errors.append(f"plugin name must be {EXPECTED_NAME!r}")
    if not KEBAB.match(str(name)):
        errors.append("plugin name must be stable kebab-case")
    if not SEMVER.match(str(version)):
        errors.append("plugin version must be valid semantic version syntax")
    if version != EXPECTED_VERSION:
        errors.append(f"plugin version must be {EXPECTED_VERSION} for this phase")
    if not isinstance(description, str) or not description.strip():
        errors.append("plugin description must be non-empty")
    elif len(description) > 180:
        errors.append("plugin description should be concise")
    if manifest.get("license") != EXPECTED_LICENSE:
        errors.append(f"plugin license must match repository license: {EXPECTED_LICENSE}")
    if manifest.get("repository") != EXPECTED_REPOSITORY:
        errors.append(f"plugin repository must be {EXPECTED_REPOSITORY}")

    for absent in ["mcpServers", "apps", "hooks"]:
        if absent in manifest:
            errors.append(f"plugin.json must not reference {absent} without companion files")

    interface = manifest.get("interface", {})
    if not isinstance(interface, dict):
        errors.append("plugin interface must be an object")
    else:
        for asset_field in ["composerIcon", "logo", "screenshots"]:
            if asset_field in interface:
                errors.append(f"plugin interface references unsupported or missing asset field: {asset_field}")
        for link_field in ["websiteURL", "privacyPolicyURL", "termsOfServiceURL"]:
            if link_field in interface:
                errors.append(f"plugin interface must not reference unavailable {link_field}")

    skills_path = manifest.get("skills")
    if isinstance(skills_path, str):
        try:
            skills_root = resolve_plugin_path(skills_path)
            if not skills_root.is_dir():
                errors.append(f"skills path does not exist: {skills_path}")
            else:
                bundled_skill_names(skills_root, errors)
        except (OSError, ValueError) as exc:
            errors.append(f"invalid skills path: {exc}")
    else:
        errors.append("plugin skills path must be a string")

    duplicate_skill_roots = [
        path
        for path in [ROOT / "skills", ROOT / "plugins", ROOT / ".codex-plugin" / "skills"]
        if path.exists()
    ]
    if duplicate_skill_roots:
        errors.append(
            "duplicate committed plugin skill tree found: "
            + ", ".join(str(path.relative_to(ROOT)) for path in duplicate_skill_roots)
        )

    return manifest


def validate_marketplace(errors: list[str], manifest: dict) -> dict:
    try:
        marketplace = load_json(MARKETPLACE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f".agents/plugins/marketplace.json: {exc}")
        return {}

    if marketplace.get("name") != "codex-long-horizon-skills":
        errors.append("marketplace name must be codex-long-horizon-skills")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append("marketplace must contain exactly one plugin entry")
        return marketplace

    plugin = plugins[0]
    if plugin.get("name") != manifest.get("name", EXPECTED_NAME):
        errors.append("marketplace plugin name must match plugin manifest")
    source = plugin.get("source")
    if not isinstance(source, dict):
        errors.append("marketplace source must be an object")
    else:
        source_type = source.get("source")
        if source_type == "url":
            if source.get("url") != EXPECTED_REPOSITORY + ".git":
                errors.append(f"marketplace source.url must be {EXPECTED_REPOSITORY}.git")
            if source.get("ref") != "main":
                errors.append("marketplace source.ref must be main")
        else:
            errors.append("marketplace source.source must be url for root plugin CLI installs")

    policy = plugin.get("policy")
    if not isinstance(policy, dict):
        errors.append("marketplace policy must be an object")
    else:
        if policy.get("installation") not in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}:
            errors.append("marketplace policy.installation has invalid value")
        if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
            errors.append("marketplace policy.authentication has invalid value")
    if plugin.get("category") != "Productivity":
        errors.append("marketplace category must be Productivity")
    return marketplace


def validate_release_sync(errors: list[str]) -> None:
    release_notes = ROOT / "docs" / "releases" / f"v{EXPECTED_VERSION}.md"
    if release_notes.exists() and f"v{EXPECTED_VERSION}" not in release_notes.read_text(encoding="utf-8"):
        errors.append("release notes do not mention the expected version")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Codex plugin manifest and marketplace.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Alias for the default validation mode.",
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    errors: list[str] = []
    manifest = validate_manifest(errors)
    validate_marketplace(errors, manifest)
    validate_release_sync(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("Plugin package validation passed.")


if __name__ == "__main__":
    main()
