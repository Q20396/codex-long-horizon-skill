#!/usr/bin/env python3
"""Run a read-only safety audit for packaged Codex skills."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[4]
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
}

NEGATION_OR_APPROVAL = re.compile(
    r"\b(do not|don't|never|must not|should not|without|unless|approval|"
    r"approved|ask|asks|requested|request|confirm|forbidden|refuse|"
    r"stop|pause|gate|dry-run|dry run|no automatic|not automatically|"
    r"not auto)\b",
    re.IGNORECASE,
)

RISK_PATTERNS = [
    ("auto_merge", re.compile(r"\b(auto[- ]?merge|merge to main)\b", re.IGNORECASE)),
    ("push_main", re.compile(r"\b(push to main|push .* main)\b", re.IGNORECASE)),
    ("auto_deploy", re.compile(r"\b(auto[- ]?deploy|deploy to production|production deploy)\b", re.IGNORECASE)),
    ("secret_upload", re.compile(r"\b(upload|send|share|publish|exfiltrate).{0,40}\b(secret|token|api key|credential|\.env)\b", re.IGNORECASE)),
    ("private_upload", re.compile(r"\b(upload|send|share|publish).{0,50}\b(private|client|legal|financial|medical|identity|family)\b", re.IGNORECASE)),
    ("destructive_shell", re.compile(r"\b(rm -rf|git reset --hard|chmod 777|mkfs|dd if=)\b", re.IGNORECASE)),
    ("curl_pipe_shell", re.compile(r"\b(curl|wget)\b.{0,80}\|\s*(sh|bash)\b", re.IGNORECASE)),
    ("ignore_instructions", re.compile(r"\b(ignore|bypass|override).{0,40}\b(previous|system|safety|policy|instruction)", re.IGNORECASE)),
]

REQUIRED_SAFETY_PHRASES = [
    "Do not auto-merge",
    "Do not store",
    "private",
    "approval",
]


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def iter_text_files(root: Path) -> list[Path]:
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(
        path
        for path in skills_root.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
    )


def load_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def check_front_matter(path: Path, root: Path) -> list[str]:
    text = load_text(path)
    if text is None:
        return []
    errors = []
    if not text.startswith("---\n"):
        errors.append(f"{relative(path, root)}: missing YAML front matter")
        return errors
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        errors.append(f"{relative(path, root)}: YAML front matter is not closed")
        return errors
    front_matter = parts[1]
    if "name:" not in front_matter:
        errors.append(f"{relative(path, root)}: front matter missing name")
    if "description:" not in front_matter:
        errors.append(f"{relative(path, root)}: front matter missing description")
    return errors


def line_is_guarded(line: str) -> bool:
    return bool(NEGATION_OR_APPROVAL.search(line))


def context_is_guarded(lines: list[str], index: int) -> bool:
    start = max(0, index - 8)
    end = min(len(lines), index + 9)
    context = " ".join(lines[start:end])
    return bool(NEGATION_OR_APPROVAL.search(context))


def is_scanner_definition(path: Path, line: str) -> bool:
    return path.name == "audit_skill_safety.py" and (
        "re.compile" in line
        or "RISK_PATTERNS" in line
        or "REQUIRED_SAFETY_PHRASES" in line
    )


def scan_risky_lines(path: Path, root: Path) -> tuple[list[str], list[str]]:
    if path.name in {"audit_skill_safety.py", "audit_external_skill_candidate.py"}:
        return [], []
    text = load_text(path)
    if text is None:
        return [], []
    errors = []
    warnings = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if is_scanner_definition(path, stripped):
            continue
        for label, pattern in RISK_PATTERNS:
            if not pattern.search(stripped):
                continue
            message = f"{relative(path, root)}:{index}: {label}: {stripped}"
            if line_is_guarded(stripped) or context_is_guarded(lines, index - 1):
                warnings.append(message)
            else:
                errors.append(message)
    return errors, warnings


def check_skill_safety_phrases(skill_md: Path, root: Path) -> list[str]:
    text = load_text(skill_md) or ""
    required = [
        phrase
        for phrase in REQUIRED_SAFETY_PHRASES
        if phrase != "Do not auto-merge" or skill_md.parent.name == "long-horizon-engineering"
    ]
    missing = [
        phrase
        for phrase in required
        if phrase.lower() not in text.lower()
    ]
    if not missing:
        return []
    return [
        f"{relative(skill_md, root)}: missing safety phrase or equivalent: {phrase}"
        for phrase in missing
    ]


def check_nested_agents(root: Path) -> list[str]:
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        return [".agents/skills directory not found"]
    return [
        f"Nested .agents path found: {relative(path, root)}"
        for path in skills_root.rglob(".agents")
    ]


def run_audit(root: Path) -> dict:
    errors = []
    warnings = []
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        errors.append(f"Missing skills directory: {relative(skills_root, root)}")
        return {"ok": False, "errors": errors, "warnings": warnings}

    errors.extend(check_nested_agents(root))
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        errors.append("No SKILL.md files found under .agents/skills")

    for skill_file in skill_files:
        errors.extend(check_front_matter(skill_file, root))
        errors.extend(check_skill_safety_phrases(skill_file, root))

    for path in iter_text_files(root):
        file_errors, file_warnings = scan_risky_lines(path, root)
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only safety audit for packaged Codex skills. Checks for "
            "unguarded risky instructions before installing or updating skills."
        )
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Repository root to audit. Defaults to the source package root.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable audit results.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print guarded risk-pattern warnings in human-readable output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    result = run_audit(root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.verbose:
            for warning in result["warnings"]:
                print(f"WARNING: {warning}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"ERROR: {error}")
        else:
            print("Skill safety audit passed.")
            if result["warnings"] and not args.verbose:
                print(
                    f"Guarded risk-pattern mentions: {len(result['warnings'])} "
                    "(use --verbose to inspect)."
                )
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
