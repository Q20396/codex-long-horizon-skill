#!/usr/bin/env python3
"""Read-only security and privacy audit for external skill candidates."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".bash",
    ".txt",
}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".cache",
}

GUARD_PATTERN = re.compile(
    r"\b(do not|don't|never|must not|should not|without|unless|approval|"
    r"approved|ask|asks|confirm|consent|dry-run|dry run|manual|"
    r"user-approved|customer-approved|redact|metadata-only|stop|refuse|"
    r"forbidden|no automatic|not automatically)\b",
    re.IGNORECASE,
)

PATTERNS = [
    (
        "high",
        "hardcoded_secret",
        re.compile(
            r"\b(api[_-]?key|secret|token|password|credential|private[_-]?key)"
            r"\b\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "high",
        "secret_or_private_upload",
        re.compile(
            r"\b(upload|send|share|publish|post|exfiltrate|sync)\b.{0,80}"
            r"\b(secret|token|credential|api key|\.env|private|client|legal|"
            r"financial|medical|identity|family|confidential)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "high",
        "dangerous_command",
        re.compile(
            r"\b(rm -rf|git reset --hard|chmod 777|mkfs|dd if=|"
            r"sudo\s+rm|shutdown|reboot)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "high",
        "curl_pipe_shell",
        re.compile(r"\b(curl|wget)\b.{0,120}\|\s*(sh|bash|zsh)\b", re.IGNORECASE),
    ),
    (
        "high",
        "bypass_safety",
        re.compile(
            r"\b(ignore|bypass|override|disable)\b.{0,80}"
            r"\b(system|safety|policy|instruction|approval|review)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "medium",
        "network_or_remote_call",
        re.compile(
            r"\b(requests\.(post|get|put)|fetch\(|axios\.|urllib\.request|"
            r"httpx\.|curl |wget |subprocess\.run\()",
            re.IGNORECASE,
        ),
    ),
    (
        "medium",
        "account_or_location_access",
        re.compile(
            r"\b(gmail|mailbox|google drive|dropbox|browser session|cookies|"
            r"gps|precise location|current location|oauth|login)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "medium",
        "auto_publish_or_deploy",
        re.compile(
            r"\b(auto[- ]?merge|push to main|deploy to production|auto[- ]?deploy|"
            r"publish automatically|post automatically)\b",
            re.IGNORECASE,
        ),
    ),
]


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def is_text_file(path: Path, max_file_bytes: int) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size <= max_file_bytes


def iter_candidate_files(root: Path, max_file_bytes: int) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file() and is_text_file(path, max_file_bytes):
            files.append(path)
    return sorted(files)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def context_guarded(lines: list[str], index: int) -> bool:
    start = max(0, index - 6)
    end = min(len(lines), index + 7)
    return bool(GUARD_PATTERN.search(" ".join(lines[start:end])))


def is_pattern_definition(lines: list[str], zero_based_index: int) -> bool:
    line = lines[zero_based_index].strip()
    start = max(0, zero_based_index - 4)
    context = "\n".join(lines[start : zero_based_index + 1])
    looks_like_pattern = (
        "PATTERNS" in context
        or "RISK_PATTERNS" in context
        or "re.compile" in context
    )
    looks_like_regex_line = (
        line.startswith(("r\"", "r'", "\"", "'", "re.compile(")) or "re.compile(" in line
    )
    return looks_like_pattern and looks_like_regex_line


def classify_line(path: Path, root: Path, index: int, line: str, lines: list[str]) -> list[dict]:
    findings = []
    stripped = line.strip()
    if not stripped:
        return findings
    if is_pattern_definition(lines, index - 1):
        return findings
    for severity, label, pattern in PATTERNS:
        if not pattern.search(stripped):
            continue
        guarded = bool(GUARD_PATTERN.search(stripped)) or context_guarded(lines, index - 1)
        effective_severity = "guarded" if guarded else severity
        findings.append(
            {
                "severity": effective_severity,
                "category": label,
                "file": relative(path, root),
                "line": index,
                "text": stripped[:240],
            }
        )
    return findings


def license_status(root: Path) -> str:
    candidates = [
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name.lower().startswith(("license", "copying"))
    ]
    if candidates:
        return ", ".join(sorted(candidates))
    return "missing_or_unknown"


def run_audit(root: Path, max_file_bytes: int) -> dict:
    if not root.exists():
        return {
            "ok": False,
            "decision_required": True,
            "errors": [f"Candidate root does not exist: {root}"],
            "summary": {},
            "findings": [],
        }
    if not root.is_dir():
        return {
            "ok": False,
            "decision_required": True,
            "errors": [f"Candidate root is not a directory: {root}"],
            "summary": {},
            "findings": [],
        }

    findings = []
    files = iter_candidate_files(root, max_file_bytes)
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            findings.extend(classify_line(path, root, index, line, lines))

    high = [finding for finding in findings if finding["severity"] == "high"]
    medium = [finding for finding in findings if finding["severity"] == "medium"]
    guarded = [finding for finding in findings if finding["severity"] == "guarded"]
    license_value = license_status(root)
    license_warning = license_value == "missing_or_unknown"
    decision_required = bool(high or medium or license_warning)
    summary = {
        "files_scanned": len(files),
        "license": license_value,
        "high": len(high),
        "medium": len(medium),
        "guarded": len(guarded),
        "recommendation": "customer_review_required" if decision_required else "no_material_risk_found",
    }
    return {
        "ok": not high,
        "decision_required": decision_required,
        "errors": [],
        "summary": summary,
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit for an external skill candidate already approved "
            "for local inspection. Makes no network calls and does not modify files."
        )
    )
    parser.add_argument(
        "candidate_root",
        help="Local path to the external skill or repository candidate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable results.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print guarded findings as well as unguarded findings.",
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit non-zero when unguarded high-severity findings are present.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=500_000,
        help="Skip text files larger than this many bytes. Default: 500000.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.candidate_root).expanduser().resolve()
    result = run_audit(root, args.max_file_bytes)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("External skill candidate safety audit")
        print(f"Candidate root: {root}")
        for key, value in result.get("summary", {}).items():
            print(f"{key}: {value}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"ERROR: {error}")
        printed = [
            finding
            for finding in result["findings"]
            if args.verbose or finding["severity"] != "guarded"
        ]
        for finding in printed:
            print(
                f"{finding['severity'].upper()}: "
                f"{finding['file']}:{finding['line']}: "
                f"{finding['category']}: {finding['text']}"
            )
        if result["decision_required"]:
            print("Customer decision required before adoption.")
        else:
            print("No material security or privacy risk found by this static scan.")
    if args.fail_on_high and not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
