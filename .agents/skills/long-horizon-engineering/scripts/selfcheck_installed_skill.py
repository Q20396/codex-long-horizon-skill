#!/usr/bin/env python3
"""Read-only comparison for an installed Codex skill and an explicit reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urlparse


EXIT_EQUIVALENT = 0
EXIT_DIFFERENT = 1
EXIT_INVALID = 2
EXIT_REFERENCE = 3
EXIT_INTERNAL = 4

REPORT_VERSION = "selfcheck-installed-skill/v0.2"
GIT_TIMEOUT_SECONDS = 30
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
MUTABLE_REFS = {"main", "master", "latest", "head"}
EXECUTABLE_SUFFIXES = {
    ".bash",
    ".bat",
    ".cmd",
    ".js",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".ts",
}
DEPENDENCY_FILENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "setup.py",
    "setup.cfg",
}
POLICY_MARKERS = {
    "policy",
    "privacy",
    "safety",
    "security",
    "approval",
    "capability-boundaries",
    "stop-conditions",
    "client-privacy",
    "self-check-policy",
    "review-checklist",
}
UPDATE_MARKERS = {
    "update",
    "install",
    "installer",
    "marketplace",
    "plugin.json",
    "manifest",
}


class PolicyError(Exception):
    """Invalid arguments or a safety policy violation."""


class ReferenceError(Exception):
    """Reference acquisition or identity verification failed."""


@dataclass(frozen=True)
class Entry:
    path: str
    entry_type: str
    sha256: str = ""
    executable: bool = False
    mode: str = ""
    symlink_target: str = ""
    size: int = 0
    source_classification: str = "UNKNOWN"

    def public(self) -> dict[str, object]:
        data: dict[str, object] = {
            "path": self.path,
            "entry_type": self.entry_type,
            "source_classification": self.source_classification,
        }
        if self.sha256:
            data["sha256"] = self.sha256
        if self.mode:
            data["mode"] = self.mode
        if self.entry_type == "regular_file":
            data["executable"] = self.executable
            data["size"] = self.size
        if self.entry_type == "symbolic_link":
            data["symlink_target"] = redact_absolute_target(self.symlink_target)
        return data


@dataclass(frozen=True)
class Difference:
    path: str
    kind: str
    installed: Entry | None = None
    reference: Entry | None = None

    def public(self) -> dict[str, object]:
        impact = impact_category(self.path, self.installed, self.reference)
        risk = risk_level(self.kind, impact, self.installed, self.reference)
        return {
            "path": self.path,
            "kind": self.kind,
            "installed": self.installed.public() if self.installed else None,
            "reference": self.reference.public() if self.reference else None,
            "impact_category": impact,
            "risk_level": risk,
            "human_review_recommendation": recommendation_for(risk, impact),
        }


GitRunner = Callable[[list[str], Path], bytes]


def redact_absolute_target(target: str) -> str:
    if target.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", target):
        return "<absolute-target-redacted>"
    return target


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mode_string(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def validate_root(path: Path, label: str) -> Path:
    if not path.exists():
        raise PolicyError(f"{label} directory does not exist.")
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise PolicyError(f"{label} directory cannot be inspected: {error}") from error
    if stat.S_ISLNK(mode):
        raise PolicyError(f"{label} directory must not be a symlink.")
    if not stat.S_ISDIR(mode):
        raise PolicyError(f"{label} path must be a directory.")
    return path


def normalized_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise PolicyError("Path traversal detected while inventorying package.")
    return relative.as_posix()


def validate_skill_path(value: str) -> str:
    if not value:
        raise PolicyError("--skill-path is required in network mode.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise PolicyError("--skill-path must be a relative POSIX path without traversal.")
    return path.as_posix()


def classify_source(path: str, executable: bool = False) -> str:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else path
    suffix = PurePosixPath(path).suffix.lower()
    lower = path.lower()
    if name == "SKILL.md":
        return "skill_metadata"
    if "scripts" in parts or executable or suffix in EXECUTABLE_SUFFIXES:
        return "executable_or_script"
    if name in DEPENDENCY_FILENAMES:
        return "dependency_or_tooling"
    if "templates" in parts:
        return "template"
    if "references" in parts:
        if any(marker in lower for marker in POLICY_MARKERS):
            return "policy_reference"
        return "reference"
    if any(marker in lower for marker in UPDATE_MARKERS):
        return "update_or_install_behavior"
    return "UNKNOWN"


def inventory_filesystem(root: Path) -> dict[str, Entry]:
    validate_root(root, "Package root")
    entries: dict[str, Entry] = {}
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as error:
            raise PolicyError("Package directory cannot be listed safely.") from error
        for child in children:
            relative = normalized_relative(child, root)
            try:
                st = child.lstat()
            except OSError as error:
                raise PolicyError(f"Cannot inspect package entry {relative}: {error}") from error

            mode = st.st_mode
            if stat.S_ISLNK(mode):
                target = os.readlink(child)
                entries[relative] = Entry(
                    path=relative,
                    entry_type="symbolic_link",
                    mode=mode_string(mode),
                    symlink_target=target,
                    source_classification=classify_source(relative),
                )
            elif stat.S_ISDIR(mode):
                stack.append(child)
            elif stat.S_ISREG(mode):
                data = child.read_bytes()
                executable = bool(stat.S_IMODE(mode) & 0o111)
                entries[relative] = Entry(
                    path=relative,
                    entry_type="regular_file",
                    sha256=sha256_bytes(data),
                    executable=executable,
                    mode=mode_string(mode),
                    size=len(data),
                    source_classification=classify_source(relative, executable),
                )
            else:
                entries[relative] = Entry(
                    path=relative,
                    entry_type="unsupported_special_file",
                    mode=mode_string(mode),
                    size=st.st_size,
                    source_classification=classify_source(relative),
                )
    return dict(sorted(entries.items()))


def impact_category(path: str, installed: Entry | None, reference: Entry | None) -> str:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else path
    suffix = PurePosixPath(path).suffix.lower()
    lower = path.lower()
    executable = bool(
        (installed and installed.executable)
        or (reference and reference.executable)
        or suffix in EXECUTABLE_SUFFIXES
    )
    if name == "SKILL.md" or name == "AGENTS.md":
        return "TRIGGER_OR_WORKFLOW"
    if "scripts" in parts or executable:
        return "EXECUTABLE_CODE"
    if any(marker in lower for marker in UPDATE_MARKERS):
        return "UPDATE_OR_INSTALL_BEHAVIOR"
    if any(marker in lower for marker in POLICY_MARKERS):
        return "SAFETY_OR_PRIVACY_POLICY"
    if name in DEPENDENCY_FILENAMES or lower.startswith((".github/", ".circleci/")):
        return "DEPENDENCY_OR_TOOLING"
    if "templates" in parts or "references" in parts:
        return "TEMPLATE_OR_REFERENCE"
    return "UNKNOWN"


def risk_level(
    kind: str,
    impact: str,
    installed: Entry | None,
    reference: Entry | None,
) -> str:
    entry_types = {entry.entry_type for entry in (installed, reference) if entry}
    if kind == "unsupported_entry" or "unsupported_special_file" in entry_types or "gitlink" in entry_types:
        return "REVIEW_REQUIRED"
    if impact in {"EXECUTABLE_CODE", "SAFETY_OR_PRIVACY_POLICY", "UPDATE_OR_INSTALL_BEHAVIOR"}:
        return "HIGH"
    if impact in {"TRIGGER_OR_WORKFLOW", "DEPENDENCY_OR_TOOLING"}:
        return "MEDIUM"
    if impact == "UNKNOWN":
        return "REVIEW_REQUIRED"
    return "LOW"


def recommendation_for(risk: str, impact: str) -> str:
    if risk in {"HIGH", "REVIEW_REQUIRED"}:
        return f"Human review required before trusting {impact} differences."
    if risk == "MEDIUM":
        return f"Review {impact} changes before updating an installed skill."
    return "Review for expected package drift."


def compare_inventories(
    installed: dict[str, Entry],
    reference: dict[str, Entry],
) -> dict[str, list[dict[str, object]]]:
    missing: list[Difference] = []
    unexpected: list[Difference] = []
    changed: list[Difference] = []
    type_changes: list[Difference] = []
    mode_changes: list[Difference] = []
    symlink_changes: list[Difference] = []
    unsupported: list[Difference] = []

    installed_paths = set(installed)
    reference_paths = set(reference)

    for path in sorted(reference_paths - installed_paths):
        missing.append(Difference(path=path, kind="missing_entry", reference=reference[path]))
    for path in sorted(installed_paths - reference_paths):
        unexpected.append(Difference(path=path, kind="unexpected_entry", installed=installed[path]))

    for path in sorted(installed_paths & reference_paths):
        left = installed[path]
        right = reference[path]
        if "unsupported_special_file" in {left.entry_type, right.entry_type} or "gitlink" in {
            left.entry_type,
            right.entry_type,
        }:
            unsupported.append(
                Difference(path=path, kind="unsupported_entry", installed=left, reference=right)
            )
            continue
        if left.entry_type != right.entry_type:
            type_changes.append(Difference(path=path, kind="type_change", installed=left, reference=right))
            continue
        if left.entry_type == "regular_file":
            if left.sha256 != right.sha256:
                changed.append(
                    Difference(path=path, kind="changed_regular_file", installed=left, reference=right)
                )
            if left.mode != right.mode or left.executable != right.executable:
                mode_changes.append(
                    Difference(path=path, kind="mode_or_executable_change", installed=left, reference=right)
                )
        elif left.entry_type == "symbolic_link" and left.symlink_target != right.symlink_target:
            symlink_changes.append(
                Difference(path=path, kind="symlink_target_change", installed=left, reference=right)
            )

    for source in (installed, reference):
        for path, entry in source.items():
            if entry.entry_type in {"unsupported_special_file", "gitlink"} and path not in installed_paths & reference_paths:
                unsupported.append(Difference(path=path, kind="unsupported_entry", installed=installed.get(path), reference=reference.get(path)))

    return {
        "missing_entries": [item.public() for item in missing],
        "unexpected_entries": [item.public() for item in unexpected],
        "changed_entries": [item.public() for item in changed],
        "type_changes": [item.public() for item in type_changes],
        "mode_or_executable_changes": [item.public() for item in mode_changes],
        "symlink_changes": [item.public() for item in symlink_changes],
        "unsupported_entries": [item.public() for item in unsupported],
    }


def summary_counts(sections: dict[str, list[dict[str, object]]]) -> dict[str, int]:
    counts = {name: len(values) for name, values in sections.items()}
    counts["total_differences"] = sum(counts.values())
    return counts


def validate_full_sha(value: str, label: str = "commit SHA") -> str:
    lowered = value.strip().lower()
    if lowered in MUTABLE_REFS or lowered.startswith(("refs/heads/", "refs/remotes/")):
        raise PolicyError(f"Mutable refs are not valid {label} values.")
    if not FULL_SHA_RE.fullmatch(value.strip()):
        raise PolicyError(f"{label} must be a full 40-character hexadecimal SHA.")
    return value.strip().lower()


def validate_tag_name(value: str) -> str:
    tag = value.strip()
    lowered = tag.lower()
    if not tag or lowered in MUTABLE_REFS or lowered.startswith(("refs/heads/", "refs/remotes/")):
        raise PolicyError("Mutable refs and branch names are not valid tag inputs.")
    if any(character.isspace() for character in tag) or ".." in tag or tag.endswith(".lock"):
        raise PolicyError("Tag input is malformed or unsafe.")
    return tag


def validate_repository_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise PolicyError("Network mode requires a public HTTPS repository URL.")
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise PolicyError("Repository URLs must not contain embedded credentials.")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise PolicyError("Local repository URLs are not allowed in network mode.")
    if not parsed.path or parsed.path == "/":
        raise PolicyError("Repository URL must include an owner and repository path.")
    return value


def git_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }


def run_git(args: list[str], cwd: Path) -> bytes:
    command = [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        "core.askPass=",
        "-c",
        "core.hooksPath=/dev/null",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=False,
        shell=False,
        timeout=GIT_TIMEOUT_SECONDS,
        env=git_environment(),
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReferenceError(message or "Git command failed while acquiring reference.")
    return result.stdout


def decode_git_output(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


def resolve_tag(
    repository_url: str,
    tag: str,
    expected_sha: str,
    workdir: Path,
    git_runner: GitRunner,
) -> str:
    tag = validate_tag_name(tag)
    expected = validate_full_sha(expected_sha, "expected commit SHA")
    output = decode_git_output(
        git_runner(
            [
                "ls-remote",
                "--tags",
                repository_url,
                f"refs/tags/{tag}",
                f"refs/tags/{tag}^{{}}",
            ],
            workdir,
        )
    )
    matches: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            matches[parts[1]] = parts[0].lower()

    resolved = matches.get(f"refs/tags/{tag}^{{}}") or matches.get(f"refs/tags/{tag}")
    if not resolved:
        raise ReferenceError("Requested tag could not be resolved.")
    if not FULL_SHA_RE.fullmatch(resolved):
        raise ReferenceError("Requested tag did not resolve to a full commit SHA.")
    if resolved != expected:
        raise ReferenceError("Possible tag movement: resolved SHA differs from expected SHA.")
    return resolved


def inventory_git_tree(repo_dir: Path, commit_sha: str, skill_path: str, git_runner: GitRunner) -> dict[str, Entry]:
    treeish = f"{commit_sha}:{skill_path}"
    output = git_runner(["-C", str(repo_dir), "ls-tree", "-r", "-z", treeish], repo_dir)
    entries: dict[str, Entry] = {}
    records = [record for record in output.split(b"\0") if record]
    for record in records:
        metadata, raw_path = record.split(b"\t", 1)
        meta_parts = metadata.decode("ascii", errors="replace").split()
        if len(meta_parts) != 3:
            raise ReferenceError("Unexpected Git tree record format.")
        mode, entry_type, object_id = meta_parts
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
            raise ReferenceError("Git tree contains an unsafe path.")

        if mode == "160000" or entry_type == "commit":
            entries[relative] = Entry(
                path=relative,
                entry_type="gitlink",
                mode=mode,
                sha256="",
                source_classification=classify_source(relative),
            )
            continue

        blob = git_runner(["-C", str(repo_dir), "cat-file", "-p", object_id], repo_dir)
        if mode == "120000":
            target = blob.decode("utf-8", errors="replace")
            entries[relative] = Entry(
                path=relative,
                entry_type="symbolic_link",
                mode="0o120000",
                symlink_target=target,
                source_classification=classify_source(relative),
            )
        elif entry_type == "blob":
            executable = mode == "100755"
            entries[relative] = Entry(
                path=relative,
                entry_type="regular_file",
                sha256=sha256_bytes(blob),
                executable=executable,
                mode="0o755" if executable else "0o644",
                size=len(blob),
                source_classification=classify_source(relative, executable),
            )
        else:
            entries[relative] = Entry(
                path=relative,
                entry_type="unsupported_special_file",
                mode=mode,
                source_classification=classify_source(relative),
            )
    return dict(sorted(entries.items()))


def acquire_remote_inventory(
    repository_url: str,
    resolved_sha: str,
    skill_path: str,
    git_runner: GitRunner,
) -> dict[str, Entry]:
    with tempfile.TemporaryDirectory(prefix="codex-skill-selfcheck-") as temp_name:
        temp_root = Path(temp_name)
        repo_dir = temp_root / "repo"
        git_runner(["init", "--quiet", str(repo_dir)], temp_root)
        git_runner(["-C", str(repo_dir), "remote", "add", "origin", repository_url], temp_root)
        git_runner(["-C", str(repo_dir), "fetch", "--depth=1", "--no-tags", "origin", resolved_sha], temp_root)
        try:
            return inventory_git_tree(repo_dir, resolved_sha, skill_path, git_runner)
        except ReferenceError as error:
            raise ReferenceError(f"Remote content lacks the requested skill path or cannot be inspected: {error}") from error


def build_report(
    mode: str,
    reference_identity: dict[str, object],
    installed_inventory: dict[str, Entry],
    reference_inventory: dict[str, Entry],
) -> dict[str, object]:
    sections = compare_inventories(installed_inventory, reference_inventory)
    summary = summary_counts(sections)
    report: dict[str, object] = {
        "report_version": REPORT_VERSION,
        "comparison_mode": mode,
        "reference_identity": reference_identity,
        "installed_package_label": "installed",
        "reference_package_label": "reference",
        "summary": summary,
        **sections,
        "statements": [
            "No files were modified.",
            "No update was applied.",
        ],
    }
    return report


def render_text(report: dict[str, object]) -> str:
    lines = [
        "Read-only installed skill self-check",
        f"Report version: {report['report_version']}",
        f"Comparison mode: {report['comparison_mode']}",
        "Installed package: installed",
        "Reference package: reference",
        "",
        "Summary:",
    ]
    summary = report["summary"]
    assert isinstance(summary, dict)
    for key in sorted(summary):
        lines.append(f"- {key}: {summary[key]}")

    for section in (
        "missing_entries",
        "unexpected_entries",
        "changed_entries",
        "type_changes",
        "mode_or_executable_changes",
        "symlink_changes",
        "unsupported_entries",
    ):
        values = report[section]
        assert isinstance(values, list)
        if not values:
            continue
        lines.append("")
        lines.append(section.replace("_", " ").title() + ":")
        for value in values:
            assert isinstance(value, dict)
            lines.append(
                "- {path} [{impact_category}, {risk_level}] {human_review_recommendation}".format(
                    **value
                )
            )

    lines.append("")
    for statement in report["statements"]:
        lines.append(str(statement))
    return "\n".join(lines) + "\n"


def print_report(report: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only, proposal-only comparison for an installed Codex skill."
    )
    parser.add_argument("--installed-dir", required=True, help="Explicit installed skill directory.")
    parser.add_argument("--reference-dir", help="Explicit local reference skill directory.")
    parser.add_argument("--repository-url", help="Public HTTPS Git repository URL for reference mode.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source-commit", help="Full 40-character commit SHA.")
    source.add_argument("--source-tag", help="Immutable tag name to resolve and verify.")
    parser.add_argument("--expected-commit", help="Expected full SHA for tag mode.")
    parser.add_argument("--skill-path", help="Repository-relative skill path for network mode.")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow network reference acquisition.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Report format.")
    return parser.parse_args(argv)


def mode_from_args(args: argparse.Namespace) -> str:
    network_fields = [args.repository_url, args.source_commit, args.source_tag, args.expected_commit, args.skill_path]
    wants_network = any(network_fields)
    if args.reference_dir and wants_network:
        raise PolicyError("Choose either --reference-dir or network reference options, not both.")
    if args.reference_dir:
        if args.allow_network:
            raise PolicyError("--allow-network is not used with local reference mode.")
        return "local"
    if wants_network:
        if not args.allow_network:
            raise PolicyError("Network mode requires --allow-network.")
        if not args.repository_url:
            raise PolicyError("Network mode requires --repository-url.")
        if not (args.source_commit or args.source_tag):
            raise PolicyError("Network mode requires --source-commit or --source-tag.")
        if args.source_tag and not args.expected_commit:
            raise PolicyError("Tag mode requires --expected-commit.")
        if args.source_commit and args.expected_commit:
            raise PolicyError("--expected-commit is only used with --source-tag.")
        validate_skill_path(args.skill_path or "")
        return "network"
    raise PolicyError("A reference source is required: use --reference-dir or explicit network options.")


def run_comparison(args: argparse.Namespace, git_runner: GitRunner = run_git) -> dict[str, object]:
    mode = mode_from_args(args)
    installed_root = validate_root(Path(args.installed_dir).expanduser(), "Installed skill")
    installed_inventory = inventory_filesystem(installed_root)

    if mode == "local":
        reference_root = validate_root(Path(args.reference_dir).expanduser(), "Reference skill")
        reference_inventory = inventory_filesystem(reference_root)
        return build_report(
            mode="local",
            reference_identity={"mode": "local"},
            installed_inventory=installed_inventory,
            reference_inventory=reference_inventory,
        )

    repository_url = validate_repository_url(args.repository_url)
    skill_path = validate_skill_path(args.skill_path)
    with tempfile.TemporaryDirectory(prefix="codex-skill-selfcheck-ref-") as temp_name:
        temp_root = Path(temp_name)
        if args.source_commit:
            resolved_sha = validate_full_sha(args.source_commit, "source commit")
            reference_identity: dict[str, object] = {
                "mode": "exact_commit",
                "repository_url": repository_url,
                "resolved_sha": resolved_sha,
                "skill_path": skill_path,
            }
        else:
            assert args.source_tag is not None
            resolved_sha = resolve_tag(
                repository_url=repository_url,
                tag=args.source_tag,
                expected_sha=args.expected_commit,
                workdir=temp_root,
                git_runner=git_runner,
            )
            reference_identity = {
                "mode": "tag_resolved_to_commit",
                "repository_url": repository_url,
                "requested_tag": args.source_tag,
                "expected_sha": validate_full_sha(args.expected_commit, "expected commit SHA"),
                "resolved_sha": resolved_sha,
                "skill_path": skill_path,
            }

    reference_inventory = acquire_remote_inventory(
        repository_url=repository_url,
        resolved_sha=resolved_sha,
        skill_path=skill_path,
        git_runner=git_runner,
    )
    return build_report(
        mode=str(reference_identity["mode"]),
        reference_identity=reference_identity,
        installed_inventory=installed_inventory,
        reference_inventory=reference_inventory,
    )


def main(argv: list[str] | None = None, git_runner: GitRunner = run_git) -> int:
    try:
        args = parse_args(argv)
        report = run_comparison(args, git_runner=git_runner)
        print_report(report, args.format)
        summary = report["summary"]
        assert isinstance(summary, dict)
        return EXIT_EQUIVALENT if summary["total_differences"] == 0 else EXIT_DIFFERENT
    except PolicyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No files were modified.", file=sys.stderr)
        print("No update was applied.", file=sys.stderr)
        return EXIT_INVALID
    except ReferenceError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No files were modified.", file=sys.stderr)
        print("No update was applied.", file=sys.stderr)
        return EXIT_REFERENCE
    except Exception as error:  # pragma: no cover - defensive final boundary.
        print(f"ERROR: unexpected internal failure: {error}", file=sys.stderr)
        print("No files were modified.", file=sys.stderr)
        print("No update was applied.", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
