#!/usr/bin/env python3
"""Safely update installed skills with dry-run and backup-first behavior."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PACKAGE_ROOT / ".agents" / "skills"
ALLOWED_SKILLS = ("long-horizon-engineering", "ai-video-production")


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def source_skill_path(skill: str) -> Path:
    return SKILLS_ROOT / skill


def target_skill_path(target_root: Path, skill: str) -> Path:
    return target_root / ".agents" / "skills" / skill


def backup_skill(target_root: Path, target: Path, skill: str) -> Path | None:
    if not target.exists():
        return None
    backup_dir = target_root / ".codex-skill-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{skill}-{timestamp()}"
    shutil.copytree(target, backup_path)
    return backup_path


def update_skill(target_root: Path, skill: str, apply: bool) -> None:
    source = source_skill_path(skill)
    target = target_skill_path(target_root, skill)

    if not source.is_dir():
        raise SystemExit(f"ERROR: source skill does not exist: {source}")

    print(f"Skill: {skill}")
    print(f"Source: {source}")
    print(f"Target: {target}")

    if not apply:
        print("Mode: dry-run")
        if target.exists():
            print("Plan: back up existing target, then copy package files over it.")
        else:
            print("Plan: create target skill directory and copy package files.")
        print("No files were changed. Re-run with --apply to update.")
        return

    print("Mode: apply")
    backup_path = backup_skill(target_root, target, skill)
    if backup_path:
        print(f"Backup: {backup_path}")
    else:
        print("Backup: target did not exist; no backup created.")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    print("Update complete.")
    print("Note: extra files already present in the target skill were not deleted.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update installed skill directories from this package. Defaults to "
            "dry-run. With --apply, backs up the existing target skill before "
            "copying package files. Does not make network calls or delete files."
        )
    )
    parser.add_argument(
        "--target-root",
        default=".",
        help="Target project root that contains or should contain .agents/skills.",
    )
    parser.add_argument(
        "--skill",
        action="append",
        choices=ALLOWED_SKILLS,
        help="Skill to update. May be provided multiple times. Defaults to both skills.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the update. Without this flag the script only prints a plan.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_root = Path(args.target_root).expanduser().resolve()
    skills = args.skill or list(ALLOWED_SKILLS)

    print("Safe skill update")
    print(f"Target root: {target_root}")
    for skill in skills:
        print()
        update_skill(target_root, skill, args.apply)


if __name__ == "__main__":
    main()
