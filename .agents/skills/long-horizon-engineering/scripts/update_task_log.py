#!/usr/bin/env python3
"""Preview or explicitly append a completed task entry inside a project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


CONFIRM_TOKEN = "WRITE_TASK_LOG"
HEADER = """# Task Log

This file records completed engineering tasks in a concise, resumable format.

Do not store secrets, private client data, legal evidence, family information,
API keys, tokens, credentials, or other sensitive personal data here.

## Entries
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview a task-log entry; writing is explicit and path-bounded."
    )
    parser.add_argument("--title", required=True, help="Short completed task title.")
    parser.add_argument("--summary", required=True, help="Brief summary of the change.")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Changed file path. Repeat for multiple files.",
    )
    parser.add_argument(
        "--verification",
        action="append",
        default=[],
        help="Verification command and result. Repeat for multiple checks.",
    )
    parser.add_argument("--notes", default="", help="Optional risk, note, or follow-up.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Allow a write after all path guards and --confirm succeed.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Typed confirmation token required with --apply: {CONFIRM_TOKEN}.",
    )
    parser.add_argument(
        "--project-root",
        required=True,
        type=Path,
        help="Existing project root that must contain --target-file.",
    )
    parser.add_argument(
        "--target-file",
        required=True,
        type=Path,
        help="Explicit project-relative Markdown target below docs/.",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        parser.error(f"--apply requires --confirm {CONFIRM_TOKEN}")
    if not args.apply and args.confirm is not None:
        parser.error("--confirm requires --apply")
    return args


def ensure_task_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER.rstrip() + "\n", encoding="utf-8")


def bullet_list(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return [f"- {fallback}\n"]
    return [f"- {item}\n" for item in cleaned]


def append_entry(path: Path, args: argparse.Namespace) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(build_entry(args))


def build_entry(args: argparse.Namespace) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    notes = args.notes.strip() or "None."
    lines = [
        f"\n### {timestamp} - {args.title.strip()}\n\n",
        "**Summary**\n\n",
        f"- {args.summary.strip()}\n\n",
        "**Files**\n\n",
        *bullet_list(args.file, "No files recorded."),
        "\n**Verification**\n\n",
        *bullet_list(args.verification, "No verification recorded."),
        "\n**Risks / Notes**\n\n",
        f"- {notes}\n",
    ]
    return "".join(lines)


def reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")


def resolve_target(project_root: Path, target_file: Path) -> Path:
    if target_file.is_absolute() or ".." in target_file.parts:
        raise ValueError("--target-file must be a relative path without '..'")
    if not target_file.parts or target_file.parts[0] != "docs" or target_file.suffix != ".md":
        raise ValueError("--target-file must be a Markdown file below docs/")
    if any(part in {".git", ".agents", ".codex"} for part in target_file.parts):
        raise ValueError("--target-file must not target repository control or skill paths")

    root = project_root.expanduser().absolute()
    if not root.is_dir():
        raise ValueError("--project-root must be an existing directory")
    reject_symlink(root, "--project-root")
    root_resolved = root.resolve()

    target = root / target_file
    for parent in (root, *target.parents):
        if parent == root.parent:
            break
        if parent.exists():
            reject_symlink(parent, "target path component")
    if target.exists():
        reject_symlink(target, "--target-file")
    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError("--target-file must resolve inside --project-root") from error
    return resolved


def main() -> None:
    args = parse_args()
    if not args.title.strip() or not args.summary.strip():
        raise SystemExit("--title and --summary must be non-empty.")

    try:
        target = resolve_target(args.project_root, args.target_file)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    entry = build_entry(args)
    if not args.apply:
        print("Preview only; nothing was written.")
        print(entry, end="")
        return

    print("Preview confirmed; writing the following entry:")
    print(entry, end="")
    ensure_task_log(target)
    append_entry(target, args)
    print(f"Appended task entry to {target}")


if __name__ == "__main__":
    main()
