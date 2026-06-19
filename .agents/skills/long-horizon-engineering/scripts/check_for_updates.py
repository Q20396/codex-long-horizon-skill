#!/usr/bin/env python3
"""Manually check whether this skill package matches an approved source."""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REMOTE_URL = "https://github.com/Q20396/codex-long-horizon-skill.git"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SCP_LIKE_RE = re.compile(r"^[^/\s:@]+@[^/\s:]+:.+")
REFERENCE_VERIFICATION_ERROR = 1
POLICY_ERROR = 2
MUTABLE_REF_NAMES = {
    "branch",
    "head",
    "latest",
    "main",
    "master",
    "release",
    "stable",
    "trunk",
}
OBVIOUS_LOCAL_HOSTNAMES = {
    "host.docker.internal",
    "gateway.docker.internal",
    "metadata.google.internal",
}
PROXY_ENV_NAMES = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}
GitRunner = Callable[[list[str], Path, int], str]
Resolver = Callable[[str, int], list[str]]


class PolicyError(ValueError):
    """Raised when the requested update check violates the safety contract."""


class RemoteCheckError(RuntimeError):
    """Raised when a permitted read-only remote check fails."""


def minimal_git_env(home_dir: Path, xdg_config_home: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home_dir),
        "XDG_CONFIG_HOME": str(xdg_config_home),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "GCM_INTERACTIVE": "Never",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    for name in ("LANG", "LC_ALL", "SYSTEMROOT", "WINDIR"):
        if name in os.environ:
            env[name] = os.environ[name]
    for name in PROXY_ENV_NAMES:
        env.pop(name, None)
    return env


def git_command(args: list[str]) -> list[str]:
    return [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        "core.askPass=",
        "-c",
        "http.proxy=",
        "-c",
        "https.proxy=",
        "-c",
        "http.followRedirects=false",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "protocol.ext.allow=never",
        *args,
    ]


def run_git(args: list[str], cwd: Path = ROOT, timeout_seconds: int = 30) -> str:
    try:
        with tempfile.TemporaryDirectory(prefix="codex-skill-git-") as temp:
            temp_root = Path(temp)
            home_dir = temp_root / "home"
            xdg_config_home = temp_root / "xdg"
            home_dir.mkdir()
            xdg_config_home.mkdir()
            result = subprocess.run(
                git_command(args),
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=minimal_git_env(home_dir, xdg_config_home),
                shell=False,
                stdin=subprocess.DEVNULL,
            )
    except subprocess.TimeoutExpired as error:
        raise RemoteCheckError("git command timed out") from error
    except OSError as error:
        raise RemoteCheckError("git command failed to start") from error

    if result.returncode != 0:
        raise RemoteCheckError(f"git command failed with exit code {result.returncode}")
    return result.stdout.strip()


def try_git(
    args: list[str],
    runner: GitRunner = run_git,
    cwd: Path = ROOT,
    timeout_seconds: int = 30,
) -> str | None:
    try:
        return runner(args, cwd, timeout_seconds)
    except (FileNotFoundError, RemoteCheckError, subprocess.SubprocessError):
        return None


def normalize_url(url: str) -> str:
    value = url.strip()
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    return value.rstrip("/")


def local_repo_matches(remote_url: str, runner: GitRunner = run_git) -> bool:
    local_origin = try_git(["remote", "get-url", "origin"], runner)
    if not local_origin:
        return False
    return normalize_url(local_origin) == normalize_url(remote_url)


def is_full_sha(value: str | None) -> bool:
    return bool(value and FULL_SHA_RE.fullmatch(value.strip().lower()))


def is_mutable_ref(value: str) -> bool:
    normalized = value.strip().lower()
    basename = normalized.rsplit("/", 1)[-1]
    return (
        normalized.startswith("refs/heads/")
        or normalized.startswith("origin/")
        or normalized in MUTABLE_REF_NAMES
        or basename in MUTABLE_REF_NAMES
    )


def is_public_ip_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_private
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def is_obvious_local_hostname(hostname: str) -> bool:
    value = hostname.rstrip(".").lower()
    return (
        value in OBVIOUS_LOCAL_HOSTNAMES
        or value == "localhost"
        or value.startswith("localhost.")
        or value.endswith(".localhost")
        or value.endswith(".local")
        or value.endswith(".internal")
        or "." not in value
    )


def resolve_hostname(hostname: str, port: int) -> list[str]:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise RemoteCheckError("DNS lookup failed for remote host") from error
    addresses = sorted({item[4][0] for item in results if item and item[4]})
    if not addresses:
        raise RemoteCheckError("DNS lookup returned no remote addresses")
    return addresses


def validate_remote_url(
    remote_url: str,
    resolve_dns: bool = False,
    resolver: Resolver = resolve_hostname,
) -> None:
    value = remote_url.strip()
    if not value:
        raise PolicyError("remote URL must be a public HTTPS URL")
    if value.startswith(("/", "./", "../", "~")):
        raise PolicyError("remote URL must be a public HTTPS URL")
    if SCP_LIKE_RE.match(value):
        raise PolicyError("SSH or scp-style Git URLs are not allowed")

    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise PolicyError("remote URL scheme must be https")
    if parsed.username or parsed.password:
        raise PolicyError("remote URL must not contain embedded credentials")
    if parsed.fragment:
        raise PolicyError("remote URL fragments are not allowed")
    hostname = parsed.hostname
    if not hostname:
        raise PolicyError("remote URL hostname is required")
    try:
        port = parsed.port
    except ValueError as error:
        raise PolicyError("remote URL port is malformed") from error
    if port is not None and port != 443:
        raise PolicyError("remote URL port must be 443 when specified")

    host = hostname.rstrip(".")
    try:
        is_ip_literal = ipaddress.ip_address(host)
    except ValueError:
        is_ip_literal = None

    if is_ip_literal is not None:
        if not is_public_ip_address(host):
            raise PolicyError("remote URL must resolve to public routable addresses")
        return

    if is_obvious_local_hostname(host):
        raise PolicyError("remote URL hostname must not be local or private")

    if resolve_dns:
        addresses = resolver(host, port or 443)
        for address in addresses:
            try:
                public_address = is_public_ip_address(address)
            except ValueError as error:
                raise PolicyError(
                    "remote URL DNS must resolve only to valid IP addresses"
                ) from error
            if not public_address:
                raise PolicyError(
                    "remote URL DNS must resolve only to public routable addresses"
                )


def validate_source_ref(args: argparse.Namespace) -> str:
    if args.source_tag:
        tag = args.source_tag.strip()
        if is_mutable_ref(tag):
            raise PolicyError(
                "mutable refs such as main, master, latest, branches, or moving "
                "aliases are not valid update-check sources"
            )
        if not args.allow_network:
            raise PolicyError(
                "--source-tag requires --allow-network because it performs a "
                "read-only git ls-remote lookup"
            )
        if not is_full_sha(args.expected_commit):
            raise PolicyError(
                "--source-tag requires --expected-commit with a full 40-character SHA"
            )
        return "tag"

    if not is_full_sha(args.source_commit):
        raise PolicyError("--source-commit requires a full 40-character SHA")
    if args.expected_commit:
        raise PolicyError("--expected-commit is only used with --source-tag")
    return "commit"


def parse_tag_output(output: str, tag: str) -> str:
    if not output.strip():
        raise RemoteCheckError(f"tag not found on remote: {tag}")

    direct_shas: list[str] = []
    peeled_shas: list[str] = []
    expected_direct_ref = f"refs/tags/{tag}"
    expected_peeled_ref = f"refs/tags/{tag}^{{}}"

    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            raise RemoteCheckError("malformed tag lookup output")
        sha, ref = parts
        if not is_full_sha(sha):
            raise RemoteCheckError("tag lookup returned an invalid SHA")
        sha = sha.lower()
        if ref == expected_direct_ref:
            direct_shas.append(sha)
        elif ref == expected_peeled_ref:
            peeled_shas.append(sha)
        else:
            raise RemoteCheckError("tag lookup returned an unexpected ref")

    direct_set = set(direct_shas)
    peeled_set = set(peeled_shas)
    if not direct_set:
        raise RemoteCheckError("peeled tag result did not include the tag ref")
    if len(direct_set) > 1:
        raise RemoteCheckError("ambiguous tag lookup: conflicting tag refs")
    if len(peeled_set) > 1:
        raise RemoteCheckError("ambiguous tag lookup: conflicting peeled refs")

    return next(iter(peeled_set or direct_set))


def resolve_tag(
    remote_url: str,
    tag: str,
    runner: GitRunner = run_git,
    timeout_seconds: int = 30,
) -> str:
    with tempfile.TemporaryDirectory(prefix="codex-skill-remote-git-") as temp:
        output = runner(
            [
                "ls-remote",
                "--tags",
                remote_url,
                f"refs/tags/{tag}",
                f"refs/tags/{tag}^{{}}",
            ],
            Path(temp),
            timeout_seconds,
        )
    return parse_tag_output(output, tag)


def is_ancestor(older_sha: str, newer_sha: str) -> bool | None:
    try:
        with tempfile.TemporaryDirectory(prefix="codex-skill-git-") as temp:
            temp_root = Path(temp)
            home_dir = temp_root / "home"
            xdg_config_home = temp_root / "xdg"
            home_dir.mkdir()
            xdg_config_home.mkdir()
            subprocess.run(
                git_command(["merge-base", "--is-ancestor", older_sha, newer_sha]),
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
                env=minimal_git_env(home_dir, xdg_config_home),
                shell=False,
                stdin=subprocess.DEVNULL,
            )
        return True
    except subprocess.CalledProcessError as error:
        if error.returncode == 1:
            return False
        return None
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manually check whether the local skill package matches an approved "
            "source. This reports status only; it does not pull, update, "
            "overwrite files, or modify the repository."
        )
    )
    parser.add_argument(
        "--remote-url",
        default=DEFAULT_REMOTE_URL,
        help="GitHub remote URL for the canonical skill repository.",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow the explicit read-only remote lookup required by --source-tag.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source-tag",
        help="Reviewed release tag to compare, for example v0.2.0.",
    )
    source.add_argument(
        "--source-commit",
        help="Reviewed exact commit SHA to compare without a remote lookup.",
    )
    parser.add_argument(
        "--expected-commit",
        help=(
            "Full SHA expected for --source-tag. Required to detect moved tags "
            "or unexpected remote results."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Timeout for git commands.",
    )
    return parser.parse_args(argv)


def print_footer() -> None:
    print("No files were changed.")
    print("No update was applied.")
    print(
        "Next step: review the release notes or diff, then run "
        "update_installed_skill.py in dry-run mode before any approved --apply."
    )


def main(
    argv: list[str] | None = None,
    runner: GitRunner = run_git,
    resolver: Resolver = resolve_hostname,
) -> int:
    try:
        args = parse_args(argv)
        mode = validate_source_ref(args)
        timeout = max(1, args.timeout_seconds)
        validate_remote_url(args.remote_url, resolve_dns=mode == "tag", resolver=resolver)

        print("Manual skill update check")
        print(f"Mode: {mode}")
        print(f"Remote: {args.remote_url}")

        if mode == "tag":
            tag = args.source_tag.strip()
            expected_commit = args.expected_commit.strip().lower()
            print(f"Source tag: {tag}")
            print(f"Expected commit: {expected_commit}")
            print("Network: allowed for one read-only remote tag lookup")
            print("Remote identity verified: pending")
            source_sha = resolve_tag(args.remote_url, tag, runner, timeout)
            print(f"Resolved tag commit: {source_sha}")
            if source_sha != expected_commit:
                raise RemoteCheckError(
                    "possible tag movement: requested tag "
                    f"{tag}; expected {expected_commit}; resolved {source_sha}"
                )
            print("Remote identity verified: yes")
        else:
            source_sha = args.source_commit.strip().lower()
            print(f"Source commit: {source_sha}")
            print("Network: not used for exact-commit comparison")
            print("Remote identity verified: no")

        local_sha = try_git(["rev-parse", "HEAD"], runner, ROOT, timeout)
        matches_expected_repo = local_repo_matches(args.remote_url, runner)

        if not local_sha or not matches_expected_repo:
            print(
                "Local status: cannot safely compare this checkout to the "
                "canonical skill repository."
            )
            print(
                "Reason: git metadata is unavailable or origin does not match "
                "the configured remote URL."
            )
            print_footer()
            return 0

        local_sha = local_sha.strip().lower()
        print(f"Local HEAD: {local_sha}")

        if local_sha == source_sha:
            print("Status: up to date with the approved source.")
            print_footer()
            return 0

        source_is_ancestor = is_ancestor(source_sha, local_sha)
        if source_is_ancestor is True:
            print("Status: local checkout is ahead of the approved source.")
            print("Action: no update is needed for that approved source.")
            print_footer()
            return 0

        local_is_ancestor = is_ancestor(local_sha, source_sha)
        if local_is_ancestor is True:
            print("Status: update may be available from the approved source.")
        else:
            print("Status: local checkout and approved source differ; review is needed.")

        print_footer()
        return 0
    except PolicyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No files were changed.", file=sys.stderr)
        print("No network request was made unless --allow-network was accepted.", file=sys.stderr)
        return POLICY_ERROR
    except RemoteCheckError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No files were changed.", file=sys.stderr)
        print("No update was applied.", file=sys.stderr)
        return REFERENCE_VERIFICATION_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
