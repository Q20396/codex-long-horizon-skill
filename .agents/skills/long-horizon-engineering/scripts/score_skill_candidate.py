#!/usr/bin/env python3
"""Score candidate skill text against non-sensitive static eval cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CASES = ROOT / "tests" / "skill-eval-cases.json"
FALLBACK_CASES = (
    Path(__file__).resolve().parents[1] / "templates" / "skill-eval-cases.json"
)
DEFAULT_SKILL = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "SKILL.md"


def load_text(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"ERROR: file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_cases(path: Path, skill_name: str) -> list[dict]:
    if not path.is_file() and path == DEFAULT_CASES and FALLBACK_CASES.is_file():
        path = FALLBACK_CASES
    if not path.is_file():
        raise SystemExit(f"ERROR: eval cases not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for skill in payload.get("skills", []):
        if skill.get("name") == skill_name:
            cases = skill.get("cases", [])
            if not isinstance(cases, list) or not cases:
                raise SystemExit(f"ERROR: no cases found for skill: {skill_name}")
            return cases
    raise SystemExit(f"ERROR: skill not found in eval cases: {skill_name}")


def phrase_present(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def score_case(text: str, case: dict) -> dict:
    required = case.get("required_phrases", [])
    forbidden = case.get("forbidden_phrases", [])
    if not isinstance(required, list) or not isinstance(forbidden, list):
        raise SystemExit(f"ERROR: invalid phrase lists in case: {case.get('id')}")

    missing = [phrase for phrase in required if not phrase_present(text, phrase)]
    present_forbidden = [
        phrase for phrase in forbidden if phrase and phrase_present(text, phrase)
    ]
    passed = not missing and not present_forbidden
    weight = float(case.get("weight", 1.0))
    return {
        "id": case.get("id", "unnamed"),
        "split": case.get("split", "validation"),
        "weight": weight,
        "passed": passed,
        "missing_required": missing,
        "present_forbidden": present_forbidden,
    }


def score_text(text: str, cases: list[dict]) -> dict:
    case_results = [score_case(text, case) for case in cases]
    total_weight = sum(result["weight"] for result in case_results)
    passed_weight = sum(
        result["weight"] for result in case_results if result["passed"]
    )
    score = passed_weight / total_weight if total_weight else 0.0
    failed = [result for result in case_results if not result["passed"]]
    return {
        "score": round(score, 4),
        "passed": len(case_results) - len(failed),
        "failed": len(failed),
        "total": len(case_results),
        "total_weight": total_weight,
        "case_results": case_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local static score for candidate skill text. This script "
            "makes no network calls, uses no external model, and does not edit files."
        )
    )
    parser.add_argument(
        "--candidate",
        default=str(DEFAULT_SKILL),
        help="Candidate SKILL.md or text file to score.",
    )
    parser.add_argument(
        "--baseline",
        help="Optional baseline SKILL.md or text file to compare against.",
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES),
        help="Path to skill eval cases JSON.",
    )
    parser.add_argument(
        "--skill-name",
        default="long-horizon-engineering",
        help="Skill name inside the eval cases fixture.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable results.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero if candidate score is lower than baseline or any candidate case fails.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_cases(Path(args.cases), args.skill_name)
    candidate_path = Path(args.candidate)
    candidate_result = score_text(load_text(candidate_path), cases)
    output = {
        "skill": args.skill_name,
        "cases": str(Path(args.cases)),
        "candidate": str(candidate_path),
        "candidate_result": candidate_result,
        "recommendation": "human_review_required",
    }

    baseline_result = None
    if args.baseline:
        baseline_path = Path(args.baseline)
        baseline_result = score_text(load_text(baseline_path), cases)
        output["baseline"] = str(baseline_path)
        output["baseline_result"] = baseline_result
        output["score_delta"] = round(
            candidate_result["score"] - baseline_result["score"], 4
        )

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print("Skill candidate static score")
        print(f"Skill: {args.skill_name}")
        if baseline_result:
            print(f"Baseline score: {baseline_result['score']:.4f}")
        print(f"Candidate score: {candidate_result['score']:.4f}")
        if baseline_result:
            print(f"Score delta: {output['score_delta']:.4f}")
        print(
            f"Candidate cases: {candidate_result['passed']} passed, "
            f"{candidate_result['failed']} failed, {candidate_result['total']} total"
        )
        for result in candidate_result["case_results"]:
            if result["passed"]:
                continue
            print(f"FAIL: {result['id']}")
            if result["missing_required"]:
                print(f"  missing required: {', '.join(result['missing_required'])}")
            if result["present_forbidden"]:
                print(f"  present forbidden: {', '.join(result['present_forbidden'])}")
        print("Recommendation: human review required before deployment.")

    regression = bool(
        baseline_result and candidate_result["score"] < baseline_result["score"]
    )
    if args.fail_on_regression and (regression or candidate_result["failed"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
