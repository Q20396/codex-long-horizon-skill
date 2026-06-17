#!/usr/bin/env python3
"""Manage active and frozen skills with dry-run defaults."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_TARGET_ROOT = Path(".")
DEFAULT_USAGE_PATH = Path(".codex") / "skill-usage.json"
CORE_SKILLS = {"long-horizon-engineering"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def target_root(path: str) -> Path:
    return Path(path).expanduser().resolve()


def active_root(root: Path) -> Path:
    return root / ".agents" / "skills"


def frozen_root(root: Path) -> Path:
    return root / ".agents" / "skills.disabled"


def usage_path(root: Path, usage_file: str | None) -> Path:
    if usage_file:
        return Path(usage_file).expanduser().resolve()
    return root / DEFAULT_USAGE_PATH


def list_skill_dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(
        child.name
        for child in path.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )


def load_usage(path: Path) -> dict:
    if not path.is_file():
        return {"skills": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_usage(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def inactive_days(last_used: str | None) -> int | None:
    parsed = parse_time(last_used)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - parsed
    return max(delta.days, 0)


def print_skills(args: argparse.Namespace) -> None:
    root = target_root(args.target_root)
    usage = load_usage(usage_path(root, args.usage_file)).get("skills", {})
    print(f"Target root: {root}")
    print("Active skills:")
    for skill in list_skill_dirs(active_root(root)):
        item = usage.get(skill, {})
        last_used = item.get("last_used", "unknown")
        use_count = item.get("use_count", 0)
        print(f"- {skill} active last_used={last_used} use_count={use_count}")
    print("Frozen skills:")
    for skill in list_skill_dirs(frozen_root(root)):
        item = usage.get(skill, {})
        last_used = item.get("last_used", "unknown")
        use_count = item.get("use_count", 0)
        print(f"- {skill} frozen last_used={last_used} use_count={use_count}")


def record_usage(args: argparse.Namespace) -> None:
    root = target_root(args.target_root)
    path = usage_path(root, args.usage_file)
    payload = load_usage(path)
    skills = payload.setdefault("skills", {})
    item = skills.setdefault(args.skill, {})
    item["last_used"] = now_iso()
    item["use_count"] = int(item.get("use_count", 0)) + 1
    item["status"] = "active"
    save_usage(path, payload)
    print(f"Recorded non-sensitive usage for skill: {args.skill}")
    print(f"Usage file: {path}")


def suggest_freeze(args: argparse.Namespace) -> None:
    root = target_root(args.target_root)
    usage = load_usage(usage_path(root, args.usage_file)).get("skills", {})
    active = list_skill_dirs(active_root(root))
    print(f"Freeze suggestions for: {root}")
    print(f"Inactive day threshold: {args.inactive_days}")
    suggested = 0
    for skill in active:
        if skill in CORE_SKILLS:
            print(f"- {skill}: keep active (core safety/recovery skill)")
            continue
        item = usage.get(skill, {})
        days = inactive_days(item.get("last_used"))
        if days is None:
            if args.include_never_used:
                suggested += 1
                print(f"- {skill}: candidate (no non-sensitive usage record)")
            else:
                print(f"- {skill}: unknown (no usage record)")
            continue
        if days >= args.inactive_days:
            suggested += 1
            print(f"- {skill}: candidate (inactive {days} days)")
        else:
            print(f"- {skill}: keep active (used {days} days ago)")
    if suggested == 0:
        print("No freeze candidates found.")
    print("No files were changed. Freeze only after customer approval.")


def freeze_skill(args: argparse.Namespace) -> None:
    root = target_root(args.target_root)
    if args.skill in CORE_SKILLS:
        raise SystemExit(f"ERROR: refusing to freeze core skill: {args.skill}")
    source = active_root(root) / args.skill
    target = frozen_root(root) / args.skill
    print(f"Skill: {args.skill}")
    print(f"Source: {source}")
    print(f"Frozen target: {target}")
    if not source.is_dir():
        raise SystemExit(f"ERROR: active skill not found: {source}")
    if target.exists():
        raise SystemExit(f"ERROR: frozen target already exists: {target}")
    if not args.apply:
        print("Mode: dry-run")
        print("Plan: move active skill into .agents/skills.disabled.")
        print("No files were changed. Re-run with --apply after approval.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    print("Freeze complete. No files were deleted.")


def restore_skill(args: argparse.Namespace) -> None:
    root = target_root(args.target_root)
    source = frozen_root(root) / args.skill
    target = active_root(root) / args.skill
    print(f"Skill: {args.skill}")
    print(f"Frozen source: {source}")
    print(f"Active target: {target}")
    if not source.is_dir():
        raise SystemExit(f"ERROR: frozen skill not found: {source}")
    if target.exists():
        raise SystemExit(f"ERROR: active target already exists: {target}")
    if not args.apply:
        print("Mode: dry-run")
        print("Plan: move frozen skill back into .agents/skills.")
        print("No files were changed. Re-run with --apply after approval.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    print("Restore complete.")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target-root",
        default=str(DEFAULT_TARGET_ROOT),
        help="Project root containing .agents/skills. Default: current directory.",
    )
    parser.add_argument(
        "--usage-file",
        help="Optional path to non-sensitive skill usage JSON.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List, track, freeze, and restore skills with customer approval. "
            "Does not delete files, make network calls, or install remote skills."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List active and frozen skills.")
    add_common(list_parser)
    list_parser.set_defaults(func=print_skills)

    record_parser = subparsers.add_parser(
        "record-usage",
        help="Record non-sensitive usage metadata for a skill.",
    )
    add_common(record_parser)
    record_parser.add_argument("skill", help="Skill name to record.")
    record_parser.set_defaults(func=record_usage)

    suggest_parser = subparsers.add_parser(
        "suggest-freeze",
        help="Suggest optional skills that may be frozen.",
    )
    add_common(suggest_parser)
    suggest_parser.add_argument(
        "--inactive-days",
        type=int,
        default=30,
        help="Suggest skills unused for at least this many days. Default: 30.",
    )
    suggest_parser.add_argument(
        "--include-never-used",
        action="store_true",
        help="Treat active optional skills with no usage record as freeze candidates.",
    )
    suggest_parser.set_defaults(func=suggest_freeze)

    freeze_parser = subparsers.add_parser("freeze", help="Freeze an active skill.")
    add_common(freeze_parser)
    freeze_parser.add_argument("skill", help="Skill name to freeze.")
    freeze_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the freeze. Without this flag, only prints a plan.",
    )
    freeze_parser.set_defaults(func=freeze_skill)

    restore_parser = subparsers.add_parser("restore", help="Restore a frozen skill.")
    add_common(restore_parser)
    restore_parser.add_argument("skill", help="Skill name to restore.")
    restore_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the restore. Without this flag, only prints a plan.",
    )
    restore_parser.set_defaults(func=restore_skill)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
