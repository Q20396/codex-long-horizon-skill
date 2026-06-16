#!/usr/bin/env python3
"""Check whether this skill package may be behind the GitHub version."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REMOTE_URL = "https://github.com/Q20396/codex-long-horizon-skill.git"
DEFAULT_BRANCH = "main"


def run_git(args: list[str], cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def try_git(args: list[str], cwd: Path = ROOT) -> str | None:
    try:
        return run_git(args, cwd)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def normalize_url(url: str) -> str:
    value = url.strip()
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    return value.rstrip("/")


def local_repo_matches(remote_url: str) -> bool:
    local_origin = try_git(["remote", "get-url", "origin"])
    if not local_origin:
        return False
    return normalize_url(local_origin) == normalize_url(remote_url)


def is_ancestor(older_sha: str, newer_sha: str) -> bool | None:
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", older_sha, newer_sha],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as error:
        if error.returncode == 1:
            return False
        return None
    except FileNotFoundError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether the local skill package appears to match the latest "
            "GitHub branch. This reports status only; it does not pull, update, "
            "overwrite files, or modify the repository."
        )
    )
    parser.add_argument(
        "--remote-url",
        default=DEFAULT_REMOTE_URL,
        help="Git remote URL for the canonical skill repository.",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help="Remote branch to compare against.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    remote_ref = f"refs/heads/{args.branch}"
    output = try_git(["ls-remote", args.remote_url, remote_ref])
    if not output:
        print("ERROR: Could not query the remote GitHub repository.")
        print("No files were changed. Check network access and the remote URL.")
        raise SystemExit(1)

    remote_sha = output.split()[0]
    local_sha = try_git(["rev-parse", "HEAD"])
    matches_expected_repo = local_repo_matches(args.remote_url)

    print("Skill package update check")
    print(f"Remote: {args.remote_url}")
    print(f"Branch: {args.branch}")
    print(f"Remote {args.branch}: {remote_sha}")

    if not local_sha or not matches_expected_repo:
        print("Local status: cannot safely compare this checkout to the skill repository.")
        print(
            "Reason: this directory does not appear to be a clone of the canonical "
            "skill repository, or git metadata is unavailable."
        )
        print("Action: compare against the GitHub repository before copying updates.")
        return

    print(f"Local HEAD: {local_sha}")

    if local_sha == remote_sha:
        print("Status: up to date.")
        return

    remote_is_ancestor = is_ancestor(remote_sha, local_sha)
    if remote_is_ancestor is True:
        print("Status: local checkout is ahead of the checked GitHub branch.")
        print("Action: no GitHub update is needed for this branch.")
        return

    local_is_ancestor = is_ancestor(local_sha, remote_sha)
    if local_is_ancestor is True:
        print("Status: update may be available.")
    else:
        print("Status: local and remote differ; review is needed.")

    print("Action: review the GitHub diff or pull request before updating local skills.")
    print("Do not overwrite local project files or private data automatically.")


if __name__ == "__main__":
    main()
