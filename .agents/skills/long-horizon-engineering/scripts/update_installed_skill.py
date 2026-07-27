#!/usr/bin/env python3
"""Update installed skills with staged replacement and retained backups."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PACKAGE_ROOT / ".agents" / "skills"
ALLOWED_SKILLS = ("long-horizon-engineering", "ai-video-production")
COPY_CHUNK_SIZE = 1024 * 1024


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


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def source_skill_path(skill: str) -> Path:
    return SKILLS_ROOT / skill


def target_skill_path(target_root: Path, skill: str) -> Path:
    return target_root / ".agents" / "skills" / skill


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


def _reject_explicit_symlink(path: Path, label: str) -> None:
    current = _lstat(path)
    if current is not None and stat.S_ISLNK(current.st_mode):
        raise SystemExit(f"ERROR: {label} must not be a symbolic link: {path}")


def _normalize_explicit_path(value: str | Path, label: str) -> Path:
    lexical = _absolute_lexical_path(value)
    _reject_explicit_symlink(lexical, label)
    return lexical.resolve(strict=False)


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
        if not path_is_relative_to(target, authorized_root):
            raise SystemExit("ERROR: direct skill target escapes its installation root.")
        if not path_is_relative_to(backup_root, authorized_root):
            raise SystemExit("ERROR: direct skill backup root escapes its installation root.")
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
    if not path_is_relative_to(target, target_root):
        raise SystemExit("ERROR: resolved target escapes --target-root.")
    if not path_is_relative_to(backup_root, target_root):
        raise SystemExit("ERROR: resolved backup root escapes --target-root.")
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
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
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
                manifest[relative_text] = ManifestEntry("directory", 0, "")
                visit(Path(entry.path), relative)
            else:
                manifest[relative_text] = ManifestEntry(
                    "file",
                    entry_stat.st_size,
                    _hash_regular_file(Path(entry.path), entry_stat, relative_text),
                )

    visit(root, Path())
    return manifest


def validate_skill_manifest(
    manifest: dict[str, ManifestEntry],
    label: str,
) -> None:
    if not manifest:
        raise UpdateError(f"{label} is empty.")
    if manifest.get("SKILL.md", ManifestEntry("", 0, "")).kind != "file":
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


def _copy_regular_file(
    source: Path,
    destination: Path,
    source_stat: os.stat_result,
    relative_path: str,
) -> None:
    source_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        source_flags |= os.O_NOFOLLOW
    try:
        source_fd = os.open(source, source_flags)
        destination_fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
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
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
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
                except OSError as exc:
                    raise UpdateError(
                        f"unable to create staged directory: {relative_text}"
                    ) from exc
                copy_directory(Path(entry.path), destination_entry, relative)
                os.chmod(destination_entry, stat.S_IMODE(entry_stat.st_mode))
            else:
                _copy_regular_file(
                    Path(entry.path),
                    destination_entry,
                    entry_stat,
                    relative_text,
                )

    copy_directory(source, destination, Path())
    os.chmod(destination, stat.S_IMODE(source_stat.st_mode))


def _unique_path(parent: Path, stem: str) -> Path:
    return parent / f"{stem}-{timestamp()}-{uuid.uuid4().hex[:12]}"


def _remove_owned_directory(path: Path) -> None:
    current = _lstat(path)
    if current is None:
        return
    if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
        raise UpdateError("refusing to clean an unexpected staging object.")
    shutil.rmtree(path)


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


def _restore_previous_target(
    previous: Path | None,
    target: Path,
    original_manifest: dict[str, ManifestEntry],
) -> str:
    if previous is None:
        return "No previous target existed; the active target remains absent."
    try:
        previous.rename(target)
        restored = build_tree_manifest(target, "restored target")
        verify_exact_manifest(original_manifest, restored, "restored target")
    except (OSError, UpdateError) as exc:
        raise UpdateError(
            "best-effort recovery failed; retained backup and previous target require "
            "manual inspection."
        ) from exc
    return "Previous target restored and its manifest verified."


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

    source_manifest = build_tree_manifest(source, "source package")
    validate_skill_manifest(source_manifest, "source package")
    target_manifest = _manifest_if_present(target, "target skill")
    if target_manifest:
        validate_skill_manifest(target_manifest, "target skill")
    added, replaced, target_only = compare_manifests(source_manifest, target_manifest)

    print(f"Skill: {skill}")
    print(f"Source: {source}")
    print(f"Target mode: {target_plan.label}")
    print(f"Target: {target}", flush=True)
    print(f"Backup root: {target_plan.backup_root}")
    print(f"Add: {_format_paths(added)}")
    print(f"Replace: {_format_paths(replaced)}")
    print(f"Target-only: {_format_paths(target_only)}")

    if not apply:
        print("Mode: dry-run")
        print("Plan: validate source, create same-filesystem staging, retain a backup,")
        print("      replace the active target, then verify the published manifest.")
        if target_only:
            print("Apply blocker: target-only files require --allow-remove-extra-files.")
        print("Residual risks: best-effort recovery is not a filesystem transaction.")
        print("No files were changed. Re-run with --apply to update.")
        return

    if target_only and not allow_remove_extra_files:
        raise UpdateError(
            "target-only files block apply; review them and explicitly pass "
            "--allow-remove-extra-files to replace the active target."
        )

    print("Mode: apply")
    print("Pre-upgrade safety audit:", flush=True)
    run_pre_upgrade_safety_audit()
    _ensure_directory(target.parent, target_plan.authorized_root, "target parent")

    staging = _unique_path(target.parent, f".{skill}.staging")
    previous: Path | None = None
    backup_path: Path | None = None
    backup_candidate: Path | None = None
    quarantine: Path | None = None
    staging_owned = False

    try:
        if _lstat(staging) is not None:
            raise UpdateError("staging destination already exists.")
        staging_owned = True
        copy_validated_tree(source, staging)
        staged_manifest = build_tree_manifest(staging, "staging")
        validate_skill_manifest(staged_manifest, "staging")
        current_source_manifest = build_tree_manifest(source, "source package")
        validate_skill_manifest(current_source_manifest, "source package")
        verify_exact_manifest(current_source_manifest, staged_manifest, "staging")
        source_manifest = current_source_manifest

        if target_manifest:
            _ensure_directory(
                target_plan.backup_root,
                target_plan.authorized_root,
                "backup root",
            )
            backup_candidate = _unique_path(
                target_plan.backup_root,
                f".{skill}.backup-incomplete",
            )
            copy_validated_tree(target, backup_candidate)
            backup_manifest = build_tree_manifest(backup_candidate, "backup")
            verify_exact_manifest(target_manifest, backup_manifest, "backup")
            backup_path = _unique_path(target_plan.backup_root, skill)
            try:
                backup_candidate.rename(backup_path)
            except OSError as exc:
                raise UpdateError(
                    "validated backup could not be finalized; active target was unchanged."
                ) from exc
            backup_candidate = None

            previous = _unique_path(target.parent, f".{skill}.previous")
            try:
                target.rename(previous)
            except OSError as exc:
                raise UpdateError(
                    f"active target could not be prepared for replacement; "
                    f"validated backup retained: {backup_path}."
                ) from exc

        try:
            staging.rename(target)
        except OSError as exc:
            recovery = _restore_previous_target(
                previous,
                target,
                target_manifest,
            )
            raise UpdateError(
                f"publishing staging failed. {recovery} "
                f"Backup retained: {backup_path or '(none)'}."
            ) from exc

        try:
            published_manifest = build_tree_manifest(target, "published target")
            validate_skill_manifest(published_manifest, "published target")
            verify_exact_manifest(source_manifest, published_manifest, "published target")
        except (OSError, UpdateError) as exc:
            quarantine = _unique_path(target.parent, f".{skill}.failed")
            try:
                target.rename(quarantine)
            except OSError as quarantine_exc:
                raise UpdateError(
                    "post-publish verification failed and the active target could not "
                    "be quarantined; backup and previous target were retained."
                ) from quarantine_exc
            recovery = _restore_previous_target(previous, target, target_manifest)
            raise UpdateError(
                f"post-publish verification failed. {recovery} "
                f"Failed target retained: {quarantine}. "
                f"Backup retained: {backup_path or '(none)'}."
            ) from exc

        if previous is not None:
            try:
                _remove_owned_directory(previous)
            except (OSError, UpdateError):
                print(f"Warning: prior target also retained at {previous}.")
    except Exception:
        if staging_owned and _lstat(staging) is not None:
            try:
                _remove_owned_directory(staging)
            except (OSError, UpdateError):
                pass
        if backup_candidate is not None and _lstat(backup_candidate) is not None:
            try:
                _remove_owned_directory(backup_candidate)
            except (OSError, UpdateError):
                pass
        raise

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
