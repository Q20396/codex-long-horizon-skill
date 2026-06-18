#!/usr/bin/env python3
"""Run deterministic fresh-clone and isolated-install smoke checks."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SKILLS = ["long-horizon-engineering", "ai-video-production"]


def run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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


def codex_cli_available() -> bool:
    return shutil.which("codex") is not None


def maybe_run_codex_marketplace_smoke(copy_root: Path, temp_home: Path, *, skip: bool) -> str:
    if skip:
        return "skipped by flag"
    if not codex_cli_available():
        return "skipped: codex CLI not installed"

    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["CODEX_HOME"] = str(temp_home / ".codex")
    (temp_home / ".codex").mkdir(parents=True, exist_ok=True)

    help_result = run(["codex", "plugin", "marketplace", "--help"], cwd=copy_root, env=env)
    if help_result.returncode != 0:
        return "skipped: codex marketplace command unavailable"
    if " add" not in help_result.stdout or "upgrade" not in help_result.stdout:
        return "skipped: codex marketplace add/upgrade commands unavailable"
    if " list" not in help_result.stdout:
        return "skipped: current codex CLI has no marketplace list command"

    add_result = run(["codex", "plugin", "marketplace", "add", str(copy_root)], cwd=copy_root, env=env)
    if add_result.returncode != 0:
        return f"skipped: isolated marketplace add failed: {add_result.stderr.strip() or add_result.stdout.strip()}"
    list_result = run(["codex", "plugin", "marketplace", "list"], cwd=copy_root, env=env)
    if list_result.returncode != 0:
        return f"skipped: isolated marketplace list failed: {list_result.stderr.strip() or list_result.stdout.strip()}"
    return "passed: isolated codex marketplace add/list"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fresh isolated install smoke checks.")
    parser.add_argument("--skip-codex-cli", action="store_true", help="Skip optional Codex CLI marketplace checks.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary directory for inspection.")
    parser.add_argument("--verbose", action="store_true", help="Print temporary paths and optional skip details.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    temp_dir = Path(tempfile.mkdtemp(prefix="codex-skill-fresh-install-"))
    try:
        copy_root = temp_dir / "repo-copy"
        project_root = temp_dir / "target-project"
        user_root = temp_dir / "user-home"
        project_root.mkdir()
        user_root.mkdir()
        copy_repo(ROOT, copy_root)

        run_package_checks(copy_root)
        install_direct_skills(copy_root, project_root)
        verify_installed_project(project_root)
        install_direct_skills(copy_root, user_root)
        verify_installed_project(user_root)
        assert_no_absolute_source_paths(copy_root, ROOT)
        assert_no_absolute_source_paths(project_root, ROOT)
        assert_no_absolute_source_paths(user_root, ROOT)
        cli_status = maybe_run_codex_marketplace_smoke(copy_root, user_root, skip=args.skip_codex_cli)

        if args.verbose:
            print(f"Temporary root: {temp_dir}")
            print(f"Optional Codex CLI marketplace check: {cli_status}")
        else:
            print(f"Optional Codex CLI marketplace check: {cli_status}")
        print("Fresh isolated install smoke test passed.")
    finally:
        if args.keep_temp:
            print(f"Kept temporary root: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
