#!/usr/bin/env python3
"""Scan top public video/image skill repositories for manual upgrade options."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path("docs/TOP_MEDIA_SKILLS_SCAN.md")
DEFAULT_QUERY = "ai video generation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find top public video/image generation skill or agent repositories, "
            "analyze code and workflow signals, and produce customer-facing "
            "manual upgrade options. This does not copy code, execute remote "
            "code, merge PRs, or update the skill package."
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
    package_files = [
        path
        for path in lowered
        if Path(path).name in {"package.json", "pyproject.toml", "requirements.txt", "uv.lock", "pnpm-lock.yaml"}
    ]
    media_keywords = {
        "video",
        "image",
        "media",
        "render",
        "storyboard",
        "prompt",
        "asset",
        "thumbnail",
        "remotion",
        "ffmpeg",
        "moviepy",
        "pillow",
        "imagegen",
    }
    media_files = [
        path
        for path in lowered
        if any(keyword in path for keyword in media_keywords)
    ]
    source_files = [
        path
        for path in lowered
        if path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh"))
    ]
    safety_words = {"safety", "security", "privacy", "policy", "permission", "review", "license"}
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
        "package_files": package_files[:5],
        "media_files": media_files[:8],
        "source_files_count": len(source_files),
        "safety_files": safety_files[:5],
    }


def media_upgrade_options(analysis: dict[str, Any]) -> list[str]:
    options = [
        "Manual review only: read the report and make no changes.",
        "Request a draft PR: ask Codex to propose an original small improvement based on selected signals.",
        "Manual copy after approval: copy only reviewed wording or structure that is license-safe and non-sensitive.",
        "Skip: ignore repositories with unclear license, weak relevance, or risky media handling.",
    ]
    if analysis["media_files"]:
        options.append("Consider improving media prompt, asset manifest, storyboard, or render-handoff coverage.")
    if analysis["package_files"] or analysis["source_files_count"]:
        options.append("Review implementation patterns conceptually; do not copy code.")
    if analysis["safety_files"]:
        options.append("Compare privacy, licensing, approval-gate, and publishing safeguards.")
    if analysis["workflows_count"]:
        options.append("Consider whether CI should verify media-skill helpers or templates.")
    return options


def render_report(repositories: list[dict[str, Any]], query: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Top Video/Image Skills Scan\n\n",
        f"Scan time: {timestamp}\n\n",
        f"Query: `{query}`\n\n",
        "Purpose: analyze public video/image skill and agent repositories, then "
        "offer manual upgrade options for customers.\n\n",
        "This report is evidence only. Do not copy code, prompts, templates, README text, "
        "assets, model settings, or media without license review and user approval.\n\n",
        "## Top Repositories\n\n",
        "| Repository | Stars | Language | License | Code / Media Signals |\n",
        "| --- | ---: | --- | --- | --- |\n",
    ]

    for repo in repositories:
        details = repo["details"]
        analysis = repo["analysis"]
        language = (details.get("primaryLanguage") or {}).get("name") or ""
        license_name = (details.get("licenseInfo") or {}).get("spdxId") or "Unknown"
        signals = (
            f"{analysis['files_scanned']} files; "
            f"{analysis['source_files_count']} source files; "
            f"{len(analysis['media_files'])} media-related paths; "
            f"{len(analysis['skill_files'])} skill files; "
            f"{analysis['scripts_count']} scripts; "
            f"{analysis['workflows_count']} workflows"
        )
        lines.append(
            f"| [{details['nameWithOwner']}]({details['url']}) | "
            f"{details.get('stargazerCount', 0)} | {language} | {license_name} | {signals} |\n"
        )

    lines.append("\n## Code And Workflow Signals\n\n")
    for repo in repositories:
        details = repo["details"]
        analysis = repo["analysis"]
        lines.append(f"### {details['nameWithOwner']}\n\n")
        lines.append(f"- Description: {details.get('description') or ''}\n")
        lines.append(f"- Last pushed: {details.get('pushedAt') or ''}\n")
        if analysis["skill_files"]:
            lines.append(f"- Skill files observed: {', '.join(analysis['skill_files'])}\n")
        if analysis["package_files"]:
            lines.append(f"- Package/config files observed: {', '.join(analysis['package_files'])}\n")
        if analysis["media_files"]:
            lines.append(f"- Media-related paths observed: {', '.join(analysis['media_files'])}\n")
        if analysis["safety_files"]:
            lines.append(f"- Safety/license/review files observed: {', '.join(analysis['safety_files'])}\n")

        lines.append("\nManual upgrade options for customer review:\n")
        for option in media_upgrade_options(analysis):
            lines.append(f"- {option}\n")
        lines.append("\n")

    lines.append("## Guardrails\n\n")
    lines.append("- System may notify the user that manual upgrade options are available.\n")
    lines.append("- User must choose whether to click a PR, request a change, copy reviewed material, or skip.\n")
    lines.append("- Do not auto-upgrade, auto-merge, or modify `main` directly.\n")
    lines.append("- Do not copy external code, prompts, media, templates, or project prose without license review.\n")
    lines.append("- Do not run remote code from scanned repositories.\n")
    lines.append("- Do not upload private assets or client material to external tools without explicit approval.\n")
    lines.append("- Do not store secrets, client data, legal evidence, family information, API keys, or confidential documents.\n")
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
    print(f"Wrote top video/image skills scan to {output_path}")


if __name__ == "__main__":
    main()
