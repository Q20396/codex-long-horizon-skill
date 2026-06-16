#!/usr/bin/env python3
"""Scan top related public skill repositories for manual upgrade review."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path("docs/TOP_RELATED_SKILLS_SCAN.md")
DEFAULT_QUERY = "agent skills"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find top related public skill repositories, analyze repository "
            "signals, and produce a manual upgrade review report. This does "
            "not copy code, edit files, merge PRs, or update the skill package."
        )
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="GitHub repository search query.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Number of top repositories to analyze.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help="Markdown output path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without writing files.",
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
    examples = [path for path in lowered if path.startswith(("examples/", "sample/"))]
    workflows = [path for path in lowered if path.startswith(".github/workflows/")]
    templates = [path for path in lowered if "template" in path or "/templates/" in path]
    references = [path for path in lowered if "/references/" in path or path.startswith("references/")]
    safety_words = {"safety", "security", "privacy", "policy", "permission", "review"}
    safety_files = []
    for path in lowered:
        parts = set(Path(path).parts)
        stems = {Path(part).stem for part in parts}
        if safety_words.intersection(parts) or safety_words.intersection(stems):
            safety_files.append(path)

    return {
        "files_scanned": len(paths),
        "skill_files": skill_files[:5],
        "docs_count": len(docs),
        "scripts_count": len(scripts),
        "examples_count": len(examples),
        "workflows_count": len(workflows),
        "templates_count": len(templates),
        "references_count": len(references),
        "safety_files": safety_files[:5],
    }


def improvement_signals(analysis: dict[str, Any]) -> list[str]:
    signals = []
    if analysis["skill_files"]:
        signals.append("Review trigger-focused SKILL.md metadata and activation language.")
    if analysis["references_count"]:
        signals.append("Compare reference organization for reusable guidance patterns.")
    if analysis["templates_count"]:
        signals.append("Compare template coverage and safety warnings.")
    if analysis["scripts_count"]:
        signals.append("Look for small validation or review helper ideas.")
    if analysis["workflows_count"]:
        signals.append("Compare CI/package validation patterns.")
    if analysis["safety_files"]:
        signals.append("Review privacy, safety, permission, or human-review guardrails.")
    if analysis["examples_count"]:
        signals.append("Compare example prompts or smoke-test packages.")
    if not signals:
        signals.append("No obvious reusable signal from the file tree; manual review required.")
    return signals


def render_report(repositories: list[dict[str, Any]], query: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Top Related Skills Scan\n\n",
        f"Scan time: {timestamp}\n\n",
        f"Query: `{query}`\n\n",
        "Purpose: identify manual-upgrade ideas from public repositories.\n\n",
        "This report is evidence only. Do not copy code, templates, prompts, README text, "
        "or assets without license review and user approval.\n\n",
        "## Top Repositories\n\n",
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
            f"{analysis['references_count']} references; "
            f"{analysis['templates_count']} templates; "
            f"{analysis['scripts_count']} scripts; "
            f"{analysis['workflows_count']} workflows"
        )
        lines.append(
            f"| [{details['nameWithOwner']}]({details['url']}) | "
            f"{details.get('stargazerCount', 0)} | {language} | {license_name} | {signals} |\n"
        )

    lines.append("\n## Manual Upgrade Review\n\n")
    for repo in repositories:
        details = repo["details"]
        analysis = repo["analysis"]
        lines.append(f"### {details['nameWithOwner']}\n\n")
        lines.append(f"- Description: {details.get('description') or ''}\n")
        lines.append(f"- Last pushed: {details.get('pushedAt') or ''}\n")
        if analysis["skill_files"]:
            lines.append(f"- Skill files observed: {', '.join(analysis['skill_files'])}\n")
        if analysis["safety_files"]:
            lines.append(f"- Safety-related files observed: {', '.join(analysis['safety_files'])}\n")
        for signal in improvement_signals(analysis):
            lines.append(f"- Possible learning: {signal}\n")
        lines.append("- Manual action: user may review, click a PR, request an original change, or skip.\n")
        lines.append("- Risk note: license, attribution, privacy, and factual claims must be reviewed first.\n\n")

    lines.append("## Guardrails\n\n")
    lines.append("- Do not auto-merge.\n")
    lines.append("- Do not modify `main` directly.\n")
    lines.append("- Do not copy external code or project prose.\n")
    lines.append("- Do not run remote code from scanned repositories.\n")
    lines.append("- Do not store secrets, client data, legal evidence, family information, API keys, or confidential documents.\n")
    lines.append("- Treat this scan as input to human review, not permission to update automatically.\n")
    return "".join(lines)


def collect_top_repositories(query: str, top: int) -> list[dict[str, Any]]:
    repositories = []
    for result in search_repositories(query, top):
        full_name = result["fullName"]
        details = repository_details(full_name)
        branch = details.get("defaultBranchRef", {}).get("name") or "main"
        try:
            paths = repository_tree(full_name, branch)
        except subprocess.CalledProcessError:
            paths = []
        repositories.append({"details": details, "analysis": analyze_paths(paths)})
    return repositories


def main() -> None:
    args = parse_args()
    repositories = collect_top_repositories(args.query, args.top)
    report = render_report(repositories, args.query)

    if args.dry_run:
        print(report, end="")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote top related skills scan to {output_path}")


if __name__ == "__main__":
    main()
