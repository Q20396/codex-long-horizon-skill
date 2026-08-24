#!/usr/bin/env python3
"""Update installed skills with staged replacement and retained backups."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import ctypes.util
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator, NamedTuple, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - POSIX is an apply-time requirement.
    fcntl = None


PACKAGE_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PACKAGE_ROOT / ".agents" / "skills"
PACKAGE_MANIFEST_PATH = (
    PACKAGE_ROOT
    / ".agents"
    / "skills"
    / "long-horizon-engineering"
    / "package-manifest.json"
)
ALLOWED_SKILLS = ("long-horizon-engineering", "ai-video-production")
COPY_CHUNK_SIZE = 1024 * 1024
LOCK_FILE_NAME = ".codex-skill-update.lock"
RECEIPT_DIRECTORY_NAME = ".codex-skill-update-receipts"


class UpdateError(RuntimeError):
    """A controlled updater failure that is safe to display."""


class TargetPlan(NamedTuple):
    label: str
    target: Path
    backup_root: Path
    authorized_root: Path
    installed_project_root: Path | None


class ManifestEntry(NamedTuple):
    kind: str
    size: int
    sha256: str
    mode: int
    uid: int


class ApprovedInventory(NamedTuple):
    files: frozenset[str]
    directories: frozenset[str]
    package_manifest_sha256: str
    inventory_sha256: str


class DirectoryIdentity(NamedTuple):
    kind: str
    uid: int
    mode: int
    device: int
    inode: int


class TargetLock(NamedTuple):
    path: Path
    authorized_root_fd: int
    lock_fd: int
    identity: DirectoryIdentity
    lock_identity: dict[str, object]


class DirectoryAnchor(NamedTuple):
    path: Path
    relative_parts: tuple[str, ...]
    fd: int
    device: int
    inode: int
    uid: int
    mode: int
    private: bool


class RenameStatus(NamedTuple):
    operation: str
    source_name: str
    destination_name: str
    rename_committed: bool | str
    source_identity_before: dict[str, object] | None
    destination_identity_before: dict[str, object] | None
    source_identity_after: dict[str, object] | None
    destination_identity_after: dict[str, object] | None
    fsync_status: str
    error_type: str | None = None
    error_message: str | None = None


VISIBLE_RENAME_OPERATIONS = {
    "target_to_previous": "target_to_previous",
    "staging_to_target": "staging_to_target",
    "target_to_quarantine": "target_to_quarantine",
    "previous_to_target": "previous_to_target",
    "backup_candidate_to_backup": "backup_candidate_to_backup",
}


TRANSACTION_PHASES = (
    "prepared",
    "staging_verified",
    "backup_ready",
    "active_target_moved",
    "staging_published",
    "published_verified",
    "cleanup_failed",
    "complete_receipt_unpersisted",
    "complete",
)


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def source_skill_path(skill: str) -> Path:
    return SKILLS_ROOT / skill


def target_skill_path(target_root: Path, skill: str) -> Path:
    return target_root / ".agents" / "skills" / skill


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_approved_source_inventory(skill: str) -> ApprovedInventory:
    try:
        manifest_bytes = PACKAGE_MANIFEST_PATH.read_bytes()
        package_manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateError("package manifest could not be loaded safely.") from exc
    if not isinstance(package_manifest, dict):
        raise UpdateError("package manifest must be a JSON object.")

    selected_paths: list[str] = []
    if skill == "long-horizon-engineering":
        components = package_manifest.get("components")
        if not isinstance(components, dict):
            raise UpdateError("package manifest components are missing or malformed.")
        for component_name in ("core", "bundled-optional"):
            component = components.get(component_name)
            if not isinstance(component, dict) or not isinstance(
                component.get("paths"), list
            ):
                raise UpdateError(
                    f"package manifest component is malformed: {component_name}"
                )
            selected_paths.extend(component["paths"])
    else:
        separate_skills = package_manifest.get("separate_skills")
        if not isinstance(separate_skills, list):
            raise UpdateError("package manifest separate_skills is malformed.")
        matches = [
            entry
            for entry in separate_skills
            if isinstance(entry, dict) and entry.get("skill_id") == skill
        ]
        if len(matches) != 1 or not isinstance(matches[0].get("paths"), list):
            raise UpdateError(
                f"package manifest must declare exactly one inventory for {skill}."
            )
        selected_paths.extend(matches[0]["paths"])

    prefix = PurePosixPath(".agents") / "skills" / skill
    files: set[str] = set()
    directories: set[str] = set()
    for raw_path in selected_paths:
        if not isinstance(raw_path, str):
            raise UpdateError("package manifest source paths must be strings.")
        candidate = PurePosixPath(raw_path)
        if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
            raise UpdateError(f"unsafe package manifest source path: {raw_path}")
        try:
            relative = candidate.relative_to(prefix)
        except ValueError as exc:
            raise UpdateError(
                f"package manifest source path escapes the selected skill: {raw_path}"
            ) from exc
        relative_text = relative.as_posix()
        if relative_text in ("", ".") or relative_text in files:
            raise UpdateError(f"duplicate or empty package manifest source path: {raw_path}")
        files.add(relative_text)
        parent = relative.parent
        while parent != PurePosixPath("."):
            directories.add(parent.as_posix())
            parent = parent.parent

    canonical_inventory = json.dumps(
        sorted(files),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ApprovedInventory(
        files=frozenset(files),
        directories=frozenset(directories),
        package_manifest_sha256=_sha256_bytes(manifest_bytes),
        inventory_sha256=_sha256_bytes(canonical_inventory),
    )


def verify_approved_source_inventory(
    manifest: dict[str, ManifestEntry],
    inventory: ApprovedInventory,
    label: str,
) -> None:
    actual_files = {
        path for path, entry in manifest.items() if entry.kind == "file"
    }
    actual_directories = {
        path for path, entry in manifest.items() if entry.kind == "directory"
    }
    missing = sorted(inventory.files - actual_files)
    unexpected = sorted(actual_files - inventory.files)
    directory_mismatch = sorted(actual_directories ^ inventory.directories)
    if missing or unexpected or directory_mismatch:
        details = []
        if missing:
            details.append(f"missing approved files: {_format_paths(missing)}")
        if unexpected:
            details.append(f"unapproved files: {_format_paths(unexpected)}")
        if directory_mismatch:
            details.append(
                "directory inventory mismatch: " + _format_paths(directory_mismatch)
            )
        raise UpdateError(f"{label} is not closed by package manifest; " + "; ".join(details))


def verify_approved_inventory_identity(
    skill: str,
    expected: ApprovedInventory,
    label: str,
) -> None:
    current = load_approved_source_inventory(skill)
    if current != expected:
        raise UpdateError(f"package manifest inventory changed {label}.")


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _absolute_lexical_path(value: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _effective_uid() -> int:
    if not hasattr(os, "geteuid"):
        raise UpdateError("apply requires POSIX owner checks.")
    return os.geteuid()


def _require_owned_non_writable_directory(
    path: Path,
    label: str,
    *,
    private: bool = False,
) -> None:
    current = _lstat(path)
    if current is None:
        raise UpdateError(f"{label} must already exist.")
    if _validate_entry_type(current, label) != "directory":
        raise UpdateError(f"{label} must be a directory.")
    if current.st_uid != _effective_uid():
        raise UpdateError(f"{label} must be owned by the current user.")
    forbidden = 0o077 if private else 0o022
    if stat.S_IMODE(current.st_mode) & forbidden:
        qualifier = "private" if private else "not group/world writable"
        raise UpdateError(f"{label} must be {qualifier}.")


def _validate_owned_non_writable_ancestor_chain(
    authorized_root: Path,
    path: Path,
    label: str,
) -> None:
    _require_within(path, authorized_root, label)
    current = authorized_root
    candidates = [current]
    for part in path.relative_to(authorized_root).parts:
        current = current / part
        candidates.append(current)
    for candidate in candidates:
        if _lstat(candidate) is None:
            continue
        relative = (
            "."
            if candidate == authorized_root
            else candidate.relative_to(authorized_root).as_posix()
        )
        _require_owned_non_writable_directory(
            candidate,
            f"{label} ancestor {relative}",
        )


def _require_owned_non_writable_file(path: Path, label: str) -> None:
    current = _lstat(path)
    if current is None or _validate_entry_type(current, label) != "file":
        raise UpdateError(f"{label} must be a regular file.")
    if current.st_uid != _effective_uid():
        raise UpdateError(f"{label} must be owned by the current user.")
    mode = stat.S_IMODE(current.st_mode)
    if mode & 0o022:
        raise UpdateError(f"{label} must not be group/world writable.")
    if mode & (stat.S_ISUID | stat.S_ISGID):
        raise UpdateError(f"{label} must not have setuid/setgid bits.")


def validate_owned_non_writable_tree(
    root: Path,
    manifest: dict[str, ManifestEntry],
    label: str,
) -> None:
    _require_owned_non_writable_directory(root, f"{label} root")
    uid = _effective_uid()
    for relative_path, entry in manifest.items():
        if entry.uid != uid:
            raise UpdateError(
                f"{label} entry must be owned by the current user: {relative_path}"
            )
        if entry.mode & 0o022:
            raise UpdateError(
                f"{label} entry must not be group/world writable: {relative_path}"
            )
        if entry.kind == "file" and entry.mode & (stat.S_ISUID | stat.S_ISGID):
            raise UpdateError(
                f"{label} file must not have setuid/setgid bits: {relative_path}"
            )


def validate_owned_non_writable_manifest_at(
    parent_fd: int,
    name: str,
    manifest: dict[str, ManifestEntry],
    label: str,
    expected_root_identity: DirectoryIdentity | None = None,
) -> None:
    descriptor, _ = _open_child_directory_at(parent_fd, name, f"{label} root")
    try:
        root_stat = _validate_directory_fd(descriptor, f"{label} root")
        if expected_root_identity is not None and not _identity_matches(
            root_stat,
            expected_root_identity,
        ):
            raise UpdateError(f"{label} root identity changed.")
    finally:
        os.close(descriptor)
    uid = _effective_uid()
    for relative_path, entry in manifest.items():
        if entry.uid != uid:
            raise UpdateError(
                f"{label} entry must be owned by the current user: {relative_path}"
            )
        if entry.mode & 0o022:
            raise UpdateError(
                f"{label} entry must not be group/world writable: {relative_path}"
            )
        if entry.kind == "file" and entry.mode & (stat.S_ISUID | stat.S_ISGID):
            raise UpdateError(
                f"{label} file must not have setuid/setgid bits: {relative_path}"
            )


def validate_owned_non_writable_manifest_fd(
    root_fd: int,
    manifest: dict[str, ManifestEntry],
    label: str,
) -> None:
    """Validate ownership/mode using the already-anchored source root FD."""
    _validate_directory_fd(root_fd, f"{label} root")
    uid = _effective_uid()
    for relative_path, entry in manifest.items():
        if entry.uid != uid:
            raise UpdateError(
                f"{label} entry must be owned by the current user: {relative_path}"
            )
        if entry.mode & 0o022:
            raise UpdateError(
                f"{label} entry must not be group/world writable: {relative_path}"
            )
        if entry.kind == "file" and entry.mode & (stat.S_ISUID | stat.S_ISGID):
            raise UpdateError(
                f"{label} file must not have setuid/setgid bits: {relative_path}"
            )


def _reject_explicit_symlink(path: Path, label: str) -> None:
    current = _lstat(path)
    if current is not None and stat.S_ISLNK(current.st_mode):
        raise SystemExit(f"ERROR: {label} must not be a symbolic link: {path}")


def _normalize_explicit_path(value: str | Path, label: str) -> Path:
    lexical = _absolute_lexical_path(value)
    _reject_explicit_symlink(lexical, label)
    _validate_lexical_ancestor_chain(lexical, label)
    return lexical.resolve(strict=False)


def _validate_lexical_ancestor_chain(path: Path, label: str) -> None:
    """Reject existing lexical components that could redirect resolution.

    This runs before ``Path.resolve`` so an explicit target cannot use a
    symlinked intermediate component to escape the caller's intended root.
    Missing components are allowed for dry-run and are created only through
    the anchored apply path.
    """
    lexical = _absolute_lexical_path(path)
    current = Path(lexical.anchor)
    for part in lexical.relative_to(Path(lexical.anchor)).parts:
        current /= part
        entry = _lstat(current)
        if entry is None:
            break
        if stat.S_ISLNK(entry.st_mode):
            # macOS exposes temporary directories through /var and /tmp
            # aliases.  They are resolved by the OS before the caller's
            # writable path begins; explicit attacker-controlled components
            # below them are still rejected one by one.
            if current in (Path("/var"), Path("/tmp")):
                continue
            raise UpdateError(f"symbolic link rejected in {label}: {current}")
        if not stat.S_ISDIR(entry.st_mode):
            raise UpdateError(f"non-directory ancestor rejected in {label}: {current}")


def _validate_existing_ancestor_chain(
    authorized_root: Path,
    path: Path,
    label: str,
) -> None:
    lexical_root = _absolute_lexical_path(authorized_root)
    lexical_path = _absolute_lexical_path(path)
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise UpdateError(f"{label} escapes the authorized installation root.") from exc

    current = lexical_root
    candidates = [current]
    for part in relative.parts:
        current = current / part
        candidates.append(current)

    for candidate in candidates:
        candidate_stat = _lstat(candidate)
        if candidate_stat is None:
            continue
        relative_label = (
            "."
            if candidate == lexical_root
            else candidate.relative_to(lexical_root).as_posix()
        )
        if stat.S_ISLNK(candidate_stat.st_mode):
            raise UpdateError(
                f"symbolic link rejected in {label}: {relative_label}"
            )
        if not stat.S_ISDIR(candidate_stat.st_mode):
            raise UpdateError(
                f"non-directory ancestor rejected in {label}: {relative_label}"
            )


def _require_within(path: Path, root: Path, label: str) -> None:
    if not path_is_relative_to(path, root):
        raise UpdateError(f"{label} resolves outside the authorized installation root.")


def _paths_overlap(first: Path, second: Path) -> bool:
    first_resolved = first.resolve(strict=False)
    second_resolved = second.resolve(strict=False)
    return path_is_relative_to(first_resolved, second_resolved) or path_is_relative_to(
        second_resolved, first_resolved
    )


def _reject_source_mutation_overlap(source: Path, target_plan: TargetPlan) -> None:
    mutation_paths = (
        target_plan.target,
        target_plan.backup_root,
        target_plan.authorized_root / LOCK_FILE_NAME,
        target_plan.authorized_root / RECEIPT_DIRECTORY_NAME,
    )
    for mutation_path in mutation_paths:
        if _paths_overlap(source, mutation_path):
            raise UpdateError(
                "apply target or transaction paths must not overlap the source package."
            )


def reject_duplicate_codex_agents_target(target_root: Path, skill: str) -> None:
    duplicate_root = (Path.home() / ".codex" / ".agents" / "skills").resolve()
    target = target_skill_path(target_root, skill)
    if path_is_relative_to(target, duplicate_root):
        raise SystemExit(
            "ERROR: --target-root would resolve under ~/.codex/.agents/skills. "
            "Use --target-skill-dir ~/.codex/skills/<skill> for the active Codex "
            "installation layout."
        )


def backup_root_for_target_skill_dir(target: Path) -> Path:
    if target.parent.name == "skills":
        return target.parent.parent / "skill-backups"
    return target.parent / ".codex-skill-backups"


def resolve_target_plan(args: argparse.Namespace, skill: str, apply: bool) -> TargetPlan:
    if args.target_root and args.target_skill_dir:
        raise SystemExit("ERROR: use either --target-root or --target-skill-dir, not both.")

    if args.target_skill_dir:
        lexical_target = _absolute_lexical_path(args.target_skill_dir)
        _reject_explicit_symlink(lexical_target, "--target-skill-dir")
        try:
            _validate_lexical_ancestor_chain(lexical_target, "--target-skill-dir path")
        except UpdateError as exc:
            raise SystemExit(f"ERROR: {exc}") from None
        lexical_authorized_root = lexical_target.parent.parent
        try:
            _validate_existing_ancestor_chain(
                lexical_authorized_root,
                lexical_target,
                "--target-skill-dir path",
            )
        except UpdateError as exc:
            raise SystemExit(f"ERROR: {exc}") from None
        target = lexical_target.resolve(strict=False)
        if target.name != skill:
            raise SystemExit(
                f"ERROR: --target-skill-dir basename must match --skill {skill!r}: {target}"
            )
        if target.parent.name != "skills":
            raise SystemExit(
                "ERROR: --target-skill-dir must point to a skills/<skill> installation "
                f"directory: {target}"
            )
        if not target.is_dir():
            raise SystemExit(
                f"ERROR: --target-skill-dir must point to an existing skill directory: {target}"
            )
        if not (target / "SKILL.md").is_file():
            raise SystemExit(
                f"ERROR: --target-skill-dir must contain SKILL.md: {target}"
            )
        authorized_root = target.parent.parent.resolve(strict=True)
        backup_root = backup_root_for_target_skill_dir(target).resolve(strict=False)
        receipt_root = (authorized_root / RECEIPT_DIRECTORY_NAME).resolve(strict=False)
        lock_path = (authorized_root / LOCK_FILE_NAME).resolve(strict=False)
        if not path_is_relative_to(target, authorized_root):
            raise SystemExit("ERROR: direct skill target escapes its installation root.")
        if not path_is_relative_to(backup_root, authorized_root):
            raise SystemExit("ERROR: direct skill backup root escapes its installation root.")
        if not path_is_relative_to(receipt_root, authorized_root):
            raise SystemExit("ERROR: direct skill receipt root escapes its installation root.")
        if not path_is_relative_to(lock_path, authorized_root):
            raise SystemExit("ERROR: direct skill lock path escapes its installation root.")
        return TargetPlan(
            label="target skill directory",
            target=target,
            backup_root=backup_root,
            authorized_root=authorized_root,
            installed_project_root=None,
        )

    if args.target_root:
        target_root = _normalize_explicit_path(args.target_root, "--target-root")
    elif apply:
        raise SystemExit("ERROR: --apply requires --target-root or --target-skill-dir.")
    else:
        target_root = Path(".").resolve()

    reject_duplicate_codex_agents_target(target_root, skill)
    target = target_skill_path(target_root, skill)
    backup_root = target_root / ".codex-skill-backups"
    receipt_root = target_root / RECEIPT_DIRECTORY_NAME
    lock_path = target_root / LOCK_FILE_NAME
    if not path_is_relative_to(target, target_root):
        raise SystemExit("ERROR: resolved target escapes --target-root.")
    if not path_is_relative_to(backup_root, target_root):
        raise SystemExit("ERROR: resolved backup root escapes --target-root.")
    if not path_is_relative_to(receipt_root, target_root):
        raise SystemExit("ERROR: resolved receipt root escapes --target-root.")
    if not path_is_relative_to(lock_path, target_root):
        raise SystemExit("ERROR: resolved lock path escapes --target-root.")
    return TargetPlan(
        label="target project root",
        target=target,
        backup_root=backup_root,
        authorized_root=target_root,
        installed_project_root=target_root,
    )


def _validate_entry_type(
    entry_stat: os.stat_result,
    relative_path: str,
) -> str:
    mode = entry_stat.st_mode
    if stat.S_ISLNK(mode):
        raise UpdateError(f"symbolic link rejected: {relative_path}")
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        if entry_stat.st_nlink > 1:
            raise UpdateError(f"hard-linked regular file rejected: {relative_path}")
        return "file"
    raise UpdateError(f"special filesystem entry rejected: {relative_path}")


def _hash_regular_file(
    path: Path,
    expected: os.stat_result,
    relative_path: str,
) -> str:
    flags = _nofollow_flags(os.O_RDONLY, "source manifest file")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise UpdateError(f"unable to open regular file safely: {relative_path}") from exc

    digest = hashlib.sha256()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or opened.st_nlink > 1
        ):
            raise UpdateError(f"regular file identity changed: {relative_path}")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            while True:
                chunk = source.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        closed = os.fstat(descriptor)
        if (
            closed.st_dev != opened.st_dev
            or closed.st_ino != opened.st_ino
            or closed.st_size != opened.st_size
        ):
            raise UpdateError(f"regular file changed while reading: {relative_path}")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def build_tree_manifest(root: Path, label: str) -> dict[str, ManifestEntry]:
    root_stat = _lstat(root)
    if root_stat is None:
        raise UpdateError(f"{label} does not exist.")
    if _validate_entry_type(root_stat, ".") != "directory":
        raise UpdateError(f"{label} must be a directory.")

    manifest: dict[str, ManifestEntry] = {}

    def visit(directory: Path, prefix: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise UpdateError(f"unable to enumerate {label}: {prefix or Path('.')}.") from exc
        for entry in entries:
            relative = prefix / entry.name
            relative_text = relative.as_posix()
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise UpdateError(
                    f"unable to inspect {label} entry: {relative_text}"
                ) from exc
            kind = _validate_entry_type(entry_stat, relative_text)
            if kind == "directory":
                manifest[relative_text] = ManifestEntry(
                    "directory",
                    0,
                    "",
                    stat.S_IMODE(entry_stat.st_mode),
                    entry_stat.st_uid,
                )
                visit(Path(entry.path), relative)
            else:
                manifest[relative_text] = ManifestEntry(
                    "file",
                    entry_stat.st_size,
                    _hash_regular_file(Path(entry.path), entry_stat, relative_text),
                    stat.S_IMODE(entry_stat.st_mode),
                    entry_stat.st_uid,
                )

    visit(root, Path())
    return manifest


def validate_skill_manifest(
    manifest: dict[str, ManifestEntry],
    label: str,
) -> None:
    if not manifest:
        raise UpdateError(f"{label} is empty.")
    if manifest.get("SKILL.md", ManifestEntry("", 0, "", 0, -1)).kind != "file":
        raise UpdateError(f"{label} must contain a regular SKILL.md file.")
    if ".agents/skills" in manifest:
        raise UpdateError(f"{label} contains a nested .agents/skills directory.")


def _format_paths(paths: list[str]) -> str:
    return ", ".join(paths) if paths else "(none)"


def compare_manifests(
    source: dict[str, ManifestEntry],
    target: dict[str, ManifestEntry],
) -> tuple[list[str], list[str], list[str]]:
    source_paths = set(source)
    target_paths = set(target)
    added = sorted(source_paths - target_paths)
    target_only = sorted(target_paths - source_paths)
    replaced = sorted(
        path for path in source_paths & target_paths if source[path] != target[path]
    )
    return added, replaced, target_only


def verify_exact_manifest(
    expected: dict[str, ManifestEntry],
    actual: dict[str, ManifestEntry],
    label: str,
) -> None:
    if expected == actual:
        return
    added, changed, unexpected = compare_manifests(expected, actual)
    details = []
    if added:
        details.append(f"missing or different expected entries: {_format_paths(added)}")
    if changed:
        details.append(f"changed entries: {_format_paths(changed)}")
    if unexpected:
        details.append(f"unexpected entries: {_format_paths(unexpected)}")
    raise UpdateError(f"{label} manifest mismatch; " + "; ".join(details))


def _ensure_directory(path: Path, authorized_root: Path, label: str) -> None:
    _require_within(path, authorized_root, label)
    _validate_existing_ancestor_chain(authorized_root, path, label)
    current = _lstat(path)
    if current is not None:
        if _validate_entry_type(current, label) != "directory":
            raise UpdateError(f"{label} must be a directory.")
        return
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UpdateError(f"unable to create {label}.") from exc
    current = _lstat(path)
    if current is None or _validate_entry_type(current, label) != "directory":
        raise UpdateError(f"{label} was not created as a safe directory.")
    _validate_existing_ancestor_chain(authorized_root, path, label)


def _ensure_private_directory(path: Path, authorized_root: Path, label: str) -> None:
    _require_within(path, authorized_root, label)
    _validate_existing_ancestor_chain(authorized_root, path, label)
    current = _lstat(path)
    if current is None:
        try:
            path.mkdir(mode=0o700)
        except OSError as exc:
            raise UpdateError(f"unable to create {label}.") from exc
    _require_owned_non_writable_directory(path, label, private=True)


def _fsync_directory(path: Path) -> None:
    flags = _directory_open_flags()
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise UpdateError(f"unable to synchronize directory metadata: {path}") from exc


def _nofollow_flags(base: int, label: str) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise UpdateError(f"{label} requires O_NOFOLLOW support (nofollow-not-supported).")
    return base | nofollow


def _directory_open_flags() -> int:
    return _nofollow_flags(
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0),
        "directory access",
    )


def _validate_directory_fd(
    descriptor: int,
    label: str,
    *,
    private: bool = False,
) -> os.stat_result:
    current = os.fstat(descriptor)
    if not stat.S_ISDIR(current.st_mode):
        raise UpdateError(f"{label} must be a directory.")
    if current.st_uid != _effective_uid():
        raise UpdateError(f"{label} must be owned by the current user.")
    forbidden = 0o077 if private else 0o022
    if stat.S_IMODE(current.st_mode) & forbidden:
        qualifier = "private" if private else "not group/world writable"
        raise UpdateError(f"{label} must be {qualifier}.")
    return current


def _directory_identity(entry_stat: os.stat_result, label: str) -> DirectoryIdentity:
    if not stat.S_ISDIR(entry_stat.st_mode):
        raise UpdateError(f"{label} must be a directory.")
    return DirectoryIdentity(
        kind="directory",
        uid=entry_stat.st_uid,
        mode=stat.S_IMODE(entry_stat.st_mode),
        device=entry_stat.st_dev,
        inode=entry_stat.st_ino,
    )


def _identity_matches(
    entry_stat: os.stat_result,
    expected: DirectoryIdentity,
) -> bool:
    return _directory_identity(entry_stat, "directory") == expected


def _identity_payload(identity: DirectoryIdentity) -> dict[str, object]:
    return {
        "kind": identity.kind,
        "uid": identity.uid,
        "mode": identity.mode,
        "st_dev": identity.device,
        "st_ino": identity.inode,
    }


def _entry_identity_payload(entry_stat: os.stat_result | None) -> dict[str, object] | None:
    if entry_stat is None:
        return None
    if stat.S_ISDIR(entry_stat.st_mode):
        kind = "directory"
    elif stat.S_ISREG(entry_stat.st_mode):
        kind = "file"
    elif stat.S_ISLNK(entry_stat.st_mode):
        kind = "symlink"
    else:
        kind = "special"
    return {
        "kind": kind,
        "uid": entry_stat.st_uid,
        "mode": stat.S_IMODE(entry_stat.st_mode),
        "st_dev": entry_stat.st_dev,
        "st_ino": entry_stat.st_ino,
    }


def _infer_rename_operation(source_name: str, destination_name: str) -> str:
    if source_name.startswith(".") and ".staging-" in source_name and destination_name:
        return VISIBLE_RENAME_OPERATIONS["staging_to_target"]
    if source_name and ".previous-" in destination_name:
        return VISIBLE_RENAME_OPERATIONS["target_to_previous"]
    if source_name and ".failed-" in destination_name:
        return VISIBLE_RENAME_OPERATIONS["target_to_quarantine"]
    if ".previous-" in source_name and destination_name:
        return VISIBLE_RENAME_OPERATIONS["previous_to_target"]
    if ".backup-incomplete-" in source_name and destination_name:
        return VISIBLE_RENAME_OPERATIONS["backup_candidate_to_backup"]
    return "unknown"


def _rename_status_payload(status: RenameStatus) -> dict[str, object]:
    return {
        "operation": status.operation,
        "source_name": status.source_name,
        "destination_name": status.destination_name,
        "rename_committed": status.rename_committed,
        "source_identity_before": status.source_identity_before,
        "destination_identity_before": status.destination_identity_before,
        "source_identity_after": status.source_identity_after,
        "destination_identity_after": status.destination_identity_after,
        "fsync_status": status.fsync_status,
        "error_type": status.error_type,
        "error_message": status.error_message,
    }


def _directory_anchor_payload(
    *,
    display_path: Path,
    identity: DirectoryIdentity,
    verified_at_phase: str,
) -> dict[str, object]:
    # Keep the historical spelling as a compatibility aid, but make the
    # display-path versus FD distinction explicit for recovery tooling.
    return {
        "display_path": str(display_path),
        "st_dev": identity.device,
        "st_ino": identity.inode,
        "uid": identity.uid,
        "mode": identity.mode,
        "verified_at_phase": verified_at_phase,
        "path": str(display_path),
        "device": identity.device,
        "inode": identity.inode,
        "display_path_identity": "CURRENT",
        "recovery_requires_fd_identity": False,
    }


def _mark_display_path_states(payload: dict[str, object]) -> None:
    anchors = payload.get("directory_anchors")
    if not isinstance(anchors, dict):
        return
    for anchor in anchors.values():
        if not isinstance(anchor, dict):
            continue
        display_path = anchor.get("display_path", anchor.get("path"))
        if not isinstance(display_path, str):
            continue
        try:
            displayed = _lstat(Path(display_path))
            expected_dev = int(anchor["st_dev"])
            expected_ino = int(anchor["st_ino"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            displayed is None
            or displayed.st_dev != expected_dev
            or displayed.st_ino != expected_ino
        ):
            anchor["display_path_identity"] = "STALE_OR_REPLACED"
            anchor["recovery_requires_fd_identity"] = True
        else:
            anchor["display_path_identity"] = "CURRENT"
            anchor["recovery_requires_fd_identity"] = False


def _record_rename_status(
    payload: dict[str, object] | None,
    status: RenameStatus,
    *,
    parent_anchor: str | None = None,
) -> None:
    if payload is None:
        return
    operations = payload.setdefault("rename_operations", [])
    if not isinstance(operations, list):
        operations = []
        payload["rename_operations"] = operations
    operations.append(_rename_status_payload(status))
    if status.rename_committed in (True, "unknown"):
        payload["rename_recovery_required"] = True
    if parent_anchor is not None:
        payload.setdefault("rename_parent_anchors", {})[status.operation] = parent_anchor


def _record_object_state(
    payload: dict[str, object] | None,
    object_kind: str,
    *,
    display_name: str | None,
    parent_anchor: str,
    expected_identity: dict[str, object] | None,
    current_identity: dict[str, object] | None,
) -> None:
    if payload is None:
        return
    objects = payload.setdefault("objects", {})
    if not isinstance(objects, dict):
        objects = {}
        payload["objects"] = objects
    objects[object_kind] = {
        "display_name": display_name,
        "parent_anchor": parent_anchor,
        "expected_identity": expected_identity,
        "current_identity_or_null": current_identity,
    }


def _rename_for_transaction(
    parent_fd: int,
    source_name: str,
    destination_name: str,
    payload: dict[str, object] | None,
    *,
    parent_anchor: str | None = None,
) -> RenameStatus:
    status = _rename_child_and_confirm(parent_fd, source_name, destination_name)
    _record_rename_status(payload, status, parent_anchor=parent_anchor)
    return status


def _require_durable_rename(status: RenameStatus, label: str) -> None:
    if status.rename_committed is not True or status.fsync_status != "completed":
        raise UpdateError(
            f"{label} rename did not reach a durable known state; "
            "the object remains subject to manual recovery."
        )


def _rename_child_and_confirm(
    parent_fd: int,
    source_name: str,
    destination_name: str,
) -> RenameStatus:
    """Perform one anchored rename and classify both visibility and durability.

    The helper deliberately returns a record even when the underlying helper
    raises after ``rename(2)``.  Callers must treat both ``True`` and
    ``unknown`` as potentially committed and inspect the anchored directory.
    """
    operation = _infer_rename_operation(source_name, destination_name)
    before_source = _entry_lstat_at(parent_fd, source_name)
    before_destination = _entry_lstat_at(parent_fd, destination_name)
    before_source_payload = _entry_identity_payload(before_source)
    before_destination_payload = _entry_identity_payload(before_destination)
    if before_destination is not None:
        # A directory rename would otherwise replace a race-created symlink,
        # file, or directory.  Refuse the operation before invoking rename(2).
        return RenameStatus(
            operation=operation,
            source_name=source_name,
            destination_name=destination_name,
            rename_committed=False,
            source_identity_before=before_source_payload,
            destination_identity_before=before_destination_payload,
            source_identity_after=before_source_payload,
            destination_identity_after=before_destination_payload,
            fsync_status="not_attempted",
            error_type="destination_occupied",
            error_message="destination already exists before anchored rename.",
        )
    error_type = None
    error_message = None
    fsync_status = "not_attempted"
    try:
        _rename_child_at(parent_fd, source_name, destination_name)
        fsync_status = "completed"
    except (OSError, UpdateError) as exc:
        error_type = type(exc).__name__
        error_message = str(exc)

    after_source = _entry_lstat_at(parent_fd, source_name)
    after_destination = _entry_lstat_at(parent_fd, destination_name)
    after_source_payload = _entry_identity_payload(after_source)
    after_destination_payload = _entry_identity_payload(after_destination)

    source_moved = (
        before_source_payload is not None
        and after_destination_payload == before_source_payload
        and after_source_payload is None
    )
    source_unchanged = (
        before_source_payload is not None
        and after_source_payload == before_source_payload
        and after_destination_payload == before_destination_payload
    )
    if source_moved:
        committed: bool | str = True
    elif source_unchanged:
        committed = False
    elif error_type is None:
        committed = True
    else:
        committed = "unknown"

    if error_type is not None:
        if committed is True:
            fsync_status = "failed"
        elif committed == "unknown":
            fsync_status = "unknown"
        else:
            fsync_status = "not_attempted"
    return RenameStatus(
        operation=operation,
        source_name=source_name,
        destination_name=destination_name,
        rename_committed=committed,
        source_identity_before=before_source_payload,
        destination_identity_before=before_destination_payload,
        source_identity_after=after_source_payload,
        destination_identity_after=after_destination_payload,
        fsync_status=fsync_status,
        error_type=error_type,
        error_message=error_message,
    )


def _open_authorized_root(path: Path) -> int:
    """Open the complete absolute path one directory FD at a time.

    Opening the final path by display string leaves its parent chain exposed to
    replacement between validation and open.  The chain below is traversed
    relative to an already-open directory and every component is opened with
    ``O_NOFOLLOW``.  Intermediate ancestors are only required to be directories
    because system roots may not be owned by the current user; the final root
    receives the normal private ownership checks.
    """
    lexical = _absolute_lexical_path(path)
    if not lexical.is_absolute():
        raise UpdateError("authorized installation root must be absolute.")
    _validate_lexical_ancestor_chain(lexical, "authorized installation root")
    # macOS exposes temporary roots through the conventional /var and /tmp
    # aliases.  Resolve only those OS-owned aliases; an attacker-controlled
    # component below them was already rejected by the lexical walk above.
    if len(lexical.parts) > 1 and lexical.parts[1] in ("var", "tmp"):
        lexical = lexical.resolve(strict=True)
    parts = lexical.parts
    current_fd: int | None = None
    try:
        current_fd = os.open(Path(parts[0]), _directory_open_flags())
        for index, part in enumerate(parts[1:]):
            if part in ("", ".", "..") or "/" in part:
                raise UpdateError("authorized installation root contains an unsafe component.")
            try:
                child_fd = os.open(
                    part,
                    _directory_open_flags(),
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise UpdateError(
                    "unable to anchor the authorized installation root parent chain."
                ) from exc
            try:
                child_stat = os.fstat(child_fd)
                if not stat.S_ISDIR(child_stat.st_mode):
                    raise UpdateError(
                        "authorized installation root parent chain contains a non-directory."
                    )
                if index == len(parts[1:]) - 1:
                    _validate_directory_fd(child_fd, "authorized installation root")
            except Exception:
                os.close(child_fd)
                raise
            os.close(current_fd)
            current_fd = child_fd
        if current_fd is None:
            raise UpdateError("unable to anchor the authorized installation root.")
        return current_fd
    except Exception:
        if current_fd is not None:
            os.close(current_fd)
        raise


def _relative_directory_parts(path: Path, root: Path, label: str) -> tuple[str, ...]:
    _require_within(path, root, label)
    parts = tuple(path.relative_to(root).parts)
    if any(part in ("", ".", "..") or "/" in part for part in parts):
        raise UpdateError(f"unsafe {label} path.")
    return parts


def _open_relative_directory_anchor(
    root_fd: int,
    root_path: Path,
    path: Path,
    label: str,
    *,
    create: bool,
    private: bool = False,
) -> DirectoryAnchor:
    parts = _relative_directory_parts(path, root_path, label)
    current_fd = os.dup(root_fd)
    try:
        if not parts:
            current = _validate_directory_fd(current_fd, label, private=private)
            return DirectoryAnchor(
                path=path,
                relative_parts=parts,
                fd=current_fd,
                device=current.st_dev,
                inode=current.st_ino,
                uid=current.st_uid,
                mode=stat.S_IMODE(current.st_mode),
                private=private,
            )
        for index, part in enumerate(parts):
            final = index == len(parts) - 1
            try:
                child_stat = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise UpdateError(f"{label} does not exist.") from None
                try:
                    os.mkdir(part, 0o700 if final and private else 0o755, dir_fd=current_fd)
                    os.fsync(current_fd)
                    child_stat = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
                except OSError as exc:
                    raise UpdateError(f"unable to create {label} safely.") from exc
            if not stat.S_ISDIR(child_stat.st_mode) or stat.S_ISLNK(child_stat.st_mode):
                raise UpdateError(f"non-directory or symbolic-link component rejected in {label}.")
            try:
                child_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            except OSError as exc:
                raise UpdateError(f"unable to anchor {label} safely.") from exc
            try:
                opened = _validate_directory_fd(
                    child_fd,
                    label if final else f"{label} ancestor {part}",
                    private=private and final,
                )
                if opened.st_dev != child_stat.st_dev or opened.st_ino != child_stat.st_ino:
                    raise UpdateError(f"{label} identity changed while opening.")
            except Exception:
                os.close(child_fd)
                raise
            os.close(current_fd)
            current_fd = child_fd
        anchored = os.fstat(current_fd)
        return DirectoryAnchor(
            path=path,
            relative_parts=parts,
            fd=current_fd,
            device=anchored.st_dev,
            inode=anchored.st_ino,
            uid=anchored.st_uid,
            mode=stat.S_IMODE(anchored.st_mode),
            private=private,
        )
    except Exception:
        os.close(current_fd)
        raise


def _verify_directory_anchor(
    root_fd: int,
    anchor: DirectoryAnchor,
    label: str,
    *,
    allow_stale_display_path: bool = False,
) -> None:
    if allow_stale_display_path:
        anchored = _validate_directory_fd(anchor.fd, label, private=anchor.private)
        if (
            anchored.st_dev != anchor.device
            or anchored.st_ino != anchor.inode
            or anchored.st_uid != anchor.uid
            or stat.S_IMODE(anchored.st_mode) != anchor.mode
        ):
            raise UpdateError(f"{label} FD identity changed during the update transaction.")
        return
    current_fd = os.dup(root_fd)
    try:
        for part in anchor.relative_parts:
            try:
                next_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            except OSError as exc:
                raise UpdateError(f"{label} is no longer reachable at its approved path.") from exc
            os.close(current_fd)
            current_fd = next_fd
        current = _validate_directory_fd(current_fd, label, private=anchor.private)
        anchored = _validate_directory_fd(anchor.fd, label, private=anchor.private)
        if (
            current.st_dev != anchor.device
            or current.st_ino != anchor.inode
            or anchored.st_dev != anchor.device
            or anchored.st_ino != anchor.inode
            or current.st_uid != anchor.uid
            or anchored.st_uid != anchor.uid
            or stat.S_IMODE(current.st_mode) != anchor.mode
            or stat.S_IMODE(anchored.st_mode) != anchor.mode
        ):
            raise UpdateError(f"{label} identity changed during the update transaction.")
    finally:
        os.close(current_fd)


def _verify_root_anchor(
    path: Path,
    descriptor: int,
    expected_identity: DirectoryIdentity | None = None,
) -> None:
    current = _lstat(path)
    anchored = _validate_directory_fd(descriptor, "authorized installation root")
    expected = expected_identity or _directory_identity(anchored, "authorized installation root")
    if (
        current is None
        or not stat.S_ISDIR(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or not _identity_matches(current, expected)
        or not _identity_matches(anchored, expected)
    ):
        raise UpdateError(
            "authorized installation root identity changed during the update transaction."
        )


def _entry_lstat_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _rename_no_replace_between_fds(
    source_parent_fd: int,
    source_name: str,
    destination_parent_fd: int,
    destination_name: str,
) -> None:
    """Atomically rename without ever replacing a destination entry.

    Plain ``os.rename`` is not sufficient here: a destination created after a
    preflight stat would be silently replaced.  Use the native no-replace
    primitive where the platform exposes one and fail closed elsewhere.
    """
    library_name = ctypes.util.find_library("c")
    try:
        library = ctypes.CDLL(library_name or None, use_errno=True)
        if sys.platform == "darwin":
            function = library.renameatx_np
            flags = 0x00000004  # RENAME_EXCL
        elif sys.platform.startswith("linux"):
            function = library.renameat2
            flags = 0x00000001  # RENAME_NOREPLACE
        else:
            raise UpdateError("platform has no approved atomic no-replace rename primitive.")
    except (AttributeError, OSError) as exc:
        raise UpdateError("platform has no approved atomic no-replace rename primitive.") from exc
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    result = function(
        source_parent_fd,
        os.fsencode(source_name),
        destination_parent_fd,
        os.fsencode(destination_name),
        flags,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _rename_no_replace_at(parent_fd: int, source_name: str, destination_name: str) -> None:
    _rename_no_replace_between_fds(
        parent_fd,
        source_name,
        parent_fd,
        destination_name,
    )


def _rename_child_at(parent_fd: int, source_name: str, destination_name: str) -> None:
    try:
        _rename_no_replace_at(parent_fd, source_name, destination_name)
        os.fsync(parent_fd)
    except OSError as exc:
        raise UpdateError("unable to rename within the anchored directory.") from exc


def manifest_sha256(manifest: dict[str, ManifestEntry]) -> str:
    serializable = [
        {
            "path": path,
            "kind": entry.kind,
            "size": entry.size,
            "sha256": entry.sha256,
            "mode": entry.mode,
            "uid": entry.uid,
        }
        for path, entry in sorted(manifest.items())
    ]
    return _sha256_bytes(
        json.dumps(serializable, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


@contextmanager
def target_update_lock(authorized_root: Path) -> Iterator[TargetLock]:
    if fcntl is None:
        raise UpdateError("apply requires POSIX advisory locking support.")
    root_fd = _open_authorized_root(authorized_root)
    lock_path = authorized_root / LOCK_FILE_NAME
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    flags = _nofollow_flags(flags, "target update lock")
    try:
        descriptor = os.open(LOCK_FILE_NAME, flags, 0o600, dir_fd=root_fd)
    except OSError as exc:
        os.close(root_fd)
        raise UpdateError("unable to open the target update lock safely.") from exc
    try:
        current = os.fstat(descriptor)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or current.st_uid != _effective_uid()
            or stat.S_IMODE(current.st_mode) & 0o077
        ):
            raise UpdateError(
                "target update lock must be a private regular file owned by the current user."
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise UpdateError("another update already holds the target lock.") from exc
        lock_identity = _entry_identity_payload(current)
        if lock_identity is None:
            raise UpdateError("target update lock identity could not be recorded.")
        visible_lock = _entry_lstat_at(root_fd, LOCK_FILE_NAME)
        if _entry_identity_payload(visible_lock) != lock_identity:
            raise UpdateError("target update lock pathname changed while acquiring the lock.")
        yield TargetLock(
            path=lock_path,
            authorized_root_fd=root_fd,
            lock_fd=descriptor,
            identity=_directory_identity(
                os.fstat(root_fd),
                "authorized installation root",
            ),
            lock_identity=lock_identity,
        )
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(descriptor)
        os.close(root_fd)


def _verify_target_lock(lock: TargetLock) -> None:
    """Reject a visible lock pathname that no longer names the held inode."""
    held = os.fstat(lock.lock_fd)
    visible = _entry_lstat_at(lock.authorized_root_fd, LOCK_FILE_NAME)
    expected = lock.lock_identity
    visible_payload = _entry_identity_payload(visible)
    held_payload = _entry_identity_payload(held)
    if (
        visible_payload != expected
        or held_payload != expected
        or visible is None
        or not stat.S_ISREG(visible.st_mode)
        or visible.st_nlink != 1
        or visible.st_uid != _effective_uid()
        or stat.S_IMODE(visible.st_mode) & 0o077
    ):
        raise UpdateError("target update lock pathname identity changed during the transaction.")


def _write_receipt_at(
    receipt_root_fd: int,
    receipt_name: str,
    payload: dict[str, object],
) -> None:
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    temporary_name = f".{receipt_name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    flags = _nofollow_flags(flags, "update receipt")
    try:
        descriptor = os.open(temporary_name, flags, 0o600, dir_fd=receipt_root_fd)
        try:
            _write_all(descriptor, encoded, "update receipt")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(
            temporary_name,
            receipt_name,
            src_dir_fd=receipt_root_fd,
            dst_dir_fd=receipt_root_fd,
        )
        os.fsync(receipt_root_fd)
    except OSError as exc:
        try:
            os.unlink(temporary_name, dir_fd=receipt_root_fd)
        except OSError:
            pass
        raise UpdateError("unable to persist the update recovery receipt.") from exc


def _update_receipt_at(
    receipt_root_fd: int,
    receipt_name: str,
    payload: dict[str, object],
    *,
    phase: str,
    status: str = "in_progress",
    error_type: str | None = None,
) -> None:
    _mark_display_path_states(payload)
    receipt_display_path_stale = False
    receipt_identity = payload.get("receipt_root_identity")
    receipt_display_path = payload.get("receipt_root")
    if isinstance(receipt_identity, dict):
        try:
            expected_receipt_identity = DirectoryIdentity(
                kind=str(receipt_identity["kind"]),
                uid=int(receipt_identity["uid"]),
                mode=int(receipt_identity["mode"]),
                device=int(receipt_identity["st_dev"]),
                inode=int(receipt_identity["st_ino"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise UpdateError("update receipt anchor identity is malformed.") from exc
        anchored = os.fstat(receipt_root_fd)
        if not _identity_matches(anchored, expected_receipt_identity):
            raise UpdateError("update receipt FD identity changed during the update transaction.")
        if isinstance(receipt_display_path, str):
            displayed = _lstat(Path(receipt_display_path))
        else:
            displayed = None
        if displayed is None or not _identity_matches(displayed, expected_receipt_identity):
            receipt_display_path_stale = True
            payload.setdefault("directory_anchors", {}).setdefault("receipt_root", {})[
                "display_path_identity"
            ] = "STALE_OR_REPLACED"
            payload.setdefault("directory_anchors", {}).setdefault("receipt_root", {})[
                "recovery_requires_fd_identity"
            ] = True
            payload["receipt_root_display_path"] = receipt_display_path
            payload["receipt_root"] = None
    if phase not in TRANSACTION_PHASES:
        raise UpdateError(f"unknown updater transaction phase: {phase}")
    previous_phase = payload.get("phase")
    if status != "failed" and previous_phase in TRANSACTION_PHASES:
        if TRANSACTION_PHASES.index(phase) < TRANSACTION_PHASES.index(str(previous_phase)):
            raise UpdateError("updater transaction phase moved backwards.")
    payload["phase"] = phase
    payload["status"] = status
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    if error_type is not None:
        payload["error_type"] = error_type
    _write_receipt_at(receipt_root_fd, receipt_name, payload)
    if receipt_display_path_stale:
        payload["status"] = "failed"
        payload["error_type"] = "RECEIPT_ROOT_REPLACED"
        payload["recovery_authority"] = "manual_only"
        _write_receipt_at(receipt_root_fd, receipt_name, payload)
        raise UpdateError(
            "update receipt display path was replaced; failure state persisted through "
            "the original anchored FD."
        )


def _write_all(descriptor: int, data: bytes, label: str) -> None:
    """Write all bytes or fail closed on a short/zero write."""
    view = memoryview(data)
    while view:
        try:
            written = os.write(descriptor, view)
        except OSError as exc:
            raise UpdateError(f"unable to write {label} completely.") from exc
        if not isinstance(written, int) or written <= 0 or written > len(view):
            raise UpdateError(f"unable to write {label} completely: invalid short write.")
        view = view[written:]


def _copy_regular_file(
    source: Path,
    destination: Path,
    source_stat: os.stat_result,
    relative_path: str,
) -> None:
    source_flags = _nofollow_flags(os.O_RDONLY, "source file")
    try:
        source_fd = os.open(source, source_flags)
        destination_fd = os.open(
            destination,
            _nofollow_flags(
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                "staged file",
            ),
            stat.S_IMODE(source_stat.st_mode),
        )
    except OSError as exc:
        if "source_fd" in locals():
            os.close(source_fd)
        raise UpdateError(f"unable to create staged file: {relative_path}") from exc

    try:
        opened = os.fstat(source_fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != source_stat.st_dev
            or opened.st_ino != source_stat.st_ino
            or opened.st_nlink > 1
        ):
            raise UpdateError(f"source file identity changed: {relative_path}")
        while True:
            chunk = os.read(source_fd, COPY_CHUNK_SIZE)
            if not chunk:
                break
            _write_all(destination_fd, chunk, f"staged file {relative_path}")
        os.fchmod(destination_fd, stat.S_IMODE(source_stat.st_mode))
        os.fsync(destination_fd)
    except OSError as exc:
        raise UpdateError(f"unable to copy staged file: {relative_path}") from exc
    finally:
        os.close(source_fd)
        os.close(destination_fd)


def copy_validated_tree(source: Path, destination: Path) -> None:
    if _lstat(destination) is not None:
        raise UpdateError("staging or backup destination already exists.")
    source_stat = _lstat(source)
    if source_stat is None or _validate_entry_type(source_stat, ".") != "directory":
        raise UpdateError("copy source must be a safe directory.")
    try:
        destination.mkdir(mode=0o700)
    except OSError as exc:
        raise UpdateError("unable to create staging or backup directory.") from exc

    def copy_directory(source_dir: Path, destination_dir: Path, prefix: Path) -> None:
        try:
            entries = sorted(os.scandir(source_dir), key=lambda item: item.name)
        except OSError as exc:
            raise UpdateError(f"unable to enumerate copy source: {prefix or Path('.')}.") from exc
        for entry in entries:
            relative = prefix / entry.name
            relative_text = relative.as_posix()
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise UpdateError(f"unable to inspect copy source: {relative_text}") from exc
            kind = _validate_entry_type(entry_stat, relative_text)
            destination_entry = destination_dir / entry.name
            if kind == "directory":
                try:
                    destination_entry.mkdir(mode=0o700)
                except (OSError, UpdateError) as exc:
                    raise UpdateError(
                        f"unable to create staged directory: {relative_text}"
                    ) from exc
                copy_directory(Path(entry.path), destination_entry, relative)
                os.chmod(destination_entry, stat.S_IMODE(entry_stat.st_mode))
                _fsync_directory(destination_entry)
            else:
                _copy_regular_file(
                    Path(entry.path),
                    destination_entry,
                    entry_stat,
                    relative_text,
                )

    copy_directory(source, destination, Path())
    os.chmod(destination, stat.S_IMODE(source_stat.st_mode))
    _fsync_directory(destination)


def _open_stable_directory_path(path: Path, label: str) -> int:
    """Open a directory path as one stable FD chain without following links."""
    lexical = _absolute_lexical_path(path)
    _validate_lexical_ancestor_chain(lexical, label)
    parts = lexical.parts
    current_fd: int | None = None
    try:
        current_fd = os.open(Path(parts[0]), _directory_open_flags())
        for part in parts[1:]:
            if part in ("", ".", "..") or "/" in part:
                raise UpdateError(f"unsafe component in {label}.")
            child_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = child_fd
        _validate_directory_fd(current_fd, label)
        return current_fd
    except (OSError, UpdateError) as exc:
        if current_fd is not None:
            os.close(current_fd)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"unable to anchor {label} safely.") from exc


def copy_validated_tree_at(
    source: Path,
    parent_fd: int,
    destination_name: str,
    source_root_fd: int | None = None,
) -> None:
    """Copy from a stable source FD into a child of an anchored destination FD."""
    source_parent_fd: int | None = None
    try:
        if source_root_fd is None:
            source_parent_fd = _open_stable_directory_path(source.parent, "source package parent")
            copy_validated_tree_between_fds(
                source_parent_fd,
                source.name,
                parent_fd,
                destination_name,
            )
        else:
            copy_validated_tree_between_fds(
                -1,
                source.name,
                parent_fd,
                destination_name,
                source_root_fd=source_root_fd,
            )
    finally:
        if source_parent_fd is not None:
            os.close(source_parent_fd)


def _open_child_directory_at(
    parent_fd: int,
    name: str,
    label: str,
) -> tuple[int, os.stat_result]:
    expected = _entry_lstat_at(parent_fd, name)
    if expected is None or _validate_entry_type(expected, label) != "directory":
        raise UpdateError(f"{label} must be a directory.")
    try:
        descriptor = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise UpdateError(f"unable to open {label} safely.") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not _identity_matches(
                opened,
                _directory_identity(expected, label),
            )
        ):
            raise UpdateError(f"{label} identity changed while opening.")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor, expected


def _capture_directory_identity_at(
    parent_fd: int,
    name: str,
    label: str,
) -> DirectoryIdentity:
    descriptor, expected = _open_child_directory_at(parent_fd, name, label)
    try:
        opened = _validate_directory_fd(descriptor, label)
        identity = _directory_identity(opened, label)
        if identity != _directory_identity(expected, label):
            raise UpdateError(f"{label} identity changed while opening.")
        return identity
    finally:
        os.close(descriptor)


def _verify_directory_entry_identity(
    parent_fd: int,
    name: str,
    expected: DirectoryIdentity,
    label: str,
) -> None:
    current = _entry_lstat_at(parent_fd, name)
    if current is None or not _identity_matches(current, expected):
        raise UpdateError(f"{label} root identity changed during the transaction.")


def _hash_regular_file_at(
    directory_fd: int,
    name: str,
    expected: os.stat_result,
    relative_path: str,
) -> str:
    flags = _nofollow_flags(
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
        "source manifest file",
    )
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise UpdateError(f"unable to open regular file safely: {relative_path}") from exc
    digest = hashlib.sha256()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or opened.st_nlink > 1
        ):
            raise UpdateError(f"regular file identity changed: {relative_path}")
        while True:
            chunk = os.read(descriptor, COPY_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        closed = os.fstat(descriptor)
        if (
            closed.st_dev != opened.st_dev
            or closed.st_ino != opened.st_ino
            or closed.st_size != opened.st_size
        ):
            raise UpdateError(f"regular file changed while reading: {relative_path}")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _build_tree_manifest_fd(
    root_fd: int,
    label: str,
) -> dict[str, ManifestEntry]:
    manifest: dict[str, ManifestEntry] = {}

    def visit(directory_fd: int, prefix: PurePosixPath) -> None:
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            raise UpdateError(f"unable to enumerate {label}: {prefix or PurePosixPath('.')}.") from exc
        for name in names:
            relative = prefix / name
            relative_text = relative.as_posix()
            try:
                entry_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise UpdateError(
                    f"unable to inspect {label} entry: {relative_text}"
                ) from exc
            kind = _validate_entry_type(entry_stat, relative_text)
            if kind == "directory":
                manifest[relative_text] = ManifestEntry(
                    "directory",
                    0,
                    "",
                    stat.S_IMODE(entry_stat.st_mode),
                    entry_stat.st_uid,
                )
                child_fd, _ = _open_child_directory_at(
                    directory_fd,
                    name,
                    f"{label} entry {relative_text}",
                )
                try:
                    visit(child_fd, relative)
                finally:
                    os.close(child_fd)
            else:
                manifest[relative_text] = ManifestEntry(
                    "file",
                    entry_stat.st_size,
                    _hash_regular_file_at(
                        directory_fd,
                        name,
                        entry_stat,
                        relative_text,
                    ),
                    stat.S_IMODE(entry_stat.st_mode),
                    entry_stat.st_uid,
                )

    visit(root_fd, PurePosixPath())
    return manifest


def _manifest_from_stable_root_fd(
    root_fd: int,
    label: str,
) -> dict[str, ManifestEntry]:
    descriptor = os.dup(root_fd)
    try:
        _validate_directory_fd(descriptor, f"{label} root")
        return _build_tree_manifest_fd(descriptor, label)
    finally:
        os.close(descriptor)


def build_tree_manifest_at(
    parent_fd: int,
    name: str,
    label: str,
) -> dict[str, ManifestEntry]:
    descriptor, _ = _open_child_directory_at(parent_fd, name, label)
    try:
        return _build_tree_manifest_fd(descriptor, label)
    finally:
        os.close(descriptor)


def _manifest_at_if_present(
    parent_fd: int,
    name: str,
    label: str,
) -> dict[str, ManifestEntry]:
    if _entry_lstat_at(parent_fd, name) is None:
        return {}
    return build_tree_manifest_at(parent_fd, name, label)


def copy_validated_tree_between_fds(
    source_parent_fd: int,
    source_name: str,
    destination_parent_fd: int,
    destination_name: str,
    *,
    source_root_fd: int | None = None,
) -> None:
    if _entry_lstat_at(destination_parent_fd, destination_name) is not None:
        raise UpdateError("staging or backup destination already exists.")
    if source_root_fd is None:
        source_fd, source_stat = _open_child_directory_at(
            source_parent_fd,
            source_name,
            "copy source",
        )
    else:
        source_fd = os.dup(source_root_fd)
        source_stat = os.fstat(source_fd)
        if not stat.S_ISDIR(source_stat.st_mode):
            os.close(source_fd)
            raise UpdateError("copy source FD must be a directory.")
    try:
        try:
            os.mkdir(destination_name, 0o700, dir_fd=destination_parent_fd)
            destination_fd = os.open(
                destination_name,
                _directory_open_flags(),
                dir_fd=destination_parent_fd,
            )
        except OSError as exc:
            raise UpdateError("unable to create anchored backup directory.") from exc
        try:
            def copy_directory(source_dir_fd: int, destination_dir_fd: int, prefix: PurePosixPath) -> None:
                try:
                    names = sorted(os.listdir(source_dir_fd))
                except OSError as exc:
                    raise UpdateError(f"unable to enumerate copy source: {prefix or PurePosixPath('.')}") from exc
                for name in names:
                    relative = prefix / name
                    relative_text = relative.as_posix()
                    try:
                        entry_stat = os.stat(
                            name,
                            dir_fd=source_dir_fd,
                            follow_symlinks=False,
                        )
                    except OSError as exc:
                        raise UpdateError(f"unable to inspect copy source: {relative_text}") from exc
                    kind = _validate_entry_type(entry_stat, relative_text)
                    if kind == "directory":
                        source_child_fd, _ = _open_child_directory_at(
                            source_dir_fd,
                            name,
                            f"copy source {relative_text}",
                        )
                        try:
                            os.mkdir(name, 0o700, dir_fd=destination_dir_fd)
                            destination_child_fd = os.open(
                                name,
                                _directory_open_flags(),
                                dir_fd=destination_dir_fd,
                            )
                        except OSError as exc:
                            os.close(source_child_fd)
                            raise UpdateError(
                                f"unable to create copied directory: {relative_text}"
                            ) from exc
                        try:
                            copy_directory(
                                source_child_fd,
                                destination_child_fd,
                                relative,
                            )
                            os.fchmod(
                                destination_child_fd,
                                stat.S_IMODE(entry_stat.st_mode),
                            )
                            os.fsync(destination_child_fd)
                        finally:
                            os.close(source_child_fd)
                            os.close(destination_child_fd)
                        continue
                    source_file_fd = None
                    destination_file_fd = None
                    try:
                        source_file_fd = os.open(
                            name,
                            _nofollow_flags(
                                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
                                "copy source file",
                            ),
                            dir_fd=source_dir_fd,
                        )
                        opened = os.fstat(source_file_fd)
                        if (
                            not stat.S_ISREG(opened.st_mode)
                            or opened.st_dev != entry_stat.st_dev
                            or opened.st_ino != entry_stat.st_ino
                            or opened.st_nlink > 1
                        ):
                            raise UpdateError(
                                f"copy source file identity changed: {relative_text}"
                            )
                        destination_file_fd = os.open(
                            name,
                            _nofollow_flags(
                                os.O_WRONLY
                                | os.O_CREAT
                                | os.O_EXCL
                                | getattr(os, "O_CLOEXEC", 0),
                                "copy destination file",
                            ),
                            stat.S_IMODE(entry_stat.st_mode),
                            dir_fd=destination_dir_fd,
                        )
                        while True:
                            chunk = os.read(source_file_fd, COPY_CHUNK_SIZE)
                            if not chunk:
                                break
                            _write_all(
                                destination_file_fd,
                                chunk,
                                f"copied file {relative_text}",
                            )
                        os.fchmod(
                            destination_file_fd,
                            stat.S_IMODE(entry_stat.st_mode),
                        )
                        os.fsync(destination_file_fd)
                    except OSError as exc:
                        raise UpdateError(
                            f"unable to copy regular file: {relative_text}"
                        ) from exc
                    finally:
                        if source_file_fd is not None:
                            os.close(source_file_fd)
                        if destination_file_fd is not None:
                            os.close(destination_file_fd)

            copy_directory(source_fd, destination_fd, PurePosixPath())
            os.fchmod(destination_fd, stat.S_IMODE(source_stat.st_mode))
            os.fsync(destination_fd)
            os.fsync(destination_parent_fd)
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def _append_cleanup_claim(payload: dict[str, object] | None, record: dict[str, object]) -> None:
    if payload is None:
        return
    claims = payload.setdefault("cleanup_claims", [])
    if isinstance(claims, list):
        claims.append(record)


def _open_cleanup_entry_fd(parent_fd: int, name: str, expected: os.stat_result) -> int:
    flags = _nofollow_flags(
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
        "retained cleanup entry",
    )
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    opened = os.fstat(descriptor)
    if (
        opened.st_dev != expected.st_dev
        or opened.st_ino != expected.st_ino
        or opened.st_uid != expected.st_uid
        or stat.S_IMODE(opened.st_mode) != stat.S_IMODE(expected.st_mode)
        or stat.S_ISDIR(opened.st_mode) != stat.S_ISDIR(expected.st_mode)
    ):
        os.close(descriptor)
        raise UpdateError("cleanup entry identity changed while opening its private claim.")
    return descriptor


def _claim_cleanup_entry(
    source_parent_fd: int,
    source_name: str,
    cleanup_parent_fd: int,
    cleanup_name: str,
    expected: os.stat_result,
    *,
    parent_anchor: str,
    cleanup_anchor: str,
    payload: dict[str, object] | None,
) -> tuple[dict[str, object], int | None]:
    record: dict[str, object] = {
        "original_parent_anchor": parent_anchor,
        "original_name": source_name,
        "expected_identity": _entry_identity_payload(expected),
        "retained_parent_anchor": cleanup_anchor,
        "retained_name": cleanup_name,
        "claimed_cleanup_anchor": cleanup_anchor,
        "claimed_cleanup_name": cleanup_name,
        "claim_outcome": "not_attempted",
        "retention_outcome": "not_attempted",
        "delete_outcome": "not_attempted",
        "error_type": None,
        "error_message": None,
        "manual_recovery_required": False,
    }
    held_fd: int | None = None
    claimed_fd: int | None = None
    try:
        visible = _entry_lstat_at(source_parent_fd, source_name)
        if visible is None or _entry_identity_payload(visible) != _entry_identity_payload(expected):
            record["claim_outcome"] = "identity_mismatch"
            record["retention_outcome"] = "not_retained"
            record["delete_outcome"] = "not_attempted"
            record["manual_recovery_required"] = True
            raise UpdateError("cleanup source identity changed before private claim.")
        if stat.S_ISLNK(visible.st_mode) or visible.st_uid != _effective_uid():
            record["claim_outcome"] = "identity_mismatch"
            record["retention_outcome"] = "not_retained"
            record["delete_outcome"] = "not_attempted"
            record["manual_recovery_required"] = True
            raise UpdateError("cleanup source is not a current-user-owned non-link entry.")
        if stat.S_ISDIR(visible.st_mode):
            if not stat.S_ISDIR(expected.st_mode):
                raise UpdateError("cleanup source type changed before private claim.")
            held_fd, _ = _open_child_directory_at(source_parent_fd, source_name, "cleanup source")
        elif stat.S_ISREG(visible.st_mode) and visible.st_nlink == 1:
            held_fd = _open_cleanup_entry_fd(source_parent_fd, source_name, expected)
        else:
            raise UpdateError("refusing to claim a non-regular or multiply-linked cleanup entry.")
        held = os.fstat(held_fd)
        if _entry_identity_payload(held) != _entry_identity_payload(expected):
            raise UpdateError("cleanup source FD identity changed before private claim.")
        _rename_no_replace_between_fds(
            source_parent_fd,
            source_name,
            cleanup_parent_fd,
            cleanup_name,
        )
        try:
            os.fsync(source_parent_fd)
            os.fsync(cleanup_parent_fd)
        except OSError as exc:
            record["claim_outcome"] = "claim_unknown"
            record["retention_outcome"] = "retained_by_security_policy"
            record["delete_outcome"] = "retained_by_security_policy"
            record["manual_recovery_required"] = True
            record["error_type"] = type(exc).__name__
            record["error_message"] = str(exc)
            raise UpdateError("cleanup claim became visible but durability is unknown.") from exc
        claimed = _entry_lstat_at(cleanup_parent_fd, cleanup_name)
        if claimed is None or _entry_identity_payload(claimed) != _entry_identity_payload(expected):
            record["claim_outcome"] = "identity_mismatch"
            record["retention_outcome"] = "retained_by_security_policy"
            record["delete_outcome"] = "retained_by_security_policy"
            record["manual_recovery_required"] = True
            raise UpdateError("private cleanup claim identity changed after atomic move.")
        claimed_fd = _open_cleanup_entry_fd(cleanup_parent_fd, cleanup_name, expected)
        record["claim_outcome"] = "claimed_and_retained"
        record["retention_outcome"] = "retained_by_security_policy"
        record["delete_outcome"] = "retained_by_security_policy"
        record["manual_recovery_required"] = True
        return record, claimed_fd
    except (OSError, UpdateError) as exc:
        if record["claim_outcome"] == "not_attempted":
            retained = _entry_lstat_at(cleanup_parent_fd, cleanup_name) is not None
            record["claim_outcome"] = "claim_unknown" if retained else "claim_failed"
            record["retention_outcome"] = (
                "retained_by_security_policy" if retained else "not_retained"
            )
            record["delete_outcome"] = (
                "retained_by_security_policy" if retained else "not_attempted"
            )
            record["manual_recovery_required"] = True
        record["error_type"] = record["error_type"] or type(exc).__name__
        record["error_message"] = record["error_message"] or str(exc)
        _append_cleanup_claim(payload, record)
        if isinstance(exc, OSError):
            raise UpdateError("unable to claim cleanup object without replacement.") from exc
        raise
    finally:
        if held_fd is not None:
            os.close(held_fd)


def _remove_owned_directory_at(
    parent_fd: int,
    name: str,
    *,
    cleanup_fd: int | None = None,
    cleanup_anchor: str | None = None,
    expected_identity: dict[str, object] | None = None,
    payload: dict[str, object] | None = None,
    object_kind: str = "transaction_object",
    parent_anchor: str = "unknown",
) -> dict[str, object]:
    """Atomically claim a cleanup object and retain it for manual recovery.

    POSIX/macOS do not provide a portable inode-bound final unlink/rmdir.  The
    updater therefore never deletes a transaction-controlled object after a
    claim.  A successful no-replace claim is the terminal cleanup action:
    revalidate the retained FD and leave the object in the transaction-specific
    quarantine namespace for explicit, separately reviewed recovery.
    """
    if cleanup_fd is None or cleanup_anchor is None:
        raise UpdateError("transaction-private cleanup FD is required for deletion.")
    current = _entry_lstat_at(parent_fd, name)
    if current is None:
        record = {
            "original_parent_anchor": parent_anchor,
            "original_name": name,
            "expected_identity": expected_identity,
            "retained_parent_anchor": cleanup_anchor,
            "retained_name": None,
            "claimed_cleanup_anchor": cleanup_anchor,
            "claimed_cleanup_name": None,
            "claim_outcome": "stale_or_replaced",
            "retention_outcome": "not_retained",
            "delete_outcome": "not_attempted",
            "error_type": None,
            "error_message": None,
            "manual_recovery_required": True,
        }
        _append_cleanup_claim(payload, record)
        raise UpdateError("cleanup object disappeared before it could be retained.")
    if expected_identity is None or _entry_identity_payload(current) != expected_identity:
        raise UpdateError("refusing cleanup because the expected entry identity is unavailable or changed.")
    if stat.S_ISLNK(current.st_mode) or current.st_uid != _effective_uid():
        raise UpdateError("refusing cleanup of an unexpected or foreign-owned entry.")
    claimed_name = f".{name}.cleanup.{uuid.uuid4().hex}"
    record, claimed_fd = _claim_cleanup_entry(
        parent_fd,
        name,
        cleanup_fd,
        claimed_name,
        current,
        parent_anchor=parent_anchor,
        cleanup_anchor=cleanup_anchor,
        payload=payload,
    )
    try:
        if claimed_fd is None:
            raise UpdateError("private cleanup claim did not produce an FD.")
        if stat.S_ISDIR(current.st_mode):
            # Re-open and validate the retained root and all descendants without
            # mutating them.  The retained namespace, not the original display
            # path, is the recovery authority.
            build_tree_manifest_at(
                cleanup_fd,
                claimed_name,
                f"retained {object_kind}",
            )
            os.fsync(claimed_fd)
        held = os.fstat(claimed_fd)
        if _entry_identity_payload(held) != _entry_identity_payload(current):
            record["claim_outcome"] = "identity_mismatch"
            record["retention_outcome"] = "retained_by_security_policy"
            record["delete_outcome"] = "retained_by_security_policy"
            record["manual_recovery_required"] = True
            raise UpdateError("retained cleanup identity changed during revalidation.")
        record["claim_outcome"] = "claimed_and_retained"
        record["retention_outcome"] = "retained_by_security_policy"
        record["delete_outcome"] = "retained_by_security_policy"
        record["manual_recovery_required"] = True
        _append_cleanup_claim(payload, record)
        return record
    except (OSError, UpdateError) as exc:
        if record.get("retention_outcome") == "not_attempted":
            record["retention_outcome"] = "retained_by_security_policy"
            record["delete_outcome"] = "retained_by_security_policy"
            record["manual_recovery_required"] = True
        record["error_type"] = record.get("error_type") or type(exc).__name__
        record["error_message"] = record.get("error_message") or str(exc)
        _append_cleanup_claim(payload, record)
        raise
    finally:
        if claimed_fd is not None:
            os.close(claimed_fd)


def _cleanup_outcome(
    payload: dict[str, object] | None,
    *,
    phase: str,
    object_kind: str,
    name: str,
    parent_fd: int,
    parent_anchor: str,
    expected_identity: dict[str, object] | None,
    cleanup_fd: int | None,
    cleanup_anchor: str | None,
) -> bool:
    """Retain one identity-matched transaction object and record the result."""
    current = _entry_lstat_at(parent_fd, name)
    outcome: dict[str, object] = {
        "phase": phase,
        "object_kind": object_kind,
        "name": name,
        "parent_anchor": parent_anchor,
        "attempted": True,
        "completed": False,
        "failure_type": None,
        "failure_message": None,
        "object_identity": _entry_identity_payload(current),
        "original_parent_anchor": parent_anchor,
        "original_name": name,
        "expected_identity": expected_identity,
        "retained_parent_anchor": cleanup_anchor,
        "retained_name": None,
        "claimed_cleanup_anchor": cleanup_anchor,
        "claimed_cleanup_name": None,
        "claim_outcome": "not_attempted",
        "retention_outcome": "not_attempted",
        "delete_outcome": "not_attempted",
        "manual_recovery_required": False,
    }
    try:
        if current is None:
            outcome["claim_outcome"] = "stale_or_replaced"
            outcome["failure_type"] = "UpdateError"
            outcome["failure_message"] = "cleanup object disappeared before retention."
            return False
        if expected_identity is None or _entry_identity_payload(current) != expected_identity:
            raise UpdateError(
                "refusing to clean an object whose expected FD identity is unavailable "
                "or no longer matches."
            )
        result = _remove_owned_directory_at(
            parent_fd,
            name,
            cleanup_fd=cleanup_fd,
            cleanup_anchor=cleanup_anchor,
            expected_identity=expected_identity,
            payload=payload,
            object_kind=object_kind,
            parent_anchor=parent_anchor,
        )
        outcome.update(result)
        if result.get("delete_outcome") != "retained_by_security_policy":
            raise UpdateError("cleanup did not reach a verified retained state.")
        outcome["completed"] = True
        return True
    except (OSError, UpdateError) as exc:
        if payload is not None:
            claims = payload.get("cleanup_claims", [])
            if isinstance(claims, list):
                for claim in reversed(claims):
                    if (
                        isinstance(claim, dict)
                        and claim.get("original_name") == name
                        and claim.get("original_parent_anchor") == parent_anchor
                    ):
                        outcome.update(claim)
                        break
        outcome["failure_type"] = type(exc).__name__
        outcome["failure_message"] = str(exc)
        return False
    finally:
        if payload is not None:
            outcomes = payload.setdefault("cleanup_outcomes", [])
            if isinstance(outcomes, list):
                outcomes.append(outcome)


def _retained_fd_identities(
    payload: dict[str, object] | None,
    parent_fds: dict[str, int],
) -> list[dict[str, object]]:
    retained: list[dict[str, object]] = []
    if payload is None:
        return retained
    objects = payload.get("objects", {})
    if not isinstance(objects, dict):
        return retained
    for object_kind, record in objects.items():
        if not isinstance(record, dict):
            continue
        name = record.get("display_name")
        parent_anchor = record.get("parent_anchor")
        parent_fd = parent_fds.get(str(parent_anchor))
        if not isinstance(name, str) or parent_fd is None:
            continue
        identity = _entry_identity_payload(_entry_lstat_at(parent_fd, name))
        if identity is not None:
            retained.append(
                {
                    "object_kind": object_kind,
                    "name": name,
                    "parent_anchor": parent_anchor,
                    "fd_identity": identity,
                }
            )
    return retained


def _expected_object_identity(
    payload: dict[str, object],
    object_kind: str,
) -> dict[str, object] | None:
    objects = payload.get("objects")
    if not isinstance(objects, dict):
        return None
    record = objects.get(object_kind)
    if not isinstance(record, dict):
        return None
    expected = record.get("expected_identity")
    return expected if isinstance(expected, dict) else None


def _unique_path(parent: Path, stem: str) -> Path:
    return parent / f"{stem}-{timestamp()}-{uuid.uuid4().hex[:12]}"


def _persist_failure_receipt(
    receipt_root_fd: int,
    receipt_name: str,
    payload: dict[str, object],
    *,
    phase: str,
    error: BaseException,
    parent_fds: dict[str, int],
) -> bool:
    payload["status"] = "failed"
    payload["phase"] = phase
    payload["recovery_authority"] = "manual_only"
    payload["failure_type"] = type(error).__name__
    payload["failure_message"] = str(error)
    payload["retained_fd_identities"] = _retained_fd_identities(payload, parent_fds)
    try:
        _update_receipt_at(
            receipt_root_fd,
            receipt_name,
            payload,
            phase=phase,
            status="failed",
            error_type=type(error).__name__,
        )
        return True
    except UpdateError:
        print("RECEIPT_PERSISTENCE_UNAVAILABLE")
        print(
            "Retained objects (FD identity): "
            + json.dumps(payload["retained_fd_identities"], sort_keys=True)
        )
        return False


def run_pre_upgrade_safety_audit() -> None:
    audit_script = (
        SKILLS_ROOT
        / "long-horizon-engineering"
        / "scripts"
        / "audit_skill_safety.py"
    )
    if not audit_script.is_file():
        raise UpdateError("safety audit script was not found in the source package.")
    result = subprocess.run(
        [sys.executable, str(audit_script), "--root", str(PACKAGE_ROOT)],
        check=False,
    )
    if result.returncode != 0:
        raise UpdateError(
            "pre-upgrade skill safety audit failed; review it before applying updates."
        )


def _manifest_if_present(path: Path, label: str) -> dict[str, ManifestEntry]:
    current = _lstat(path)
    if current is None:
        return {}
    return build_tree_manifest(path, label)


def _restore_previous_target_at(
    target_parent_fd: int,
    previous_name: str | None,
    target_name: str,
    original_manifest: dict[str, ManifestEntry],
    original_root_identity: DirectoryIdentity | None = None,
    receipt_payload: dict[str, object] | None = None,
    restore_phase: str = "recovery",
    cleanup_fd: int | None = None,
    cleanup_anchor: str | None = None,
) -> str:
    if previous_name is None:
        if receipt_payload is not None:
            receipt_payload["restore_status"] = "restore_not_attempted"
        return "No previous target existed; the active target remains absent."
    rename_status: RenameStatus | None = None
    if receipt_payload is not None:
        receipt_payload["restore_status"] = "restore_attempted_but_unverified"
    try:
        if _entry_lstat_at(target_parent_fd, target_name) is not None:
            raise UpdateError(
                "refusing previous-to-target restore while the active target path is occupied."
            )
        previous_before_restore = _entry_lstat_at(target_parent_fd, previous_name)
        if previous_before_restore is None:
            raise UpdateError("previous target disappeared before restore.")
        if (
            original_root_identity is not None
            and _entry_identity_payload(previous_before_restore)
            != _identity_payload(original_root_identity)
        ):
            raise UpdateError("previous target identity does not match the original target manifest.")
        rename_status = _rename_for_transaction(
            target_parent_fd,
            previous_name,
            target_name,
            receipt_payload,
            parent_anchor="target_parent",
        )
        _require_durable_rename(rename_status, "previous-to-target restore")
        restored = build_tree_manifest_at(
            target_parent_fd,
            target_name,
            "restored target",
        )
        validate_owned_non_writable_manifest_at(
            target_parent_fd,
            target_name,
            restored,
            "restored target",
            original_root_identity,
        )
        verify_exact_manifest(original_manifest, restored, "restored target")
    except UpdateError as exc:
        if receipt_payload is not None:
            receipt_payload["restore_status"] = "restore_attempted_but_unverified"
            current_identity = _entry_lstat_at(target_parent_fd, target_name)
            receipt_payload["restored_target_identity"] = _entry_identity_payload(
                current_identity
            )
            receipt_payload["restored_manifest_sha256"] = None
            receipt_payload["restored_at_phase"] = restore_phase
            _record_object_state(
                receipt_payload,
                "target",
                display_name=target_name,
                parent_anchor="target_parent",
                expected_identity=receipt_payload.get("objects", {})
                .get("target", {})
                .get("expected_identity")
                if isinstance(receipt_payload.get("objects"), dict)
                and isinstance(receipt_payload.get("objects", {}).get("target"), dict)
                else None,
                current_identity=_entry_identity_payload(current_identity),
            )
        raise UpdateError(
            "best-effort recovery failed; retained backup and previous target require "
            "manual inspection."
        ) from exc
    if receipt_payload is not None:
        restored_identity = _entry_lstat_at(target_parent_fd, target_name)
        receipt_payload["restore_status"] = "restored_verified"
        receipt_payload["restored_target_identity"] = _entry_identity_payload(
            restored_identity
        )
        receipt_payload["restored_manifest_sha256"] = manifest_sha256(restored)
        receipt_payload["restored_at_phase"] = restore_phase
        root_identities = receipt_payload.setdefault("root_identities", {})
        if isinstance(root_identities, dict) and restored_identity is not None:
            restored_payload = _entry_identity_payload(restored_identity)
            root_identities["restored"] = restored_payload
            root_identities["target"] = restored_payload
        _record_object_state(
            receipt_payload,
            "target",
            display_name=target_name,
            parent_anchor="target_parent",
            expected_identity=_entry_identity_payload(restored_identity),
            current_identity=_entry_identity_payload(restored_identity),
        )
    return "Previous target restored and its manifest verified."


def _restore_verified_backup_at(
    authorized_root_fd: int,
    target_parent_anchor: DirectoryAnchor,
    backup_root_anchor: DirectoryAnchor,
    backup_path: Path,
    target_name: str,
    original_manifest: dict[str, ManifestEntry],
    original_root_identity: DirectoryIdentity | None = None,
    receipt_payload: dict[str, object] | None = None,
    restore_phase: str = "verified_backup_recovery",
    cleanup_fd: int | None = None,
    cleanup_anchor: str | None = None,
) -> str:
    """Restore only a separately verified backup after a moved-target mismatch."""
    _verify_directory_anchor(
        authorized_root_fd,
        target_parent_anchor,
        "target parent",
    )
    _verify_directory_anchor(
        authorized_root_fd,
        backup_root_anchor,
        "backup root",
        allow_stale_display_path=True,
    )
    backup_identity = _capture_directory_identity_at(
        backup_root_anchor.fd,
        backup_path.name,
        "verified backup",
    )
    recovery_name = _unique_path(
        target_parent_anchor.path,
        f".{target_name}.recovery",
    ).name
    try:
        copy_validated_tree_between_fds(
            backup_root_anchor.fd,
            backup_path.name,
            target_parent_anchor.fd,
            recovery_name,
        )
        recovery_manifest = build_tree_manifest_at(
            target_parent_anchor.fd,
            recovery_name,
            "verified recovery",
        )
        validate_owned_non_writable_manifest_at(
            target_parent_anchor.fd,
            recovery_name,
            recovery_manifest,
            "verified recovery",
        )
        verify_exact_manifest(
            original_manifest,
            recovery_manifest,
            "verified recovery",
        )
        durable = _rename_for_transaction(
            target_parent_anchor.fd,
            recovery_name,
            target_name,
            receipt_payload,
            parent_anchor="target_parent",
        )
        if durable.rename_committed is not True or durable.fsync_status != "completed":
            raise UpdateError(
                "verified backup restored but parent-directory durability could not be confirmed."
            )
        restored_identity = _capture_directory_identity_at(
            target_parent_anchor.fd,
            target_name,
            "restored target",
        )
        if original_root_identity is not None and restored_identity.mode != original_root_identity.mode:
            raise UpdateError("restored target root mode changed during recovery.")
        _verify_directory_entry_identity(
            backup_root_anchor.fd,
            backup_path.name,
            backup_identity,
            "verified backup",
        )
        if receipt_payload is not None:
            receipt_payload["restore_status"] = "restored_verified"
            receipt_payload["restored_target_identity"] = _entry_identity_payload(
                _entry_lstat_at(target_parent_anchor.fd, target_name)
            )
            receipt_payload["restored_manifest_sha256"] = manifest_sha256(
                recovery_manifest
            )
            receipt_payload["restored_at_phase"] = restore_phase
            root_identities = receipt_payload.setdefault("root_identities", {})
            if isinstance(root_identities, dict):
                root_identities["restored"] = _identity_payload(restored_identity)
                root_identities["target"] = _identity_payload(restored_identity)
            _record_object_state(
                receipt_payload,
                "target",
                display_name=target_name,
                parent_anchor="target_parent",
                expected_identity=_identity_payload(restored_identity),
                current_identity=_identity_payload(restored_identity),
            )
    except UpdateError:
        if receipt_payload is not None:
            receipt_payload["restore_status"] = "restore_attempted_but_unverified"
            receipt_payload["restored_target_identity"] = _entry_identity_payload(
                _entry_lstat_at(target_parent_anchor.fd, target_name)
            )
            receipt_payload["restored_manifest_sha256"] = None
            receipt_payload["restored_at_phase"] = restore_phase
        raise
    finally:
        if _entry_lstat_at(target_parent_anchor.fd, recovery_name) is not None:
            _remove_owned_directory_at(
                target_parent_anchor.fd,
                recovery_name,
                cleanup_fd=cleanup_fd,
                cleanup_anchor=cleanup_anchor,
                expected_identity=_entry_identity_payload(
                    _entry_lstat_at(target_parent_anchor.fd, recovery_name)
                ),
                payload=receipt_payload,
                object_kind="recovery",
                parent_anchor="target_parent",
            )
    return "Verified backup restored; the unverified moved target remains quarantined."


def _apply_update_with_source_fd(
    target_plan: TargetPlan,
    skill: str,
    source: Path,
    source_manifest: dict[str, ManifestEntry],
    target_manifest: dict[str, ManifestEntry],
    approved_inventory: ApprovedInventory,
    source_fd: int | None = None,
) -> Path | None:
    target = target_plan.target
    _require_owned_non_writable_directory(
        target_plan.authorized_root,
        "authorized installation root",
    )
    _validate_owned_non_writable_ancestor_chain(
        target_plan.authorized_root,
        target.parent,
        "target path",
    )
    backup_path: Path | None = None

    with target_update_lock(target_plan.authorized_root) as target_lock:
        verify_approved_inventory_identity(
            skill,
            approved_inventory,
            "before audit",
        )
        locked_source_manifest = (
            _manifest_from_stable_root_fd(source_fd, "locked source package")
            if source_fd is not None
            else build_tree_manifest(source, "locked source package")
        )
        verify_exact_manifest(
            source_manifest,
            locked_source_manifest,
            "source package before audit",
        )
        verify_approved_source_inventory(
            locked_source_manifest,
            approved_inventory,
            "locked source package",
        )
        if source_fd is not None:
            validate_owned_non_writable_manifest_fd(
                source_fd,
                locked_source_manifest,
                "locked source package",
            )
        else:
            validate_owned_non_writable_tree(
                source,
                locked_source_manifest,
                "locked source package",
            )
        locked_target_manifest = _manifest_if_present(target, "locked target skill")
        verify_exact_manifest(
            target_manifest,
            locked_target_manifest,
            "target before audit",
        )
        if locked_target_manifest:
            validate_owned_non_writable_tree(
                target,
                locked_target_manifest,
                "locked target skill",
            )

        print("Pre-upgrade safety audit:", flush=True)
        run_pre_upgrade_safety_audit()
        source_after_audit = (
            _manifest_from_stable_root_fd(source_fd, "source package after audit")
            if source_fd is not None
            else build_tree_manifest(source, "source package after audit")
        )
        verify_approved_inventory_identity(
            skill,
            approved_inventory,
            "during audit",
        )
        verify_exact_manifest(
            source_manifest,
            source_after_audit,
            "source package after audit",
        )
        verify_approved_source_inventory(
            source_after_audit,
            approved_inventory,
            "source package after audit",
        )
        if source_fd is not None:
            validate_owned_non_writable_manifest_fd(
                source_fd,
                source_after_audit,
                "source package after audit",
            )
        else:
            validate_owned_non_writable_tree(
                source,
                source_after_audit,
                "source package after audit",
            )

        receipt_root = target_plan.authorized_root / RECEIPT_DIRECTORY_NAME
        target_parent_anchor = None
        receipt_root_anchor = None
        cleanup_root_anchor = None
        backup_root_anchor = None
        staging = None
        previous = None
        backup_candidate = None
        backup_path = None
        receipt_name = None
        receipt_path = None
        receipt_payload = None
        staging_owned = False
        published_identity = None
        backup_root_created = False
        backup_root_detached = False
        previous_cleanup_completed = False

        try:
            target_parent_anchor = _open_relative_directory_anchor(
                target_lock.authorized_root_fd,
                target_plan.authorized_root,
                target.parent,
                "target parent",
                create=True,
            )
            backup_root_created = (
                _entry_lstat_at(
                    target_lock.authorized_root_fd,
                    target_plan.backup_root.name,
                )
                is None
            )
            backup_root_anchor = _open_relative_directory_anchor(
                target_lock.authorized_root_fd,
                target_plan.authorized_root,
                target_plan.backup_root,
                "backup root",
                create=True,
                private=True,
            )
            receipt_root_anchor = _open_relative_directory_anchor(
                target_lock.authorized_root_fd,
                target_plan.authorized_root,
                receipt_root,
                "update receipt directory",
                create=True,
                private=True,
            )
            _verify_root_anchor(
                target_plan.authorized_root,
                target_lock.authorized_root_fd,
                target_lock.identity,
            )
            _verify_directory_anchor(
                target_lock.authorized_root_fd,
                target_parent_anchor,
                "target parent",
            )
            _verify_directory_anchor(
                target_lock.authorized_root_fd,
                backup_root_anchor,
                "backup root",
            )
            _verify_directory_anchor(
                target_lock.authorized_root_fd,
                receipt_root_anchor,
                "update receipt directory",
            )
            anchored_target_manifest = _manifest_at_if_present(
                target_parent_anchor.fd,
                target.name,
                "anchored target before staging",
            )
            verify_exact_manifest(
                target_manifest,
                anchored_target_manifest,
                "anchored target before staging",
            )
            if anchored_target_manifest:
                target_identity = _capture_directory_identity_at(
                    target_parent_anchor.fd,
                    target.name,
                    "anchored target before staging",
                )
                validate_owned_non_writable_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    anchored_target_manifest,
                    "anchored target before staging",
                    target_identity,
                )
            else:
                target_identity = None

            transaction_id = uuid.uuid4().hex
            cleanup_root_name = f".{skill}.cleanup-{transaction_id}"
            cleanup_root_anchor = _open_relative_directory_anchor(
                target_lock.authorized_root_fd,
                target_plan.authorized_root,
                receipt_root / cleanup_root_name,
                "transaction cleanup directory",
                create=True,
                private=True,
            )
            _verify_directory_anchor(
                target_lock.authorized_root_fd,
                cleanup_root_anchor,
                "transaction cleanup directory",
            )
            staging = _unique_path(target.parent, f".{skill}.staging")
            previous = (
                _unique_path(target.parent, f".{skill}.previous")
                if target_manifest
                else None
            )
            backup_candidate = (
                _unique_path(target_plan.backup_root, f".{skill}.backup-incomplete")
                if target_manifest
                else None
            )
            backup_path = (
                _unique_path(target_plan.backup_root, skill)
                if target_manifest
                else None
            )
            quarantine = _unique_path(target.parent, f".{skill}.failed")
            receipt_name = f"{skill}-{transaction_id}.json"
            receipt_path = receipt_root / receipt_name
            receipt_payload: dict[str, object] = {
            "schema_version": "1.0",
            "transaction_id": transaction_id,
            "skill": skill,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "target": str(target),
            "backup": str(backup_path) if backup_path else None,
            "backup_incomplete": str(backup_candidate) if backup_candidate else None,
            "staging": str(staging),
            "previous": str(previous) if previous else None,
            "quarantine": str(quarantine),
            "lock": str(target_lock.path),
            "package_manifest_sha256": approved_inventory.package_manifest_sha256,
            "approved_inventory_sha256": approved_inventory.inventory_sha256,
            "source_manifest_sha256": manifest_sha256(source_manifest),
            "target_manifest_sha256": manifest_sha256(target_manifest),
            "receipt_root": str(receipt_root),
            "cleanup_root": str(receipt_root / cleanup_root_name),
            "cleanup_root_identity": _identity_payload(
                _directory_identity(
                    os.fstat(cleanup_root_anchor.fd),
                    "transaction cleanup directory",
                )
            ),
            "receipt_root_identity": _identity_payload(
                _directory_identity(
                    os.fstat(receipt_root_anchor.fd),
                    "update receipt directory",
                )
            ),
                "authorized_root_identity": _identity_payload(target_lock.identity),
                "recovery_authority": "manual_only",
            "recovery_instructions": [
                "Do not rerun apply until the recorded target and recovery paths are inspected.",
                "Restore only from the recorded previous or validated backup path after comparing its manifest.",
                "Retain this receipt and record manual recovery as a separate explicit action.",
            ],
                "directory_anchors": {
                    "authorized_root": _directory_anchor_payload(
                        display_path=target_plan.authorized_root,
                        identity=target_lock.identity,
                        verified_at_phase="prepared",
                    ),
                    "target_parent": _directory_anchor_payload(
                        display_path=target_parent_anchor.path,
                        identity=DirectoryIdentity(
                            "directory",
                            target_parent_anchor.uid,
                            target_parent_anchor.mode,
                            target_parent_anchor.device,
                            target_parent_anchor.inode,
                        ),
                        verified_at_phase="prepared",
                    ),
                    "backup_root": _directory_anchor_payload(
                        display_path=backup_root_anchor.path,
                        identity=DirectoryIdentity(
                            "directory",
                            backup_root_anchor.uid,
                            backup_root_anchor.mode,
                            backup_root_anchor.device,
                            backup_root_anchor.inode,
                        ),
                        verified_at_phase="prepared",
                    ),
                    "receipt_root": _directory_anchor_payload(
                        display_path=receipt_root_anchor.path,
                        identity=DirectoryIdentity(
                            "directory",
                            receipt_root_anchor.uid,
                            receipt_root_anchor.mode,
                            receipt_root_anchor.device,
                            receipt_root_anchor.inode,
                        ),
                        verified_at_phase="prepared",
                    ),
                    "cleanup_root": _directory_anchor_payload(
                        display_path=cleanup_root_anchor.path,
                        identity=DirectoryIdentity(
                            "directory",
                            cleanup_root_anchor.uid,
                            cleanup_root_anchor.mode,
                            cleanup_root_anchor.device,
                            cleanup_root_anchor.inode,
                        ),
                        verified_at_phase="prepared",
                    ),
                },
                "objects": {},
                "rename_operations": [],
                "cleanup_outcomes": [],
                "cleanup_claims": [],
                "restore_status": "restore_not_attempted",
                "restored_target_identity": None,
                "restored_manifest_sha256": None,
                "restored_at_phase": None,
            }
            _record_object_state(
                receipt_payload,
                "target",
                display_name=target.name,
                parent_anchor="target_parent",
                expected_identity=_identity_payload(target_identity) if target_identity else None,
                current_identity=_identity_payload(target_identity) if target_identity else None,
            )
            _record_object_state(
                receipt_payload,
                "previous",
                display_name=previous.name if previous else None,
                parent_anchor="target_parent",
                expected_identity=_identity_payload(target_identity) if target_identity else None,
                current_identity=None,
            )
            _record_object_state(
                receipt_payload,
                "staging",
                display_name=staging.name,
                parent_anchor="target_parent",
                expected_identity=None,
                current_identity=None,
            )
            _record_object_state(
                receipt_payload,
                "backup",
                display_name=backup_path.name if backup_path else None,
                parent_anchor="backup_root",
                expected_identity=_identity_payload(target_identity) if target_identity else None,
                current_identity=None,
            )
            _record_object_state(
                receipt_payload,
                "quarantine",
                display_name=quarantine.name,
                parent_anchor="target_parent",
                expected_identity=None,
                current_identity=None,
            )
            _update_receipt_at(
                receipt_root_anchor.fd,
                receipt_name,
                receipt_payload,
                phase="prepared",
            )
            print(f"Recovery receipt: {receipt_path}", flush=True)

            if _entry_lstat_at(target_parent_anchor.fd, staging.name) is not None:
                raise UpdateError("staging destination already exists.")
            staging_owned = True
            copy_validated_tree_at(
                source,
                target_parent_anchor.fd,
                staging.name,
                source_root_fd=source_fd,
            )
            staged_manifest = build_tree_manifest_at(
                target_parent_anchor.fd,
                staging.name,
                "staging",
            )
            staging_identity = _capture_directory_identity_at(
                target_parent_anchor.fd,
                staging.name,
                "staging",
            )
            receipt_payload["root_identities"] = {
                "target": _identity_payload(target_identity) if target_identity else None,
                "staging": _identity_payload(staging_identity),
                "backup": None,
                "previous": None,
                "published": None,
                "restored": None,
                "quarantine": None,
            }
            _record_object_state(
                receipt_payload,
                "staging",
                display_name=staging.name,
                parent_anchor="target_parent",
                expected_identity=_identity_payload(staging_identity),
                current_identity=_identity_payload(staging_identity),
            )
            validate_skill_manifest(staged_manifest, "staging")
            verify_exact_manifest(source_manifest, staged_manifest, "staging")
            verify_approved_source_inventory(
                staged_manifest,
                approved_inventory,
                "staging",
            )
            _verify_directory_entry_identity(
                target_parent_anchor.fd,
                staging.name,
                staging_identity,
                "staging",
            )
            source_after_copy = (
                _manifest_from_stable_root_fd(source_fd, "source package after staging copy")
                if source_fd is not None
                else build_tree_manifest(source, "source package after staging copy")
            )
            verify_approved_inventory_identity(
                skill,
                approved_inventory,
                "during staging copy",
            )
            verify_exact_manifest(
                source_manifest,
                source_after_copy,
                "source package after staging copy",
            )
            if source_fd is not None:
                validate_owned_non_writable_manifest_fd(
                    source_fd,
                    source_after_copy,
                    "source package after staging copy",
                )
            else:
                validate_owned_non_writable_tree(
                    source,
                    source_after_copy,
                    "source package after staging copy",
                )
            target_before_backup = _manifest_at_if_present(
                target_parent_anchor.fd,
                target.name,
                "target immediately before replacement",
            )
            verify_exact_manifest(
                target_manifest,
                target_before_backup,
                "target immediately before replacement",
            )
            _update_receipt_at(
                receipt_root_anchor.fd,
                receipt_name,
                receipt_payload,
                phase="staging_verified",
            )

            if target_manifest:
                assert backup_candidate is not None
                assert backup_path is not None
                assert previous is not None
                _verify_target_lock(target_lock)
                _verify_root_anchor(
                    target_plan.authorized_root,
                    target_lock.authorized_root_fd,
                    target_lock.identity,
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    target_parent_anchor,
                    "target parent",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    receipt_root_anchor,
                    "update receipt directory",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    backup_root_anchor,
                    "backup root",
                )
                copy_validated_tree_between_fds(
                    target_parent_anchor.fd,
                    target.name,
                    backup_root_anchor.fd,
                    backup_candidate.name,
                )
                backup_candidate_identity = _capture_directory_identity_at(
                    backup_root_anchor.fd,
                    backup_candidate.name,
                    "backup candidate",
                )
                backup_manifest = build_tree_manifest_at(
                    backup_root_anchor.fd,
                    backup_candidate.name,
                    "backup",
                )
                verify_exact_manifest(target_manifest, backup_manifest, "backup")
                _verify_directory_entry_identity(
                    backup_root_anchor.fd,
                    backup_candidate.name,
                    backup_candidate_identity,
                    "backup candidate",
                )
                receipt_payload["root_identities"]["backup"] = _identity_payload(
                    backup_candidate_identity
                )
                _record_object_state(
                    receipt_payload,
                    "backup",
                    display_name=backup_path.name,
                    parent_anchor="backup_root",
                    expected_identity=_identity_payload(backup_candidate_identity),
                    current_identity=_identity_payload(backup_candidate_identity),
                )
                try:
                    backup_durable = _rename_for_transaction(
                        backup_root_anchor.fd,
                        backup_candidate.name,
                        backup_path.name,
                        receipt_payload,
                        parent_anchor="backup_root",
                    )
                except UpdateError as exc:
                    raise UpdateError(
                        "validated backup could not be finalized; active target was unchanged."
                    ) from exc
                if (
                    backup_durable.rename_committed is not True
                    or backup_durable.fsync_status != "completed"
                ):
                    raise UpdateError(
                        "validated backup finalization did not reach a durable known state; "
                        "active target was unchanged and all backup objects were retained."
                    )
                backup_final_identity = _capture_directory_identity_at(
                    backup_root_anchor.fd,
                    backup_path.name,
                    "validated backup",
                )
                if backup_final_identity != backup_candidate_identity:
                    raise UpdateError("validated backup identity changed during finalization.")
                receipt_payload["root_identities"]["backup"] = _identity_payload(
                    backup_final_identity
                )
                _record_object_state(
                    receipt_payload,
                    "backup",
                    display_name=backup_path.name,
                    parent_anchor="backup_root",
                    expected_identity=_identity_payload(backup_final_identity),
                    current_identity=_identity_payload(backup_final_identity),
                )
                _verify_directory_entry_identity(
                    backup_root_anchor.fd,
                    backup_path.name,
                    backup_final_identity,
                    "validated backup",
                )
                backup_candidate = None
                receipt_payload["backup_incomplete"] = None
                _update_receipt_at(
                    receipt_root_anchor.fd,
                    receipt_name,
                    receipt_payload,
                    phase="backup_ready",
                )

                target_before_move = build_tree_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    "target immediately before move",
                )
                if target_identity is None:
                    raise UpdateError("target root identity is unavailable before active move.")
                _verify_directory_entry_identity(
                    target_parent_anchor.fd,
                    target.name,
                    target_identity,
                    "target immediately before move",
                )
                verify_exact_manifest(
                    target_manifest,
                    target_before_move,
                    "target immediately before move",
                )
                validate_owned_non_writable_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    target_before_move,
                    "target immediately before move",
                    target_identity,
                )
                _verify_root_anchor(
                    target_plan.authorized_root,
                    target_lock.authorized_root_fd,
                    target_lock.identity,
                )
                _verify_target_lock(target_lock)
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    target_parent_anchor,
                    "target parent",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    receipt_root_anchor,
                    "update receipt directory",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    backup_root_anchor,
                    "backup root",
                )
                try:
                    active_move_durable = _rename_for_transaction(
                        target_parent_anchor.fd,
                        target.name,
                        previous.name,
                        receipt_payload,
                        parent_anchor="target_parent",
                    )
                    _record_object_state(
                        receipt_payload,
                        "target",
                        display_name=target.name,
                        parent_anchor="target_parent",
                        expected_identity=_identity_payload(target_identity),
                        current_identity=active_move_durable.destination_identity_after
                        if active_move_durable.rename_committed in (True, "unknown")
                        else active_move_durable.source_identity_after,
                    )
                except UpdateError as exc:
                    raise UpdateError(
                        f"active target could not be prepared for replacement; "
                        f"validated backup retained: {backup_path}."
                    ) from exc
                if (
                    active_move_durable.rename_committed is not True
                    or active_move_durable.fsync_status != "completed"
                ):
                    recovery = _restore_previous_target_at(
                        target_parent_anchor.fd,
                        previous.name,
                        target.name,
                        target_manifest,
                        target_identity,
                        receipt_payload,
                        "active_target_move_recovery",
                        cleanup_fd=cleanup_root_anchor.fd,
                        cleanup_anchor="cleanup_root",
                    )
                    raise UpdateError(
                        "active target move completed but parent-directory durability "
                        f"could not be confirmed. {recovery} Backup retained: {backup_path}."
                    )
                previous_identity = _capture_directory_identity_at(
                    target_parent_anchor.fd,
                    previous.name,
                    "moved previous target",
                )
                receipt_payload["root_identities"]["previous"] = _identity_payload(
                    previous_identity
                )
                _record_object_state(
                    receipt_payload,
                    "previous",
                    display_name=previous.name,
                    parent_anchor="target_parent",
                    expected_identity=_identity_payload(target_identity),
                    current_identity=_identity_payload(previous_identity),
                )
                try:
                    if target_identity is not None and previous_identity != target_identity:
                        raise UpdateError("previous target root identity changed during move.")
                    moved_target_manifest = build_tree_manifest_at(
                        target_parent_anchor.fd,
                        previous.name,
                        "moved previous target",
                    )
                    verify_exact_manifest(
                        target_manifest,
                        moved_target_manifest,
                        "moved previous target",
                    )
                    validate_owned_non_writable_manifest_at(
                        target_parent_anchor.fd,
                        previous.name,
                        moved_target_manifest,
                        "moved previous target",
                        previous_identity,
                    )
                except UpdateError as exc:
                    if backup_root_anchor is None or backup_path is None:
                        raise UpdateError(
                            "target identity changed during move and no verified backup "
                            "is available for recovery."
                        ) from exc
                    try:
                        quarantined_durable = _rename_for_transaction(
                            target_parent_anchor.fd,
                            previous.name,
                            quarantine.name,
                            receipt_payload,
                            parent_anchor="target_parent",
                        )
                        if (
                            quarantined_durable.rename_committed is not True
                            or quarantined_durable.fsync_status != "completed"
                        ):
                            raise UpdateError(
                                "unverified moved target was quarantined but parent-directory "
                                "durability could not be confirmed."
                            )
                        recovery = _restore_verified_backup_at(
                            target_lock.authorized_root_fd,
                            target_parent_anchor,
                            backup_root_anchor,
                            backup_path,
                            target.name,
                            target_manifest,
                            target_identity,
                            receipt_payload,
                            "active_target_move_identity_recovery",
                            cleanup_fd=cleanup_root_anchor.fd,
                            cleanup_anchor="cleanup_root",
                        )
                    except UpdateError as restore_exc:
                        raise UpdateError(
                            "target identity changed during move; unverified previous "
                            f"target was not restored automatically: {restore_exc}"
                        ) from restore_exc
                    raise UpdateError(
                        f"target identity changed during move. {recovery}"
                    ) from exc
                try:
                    _update_receipt_at(
                        receipt_root_anchor.fd,
                        receipt_name,
                        receipt_payload,
                        phase="active_target_moved",
                    )
                except UpdateError as exc:
                    recovery = _restore_previous_target_at(
                        target_parent_anchor.fd,
                        previous.name,
                        target.name,
                        target_manifest,
                        target_identity,
                        receipt_payload,
                        "active_target_move_receipt_recovery",
                        cleanup_fd=cleanup_root_anchor.fd,
                        cleanup_anchor="cleanup_root",
                    )
                    raise UpdateError(
                        "recovery receipt could not record the moved active target. "
                        f"{recovery} Backup retained: {backup_path}."
                    ) from exc

            try:
                _verify_target_lock(target_lock)
                _verify_root_anchor(
                    target_plan.authorized_root,
                    target_lock.authorized_root_fd,
                    target_lock.identity,
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    target_parent_anchor,
                    "target parent",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    receipt_root_anchor,
                    "update receipt directory",
                )
                if backup_root_anchor is not None:
                    _verify_directory_anchor(
                        target_lock.authorized_root_fd,
                        backup_root_anchor,
                        "backup root",
                    )
                publish_durable = _rename_for_transaction(
                    target_parent_anchor.fd,
                    staging.name,
                    target.name,
                    receipt_payload,
                    parent_anchor="target_parent",
                )
                _record_object_state(
                    receipt_payload,
                    "staging",
                    display_name=staging.name,
                    parent_anchor="target_parent",
                    expected_identity=_identity_payload(staging_identity),
                    current_identity=publish_durable.source_identity_after,
                )
                staging_owned = publish_durable.rename_committed is False
                if (
                    publish_durable.rename_committed is not True
                    or publish_durable.fsync_status != "completed"
                ):
                    raise UpdateError(
                        "staging publish completed but parent-directory durability "
                        "could not be confirmed."
                    )
                published_identity = _capture_directory_identity_at(
                    target_parent_anchor.fd,
                    target.name,
                    "published target",
                )
                if published_identity != staging_identity:
                    raise UpdateError("published target root metadata changed during publish.")
                receipt_payload["root_identities"]["published"] = _identity_payload(
                    published_identity
                )
                _record_object_state(
                    receipt_payload,
                    "target",
                    display_name=target.name,
                    parent_anchor="target_parent",
                    expected_identity=_identity_payload(published_identity),
                    current_identity=_identity_payload(published_identity),
                )
                _update_receipt_at(
                    receipt_root_anchor.fd,
                    receipt_name,
                    receipt_payload,
                    phase="staging_published",
                )
            except UpdateError as exc:
                if (
                    not staging_owned
                    and _entry_lstat_at(target_parent_anchor.fd, target.name) is not None
                ):
                    try:
                        quarantine_durable = _rename_for_transaction(
                            target_parent_anchor.fd,
                            target.name,
                            quarantine.name,
                            receipt_payload,
                            parent_anchor="target_parent",
                        )
                        _require_durable_rename(
                            quarantine_durable,
                            "published target quarantine",
                        )
                    except UpdateError as quarantine_exc:
                        raise UpdateError(
                            "publishing staging failed and the active target could not "
                            "be quarantined; backup and previous target were retained."
                        ) from quarantine_exc
                    quarantine_identity = _capture_directory_identity_at(
                        target_parent_anchor.fd,
                        quarantine.name,
                        "quarantine",
                    )
                    if published_identity is not None and quarantine_identity != published_identity:
                        raise UpdateError("quarantine root identity changed during recovery.")
                    receipt_payload["root_identities"]["quarantine"] = _identity_payload(
                        quarantine_identity
                    )
                    _record_object_state(
                        receipt_payload,
                        "quarantine",
                        display_name=quarantine.name,
                        parent_anchor="target_parent",
                        expected_identity=_identity_payload(quarantine_identity),
                        current_identity=_identity_payload(quarantine_identity),
                    )
                recovery = _restore_previous_target_at(
                    target_parent_anchor.fd,
                    previous.name if previous is not None else None,
                    target.name,
                    target_manifest,
                    target_identity,
                    receipt_payload,
                    "staging_publish_recovery",
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                )
                raise UpdateError(
                    f"publishing staging failed: {exc}. {recovery} "
                    f"Backup retained: {backup_path or '(none)'}."
                ) from exc

            try:
                published_manifest = build_tree_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    "published target",
                )
                _verify_directory_entry_identity(
                    target_parent_anchor.fd,
                    target.name,
                    published_identity,
                    "published target",
                )
                validate_skill_manifest(published_manifest, "published target")
                verify_exact_manifest(
                    source_manifest,
                    published_manifest,
                    "published target",
                )
                verify_approved_source_inventory(
                    published_manifest,
                    approved_inventory,
                    "published target",
                )
                validate_owned_non_writable_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    published_manifest,
                    "published target",
                    published_identity,
                )
                _update_receipt_at(
                    receipt_root_anchor.fd,
                    receipt_name,
                    receipt_payload,
                    phase="published_verified",
                )
            except UpdateError as exc:
                try:
                    quarantine_durable = _rename_for_transaction(
                        target_parent_anchor.fd,
                        target.name,
                        quarantine.name,
                        receipt_payload,
                        parent_anchor="target_parent",
                    )
                    _require_durable_rename(
                        quarantine_durable,
                        "published target quarantine",
                    )
                except UpdateError as quarantine_exc:
                    raise UpdateError(
                        "post-publish verification failed and the active target could not "
                        "be quarantined; backup and previous target were retained."
                    ) from quarantine_exc
                quarantine_identity = _capture_directory_identity_at(
                    target_parent_anchor.fd,
                    quarantine.name,
                    "quarantine",
                )
                if published_identity is not None and quarantine_identity != published_identity:
                    raise UpdateError("quarantine root identity changed during recovery.")
                receipt_payload["root_identities"]["quarantine"] = _identity_payload(
                    quarantine_identity
                )
                _record_object_state(
                    receipt_payload,
                    "quarantine",
                    display_name=quarantine.name,
                    parent_anchor="target_parent",
                    expected_identity=_identity_payload(quarantine_identity),
                    current_identity=_identity_payload(quarantine_identity),
                )
                recovery = _restore_previous_target_at(
                    target_parent_anchor.fd,
                    previous.name if previous is not None else None,
                    target.name,
                    target_manifest,
                    target_identity,
                    receipt_payload,
                    "published_verification_recovery",
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                )
                raise UpdateError(
                    f"post-publish verification failed: {exc}. {recovery} "
                    f"Failed target retained: {quarantine}. "
                    f"Backup retained: {backup_path or '(none)'}."
                ) from exc

            if not target_manifest and backup_root_created:
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    backup_root_anchor,
                    "backup root",
                )
                if not _cleanup_outcome(
                    receipt_payload,
                    phase="backup_root_cleanup",
                    object_kind="backup_root",
                    name=target_plan.backup_root.name,
                    parent_fd=target_lock.authorized_root_fd,
                    parent_anchor="authorized_root",
                    expected_identity=_identity_payload(
                        DirectoryIdentity(
                            "directory",
                            backup_root_anchor.uid,
                            backup_root_anchor.mode,
                            backup_root_anchor.device,
                            backup_root_anchor.inode,
                        )
                    ),
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                ):
                    raise UpdateError("backup root cleanup failed after publish.")
                backup_root_detached = True
                receipt_payload["backup_root_disposition"] = "retained_by_security_policy"
                backup_anchor_record = receipt_payload["directory_anchors"].get("backup_root")
                if isinstance(backup_anchor_record, dict):
                    backup_anchor_record["removed_at_phase"] = "published_verified"
            if previous is not None:
                if not _cleanup_outcome(
                    receipt_payload,
                    phase="previous_cleanup",
                    object_kind="previous",
                    name=previous.name,
                    parent_fd=target_parent_anchor.fd,
                    parent_anchor="target_parent",
                    expected_identity=_expected_object_identity(receipt_payload, "previous"),
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                ):
                    raise UpdateError(
                        "previous cleanup failed; active target remains available but "
                        "the transaction is a manual-only failure."
                    )
                previous_cleanup_completed = True
            if cleanup_root_anchor is not None:
                # The cleanup namespace is a retained quarantine.  It may contain
                # claimed previous/staging/backup objects and must never be
                # removed automatically after the final identity check.
                receipt_payload["cleanup_policy"] = "claim_and_retain_no_final_delete"
                receipt_payload["cleanup_root_retained"] = True
            try:
                _verify_target_lock(target_lock)
                _verify_root_anchor(
                    target_plan.authorized_root,
                    target_lock.authorized_root_fd,
                    target_lock.identity,
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    target_parent_anchor,
                    "target parent",
                )
                _verify_directory_anchor(
                    target_lock.authorized_root_fd,
                    receipt_root_anchor,
                    "update receipt directory",
                )
                if backup_root_anchor is not None and not backup_root_detached:
                    _verify_directory_anchor(
                        target_lock.authorized_root_fd,
                        backup_root_anchor,
                        "backup root",
                    )
                if published_identity is None:
                    raise UpdateError("verified output directory handle is unavailable before completion.")
                final_published_manifest = build_tree_manifest_at(
                    target_parent_anchor.fd,
                    target.name,
                    "final published target",
                )
                verify_exact_manifest(
                    source_manifest,
                    final_published_manifest,
                    "final published target",
                )
                _verify_directory_entry_identity(
                    target_parent_anchor.fd,
                    target.name,
                    published_identity,
                    "final published target",
                )
                _update_receipt_at(
                    receipt_root_anchor.fd,
                    receipt_name,
                    receipt_payload,
                    phase="complete",
                    status="complete",
                )
            except UpdateError as exc:
                receipt_payload["phase"] = "complete_receipt_unpersisted"
                receipt_payload["status"] = "failed"
                receipt_payload["recovery_authority"] = "manual_only"
                try:
                    quarantine_durable = _rename_for_transaction(
                        target_parent_anchor.fd,
                        target.name,
                        quarantine.name,
                        receipt_payload,
                        parent_anchor="target_parent",
                    )
                    _require_durable_rename(
                        quarantine_durable,
                        "published target quarantine during completion recovery",
                    )
                    quarantine_identity = _capture_directory_identity_at(
                        target_parent_anchor.fd,
                        quarantine.name,
                        "quarantine",
                    )
                    if published_identity is not None and quarantine_identity != published_identity:
                        raise UpdateError("quarantine root identity changed during completion recovery.")
                    receipt_payload["root_identities"]["quarantine"] = _identity_payload(
                        quarantine_identity
                    )
                    if previous is not None and not previous_cleanup_completed:
                        recovery = _restore_previous_target_at(
                            target_parent_anchor.fd,
                            previous.name,
                            target.name,
                            target_manifest,
                            target_identity,
                            receipt_payload,
                            "complete_receipt_recovery",
                            cleanup_fd=cleanup_root_anchor.fd,
                            cleanup_anchor="cleanup_root",
                        )
                    elif backup_path is not None and backup_root_anchor is not None:
                        recovery = _restore_verified_backup_at(
                            target_lock.authorized_root_fd,
                            target_parent_anchor,
                            backup_root_anchor,
                            backup_path,
                            target.name,
                            target_manifest,
                            target_identity,
                            receipt_payload,
                            "complete_receipt_backup_recovery",
                            cleanup_fd=cleanup_root_anchor.fd,
                            cleanup_anchor="cleanup_root",
                        )
                    else:
                        recovery = (
                            "No previous or verified backup was available; the quarantined "
                            "target requires manual inspection."
                        )
                except UpdateError as recovery_exc:
                    raise UpdateError(
                        "completion receipt failed after publish; the new active target "
                        f"could not be quarantined or previous target restored: {recovery_exc}"
                    ) from recovery_exc
                raise UpdateError(
                    "completion receipt failed after publish; new target quarantined. "
                    f"{recovery} Backup retained: {backup_path or '(none)'}."
                ) from exc
        except Exception as exc:
            cleanup_failed = any(
                isinstance(outcome, dict)
                and outcome.get("attempted") is True
                and outcome.get("completed") is False
                for outcome in receipt_payload.get("cleanup_outcomes", [])
            ) if isinstance(receipt_payload, dict) else False
            if (
                staging_owned
                and staging is not None
                and target_parent_anchor is not None
                and _entry_lstat_at(target_parent_anchor.fd, staging.name) is not None
            ):
                cleanup_failed = not _cleanup_outcome(
                    receipt_payload,
                    phase="staging_cleanup",
                    object_kind="staging",
                    name=staging.name,
                    parent_fd=target_parent_anchor.fd,
                    parent_anchor="target_parent",
                    expected_identity=_expected_object_identity(receipt_payload, "staging"),
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                ) or cleanup_failed
            if (
                backup_candidate is not None
                and backup_root_anchor is not None
                and _entry_lstat_at(
                    backup_root_anchor.fd,
                    backup_candidate.name,
                )
                is not None
            ):
                cleanup_failed = not _cleanup_outcome(
                    receipt_payload,
                    phase="backup_candidate_cleanup",
                    object_kind="backup_candidate",
                    name=backup_candidate.name,
                    parent_fd=backup_root_anchor.fd,
                    parent_anchor="backup_root",
                    expected_identity=_expected_object_identity(receipt_payload, "backup"),
                    cleanup_fd=cleanup_root_anchor.fd,
                    cleanup_anchor="cleanup_root",
                ) or cleanup_failed
            if (
                backup_root_created
                and backup_root_anchor is not None
                and cleanup_root_anchor is not None
            ):
                try:
                    if not os.listdir(backup_root_anchor.fd):
                        _verify_directory_anchor(
                            target_lock.authorized_root_fd,
                            backup_root_anchor,
                            "backup root",
                        )
                        cleanup_failed = not _cleanup_outcome(
                            receipt_payload,
                            phase="backup_root_cleanup",
                            object_kind="backup_root",
                            name=target_plan.backup_root.name,
                            parent_fd=target_lock.authorized_root_fd,
                            parent_anchor="authorized_root",
                            expected_identity=_identity_payload(
                                DirectoryIdentity(
                                    "directory",
                                    backup_root_anchor.uid,
                                    backup_root_anchor.mode,
                                    backup_root_anchor.device,
                                    backup_root_anchor.inode,
                                )
                            ),
                            cleanup_fd=cleanup_root_anchor.fd,
                            cleanup_anchor="cleanup_root",
                        ) or cleanup_failed
                        backup_root_detached = not cleanup_failed
                except (OSError, UpdateError):
                    cleanup_failed = True
                    receipt_payload.setdefault("cleanup_outcomes", []).append(
                        {
                            "phase": "backup_root_cleanup",
                            "object_kind": "backup_root",
                            "name": target_plan.backup_root.name,
                            "parent_anchor": "authorized_root",
                            "attempted": True,
                            "completed": False,
                            "failure_type": "anchor_or_enumeration_failure",
                            "failure_message": "backup root could not be safely inspected for cleanup.",
                            "object_identity": _entry_identity_payload(
                                _entry_lstat_at(
                                    target_lock.authorized_root_fd,
                                    target_plan.backup_root.name,
                                )
                            ),
                        }
                    )
            if (
                receipt_root_anchor is not None
                and receipt_name is not None
                and receipt_payload is not None
            ):
                displayed_receipt_root = _lstat(receipt_root)
                if (
                    displayed_receipt_root is None
                    or not _identity_matches(
                        displayed_receipt_root,
                        _directory_identity(
                            os.fstat(receipt_root_anchor.fd),
                            "update receipt directory",
                        ),
                    )
                ):
                    receipt_payload["receipt_root"] = None
                    receipt_payload["receipt_root_anchor_replaced"] = True
                failure_phase = "cleanup_failed" if cleanup_failed else str(
                    receipt_payload.get("phase", "prepared")
                )
                if failure_phase == "complete":
                    failure_phase = "complete_receipt_unpersisted"
                receipt_persisted = _persist_failure_receipt(
                    receipt_root_anchor.fd,
                    receipt_name,
                    receipt_payload,
                    phase=failure_phase,
                    error=exc,
                    parent_fds={
                        "authorized_root": target_lock.authorized_root_fd,
                        "target_parent": target_parent_anchor.fd,
                        "backup_root": backup_root_anchor.fd if backup_root_anchor else -1,
                    },
                )
                if receipt_persisted and receipt_payload.get("receipt_root"):
                    print(f"Recovery receipt: {receipt_path}")
                elif receipt_persisted:
                    print("Recovery receipt: persisted through the original anchored FD; display path is stale.")
                else:
                    print("Recovery receipt: unavailable; anchored persistence failed.")
            else:
                print("Recovery receipt: unavailable; failure occurred before receipt creation.")
            print("Recovery authority: manual_only; inspect recorded paths before retrying.")
            raise
        finally:
            if cleanup_root_anchor is not None:
                os.close(cleanup_root_anchor.fd)
            if backup_root_anchor is not None:
                os.close(backup_root_anchor.fd)
            if receipt_root_anchor is not None:
                os.close(receipt_root_anchor.fd)
            if target_parent_anchor is not None:
                os.close(target_parent_anchor.fd)

    return backup_path


def _apply_update(
    target_plan: TargetPlan,
    skill: str,
    source: Path,
    source_manifest: dict[str, ManifestEntry],
    target_manifest: dict[str, ManifestEntry],
    approved_inventory: ApprovedInventory,
) -> Path | None:
    """Apply using one stable source-root FD for the whole transaction."""
    source_fd = _open_stable_directory_path(source, "source package")
    try:
        return _apply_update_with_source_fd(
            target_plan,
            skill,
            source,
            source_manifest,
            target_manifest,
            approved_inventory,
            source_fd=source_fd,
        )
    finally:
        os.close(source_fd)


def update_skill(
    target_plan: TargetPlan,
    skill: str,
    apply: bool,
    allow_remove_extra_files: bool = False,
) -> None:
    source_lexical = source_skill_path(skill)
    source_stat = _lstat(source_lexical)
    if source_stat is not None and stat.S_ISLNK(source_stat.st_mode):
        raise UpdateError("source skill root must not be a symbolic link.")
    source = source_lexical.resolve(strict=False)
    target = target_plan.target
    _require_within(target, target_plan.authorized_root, "target")
    _require_within(target_plan.backup_root, target_plan.authorized_root, "backup root")
    _validate_existing_ancestor_chain(
        target_plan.authorized_root,
        target,
        "target path",
    )
    _validate_existing_ancestor_chain(
        target_plan.authorized_root,
        target_plan.backup_root,
        "backup path",
    )

    if apply:
        _reject_source_mutation_overlap(source, target_plan)
        package_control_root = PACKAGE_ROOT.resolve(strict=True)
        skills_control_root = SKILLS_ROOT.resolve(strict=True)
        source_control_root = (
            package_control_root
            if path_is_relative_to(source, package_control_root)
            else skills_control_root
        )
        _validate_owned_non_writable_ancestor_chain(
            source_control_root,
            source,
            "source package path",
        )
        _validate_owned_non_writable_ancestor_chain(
            package_control_root,
            PACKAGE_MANIFEST_PATH.parent.resolve(strict=True),
            "package manifest path",
        )
        _require_owned_non_writable_file(
            PACKAGE_MANIFEST_PATH,
            "package manifest",
        )

    approved_inventory = load_approved_source_inventory(skill)
    source_manifest = build_tree_manifest(source, "source package")
    validate_skill_manifest(source_manifest, "source package")
    verify_approved_source_inventory(
        source_manifest,
        approved_inventory,
        "source package",
    )
    if apply:
        validate_owned_non_writable_tree(source, source_manifest, "source package")
    target_manifest = _manifest_if_present(target, "target skill")
    if target_manifest:
        validate_skill_manifest(target_manifest, "target skill")
    added, replaced, target_only = compare_manifests(source_manifest, target_manifest)

    print(f"Skill: {skill}")
    print(f"Source: {source}")
    print(f"Target mode: {target_plan.label}")
    print(f"Target: {target}", flush=True)
    print(f"Backup root: {target_plan.backup_root}")
    print(f"Approved inventory SHA-256: {approved_inventory.inventory_sha256}")
    print(f"Add: {_format_paths(added)}")
    print(f"Replace: {_format_paths(replaced)}")
    print(f"Target-only: {_format_paths(target_only)}")

    if not apply:
        print("Mode: dry-run")
        print("Plan: validate source, create same-filesystem staging, retain a backup,")
        print("      replace the active target, then verify the published manifest.")
        if target_only:
            print("Apply blocker: target-only files require --allow-remove-extra-files.")
        print("Residual risks: recovery is receipt-guided, not a filesystem transaction.")
        print("No files were changed. Re-run with --apply to update.")
        return

    if target_only and not allow_remove_extra_files:
        raise UpdateError(
            "target-only files block apply; review them and explicitly pass "
            "--allow-remove-extra-files to replace the active target."
        )

    print("Mode: apply")
    backup_path = _apply_update(
        target_plan,
        skill,
        source,
        source_manifest,
        target_manifest,
        approved_inventory,
    )

    print("Update complete.")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
        print(f"Backup retained: {backup_path}")
        print(f"Rollback source: {backup_path}")
    else:
        print("Backup: target did not exist; no previous version was available.")
    if target_plan.installed_project_root is not None:
        print(
            "Installed-project check: run "
            ".agents/skills/long-horizon-engineering/scripts/"
            "check_skill_package.py --installed from the target root."
        )
    else:
        print(
            "Direct skill directory check: run the installed skill's doctor.py or "
            "package check from the active Codex installation as appropriate."
        )
    print("Source-package checks should be run from the skill source repository.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update installed skills from this package. Defaults to a read-only "
            "plan. Apply uses validated staging, retained backup, replacement, "
            "and post-publish manifest verification without network access."
        )
    )
    parser.add_argument(
        "--target-root",
        help="Target project root that contains or should contain .agents/skills.",
    )
    parser.add_argument(
        "--target-skill-dir",
        help=(
            "Direct path to an existing installed skill directory, such as "
            "~/.codex/skills/long-horizon-engineering. The directory basename "
            "must match --skill."
        ),
    )
    parser.add_argument(
        "--skill",
        action="append",
        choices=ALLOWED_SKILLS,
        help="Skill to inspect. Dry-run may inspect multiple skills.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply one update. Requires exactly one explicit --skill and one "
            "explicit target option."
        ),
    )
    parser.add_argument(
        "--allow-remove-extra-files",
        action="store_true",
        help=(
            "Permit apply to replace a target containing target-only files. "
            "Those files remain in the retained backup, not the active target."
        ),
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List skills that can be updated, then exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.list_skills:
        for skill in ALLOWED_SKILLS:
            print(skill)
        return

    skills = args.skill or list(ALLOWED_SKILLS)
    if args.apply and (not args.skill or len(skills) != 1):
        raise SystemExit("ERROR: --apply requires exactly one explicit --skill.")
    if args.allow_remove_extra_files and not args.apply:
        raise SystemExit("ERROR: --allow-remove-extra-files is only valid with --apply.")

    print("Safe skill update")
    if args.target_root:
        print(
            f"Target root: {_normalize_explicit_path(args.target_root, '--target-root')}",
            flush=True,
        )
    elif args.target_skill_dir:
        print(
            "Target skill dir: "
            f"{_normalize_explicit_path(args.target_skill_dir, '--target-skill-dir')}",
            flush=True,
        )
    else:
        print(f"Target root: {Path('.').resolve()} (default dry-run)", flush=True)

    for skill in skills:
        print()
        target_plan = resolve_target_plan(args, skill, args.apply)
        update_skill(
            target_plan,
            skill,
            args.apply,
            args.allow_remove_extra_files,
        )


if __name__ == "__main__":
    try:
        main()
    except UpdateError as exc:
        raise SystemExit(f"ERROR: {exc}") from None
