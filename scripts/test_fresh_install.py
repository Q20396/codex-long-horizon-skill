#!/usr/bin/env python3
"""Run deterministic fresh-clone and isolated-install smoke checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SKILLS = ["long-horizon-engineering", "ai-video-production"]
EXPECTED_REPOSITORY = "https://github.com/Q20396/codex-long-horizon-skill"

PASSED = "passed"
FAILED = "failed"
SKIPPED_UNAVAILABLE = "skipped_unavailable"
SKIPPED_BY_FLAG = "skipped_by_flag"


@dataclass
class StageResult:
    name: str
    status: str
    detail: str = ""


@dataclass
class CliSummary:
    version: str = "unavailable"
    marketplace_add: str = "unavailable"
    marketplace_add_json: str = "unavailable"
    marketplace_list: str = "unavailable"
    marketplace_list_json: str = "unavailable"
    plugin_add: str = "unavailable"
    plugin_add_json: str = "unavailable"
    plugin_list: str = "unavailable"
    plugin_list_json: str = "unavailable"


@dataclass
class MarketplaceEvidence:
    name: str
    source_root: Path
    installed_roots: list[Path]


def run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def copy_repo(source: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".DS_Store",
    )
    shutil.copytree(source, target, ignore=ignored)


def assert_no_absolute_source_paths(root: Path, source_root: Path) -> None:
    source_text = str(source_root)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if source_text in text:
            raise AssertionError(f"absolute source checkout path found in {path}")


def run_package_checks(copy_root: Path) -> None:
    commands = [
        [PYTHON, "scripts/validate_plugin_package.py"],
        [PYTHON, ".agents/skills/long-horizon-engineering/scripts/check_skill_package.py"],
        [PYTHON, ".agents/skills/long-horizon-engineering/scripts/doctor.py"],
    ]
    for command in commands:
        result = run(command, cwd=copy_root)
        if result.returncode != 0:
            raise AssertionError(
                f"command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )


def install_direct_skills(copy_root: Path, target_root: Path) -> None:
    update_script = ".agents/skills/long-horizon-engineering/scripts/update_installed_skill.py"
    for skill in SKILLS:
        result = run(
            [
                PYTHON,
                update_script,
                "--target-root",
                str(target_root),
                "--skill",
                skill,
                "--apply",
            ],
            cwd=copy_root,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"direct install failed for {skill}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        installed = target_root / ".agents" / "skills" / skill / "SKILL.md"
        if not installed.is_file():
            raise AssertionError(f"installed skill missing: {installed}")


def verify_installed_project(target_root: Path) -> None:
    checker = target_root / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "check_skill_package.py"
    result = run([PYTHON, str(checker), "--installed"], cwd=target_root)
    if result.returncode != 0:
        raise AssertionError(
            f"installed project check failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_metadata(copy_root: Path) -> tuple[str, str, str]:
    manifest = load_json(copy_root / ".codex-plugin" / "plugin.json")
    marketplace = load_json(copy_root / ".agents" / "plugins" / "marketplace.json")
    return manifest["name"], manifest["version"], marketplace["name"]


def isolated_env(temp_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["CODEX_HOME"] = str(temp_home / ".codex")
    env["XDG_CONFIG_HOME"] = str(temp_home / ".config")
    env["XDG_CACHE_HOME"] = str(temp_home / ".cache")
    env["XDG_DATA_HOME"] = str(temp_home / ".local" / "share")
    for key in ["CODEX_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"]:
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def codex_path(env: dict[str, str]) -> str | None:
    return shutil.which("codex", path=env.get("PATH"))


def output_text(result: subprocess.CompletedProcess[str]) -> str:
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def command_help(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return run(["codex", *args, "--help"], cwd=cwd, env=env)


def command_available(args: list[str], *, cwd: Path, env: dict[str, str]) -> tuple[bool, str]:
    result = command_help(args, cwd=cwd, env=env)
    return result.returncode == 0, output_text(result)


def has_json_option(help_text: str) -> bool:
    return "--json" in help_text


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_files(root: Path) -> dict[Path, tuple[int, int, str]]:
    snapshot: dict[Path, tuple[int, int, str]] = {}
    if not root.exists():
        return snapshot
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        snapshot[path.resolve()] = (stat.st_size, stat.st_mtime_ns, file_digest(path))
    return snapshot


def changed_files(before: dict[Path, tuple[int, int, str]], root: Path) -> list[Path]:
    after = snapshot_files(root)
    return sorted(path for path, state in after.items() if before.get(path) != state)


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def parse_json_output(result: subprocess.CompletedProcess[str]) -> object | None:
    text = result.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def json_contains(data: object, expected: str) -> bool:
    if isinstance(data, dict):
        return any(json_contains(value, expected) for value in data.values())
    if isinstance(data, list):
        return any(json_contains(value, expected) for value in data)
    return expected in str(data)


def verify_json_path(data: object, key: str, temp_root: Path) -> str | None:
    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, str):
            path = Path(value).expanduser()
            if path.exists() and is_inside(path, temp_root):
                return str(path)
            return None
        for child in data.values():
            found = verify_json_path(child, key, temp_root)
            if found:
                return found
    if isinstance(data, list):
        for child in data:
            found = verify_json_path(child, key, temp_root)
            if found:
                return found
    return None


def safe_relative_path(root: Path, value: str) -> Path | None:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = canonical(candidate)
    if is_inside(candidate, root):
        return candidate
    return None


def verify_persisted_registration(
    files: list[Path],
    *,
    marketplace_name: str,
    source_root: Path,
    isolated_root: Path,
) -> str | None:
    source_texts = {str(source_root), str(source_root.resolve())}
    inspected: list[str] = []
    isolated_resolved = isolated_root.resolve()
    for path in files:
        resolved_path = path.resolve()
        if not is_inside(resolved_path, isolated_resolved):
            continue
        if resolved_path.stat().st_size > 2_000_000:
            continue
        try:
            text = resolved_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        inspected.append(str(resolved_path.relative_to(isolated_resolved)))
        if marketplace_name in text and any(source_text in text for source_text in source_texts):
            return f"{resolved_path.relative_to(isolated_resolved)} contains marketplace name and source path"
    if inspected:
        return None
    return None


def verify_marketplace_root(
    root: Path,
    *,
    marketplace_name: str,
    plugin_name: str,
    version: str,
    boundary: Path,
) -> str | None:
    root = canonical(root)
    if not root.is_dir() or not is_inside(root, boundary):
        return None
    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    if not marketplace_path.is_file():
        return None
    try:
        marketplace = load_json(marketplace_path)
    except (OSError, json.JSONDecodeError):
        return None
    if marketplace.get("name") != marketplace_name:
        return None
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        return None
    plugin_entry = next(
        (entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == plugin_name),
        None,
    )
    if plugin_entry is None:
        return None
    source = plugin_entry.get("source", {})
    if not isinstance(source, dict):
        return None
    source_type = source.get("source")
    if source_type in {"url", "git"}:
        url = source.get("url")
        if url not in {EXPECTED_REPOSITORY, EXPECTED_REPOSITORY + ".git"}:
            return None
        ref = source.get("ref")
        if ref not in {None, "main"}:
            return None
        return str(root)
    plugin_path_value = source.get("path", "./")
    if not isinstance(plugin_path_value, str):
        return None
    plugin_root = safe_relative_path(root, plugin_path_value)
    if plugin_root is None:
        return None
    return verify_plugin_root(plugin_root, plugin_name, version, boundary=boundary, excluded_roots=[])


def json_string_values(data: object) -> list[str]:
    if isinstance(data, dict):
        values: list[str] = []
        for value in data.values():
            values.extend(json_string_values(value))
        return values
    if isinstance(data, list):
        values = []
        for value in data:
            values.extend(json_string_values(value))
        return values
    if isinstance(data, str):
        return [data]
    return []


def marketplace_entry_linked(entry: dict, root: Path, evidence: MarketplaceEvidence) -> bool:
    expected_roots = {canonical(evidence.source_root), *[canonical(path) for path in evidence.installed_roots]}
    if root in expected_roots:
        return True
    source_root = canonical(evidence.source_root)
    for value in json_string_values(entry.get("marketplaceSource")):
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            continue
        if canonical(candidate) == source_root:
            return True
    return False


def verify_plugin_root(
    root: Path,
    plugin_name: str,
    version: str,
    *,
    boundary: Path,
    excluded_roots: list[Path],
) -> str | None:
    root = canonical(root)
    if not root.is_dir() or not is_inside(root, boundary):
        return None
    if any(root == canonical(excluded) or is_inside(root, canonical(excluded)) for excluded in excluded_roots):
        return None
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("name") != plugin_name or manifest.get("version") != version:
        return None
    skills_root = root / manifest.get("skills", "./.agents/skills/")
    if not (skills_root / "long-horizon-engineering" / "SKILL.md").is_file():
        return None
    if not (skills_root / "ai-video-production" / "SKILL.md").is_file():
        return None
    return str(root)


def verify_installed_plugin_root(
    path_text: str,
    plugin_name: str,
    version: str,
    *,
    boundary: Path,
    excluded_roots: list[Path],
) -> str | None:
    return verify_plugin_root(
        Path(path_text),
        plugin_name,
        version,
        boundary=boundary,
        excluded_roots=excluded_roots,
    )


def marketplace_list_entries(data: object) -> list[dict]:
    if isinstance(data, dict):
        marketplaces = data.get("marketplaces")
        if isinstance(marketplaces, list):
            return [entry for entry in marketplaces if isinstance(entry, dict)]
        return [data]
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    return []


def verify_marketplace_list_json(
    data: object,
    evidence: MarketplaceEvidence,
    *,
    plugin_name: str,
    version: str,
    boundary: Path,
) -> str | None:
    for entry in marketplace_list_entries(data):
        if entry.get("name") != evidence.name:
            continue
        root_value = entry.get("root")
        if not isinstance(root_value, str) or not root_value.strip():
            continue
        root = canonical(Path(root_value))
        if not root.exists() or not is_inside(root, boundary):
            continue
        verified_root = verify_marketplace_root(
            root,
            marketplace_name=evidence.name,
            plugin_name=plugin_name,
            version=version,
            boundary=boundary,
        )
        if marketplace_entry_linked(entry, root, evidence) and verified_root:
            return f"marketplace list JSON verified root={root}"
    return None


def candidate_paths_from_text(text: str) -> list[Path]:
    candidates: list[Path] = []
    for raw in text.replace(",", " ").split():
        token = raw.strip("`'\"()[]{}<>")
        if "/" in token or token.startswith("."):
            candidates.append(Path(token).expanduser())
    return candidates


def verify_marketplace_list_text(
    text: str,
    evidence: MarketplaceEvidence,
    *,
    plugin_name: str,
    version: str,
    boundary: Path,
) -> str | None:
    if evidence.name not in text:
        return None
    expected_roots = {canonical(evidence.source_root), *[canonical(path) for path in evidence.installed_roots]}
    for line in text.splitlines():
        if evidence.name not in line:
            continue
        for root in expected_roots:
            if str(root) in line and verify_marketplace_root(
                root,
                marketplace_name=evidence.name,
                plugin_name=plugin_name,
                version=version,
                boundary=boundary,
            ):
                return f"marketplace list text contains verified root={root}"
        for path in candidate_paths_from_text(line):
            root = canonical(path)
            if root in expected_roots and verify_marketplace_root(
                root,
                marketplace_name=evidence.name,
                plugin_name=plugin_name,
                version=version,
                boundary=boundary,
            ):
                return f"marketplace list text verified root={root}"
    return None


def plugin_list_entries(data: object) -> list[tuple[dict, bool]]:
    if isinstance(data, dict):
        installed = data.get("installed")
        if isinstance(installed, list):
            return [(entry, True) for entry in installed if isinstance(entry, dict)]
        if data.get("name"):
            return [(data, False)]
    if isinstance(data, list):
        return [(entry, False) for entry in data if isinstance(entry, dict)]
    return []


def verify_plugin_list_json(data: object, *, plugin_name: str, marketplace_name: str, version: str) -> str | None:
    for entry, installed_collection in plugin_list_entries(data):
        if entry.get("name") != plugin_name:
            continue
        if entry.get("marketplaceName") != marketplace_name:
            continue
        if str(entry.get("version")) != version:
            continue
        installed = entry.get("installed")
        if installed_collection:
            if installed is not None and installed is not True:
                continue
        elif installed is not True:
            continue
        return f"plugin list JSON verified {plugin_name}@{marketplace_name} version={version}"
    return None


def exact_token_present(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_.-]){re.escape(token)}(?![A-Za-z0-9_.-])"
    return re.search(pattern, text) is not None


def verify_plugin_list_text(text: str, *, plugin_name: str, marketplace_name: str, version: str) -> str | None:
    for line in text.splitlines():
        lower = line.lower()
        if "installed" not in lower or "not installed" in lower:
            continue
        if not exact_token_present(line, plugin_name):
            continue
        if not exact_token_present(line, marketplace_name):
            continue
        if not exact_token_present(line, version):
            continue
        return f"plugin list text verified {plugin_name}@{marketplace_name} version={version}"
    return None


def find_ancestor_plugin_roots(
    paths: list[Path],
    *,
    boundary: Path,
    excluded_roots: list[Path],
) -> list[Path]:
    boundary = canonical(boundary)
    excluded = [canonical(path) for path in excluded_roots]
    roots: list[Path] = []
    seen: set[Path] = set()
    for changed in paths:
        current = canonical(changed)
        if current.is_file():
            current = current.parent
        while is_inside(current, boundary):
            if any(current == root or is_inside(current, root) for root in excluded):
                break
            if (current / ".codex-plugin" / "plugin.json").is_file():
                if current not in seen:
                    roots.append(current)
                    seen.add(current)
                break
            if current == boundary or current.parent == current:
                break
            current = current.parent
    return roots


def detect_cli(copy_root: Path, env: dict[str, str]) -> CliSummary:
    summary = CliSummary()
    if not codex_path(env):
        return summary
    version = run(["codex", "--version"], cwd=copy_root, env=env)
    if version.returncode == 0:
        summary.version = output_text(version).splitlines()[-1]
    for attr, args in [
        ("marketplace_add", ["plugin", "marketplace", "add"]),
        ("marketplace_list", ["plugin", "marketplace", "list"]),
        ("plugin_add", ["plugin", "add"]),
        ("plugin_list", ["plugin", "list"]),
    ]:
        available, help_text = command_available(args, cwd=copy_root, env=env)
        setattr(summary, attr, "available" if available else "unavailable")
        setattr(summary, f"{attr}_json", "available" if available and has_json_option(help_text) else "unavailable")
    return summary


def run_codex_cli_smoke(
    copy_root: Path,
    temp_home: Path,
    *,
    skip: bool,
    require_codex_cli: bool,
    require_plugin_install: bool,
) -> tuple[CliSummary, list[StageResult]]:
    stages: list[StageResult] = []
    env = isolated_env(temp_home)
    isolated_root = temp_home.parent
    plugin_name, version, marketplace_name = plugin_metadata(copy_root)

    if skip:
        for name in [
            "Marketplace registration",
            "Marketplace listing",
            "Plugin installation",
            "Plugin listing",
        ]:
            stages.append(StageResult(name, SKIPPED_BY_FLAG, "Codex CLI checks skipped by explicit flag"))
        return CliSummary(), stages

    if not codex_path(env):
        status = FAILED if require_codex_cli or require_plugin_install else SKIPPED_UNAVAILABLE
        detail = "Codex CLI not installed"
        for name in [
            "Marketplace registration",
            "Marketplace listing",
            "Plugin installation",
            "Plugin listing",
        ]:
            stages.append(StageResult(name, status if name == "Marketplace registration" else SKIPPED_UNAVAILABLE, detail))
        return CliSummary(), stages

    summary = detect_cli(copy_root, env)
    if summary.marketplace_add != "available":
        status = FAILED if require_codex_cli or require_plugin_install else SKIPPED_UNAVAILABLE
        stages.append(StageResult("Marketplace registration", status, "codex plugin marketplace add unavailable"))
        stages.append(StageResult("Marketplace listing", SKIPPED_UNAVAILABLE, "marketplace add unavailable"))
        stages.append(StageResult("Plugin installation", SKIPPED_UNAVAILABLE, "marketplace registration unavailable"))
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
        return summary, stages

    before = snapshot_files(temp_home)
    add_command = ["codex", "plugin", "marketplace", "add", str(copy_root)]
    if summary.marketplace_add_json == "available":
        add_command.append("--json")
    add_result = run(add_command, cwd=copy_root, env=env)
    if add_result.returncode != 0:
        stages.append(StageResult("Marketplace registration", FAILED, output_text(add_result)))
        stages.append(StageResult("Marketplace listing", SKIPPED_UNAVAILABLE, "registration failed"))
        stages.append(StageResult("Plugin installation", SKIPPED_UNAVAILABLE, "registration failed"))
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
        return summary, stages

    registration_evidence = ""
    registered_roots: list[Path] = []
    add_json = parse_json_output(add_result) if summary.marketplace_add_json == "available" else None
    if add_json is not None:
        if json_contains(add_json, marketplace_name):
            registration_evidence = "marketplace add JSON contains marketplace name"
        installed_root = verify_json_path(add_json, "installedRoot", isolated_root)
        if installed_root:
            registered_roots.append(Path(installed_root))
            registration_evidence = f"marketplace add JSON installedRoot={installed_root}"
    evidence = MarketplaceEvidence(
        name=marketplace_name,
        source_root=copy_root,
        installed_roots=registered_roots,
    )

    if summary.marketplace_list == "available":
        list_command = ["codex", "plugin", "marketplace", "list"]
        if summary.marketplace_list_json == "available":
            list_command.append("--json")
        list_result = run(list_command, cwd=copy_root, env=env)
        if list_result.returncode != 0:
            stages.append(StageResult("Marketplace registration", PASSED, registration_evidence or "add exited zero"))
            stages.append(StageResult("Marketplace listing", FAILED, output_text(list_result)))
            stages.append(StageResult("Plugin installation", SKIPPED_UNAVAILABLE, "listing failed"))
            stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
            return summary, stages
        if summary.marketplace_list_json == "available":
            list_json = parse_json_output(list_result)
            list_evidence = verify_marketplace_list_json(
                list_json,
                evidence,
                plugin_name=plugin_name,
                version=version,
                boundary=isolated_root,
            ) if list_json is not None else None
        else:
            list_evidence = verify_marketplace_list_text(
                output_text(list_result),
                evidence,
                plugin_name=plugin_name,
                version=version,
                boundary=isolated_root,
            )
        if not list_evidence:
            stages.append(StageResult("Marketplace registration", PASSED, registration_evidence or "add exited zero"))
            stages.append(
                StageResult(
                    "Marketplace listing",
                    FAILED,
                    "marketplace list did not identify the isolated registered marketplace root or source",
                )
            )
            stages.append(StageResult("Plugin installation", SKIPPED_UNAVAILABLE, "listing failed"))
            stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
            return summary, stages
        registration_evidence = registration_evidence or list_evidence
        stages.append(StageResult("Marketplace listing", PASSED, list_evidence))
    else:
        fallback = verify_persisted_registration(
            changed_files(before, temp_home),
            marketplace_name=marketplace_name,
            source_root=copy_root,
            isolated_root=temp_home,
        )
        if fallback:
            registration_evidence = registration_evidence or fallback
        stages.append(StageResult("Marketplace listing", SKIPPED_UNAVAILABLE, "codex plugin marketplace list unavailable"))

    if not registration_evidence:
        detail = (
            "marketplace add exited zero but no durable isolated registration evidence was found; "
            f"stdout={add_result.stdout.strip()!r}; stderr={add_result.stderr.strip()!r}; "
            f"isolated_home={temp_home}"
        )
        stages.insert(0, StageResult("Marketplace registration", FAILED, detail))
        stages.append(StageResult("Plugin installation", SKIPPED_UNAVAILABLE, "registration failed"))
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
        return summary, stages

    stages.insert(0, StageResult("Marketplace registration", PASSED, registration_evidence))

    if summary.plugin_add != "available":
        status = FAILED if require_plugin_install else SKIPPED_UNAVAILABLE
        stages.append(
            StageResult(
                "Plugin installation",
                status,
                "Marketplace registration verified; actual plugin installation command is unavailable on this installed Codex CLI version.",
            )
        )
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation unavailable"))
        return summary, stages

    plugin_arg = f"{plugin_name}@{marketplace_name}"
    plugin_command = ["codex", "plugin", "add", plugin_arg]
    if summary.plugin_add_json == "available":
        plugin_command.append("--json")
    plugin_before = snapshot_files(temp_home)
    plugin_result = run(plugin_command, cwd=copy_root, env=env)
    if plugin_result.returncode != 0:
        stages.append(StageResult("Plugin installation", FAILED, output_text(plugin_result)))
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation failed"))
        return summary, stages

    plugin_evidence = ""
    excluded_roots = [copy_root, *registered_roots]
    plugin_json = parse_json_output(plugin_result) if summary.plugin_add_json == "available" else None
    if plugin_json is not None:
        if not json_contains(plugin_json, plugin_name):
            stages.append(StageResult("Plugin installation", FAILED, "plugin add JSON did not contain plugin name"))
            stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation failed"))
            return summary, stages
        installed_path = verify_json_path(plugin_json, "installedPath", isolated_root)
        if installed_path:
            verified_root = verify_installed_plugin_root(
                installed_path,
                plugin_name,
                version,
                boundary=isolated_root,
                excluded_roots=excluded_roots,
            )
            if verified_root:
                plugin_evidence = f"installedPath verified at {verified_root}"
    if not plugin_evidence:
        candidates = find_ancestor_plugin_roots(
            changed_files(plugin_before, temp_home),
            boundary=isolated_root,
            excluded_roots=excluded_roots,
        )
        verified_roots = []
        for path in candidates:
            verified_root = verify_installed_plugin_root(
                str(path),
                plugin_name,
                version,
                boundary=isolated_root,
                excluded_roots=excluded_roots,
            )
            if verified_root:
                verified_roots.append(verified_root)
        if len(verified_roots) == 1:
            plugin_evidence = f"installed plugin files verified at {verified_roots[0]}"
        elif len(verified_roots) > 1:
            stages.append(StageResult("Plugin installation", FAILED, f"ambiguous plugin roots: {', '.join(verified_roots)}"))
            stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation failed"))
            return summary, stages
    if not plugin_evidence:
        stages.append(StageResult("Plugin installation", FAILED, "plugin add succeeded but installed package was not verified"))
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "plugin installation failed"))
        return summary, stages
    stages.append(StageResult("Plugin installation", PASSED, plugin_evidence))

    if summary.plugin_list != "available":
        stages.append(StageResult("Plugin listing", SKIPPED_UNAVAILABLE, "codex plugin list unavailable"))
        return summary, stages

    list_command = ["codex", "plugin", "list"]
    if summary.plugin_list_json == "available":
        list_command.append("--json")
    plugin_list_result = run(list_command, cwd=copy_root, env=env)
    if plugin_list_result.returncode != 0:
        stages.append(StageResult("Plugin listing", FAILED, output_text(plugin_list_result)))
    else:
        if summary.plugin_list_json == "available":
            plugin_list_json = parse_json_output(plugin_list_result)
            plugin_list_evidence = verify_plugin_list_json(
                plugin_list_json,
                plugin_name=plugin_name,
                marketplace_name=marketplace_name,
                version=version,
            ) if plugin_list_json is not None else None
        else:
            plugin_list_evidence = verify_plugin_list_text(
                output_text(plugin_list_result),
                plugin_name=plugin_name,
                marketplace_name=marketplace_name,
                version=version,
            )
        if plugin_list_evidence:
            stages.append(StageResult("Plugin listing", PASSED, plugin_list_evidence))
        else:
            stages.append(
                StageResult(
                    "Plugin listing",
                    FAILED,
                    "plugin list did not show exact installed plugin identity, marketplace, version, and installed state",
                )
            )
    return summary, stages


def print_stage(stage: StageResult) -> None:
    detail = f" - {stage.detail}" if stage.detail else ""
    print(f"{stage.name}: {stage.status}{detail}")


def failed(stages: list[StageResult]) -> bool:
    return any(stage.status == FAILED for stage in stages)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fresh isolated install smoke checks.")
    parser.add_argument("--skip-codex-cli", action="store_true", help="Skip Codex CLI marketplace/plugin checks.")
    parser.add_argument("--require-codex-cli", action="store_true", help="Fail unless Codex CLI marketplace registration passes.")
    parser.add_argument(
        "--require-plugin-install",
        action="store_true",
        help="Fail unless Codex CLI plugin installation passes; implies --require-codex-cli.",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary directory for inspection.")
    parser.add_argument("--verbose", action="store_true", help="Print temporary paths and CLI capability details.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.skip_codex_cli and (args.require_codex_cli or args.require_plugin_install):
        raise SystemExit("ERROR: --skip-codex-cli cannot be combined with strict CLI requirements.")
    require_codex_cli = args.require_codex_cli or args.require_plugin_install

    temp_dir = Path(tempfile.mkdtemp(prefix="codex-skill-fresh-install-"))
    stages: list[StageResult] = []
    try:
        copy_root = temp_dir / "repo-copy"
        project_root = temp_dir / "target-project"
        user_root = temp_dir / "user-home"
        project_root.mkdir()
        user_root.mkdir()
        copy_repo(ROOT, copy_root)

        run_package_checks(copy_root)
        stages.append(StageResult("Deterministic plugin package validation", PASSED))
        install_direct_skills(copy_root, project_root)
        verify_installed_project(project_root)
        stages.append(StageResult("Project-scoped direct skill installation", PASSED))
        install_direct_skills(copy_root, user_root)
        verify_installed_project(user_root)
        stages.append(StageResult("User-scoped direct skill installation", PASSED))
        assert_no_absolute_source_paths(copy_root, ROOT)
        assert_no_absolute_source_paths(project_root, ROOT)
        assert_no_absolute_source_paths(user_root, ROOT)

        cli_summary, cli_stages = run_codex_cli_smoke(
            copy_root,
            user_root,
            skip=args.skip_codex_cli,
            require_codex_cli=require_codex_cli,
            require_plugin_install=args.require_plugin_install,
        )
        stages.extend(cli_stages)

        if args.verbose:
            print(f"Temporary root: {temp_dir}")
            print(f"Codex CLI version: {cli_summary.version}")
            print(f"Capability marketplace add: {cli_summary.marketplace_add}")
            print(f"Capability marketplace add --json: {cli_summary.marketplace_add_json}")
            print(f"Capability marketplace list: {cli_summary.marketplace_list}")
            print(f"Capability marketplace list --json: {cli_summary.marketplace_list_json}")
            print(f"Capability plugin add: {cli_summary.plugin_add}")
            print(f"Capability plugin add --json: {cli_summary.plugin_add_json}")
            print(f"Capability plugin list: {cli_summary.plugin_list}")
            print(f"Capability plugin list --json: {cli_summary.plugin_list_json}")
        for stage in stages:
            print_stage(stage)
        if failed(stages):
            raise SystemExit(1)

        unavailable = [stage for stage in stages if stage.status == SKIPPED_UNAVAILABLE]
        if unavailable:
            print("Fresh isolated install checks passed with unavailable CLI capabilities reported above.")
        else:
            print("Fresh isolated install checks passed.")
    finally:
        if args.keep_temp:
            print(f"Kept temporary root: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
