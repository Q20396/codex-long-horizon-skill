#!/usr/bin/env python3
"""Safely update installed skills with dry-run and backup-first behavior."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, NamedTuple


PACKAGE_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PACKAGE_ROOT / ".agents" / "skills"
ALLOWED_SKILLS = ("long-horizon-engineering", "ai-video-production")


class TargetPlan(NamedTuple):
    label: str
    target: Path
    backup_root: Path
    installed_project_root: Path | None


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
        target = Path(args.target_skill_dir).expanduser().resolve()
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
        return TargetPlan(
            label="target skill directory",
            target=target,
            backup_root=backup_root_for_target_skill_dir(target),
            installed_project_root=None,
        )

    if args.target_root:
        target_root = Path(args.target_root).expanduser().resolve()
    elif apply:
        raise SystemExit("ERROR: --apply requires --target-root or --target-skill-dir.")
    else:
        target_root = Path(".").resolve()

    reject_duplicate_codex_agents_target(target_root, skill)
    return TargetPlan(
        label="target project root",
        target=target_skill_path(target_root, skill),
        backup_root=target_root / ".codex-skill-backups",
        installed_project_root=target_root,
    )


def backup_skill(backup_root: Path, target: Path, skill: str) -> Path | None:
    if not target.exists():
        return None
    backup_dir = backup_root
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{skill}-{timestamp()}"
    shutil.copytree(target, backup_path)
    return backup_path


def run_pre_upgrade_safety_audit() -> None:
    audit_script = (
        SKILLS_ROOT
        / "long-horizon-engineering"
        / "scripts"
        / "audit_skill_safety.py"
    )
    if not audit_script.is_file():
        raise SystemExit(f"ERROR: safety audit script not found: {audit_script}")
    result = subprocess.run(
        [sys.executable, str(audit_script), "--root", str(PACKAGE_ROOT)],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "ERROR: pre-upgrade skill safety audit failed. "
            "Review the audit findings before applying updates."
        )


def update_skill(target_plan: TargetPlan, skill: str, apply: bool) -> None:
    source = source_skill_path(skill)
    target = target_plan.target

    if not source.is_dir():
        raise SystemExit(f"ERROR: source skill does not exist: {source}")

    print(f"Skill: {skill}")
    print(f"Source: {source}")
    print(f"Target mode: {target_plan.label}")
    print(f"Target: {target}", flush=True)
    print(f"Backup root: {target_plan.backup_root}")

    if not apply:
        print("Mode: dry-run")
        if target.exists():
            print("Plan: back up existing target, then copy package files over it.")
        else:
            print("Plan: create target skill directory and copy package files.")
        print("Pre-upgrade safety audit will run before --apply copies files.")
        print("No files were changed. Re-run with --apply to update.")
        return

    print("Mode: apply")
    print("Pre-upgrade safety audit:", flush=True)
    run_pre_upgrade_safety_audit()
    backup_path = backup_skill(target_plan.backup_root, target, skill)
    if backup_path:
        print(f"Backup: {backup_path}")
    else:
        print("Backup: target did not exist; no backup created.")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    print("Update complete.")
    print("Note: extra files already present in the target skill were not deleted.")
    if target_plan.installed_project_root is not None:
        print("Installed-project check: run .agents/skills/long-horizon-engineering/scripts/check_skill_package.py --installed from the target root.")
    else:
        print("Direct skill directory check: run the installed skill's doctor.py or package check from the active Codex installation as appropriate.")
    print("Source-package checks such as trigger fixtures should be run from the skill source repository.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update installed skill directories from this package. Defaults to "
            "dry-run. With --apply, backs up the existing target skill before "
            "copying package files. Does not make network calls or delete files."
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
        help="Skill to update. May be provided multiple times. Defaults to both skills.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply the update. Requires exactly one --skill and either "
            "--target-root or --target-skill-dir. Without this flag the script "
            "only prints a plan."
        ),
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List skills that can be updated, then exit.",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    if args.list_skills:
        for skill in ALLOWED_SKILLS:
            print(skill)
        return

    skills = args.skill or list(ALLOWED_SKILLS)
    if args.apply and len(skills) != 1:
        raise SystemExit("ERROR: --apply requires exactly one explicit --skill.")

    print("Safe skill update")
    if args.target_root:
        print(f"Target root: {Path(args.target_root).expanduser().resolve()}", flush=True)
    elif args.target_skill_dir:
        print(f"Target skill dir: {Path(args.target_skill_dir).expanduser().resolve()}", flush=True)
    else:
        print(f"Target root: {Path('.').resolve()} (default dry-run)", flush=True)
    for skill in skills:
        print()
        target_plan = resolve_target_plan(args, skill, args.apply)
        update_skill(target_plan, skill, args.apply)


if __name__ == "__main__":
    main()
