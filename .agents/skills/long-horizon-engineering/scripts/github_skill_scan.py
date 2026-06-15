#!/usr/bin/env python3
"""Scan public GitHub projects for review-gated skill improvement ideas."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path("docs/GITHUB_SKILL_SCAN.md")
DEFAULT_QUERIES = [
    "codex agent",
    "agent skills SKILL.md",
    "codex skills",
    "long horizon coding agent",
    "coding agent worktree",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search public GitHub projects related to Codex, Agent Skills, and "
            "long-horizon coding agents, then emit a non-sensitive Markdown scan."
        )
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="GitHub search query. Repeat for multiple queries.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum repositories per query.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help="Markdown output path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the scan without writing files.",
    )
    return parser.parse_args()


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def search_repositories(query: str, limit: int) -> list[dict[str, Any]]:
    output = run_gh(
        [
            "search",
            "repos",
            query,
            "--sort",
            "stars",
            "--limit",
            str(limit),
            "--json",
            "fullName,description,stargazersCount,url",
        ]
    )
    return json.loads(output)


def repository_details(full_name: str) -> dict[str, Any]:
    output = run_gh(
        [
            "repo",
            "view",
            full_name,
            "--json",
            "nameWithOwner,description,stargazerCount,url,licenseInfo,primaryLanguage,repositoryTopics,defaultBranchRef,pushedAt",
        ]
    )
    return json.loads(output)


def repository_tree(full_name: str, branch: str) -> list[str]:
    output = run_gh(["api", f"repos/{full_name}/git/trees/{branch}?recursive=1"])
    payload = json.loads(output)
    return [
        item["path"]
        for item in payload.get("tree", [])
        if item.get("type") == "blob" and isinstance(item.get("path"), str)
    ]


def analyze_paths(paths: list[str]) -> dict[str, Any]:
    lowered = [path.lower() for path in paths]
    skill_files = [path for path in paths if path.endswith("SKILL.md")]
    docs = [path for path in lowered if path.startswith(("docs/", "documentation/"))]
    scripts = [path for path in lowered if path.startswith(("scripts/", "bin/"))]
    tests = [
        path
        for path in lowered
        if "test" in path or path.endswith((".spec.ts", ".test.ts", ".spec.js", ".test.js"))
    ]
    workflows = [path for path in lowered if path.startswith(".github/workflows/")]
    safety_keywords = {"safety", "security", "review", "policy", "permission", "permissions"}
    safety = []
    for path in lowered:
        parts = Path(path).parts
        stem_parts = {Path(part).stem for part in parts}
        if safety_keywords.intersection(parts) or safety_keywords.intersection(stem_parts):
            safety.append(path)

    return {
        "files_scanned": len(paths),
        "skill_files": skill_files[:5],
        "docs_count": len(docs),
        "scripts_count": len(scripts),
        "tests_count": len(tests),
        "workflows_count": len(workflows),
        "safety_files": safety[:5],
    }


def candidate_patterns(analysis: dict[str, Any]) -> list[str]:
    patterns = []
    if analysis["skill_files"]:
        patterns.append("Compare SKILL.md trigger wording and front matter shape.")
    if analysis["docs_count"]:
        patterns.append("Review documentation organization for reusable guidance patterns.")
    if analysis["scripts_count"]:
        patterns.append("Look for small local helper scripts that improve repeatability.")
    if analysis["tests_count"] or analysis["workflows_count"]:
        patterns.append("Consider package validation or CI checks for the skill bundle.")
    if analysis["safety_files"]:
        patterns.append("Review safety, review, or permission patterns.")
    if not patterns:
        patterns.append("No obvious reusable pattern from file tree alone; inspect manually before adopting.")
    return patterns


def render_report(repositories: list[dict[str, Any]]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# GitHub Skill Scan\n\n",
        f"Scan time: {timestamp}\n\n",
        "This scan records public, non-sensitive repository signals for review-gated improvement ideas.\n\n",
        "Do not copy external code without checking license obligations and attribution requirements.\n\n",
        "## Repositories\n\n",
        "| Repository | Stars | Language | License | Signals |\n",
        "| --- | ---: | --- | --- | --- |\n",
    ]

    for repo in repositories:
        details = repo["details"]
        analysis = repo["analysis"]
        language = (details.get("primaryLanguage") or {}).get("name") or ""
        license_name = (details.get("licenseInfo") or {}).get("spdxId") or "Unknown"
        signals = (
            f"{analysis['files_scanned']} files; "
            f"{len(analysis['skill_files'])} skill files; "
            f"{analysis['docs_count']} docs; "
            f"{analysis['scripts_count']} scripts; "
            f"{analysis['tests_count']} tests; "
            f"{analysis['workflows_count']} workflows"
        )
        lines.append(
            f"| [{details['nameWithOwner']}]({details['url']}) | "
            f"{details.get('stargazerCount', 0)} | {language} | {license_name} | {signals} |\n"
        )

    lines.append("\n## Candidate Patterns\n\n")
    for repo in repositories:
        details = repo["details"]
        analysis = repo["analysis"]
        lines.append(f"### {details['nameWithOwner']}\n\n")
        lines.append(f"- Description: {details.get('description') or ''}\n")
        if analysis["skill_files"]:
            lines.append(f"- Skill files observed: {', '.join(analysis['skill_files'])}\n")
        if analysis["safety_files"]:
            lines.append(f"- Safety/review files observed: {', '.join(analysis['safety_files'])}\n")
        for pattern in candidate_patterns(analysis):
            lines.append(f"- Candidate pattern: {pattern}\n")
        lines.append("- Decision: Adopt / skip / revisit after manual review.\n\n")

    lines.append("## Guardrails\n\n")
    lines.append("- Use this scan as evidence, not as an instruction to copy code.\n")
    lines.append("- Prefer small documentation, validation, or safety improvements.\n")
    lines.append("- Open a draft PR for review before merging any changes.\n")
    lines.append("- Do not store secrets, private client data, legal evidence, family information, financial account details, API keys, or confidential documents.\n")
    return "".join(lines)


def collect_repositories(queries: list[str], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    collected: list[dict[str, Any]] = []
    for query in queries:
        for search_result in search_repositories(query, limit):
            full_name = search_result["fullName"]
            if full_name in seen:
                continue
            seen.add(full_name)

            details = repository_details(full_name)
            branch = details.get("defaultBranchRef", {}).get("name") or "main"
            try:
                paths = repository_tree(full_name, branch)
            except subprocess.CalledProcessError:
                paths = []
            collected.append({"details": details, "analysis": analyze_paths(paths)})
    return collected


def main() -> None:
    args = parse_args()
    queries = args.query or DEFAULT_QUERIES
    repositories = collect_repositories(queries, args.limit)
    report = render_report(repositories)

    if args.dry_run:
        print(report, end="")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote GitHub skill scan to {output_path}")


if __name__ == "__main__":
    main()
