#!/usr/bin/env python3
"""Validate deterministic routing contract fixtures for packaged skills.

This is a static routing regression proxy. It validates fixture structure,
coverage, and skill metadata boundaries. It does not claim to reproduce Codex
model routing.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests" / "expected-triggers.json"
SKILLS_ROOT = ROOT / ".agents" / "skills"

ALLOWED_EXPECTED = {"long-horizon-engineering", "ai-video-production", "none"}
ALLOWED_MODES = {"implicit", "explicit"}
REQUIRED_CATEGORIES = {
    "long-horizon-positive",
    "ai-video-positive",
    "no-skill-negative",
    "boundary-overlap",
    "explicit-invocation",
    "capability-discovery",
}
MIN_COUNTS = {
    "long-horizon-positive": 10,
    "ai-video-positive": 7,
    "no-skill-negative": 8,
    "boundary-overlap": 5,
    "explicit-invocation": 3,
    "capability-discovery": 3,
}
DISCOVERY_ESCALATION_TAG = "discovery-escalation"

LONG_HORIZON_FORBIDDEN_IMPLICIT_DOMAINS = {
    "storyboard",
    "shot list",
    "asset manifest",
    "render handoff",
    "stock",
    "legal",
    "disaster",
    "storm",
}
AI_VIDEO_FORBIDDEN_ENGINEERING_TERMS = {
    "repository exploration",
    "multi-file changes",
    "ci/build failures",
    "schema changes",
    "migrations",
    "refactors",
}


def load_fixture(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"ERROR: trigger fixture not found: {path}. "
            "Run this from the source package or pass --fixture /path/to/tests/expected-triggers.json."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def skill_names() -> set[str]:
    names = set()
    for path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        meta = text.split("---\n", 2)[1] if text.startswith("---\n") else ""
        match = re.search(r"^name:\s*(.+)$", meta, flags=re.MULTILINE)
        names.add(match.group(1).strip() if match else path.parent.name)
    return names


def skill_description(name: str) -> str:
    path = SKILLS_ROOT / name / "SKILL.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ""
    meta = text.split("---\n", 2)[1]
    match = re.search(r"^description:\s*(.+)$", meta, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def validate_case(case, index: int, valid_skills: set[str]) -> list[str]:
    errors: list[str] = []
    context = f"case #{index + 1}"
    if not isinstance(case, dict):
        return [f"{context}: must be an object"]

    required_fields = {
        "id",
        "prompt",
        "invocation_mode",
        "expected_skill",
        "category",
        "rationale",
        "tags",
    }
    for field in sorted(required_fields):
        if field not in case:
            errors.append(f"{context}: missing field {field}")

    case_id = case.get("id", context)
    if not isinstance(case.get("id"), str) or not case.get("id", "").strip():
        errors.append(f"{context}: id must be a non-empty string")
    if not isinstance(case.get("prompt"), str) or len(case.get("prompt", "").split()) < 5:
        errors.append(f"{case_id}: prompt must be a realistic non-empty string")
    invocation_mode = case.get("invocation_mode")
    if not isinstance(invocation_mode, str) or invocation_mode not in ALLOWED_MODES:
        errors.append(f"{case_id}: invalid invocation_mode {case.get('invocation_mode')!r}")
    expected_skill = case.get("expected_skill")
    if not isinstance(expected_skill, str) or expected_skill not in ALLOWED_EXPECTED:
        errors.append(f"{case_id}: invalid expected_skill {case.get('expected_skill')!r}")
    if isinstance(expected_skill, str) and expected_skill not in valid_skills | {"none"}:
        errors.append(f"{case_id}: expected skill does not exist: {case.get('expected_skill')}")
    category = case.get("category")
    if not isinstance(category, str) or category not in REQUIRED_CATEGORIES:
        errors.append(f"{case_id}: invalid category {case.get('category')!r}")
    rationale = case.get("rationale")
    rationale_text = rationale if isinstance(rationale, str) else ""
    if not rationale_text.strip():
        errors.append(f"{case_id}: rationale must be a non-empty string")
    tags = case.get("tags")
    if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag for tag in tags):
        errors.append(f"{case_id}: tags must be a non-empty string list")

    if case.get("invocation_mode") == "explicit":
        prompt = case.get("prompt", "")
        expected = case.get("expected_skill")
        if expected != "none" and f"${expected}" not in prompt and f"Use the {expected} skill" not in prompt:
            errors.append(f"{case_id}: explicit case should name the expected skill")

    if category == "capability-discovery":
        if case.get("invocation_mode") != "implicit":
            errors.append(f"{case_id}: capability discovery must be implicit")
        if case.get("expected_skill") != "long-horizon-engineering":
            errors.append(
                f"{case_id}: capability discovery must enter the LHE discovery shell"
            )
        if "descriptor-only" not in (case.get("tags") or []):
            errors.append(
                f"{case_id}: capability discovery must be tagged descriptor-only"
            )
        if "suggest" not in rationale_text.casefold():
            errors.append(
                f"{case_id}: capability discovery rationale must say suggestion-only"
            )

    if isinstance(tags, list) and DISCOVERY_ESCALATION_TAG in tags:
        if category != "no-skill-negative" or expected_skill != "none":
            errors.append(
                f"{case_id}: discovery escalation must remain a no-skill rejection"
            )
        if not {"prompt-injection", "unauthorized-suggestion"} & set(
            tag for tag in tags if isinstance(tag, str)
        ):
            errors.append(
                f"{case_id}: discovery escalation must identify its attack class"
            )
        if "reject" not in rationale_text.casefold():
            errors.append(
                f"{case_id}: discovery escalation rationale must explicitly reject it"
            )

    return errors


def validate_descriptions() -> list[str]:
    errors: list[str] = []
    descriptions = {
        name: skill_description(name)
        for name in sorted(skill_names())
    }
    for name, description in descriptions.items():
        if not description:
            errors.append(f"{name}: missing description")
        if len(description) > 360:
            errors.append(f"{name}: description too long for routing metadata ({len(description)} chars)")

    lhe = descriptions.get("long-horizon-engineering", "").lower()
    video = descriptions.get("ai-video-production", "").lower()
    if "software engineering" not in lhe:
        errors.append("long-horizon-engineering: description should state software engineering scope")
    if "do not use" not in lhe:
        errors.append("long-horizon-engineering: description should include a compact boundary")
    for term in LONG_HORIZON_FORBIDDEN_IMPLICIT_DOMAINS:
        if term == "legal" and "descriptor-only legal-evidence" in lhe:
            continue
        negative_boundary = f"unrelated {term}" in lhe or f"{term}/financial tasks" in lhe
        if term in lhe and not negative_boundary:
            errors.append(f"long-horizon-engineering: description advertises unrelated domain term: {term}")
    if "descriptor-only" not in lhe or "keywords never authorize" not in lhe:
        errors.append(
            "long-horizon-engineering: description must keep capability discovery "
            "descriptor-only and non-authoritative"
        )

    if "video" not in video or "storyboard" not in video:
        errors.append("ai-video-production: description should front-load video/storyboard scope")
    if "general repository engineering" not in video:
        errors.append("ai-video-production: description should exclude general repository engineering")
    for term in AI_VIDEO_FORBIDDEN_ENGINEERING_TERMS:
        if term in video:
            errors.append(f"ai-video-production: description advertises engineering trigger: {term}")
    return errors


def validate_fixture(payload) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["fixture root must be an object"]
    valid_skills = skill_names()
    cases = payload.get("cases")
    if payload.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    allowed_expected = payload.get("allowed_expected_skills")
    if (
        not isinstance(allowed_expected, list)
        or not all(isinstance(value, str) for value in allowed_expected)
        or set(allowed_expected) != ALLOWED_EXPECTED
    ):
        errors.append("allowed_expected_skills does not match validator contract")
    allowed_modes = payload.get("allowed_invocation_modes")
    if (
        not isinstance(allowed_modes, list)
        or not all(isinstance(value, str) for value in allowed_modes)
        or set(allowed_modes) != ALLOWED_MODES
    ):
        errors.append("allowed_invocation_modes does not match validator contract")
    if not isinstance(cases, list) or len(cases) < 36:
        errors.append("cases must contain at least 36 routing examples")
        cases = cases if isinstance(cases, list) else []

    seen: set[str] = set()
    categories = Counter()
    expected = Counter()
    modes = Counter()
    boundary_tags = 0
    for index, case in enumerate(cases):
        errors.extend(validate_case(case, index, valid_skills))
        if not isinstance(case, dict):
            continue
        raw_case_id = case.get("id")
        case_id = raw_case_id if isinstance(raw_case_id, str) else f"case #{index + 1}"
        if case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        seen.add(case_id)
        category = case.get("category")
        expected_skill = case.get("expected_skill")
        invocation_mode = case.get("invocation_mode")
        if isinstance(category, str):
            categories[category] += 1
        if isinstance(expected_skill, str):
            expected[expected_skill] += 1
        if isinstance(invocation_mode, str):
            modes[invocation_mode] += 1
        if case.get("category") == "boundary-overlap":
            boundary_tags += 1

    for category in sorted(REQUIRED_CATEGORIES):
        if categories[category] < MIN_COUNTS[category]:
            errors.append(
                f"category {category} has {categories[category]} cases; "
                f"expected at least {MIN_COUNTS[category]}"
            )
    if expected["none"] < 8:
        errors.append("no-skill expected result must be represented by at least 8 cases")
    if modes["explicit"] < 3 or modes["implicit"] < 30:
        errors.append("explicit and implicit invocation modes must both be represented")
    if boundary_tags < 5:
        errors.append("boundary/overlap prompts are underrepresented")

    errors.extend(validate_descriptions())
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate deterministic routing contract fixtures. This is a static "
            "routing regression proxy; it does not call a model or make network requests."
        )
    )
    parser.add_argument(
        "--fixture",
        default=str(FIXTURE),
        help="Path to expected trigger JSON fixture.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_fixture(Path(args.fixture))
    errors = validate_fixture(payload)
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    safe_cases = [case for case in cases if isinstance(case, dict)]

    def string_counter(field: str) -> dict[str, int]:
        return dict(
            Counter(
                value
                for case in safe_cases
                if isinstance((value := case.get(field)), str)
            )
        )

    summary = {
        "ok": not errors,
        "case_count": len(cases) if isinstance(cases, list) else 0,
        "categories": string_counter("category"),
        "expected_skills": string_counter("expected_skill"),
        "invocation_modes": string_counter("invocation_mode"),
        "errors": errors,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print(
            "Routing contract fixtures passed: "
            f"{summary['case_count']} cases, "
            f"categories={summary['categories']}, "
            f"expected_skills={summary['expected_skills']}."
        )

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
