#!/usr/bin/env python3
"""Generate and validate the README skill catalog."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
README = ROOT / "README.md"
START = "<!-- skill-catalog:start -->"
END = "<!-- skill-catalog:end -->"

BEST_FOR = {
    "ai-video-production": (
        "Video briefs, scripts, storyboards, visual prompts, asset manifests, "
        "and render handoffs."
    ),
    "long-horizon-engineering": (
        "Large refactors, migrations, debugging, PR workflows, resumable tasks, "
        "and validation-heavy engineering."
    ),
}

QUALITY_TERMS = {
    "examples": ("example prompt", "example prompts", "copy-paste prompt"),
    "validation guidance": ("validation", "verify", "test"),
    "safety boundaries": ("safety", "privacy", "approval", "do not"),
}

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

REQUIRED_OPEN_SOURCE_FILES = [
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/skill_proposal.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/pull_request_template.md",
    "CODE_OF_CONDUCT.md",
    "COMMUNITY_SKILLS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/demo/README.md",
]

EXAMPLE_WORKFLOWS = [
    "bug-investigation",
    "large-refactor",
    "repository-migration",
    "resume-work",
]

EXAMPLE_REQUIRED_FILES = [
    "prompt.md",
    "workflow.md",
    "expected-output.md",
]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    best_for: str
    path: Path


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.relative_to(ROOT)} is missing YAML front matter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path.relative_to(ROOT)} front matter is not closed")

    data: dict[str, str] = {}
    for raw_line in parts[1].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def one_line(text: str) -> str:
    return " ".join(text.split())


def discover_skills() -> list[Skill]:
    if not SKILLS_ROOT.is_dir():
        raise SystemExit(f"ERROR: skills directory not found: {SKILLS_ROOT}")

    skills: list[Skill] = []
    for skill_dir in sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise SystemExit(f"ERROR: missing SKILL.md: {skill_dir.relative_to(ROOT)}")
        metadata = parse_front_matter(skill_md)
        name = metadata.get("name", skill_dir.name)
        description = one_line(metadata.get("description", "No description provided."))
        best_for = BEST_FOR.get(name, "Specialized Codex workflows and reusable task guidance.")
        skills.append(Skill(name=name, description=description, best_for=best_for, path=skill_md))
    return skills


def render_catalog(skills: list[Skill]) -> str:
    lines = [
        START,
        "| Skill | Purpose | Best For |",
        "| --- | --- | --- |",
    ]
    for skill in skills:
        rel_path = skill.path.relative_to(ROOT).as_posix()
        lines.append(
            f"| [`{skill.name}`]({rel_path}) | {skill.description} | {skill.best_for} |"
        )
    lines.append(END)
    return "\n".join(lines)


def replace_catalog(readme_text: str, catalog: str) -> str:
    pattern = re.compile(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        flags=re.DOTALL,
    )
    if not pattern.search(readme_text):
        raise SystemExit("ERROR: README.md is missing skill catalog markers.")
    return pattern.sub(catalog, readme_text)


def check_quality(skills: list[Skill]) -> list[str]:
    errors: list[str] = []
    for skill in skills:
        text = skill.path.read_text(encoding="utf-8").lower()
        for label, terms in QUALITY_TERMS.items():
            if not any(term in text for term in terms):
                errors.append(f"{skill.path.relative_to(ROOT)} is missing {label}.")
    return errors


def slugify(heading: str) -> str:
    slug = heading.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug


def markdown_headings(path: Path) -> set[str]:
    headings: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            continue
        heading = line.lstrip("#").strip()
        if heading:
            headings.add(slugify(heading))
    return headings


def check_internal_links() -> list[str]:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(text):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith(("http://", "https://", "mailto:"))
                or target.startswith("<")
            ):
                continue
            target_path, _, anchor = target.partition("#")
            linked_file = path if not target_path else (path.parent / target_path)
            linked_file = linked_file.resolve()
            if not linked_file.exists():
                errors.append(
                    f"{path.relative_to(ROOT)} links to missing path: {target}"
                )
                continue
            if anchor and linked_file.suffix.lower() == ".md":
                headings = markdown_headings(linked_file)
                if anchor.lower() not in headings:
                    errors.append(
                        f"{path.relative_to(ROOT)} links to missing anchor: {target}"
                    )
    return errors


def check_required_files() -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_OPEN_SOURCE_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"Missing open-source support file: {relative}")
    for example in EXAMPLE_WORKFLOWS:
        directory = ROOT / "examples" / example
        if not directory.is_dir():
            errors.append(f"Missing example directory: examples/{example}")
            continue
        for filename in EXAMPLE_REQUIRED_FILES:
            path = directory / filename
            if not path.is_file():
                errors.append(f"Missing example file: examples/{example}/{filename}")
    return errors


def check_issue_template_config() -> list[str]:
    path = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "blank_issues_enabled:" not in text:
        errors.append(".github/ISSUE_TEMPLATE/config.yml missing blank_issues_enabled")
    if "http://" in text or "https://" in text:
        errors.append(
            ".github/ISSUE_TEMPLATE/config.yml contains external links; verify they are not dead."
        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check the README skill catalog and product docs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if README catalog, skill quality, or internal links are invalid.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skills = discover_skills()
    catalog = render_catalog(skills)
    readme_text = README.read_text(encoding="utf-8")
    expected = replace_catalog(readme_text, catalog)

    if args.check:
        errors = []
        if expected != readme_text:
            errors.append("README.md skill catalog is not synchronized.")
        errors.extend(check_required_files())
        errors.extend(check_quality(skills))
        errors.extend(check_internal_links())
        errors.extend(check_issue_template_config())
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("Skill catalog and product documentation checks passed.")
        return 0

    README.write_text(expected, encoding="utf-8")
    print(f"Updated README skill catalog with {len(skills)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
