#!/usr/bin/env python3
"""Safely compare installed Codex skills with the public source repository."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


DEFAULT_REPO = "https://github.com/Q20396/codex-long-horizon-skill"
APPROVED_SKILLS = ("long-horizon-engineering", "ai-video-production")
DEFAULT_SKILLS = list(APPROVED_SKILLS)
DEFAULT_INSTALLED_ROOT = Path("~/.agents/skills").expanduser()
SAFE_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

IGNORE_NAMES = {".DS_Store", "__pycache__", ".git"}
IGNORE_PATTERNS = ["*.pyc"]
RISK_TERMS = (
    "security",
    "safety",
    "privacy",
    "validation",
    "update",
    "install",
    "credential",
    "secret",
    "approval",
)


@dataclass
class SkillReport:
    skill_id: str
    local_path: str
    remote_path: str
    local_version: str | None
    remote_version: str | None
    local_missing: bool
    added_files: list[str]
    removed_files: list[str]
    modified_files: list[str]
    possible_breaking_changes: list[str]
    risk_level: str
    upgrade_recommendation: str
    backup_plan: str
    rollback_plan: str


def parse_front_matter(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}

    metadata: dict[str, str] = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key in {"version", "repo", "skill_id", "update_channel", "name", "description"}:
            metadata[key] = value
    return metadata


def should_ignore(path: Path) -> bool:
    if any(part in IGNORE_NAMES for part in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in IGNORE_PATTERNS)


def validate_skill_id(skill_id: str) -> str:
    value = skill_id.strip()
    if not value:
        raise ValueError("Skill id cannot be empty.")
    if value in {".", ".."} or ".." in value:
        raise ValueError(f"Skill id is not safe: {skill_id!r}")
    if "/" in value or "\\" in value:
        raise ValueError(f"Skill id must be a single folder name: {skill_id!r}")
    if Path(value).is_absolute():
        raise ValueError(f"Skill id must not be an absolute path: {skill_id!r}")
    if not SAFE_SKILL_ID_RE.fullmatch(value):
        raise ValueError(f"Skill id does not match the safe id pattern: {skill_id!r}")
    if value not in APPROVED_SKILLS:
        allowed = ", ".join(APPROVED_SKILLS)
        raise ValueError(f"Unsupported skill id {value!r}. Approved skills: {allowed}.")
    return value


def parse_skill_list(raw: str) -> list[str]:
    seen: set[str] = set()
    skills: list[str] = []
    for item in raw.split(","):
        skill_id = validate_skill_id(item)
        if skill_id not in seen:
            seen.add(skill_id)
            skills.append(skill_id)
    if not skills:
        raise ValueError("At least one skill is required.")
    return skills


def resolve_installed_root(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def assert_path_under(parent: Path, child: Path, label: str) -> None:
    parent_resolved = parent.expanduser().resolve(strict=False)
    child_resolved = child.expanduser().resolve(strict=False)
    if child_resolved != parent_resolved and parent_resolved not in child_resolved.parents:
        raise ValueError(f"{label} escapes allowed root: {child_resolved}")


def assert_direct_child(parent: Path, child: Path, label: str) -> None:
    parent_resolved = parent.expanduser().resolve(strict=False)
    child_resolved = child.expanduser().resolve(strict=False)
    if child_resolved.parent != parent_resolved:
        raise ValueError(f"{label} must be a direct child of {parent_resolved}: {child_resolved}")


def safe_child_path(parent: Path, child_name: str) -> Path:
    skill_id = validate_skill_id(child_name)
    parent_resolved = parent.expanduser().resolve(strict=False)
    child = parent_resolved / skill_id
    assert_direct_child(parent_resolved, child, "skill path")
    if child.name != skill_id:
        raise ValueError(f"Skill path name mismatch: {child}")
    return child


def remote_skills_root(remote_repo_root: Path) -> Path:
    repo_root = remote_repo_root.expanduser().resolve(strict=False)
    root = (repo_root / ".agents" / "skills").resolve(strict=False)
    assert_path_under(repo_root, root, "remote skills root")
    return root


def safe_update_staging_path(installed_root: Path, skill_id: str) -> Path:
    skill_id = validate_skill_id(skill_id)
    root = resolve_installed_root(installed_root)
    staging = root / f".{skill_id}.update-staging"
    assert_direct_child(root, staging, "update staging path")
    return staging


def validate_apply_paths(
    installed_root: Path,
    backup_root: Path,
    remote_root: Path,
    skill_id: str,
) -> tuple[Path, Path, Path]:
    skill_id = validate_skill_id(skill_id)
    installed = resolve_installed_root(installed_root)
    target = safe_child_path(installed, skill_id)
    assert_direct_child(installed, target, "target skill path")
    if target.name != skill_id:
        raise ValueError(f"Target skill path name mismatch: {target}")

    backups_parent = (installed / ".backups").resolve(strict=False)
    backup_root_resolved = backup_root.expanduser().resolve(strict=False)
    assert_direct_child(backups_parent, backup_root_resolved, "backup root")
    backup = safe_child_path(backup_root_resolved, skill_id)
    assert_direct_child(backup_root_resolved, backup, "backup skill path")

    remote_root_resolved = remote_root.expanduser().resolve(strict=False)
    remote = safe_child_path(remote_root_resolved, skill_id)
    assert_direct_child(remote_root_resolved, remote, "remote skill path")
    if remote.name != skill_id:
        raise ValueError(f"Remote skill path name mismatch: {remote}")
    return target, backup, remote


def assert_no_unsafe_symlinks(root: Path, label: str) -> None:
    root_resolved = root.expanduser().resolve(strict=False)
    if root.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {root}")
    if not root.exists():
        return
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(dirs) + list(names):
            path = current_path / name
            if not path.is_symlink():
                continue
            target = path.resolve(strict=False)
            if target != root_resolved and root_resolved not in target.parents:
                raise ValueError(f"{label} contains unsafe symlink: {path} -> {os.readlink(path)}")


def file_digest(path: Path) -> str:
    if path.is_symlink():
        return "symlink:" + os.readlink(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_file_digests(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    if root.is_symlink():
        return {"<skill-root-symlink>": file_digest(root)}
    files: dict[str, str] = {}
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in dirs:
            path = current_path / name
            if should_ignore(path):
                continue
            if path.is_symlink():
                relative = path.relative_to(root).as_posix()
                files[relative] = file_digest(path)
                continue
            kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in names:
            path = current_path / name
            if should_ignore(path):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_file() or path.is_symlink():
                files[relative] = file_digest(path)
    return files


def compare_directories(local_root: Path, remote_root: Path) -> dict[str, list[str]]:
    local_files = collect_file_digests(local_root)
    remote_files = collect_file_digests(remote_root)
    local_names = set(local_files)
    remote_names = set(remote_files)
    return {
        "added_files": sorted(remote_names - local_names),
        "removed_files": sorted(local_names - remote_names),
        "modified_files": sorted(
            name for name in local_names & remote_names if local_files[name] != remote_files[name]
        ),
    }


def version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for piece in value.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def changed_paths(diff: dict[str, list[str]]) -> list[str]:
    return sorted(set(diff["added_files"] + diff["removed_files"] + diff["modified_files"]))


def possible_breaking_changes(diff: dict[str, list[str]]) -> list[str]:
    changes = []
    paths = changed_paths(diff)
    if "SKILL.md" in diff["modified_files"]:
        changes.append("SKILL.md changed; review routing, metadata, and safety instructions.")
    if diff["removed_files"]:
        changes.append("Files would be removed by the update.")
    if any(path.endswith(".py") or "/scripts/" in f"/{path}" for path in paths):
        changes.append("Executable or helper script content changed.")
    if any(any(term in path.lower() for term in RISK_TERMS) for path in paths):
        changes.append("Validation, update, security, privacy, or approval-related files changed.")
    return changes


def classify_risk(diff: dict[str, list[str]]) -> str:
    paths = changed_paths(diff)
    if not paths:
        return "LOW"
    if possible_breaking_changes(diff):
        return "HIGH"
    if len(paths) > 1:
        return "MEDIUM"
    if any(path.startswith(("references/", "templates/")) for path in paths):
        return "MEDIUM"
    if all(
        path.startswith(("docs/", "releases/", "templates/"))
        or path in {"README.md", "CHANGELOG.md"}
        or path.endswith((".json", ".md"))
        for path in paths
    ):
        return "LOW"
    return "MEDIUM"


def recommendation(local_version: str | None, remote_version: str | None, diff: dict[str, list[str]], risk: str) -> str:
    if not changed_paths(diff):
        return "No upgrade needed."
    if risk == "HIGH":
        return "Manual review recommended before upgrading."
    if version_tuple(remote_version) > version_tuple(local_version):
        return "Upgrade recommended after reviewing the summary."
    return "Review recommended because meaningful files changed."


def rollback_command(installed_root: Path, backup_path: Path, skill_id: str, local_missing: bool) -> str:
    skill_id = validate_skill_id(skill_id)
    target = safe_child_path(resolve_installed_root(installed_root), skill_id)
    backup = backup_path.expanduser().resolve(strict=False)
    if local_missing:
        return f"rm -rf {shlex.quote(str(target))}"
    return f"rm -rf {shlex.quote(str(target))} && cp -R {shlex.quote(str(backup))} {shlex.quote(str(target))}"


def build_skill_report(
    skill_id: str,
    installed_root: Path,
    remote_repo_root: Path,
    backup_root: Path | None = None,
) -> SkillReport:
    skill_id = validate_skill_id(skill_id)
    installed = resolve_installed_root(installed_root)
    local_path = safe_child_path(installed, skill_id)
    remote_root = remote_skills_root(remote_repo_root)
    remote_path = safe_child_path(remote_root, skill_id)
    diff = compare_directories(local_path, remote_path)
    local_meta = parse_front_matter(local_path / "SKILL.md")
    remote_meta = parse_front_matter(remote_path / "SKILL.md")
    risk = classify_risk(diff)
    backup_path = (
        (backup_root or installed / ".backups" / "YYYYMMDD-HHMMSS").expanduser().resolve(strict=False)
        / skill_id
    )
    local_missing = not local_path.exists()
    return SkillReport(
        skill_id=skill_id,
        local_path=str(local_path),
        remote_path=str(remote_path),
        local_version=local_meta.get("version"),
        remote_version=remote_meta.get("version"),
        local_missing=local_missing,
        added_files=diff["added_files"],
        removed_files=diff["removed_files"],
        modified_files=diff["modified_files"],
        possible_breaking_changes=possible_breaking_changes(diff),
        risk_level=risk,
        upgrade_recommendation=recommendation(
            local_meta.get("version"), remote_meta.get("version"), diff, risk
        ),
        backup_plan=f"Create backup at {backup_path} before replacing {local_path}.",
        rollback_plan=rollback_command(installed_root, backup_path, skill_id, local_missing),
    )


def clone_repo(repo: str, ref: str | None, temp_root: Path) -> Path:
    target = temp_root / "repo"
    subprocess.run(["git", "clone", repo, str(target)], check=True)
    if ref:
        subprocess.run(["git", "-C", str(target), "checkout", ref], check=True)
    return target


def validate_skill_directory(path: Path) -> None:
    if not path.is_dir():
        raise ValueError(f"Skill directory is missing: {path}")
    if not any(path.iterdir()):
        raise ValueError(f"Skill directory is empty: {path}")
    if not (path / "SKILL.md").is_file():
        raise ValueError(f"SKILL.md is missing from {path}")
    nested = path / ".agents" / "skills"
    if nested.exists():
        raise ValueError(f"Nested duplicated .agents/skills path found: {nested}")


def restore_from_backup(target: Path, backup: Path, local_missing: bool) -> None:
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    if local_missing:
        return
    shutil.copytree(backup, target, symlinks=True)


def apply_skill_update(report: SkillReport, remote_repo_root: Path, backup_root: Path) -> None:
    skill_id = validate_skill_id(report.skill_id)
    installed_root = resolve_installed_root(Path(report.local_path).expanduser().parent)
    remote_root = remote_skills_root(remote_repo_root)
    target, backup, remote = validate_apply_paths(installed_root, backup_root, remote_root, skill_id)
    if Path(report.local_path).expanduser().resolve(strict=False) != target:
        raise ValueError(f"Report local path does not match validated target path: {report.local_path}")
    if target.is_symlink():
        raise ValueError(f"Refusing to replace symlinked skill directory: {target}")
    if remote.is_symlink():
        raise ValueError(f"Refusing to use symlinked remote skill directory: {remote}")
    if not remote.is_dir():
        raise ValueError(f"Remote skill directory is missing: {remote}")
    if target.exists():
        assert_no_unsafe_symlinks(target, "local skill directory")
    assert_no_unsafe_symlinks(remote, "remote skill directory")

    backup.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.copytree(target, backup, symlinks=True)
    else:
        backup.mkdir(parents=True, exist_ok=True)
        (backup / "MISSING_LOCAL_SKILL.txt").write_text(
            "The local skill did not exist before update.\n", encoding="utf-8"
        )

    staging = safe_update_staging_path(installed_root, skill_id)
    if staging.is_symlink():
        raise ValueError(f"Refusing to remove symlinked staging path: {staging}")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(remote, staging, symlinks=True)
    validate_skill_directory(staging)
    assert_no_unsafe_symlinks(staging, "staged skill directory")

    local_missing = report.local_missing
    try:
        target, backup, remote = validate_apply_paths(installed_root, backup_root, remote_root, skill_id)
        if target.is_symlink():
            raise ValueError(f"Refusing to replace symlinked skill directory: {target}")
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(staging), str(target))
        validate_skill_directory(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        restore_from_backup(target, backup, local_missing)
        raise


def print_report(report: SkillReport) -> None:
    print(f"\n== {report.skill_id} ==")
    print(f"Local path: {report.local_path}")
    print(f"Remote path: {report.remote_path}")
    print(f"Local version: {report.local_version or 'unknown'}")
    print(f"Remote version: {report.remote_version or 'unknown'}")
    print(f"Local skill missing: {'yes' if report.local_missing else 'no'}")
    print(f"Risk level: {report.risk_level}")
    print(f"Upgrade recommendation: {report.upgrade_recommendation}")
    print(f"Added files: {len(report.added_files)}")
    for path in report.added_files:
        print(f"  + {path}")
    print(f"Removed files: {len(report.removed_files)}")
    for path in report.removed_files:
        print(f"  - {path}")
    print(f"Modified files: {len(report.modified_files)}")
    for path in report.modified_files:
        print(f"  * {path}")
    print("Important instruction changes:")
    if report.possible_breaking_changes:
        for change in report.possible_breaking_changes:
            print(f"  - {change}")
    else:
        print("  - None detected by static path checks.")
    print(f"Backup plan: {report.backup_plan}")
    print(f"Rollback plan: {report.rollback_plan}")


def parse_skills(value: str) -> list[str]:
    return parse_skill_list(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely compare installed Codex skills with the public repository."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--skills", default=",".join(DEFAULT_SKILLS))
    parser.add_argument("--installed-root", default=str(DEFAULT_INSTALLED_ROOT))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--ref", help="Optional git ref, branch, tag, or commit to compare.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary clone for debugging.")
    parser.add_argument("--apply", action="store_true", help="Apply update after typed confirmation.")
    args = parser.parse_args(argv)
    args.skills = parse_skill_list(args.skills)
    return args


def choose_skills_for_apply(reports: list[SkillReport]) -> list[str]:
    report_skill_ids = [validate_skill_id(report.skill_id) for report in reports]
    allowed = {f"UPDATE {skill_id}": [skill_id] for skill_id in report_skill_ids}
    allowed["UPDATE ALL"] = list(report_skill_ids)
    print("\nTo apply, type exactly one of:")
    for phrase in allowed:
        print(f"  {phrase}")
    answer = input("> ").strip()
    if answer not in allowed:
        raise ValueError("Confirmation phrase did not match an approved update action.")
    return allowed[answer]


def main(argv: list[str] | None = None) -> int:
    temp_dir: Path | None = None
    try:
        args = parse_args(argv)
        installed_root = resolve_installed_root(Path(args.installed_root))
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = installed_root / ".backups" / timestamp
        temp_dir = Path(tempfile.mkdtemp(prefix="codex-skill-update-"))
        repo_root = clone_repo(args.repo, args.ref, temp_dir)
        reports = [
            build_skill_report(skill_id, installed_root, repo_root, backup_root)
            for skill_id in args.skills
        ]
        if args.json:
            print(json.dumps([asdict(report) for report in reports], indent=2, sort_keys=True))
        else:
            print("Safe skill update self-check")
            print("Default mode is check-only. No installed skill has been modified.")
            for report in reports:
                print_report(report)

        has_differences = any(
            report.added_files or report.removed_files or report.modified_files or report.local_missing
            for report in reports
        )
        if not args.apply:
            return 2 if has_differences else 0

        selected = set(choose_skills_for_apply(reports))
        for report in reports:
            if report.skill_id not in selected:
                continue
            apply_skill_update(report, repo_root, backup_root)
            print(f"Updated {report.skill_id}.")
            print(f"Backup: {backup_root / report.skill_id}")
            print(f"Rollback: {report.rollback_plan}")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"git command failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_dir is not None:
            if args.keep_temp:
                print(f"Temporary clone kept at: {temp_dir}")
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
