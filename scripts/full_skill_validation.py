#!/usr/bin/env python3
"""Run comprehensive local validation for the Codex skill package."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
TMP_ROOT = (
    Path(os.environ.get("CODEX_SKILL_TMP_ROOT", tempfile.gettempdir()))
    .expanduser()
    .resolve()
)

LHE = Path(".agents/skills/long-horizon-engineering")
AI_VIDEO = Path(".agents/skills/ai-video-production")
LHE_SCRIPTS = LHE / "scripts"

REQUIRED_CORE_FILES = [
    LHE / "SKILL.md",
    AI_VIDEO / "SKILL.md",
    LHE_SCRIPTS / "check_skill_package.py",
    LHE_SCRIPTS / "doctor.py",
    LHE_SCRIPTS / "test_expected_triggers.py",
    LHE_SCRIPTS / "audit_skill_descriptions.py",
    LHE_SCRIPTS / "update_installed_skill.py",
    Path("tests/expected-triggers.json"),
    Path("README.md"),
    Path("INSTALL.md"),
    Path("UPGRADE_GUIDE.md"),
    Path("CHANGELOG.md"),
]

PRODUCTIZED_FILES = [
    LHE / "references/repomix-codebase-context.md",
    LHE / "references/skill-authoring-methodology.md",
    LHE / "references/external-search-protocol.md",
    LHE / "templates/implementation-plan.md",
    LHE / "templates/verification-evidence.md",
]

CONTENT_RESEARCH_DESIGN_FILES = [
    LHE / "references/writing-humanization-protocol.md",
    LHE / "references/ideation-to-plan-protocol.md",
    LHE / "references/evidence-backed-writing.md",
    LHE / "references/notebook-analysis-protocol.md",
    LHE / "references/presentation-delivery-protocol.md",
    AI_VIDEO / "references/design-system-for-video.md",
    AI_VIDEO / "templates/DESIGN.md",
    AI_VIDEO / "templates/visual-style-tokens.md",
    AI_VIDEO / "templates/brand-system-for-video.md",
]

SKILLOPT_FILES = [
    LHE / "references/skill-optimization-protocol.md",
    LHE / "templates/skill-rollout-log.md",
    LHE / "templates/skill-reflection-report.md",
    LHE / "templates/bounded-skill-edit.md",
    LHE / "templates/skill-validation-gate.md",
    LHE / "templates/rejected-skill-edit-log.md",
    LHE_SCRIPTS / "audit_skill_optimization_readiness.py",
]

DISASTER_FILES = [
    LHE / "references/disaster-monitoring-protocol.md",
    LHE / "references/disaster-monitoring-enablement.md",
    LHE_SCRIPTS / "enable_disaster_monitoring.py",
    LHE / "templates/disaster-alert-rule.md",
    LHE / "templates/situation-report.md",
    LHE / "templates/source-reliability-table.md",
    LHE / "templates/incident-timeline.md",
    LHE / "templates/affected-area-summary.md",
    LHE / "templates/public-safety-communication-checklist.md",
    LHE / "templates/public-alert-draft.md",
    LHE / "templates/monitoring-runbook.md",
]

CORE_COMMANDS = [
    [PYTHON, str(LHE_SCRIPTS / "check_skill_package.py")],
    [PYTHON, str(LHE_SCRIPTS / "doctor.py")],
    [PYTHON, str(LHE_SCRIPTS / "test_expected_triggers.py")],
    [PYTHON, str(LHE_SCRIPTS / "audit_skill_descriptions.py")],
    [PYTHON, str(LHE_SCRIPTS / "audit_skill_descriptions.py"), "--json"],
    [PYTHON, str(LHE_SCRIPTS / "audit_skill_descriptions.py"), "--help"],
    [PYTHON, str(LHE_SCRIPTS / "update_installed_skill.py"), "--list-skills"],
    ["git", "diff", "--check"],
]

CI_EXPECTED = [
    ("check_skill_package.py", ["check_skill_package.py"]),
    ("doctor.py", ["doctor.py"]),
    ("test_expected_triggers.py", ["test_expected_triggers.py"]),
    ("audit_skill_descriptions.py", ["audit_skill_descriptions.py"]),
    ("update_installed_skill.py --list-skills", ["update_installed_skill.py", "--list-skills"]),
    ("Python compile check", ["py_compile"]),
    ("git diff --check", ["git", "diff", "--check"]),
    ("update dry-run smoke test", ["update_installed_skill.py", "--target-root"]),
]

BIDI_CONTROLS = {
    chr(value)
    for value in [
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    ]
}


@dataclass
class Check:
    section: str
    name: str
    status: str
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def pass_(self, section: str, name: str, detail: str = "") -> None:
        self.checks.append(Check(section, name, "PASS", detail))

    def warn(self, section: str, name: str, detail: str = "") -> None:
        self.checks.append(Check(section, name, "WARN", detail))

    def partial(self, section: str, name: str, detail: str = "") -> None:
        self.checks.append(Check(section, name, "PARTIAL", detail))

    def fail(self, section: str, name: str, detail: str = "") -> None:
        self.checks.append(Check(section, name, "FAIL", detail))

    def by_section(self) -> dict[str, list[Check]]:
        sections: dict[str, list[Check]] = {}
        for check in self.checks:
            sections.setdefault(check.section, []).append(check)
        return sections

    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.status == "FAIL"]

    def warnings(self) -> list[Check]:
        return [check for check in self.checks if check.status in {"WARN", "PARTIAL"}]

    def verdict(self) -> str:
        if self.failures():
            return "FAIL"
        if self.warnings():
            return "PASS_WITH_WARNINGS"
        return "PASS"


def rel(path: Path) -> str:
    return str(path)


def run_command(args: list[str], *, cwd: Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def cmd_label(args: list[str]) -> str:
    return " ".join(args)


def summarize_output(result: subprocess.CompletedProcess[str], limit: int = 1200) -> str:
    text = (result.stdout or "") + (result.stderr or "")
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + "... [truncated]"
    return text


def safe_rmtree(path: Path) -> None:
    resolved = path.resolve()
    tmp = TMP_ROOT.resolve()
    if not str(resolved).startswith(str(tmp) + os.sep):
        raise RuntimeError(f"Refusing to remove non-temp path: {resolved}")
    shutil.rmtree(resolved, ignore_errors=True)


def load_required_from_check_script() -> set[Path]:
    script = ROOT / LHE_SCRIPTS / "check_skill_package.py"
    if not script.is_file():
        return set()
    tree = ast.parse(script.read_text(encoding="utf-8"))
    required: set[Path] = set()
    wanted = {"INSTALLED_REQUIRED_FILES", "AI_VIDEO_REQUIRED_FILES", "PACKAGE_ONLY_FILES"}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    required.add(Path(item))
    return required


def check_files(report: Report, section: str, files: list[Path], *, required_by_checker: set[Path], fail_missing: bool) -> None:
    for path in files:
        full = ROOT / path
        if full.is_file():
            report.pass_(section, rel(path), "exists")
        elif fail_missing or path in required_by_checker:
            report.fail(section, rel(path), "missing required file")
        else:
            report.warn(section, rel(path), "optional file missing")


def check_repo_state(report: Report) -> None:
    for name, args in [
        ("git status", ["git", "status", "--short", "--branch"]),
        ("current branch", ["git", "branch", "--show-current"]),
        ("recent log", ["git", "log", "--oneline", "-10"]),
    ]:
        result = run_command(args)
        if result.returncode == 0:
            report.pass_("Repository State", name, summarize_output(result))
        else:
            report.fail("Repository State", name, summarize_output(result))


def check_optional_group(report: Report, name: str, files: list[Path], required_by_checker: set[Path]) -> None:
    present = [path for path in files if (ROOT / path).is_file()]
    if not present:
        report.warn("Optional Integration Checks", name, "not present; skipped")
        return
    for path in files:
        full = ROOT / path
        if full.is_file():
            report.pass_("Optional Integration Checks", rel(path), "exists")
        elif path in required_by_checker:
            report.fail("Optional Integration Checks", rel(path), "missing but required by package checker")
        else:
            report.warn("Optional Integration Checks", rel(path), "optional related file missing")


def run_core_commands(report: Report) -> None:
    for args in CORE_COMMANDS:
        result = run_command(args)
        label = cmd_label(args)
        if result.returncode == 0:
            report.pass_("Core Command Results", label, summarize_output(result))
        else:
            report.fail("Core Command Results", label, summarize_output(result))


def run_update_smoke(report: Report) -> None:
    dry_root = TMP_ROOT / "codex-full-skill-validation-dry-run"
    apply_root = TMP_ROOT / "codex-full-skill-validation-apply"
    update_script = LHE_SCRIPTS / "update_installed_skill.py"

    safe_rmtree(dry_root)
    dry_root.mkdir(parents=True, exist_ok=True)
    for skill in ["long-horizon-engineering", "ai-video-production"]:
        result = run_command(
            [PYTHON, str(update_script), "--target-root", str(dry_root), "--skill", skill]
        )
        if result.returncode == 0:
            report.pass_("Update / Install Smoke Test", f"dry-run {skill}", summarize_output(result))
        else:
            report.fail("Update / Install Smoke Test", f"dry-run {skill}", summarize_output(result))
    if (dry_root / ".agents" / "skills").exists():
        report.fail("Update / Install Smoke Test", "dry-run did not install", "dry-run created .agents/skills")
    else:
        report.pass_("Update / Install Smoke Test", "dry-run did not install", "target skills absent")

    safe_rmtree(apply_root)
    apply_root.mkdir(parents=True, exist_ok=True)
    for skill in ["long-horizon-engineering", "ai-video-production"]:
        result = run_command(
            [PYTHON, str(update_script), "--target-root", str(apply_root), "--skill", skill, "--apply"]
        )
        if result.returncode == 0:
            report.pass_("Update / Install Smoke Test", f"apply {skill}", summarize_output(result))
        else:
            report.fail("Update / Install Smoke Test", f"apply {skill}", summarize_output(result))
        installed = apply_root / ".agents" / "skills" / skill / "SKILL.md"
        if installed.is_file():
            report.pass_("Update / Install Smoke Test", f"installed {skill}", str(installed))
        else:
            report.fail("Update / Install Smoke Test", f"installed {skill}", "SKILL.md missing")

    backup_seen = False
    for skill in ["long-horizon-engineering", "ai-video-production"]:
        result = run_command(
            [PYTHON, str(update_script), "--target-root", str(apply_root), "--skill", skill, "--apply"]
        )
        if result.returncode == 0:
            report.pass_("Update / Install Smoke Test", f"second apply {skill}", summarize_output(result))
        else:
            report.fail("Update / Install Smoke Test", f"second apply {skill}", summarize_output(result))
        backup_seen = backup_seen or "Backup:" in result.stdout
    backup_dir = apply_root / ".codex-skill-backups"
    if backup_seen and backup_dir.is_dir() and any(backup_dir.iterdir()):
        report.pass_("Update / Install Smoke Test", "backup-first behavior", str(backup_dir))
    else:
        report.fail("Update / Install Smoke Test", "backup-first behavior", "backup folder not found after second apply")


def run_installed_project_smoke(report: Report) -> None:
    target = TMP_ROOT / "codex-full-skill-installed-project"
    update_script = LHE_SCRIPTS / "update_installed_skill.py"
    safe_rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            PYTHON,
            str(update_script),
            "--target-root",
            str(target),
            "--skill",
            "long-horizon-engineering",
            "--skill",
            "ai-video-production",
            "--apply",
        ]
    )
    if result.returncode == 0:
        report.pass_("Installed Project Smoke Test", "install both skills", summarize_output(result))
    else:
        report.fail("Installed Project Smoke Test", "install both skills", summarize_output(result))

    installed_doctor = target / LHE_SCRIPTS / "doctor.py"
    installed_check = target / LHE_SCRIPTS / "check_skill_package.py"
    for name, args in [
        ("installed doctor", [PYTHON, str(installed_doctor)]),
        ("installed check --installed", [PYTHON, str(installed_check), "--installed"]),
    ]:
        if not Path(args[1]).is_file():
            report.fail("Installed Project Smoke Test", name, f"script missing: {args[1]}")
            continue
        result = run_command(args, cwd=target)
        if result.returncode == 0:
            report.pass_("Installed Project Smoke Test", name, summarize_output(result))
        else:
            report.fail("Installed Project Smoke Test", name, summarize_output(result))


def run_optional_disaster(report: Report) -> None:
    script = ROOT / LHE_SCRIPTS / "enable_disaster_monitoring.py"
    if not script.is_file():
        report.warn("Optional Disaster Monitoring Scaffold", "scaffold", "not present; skipped")
        return
    dry_root = TMP_ROOT / "codex-full-disaster-dry-run"
    apply_root = TMP_ROOT / "codex-full-disaster-apply"
    safe_rmtree(dry_root)
    safe_rmtree(apply_root)
    dry_root.mkdir(parents=True, exist_ok=True)
    apply_root.mkdir(parents=True, exist_ok=True)

    for name, args in [
        ("help", [PYTHON, str(script), "--help"]),
        ("dry-run", [PYTHON, str(script), "--target-root", str(dry_root)]),
        ("apply", [PYTHON, str(script), "--target-root", str(apply_root), "--apply"]),
        ("second apply", [PYTHON, str(script), "--target-root", str(apply_root), "--apply"]),
    ]:
        result = run_command(args)
        if result.returncode == 0:
            report.pass_("Optional Disaster Monitoring Scaffold", name, summarize_output(result))
        else:
            report.fail("Optional Disaster Monitoring Scaffold", name, summarize_output(result))

    expected = [
        ".codex/disaster-monitoring/README.md",
        ".codex/disaster-monitoring/alert-rules.example.md",
        ".codex/disaster-monitoring/sources.example.md",
        ".codex/disaster-monitoring/monitoring-runbook.md",
        ".codex/disaster-monitoring/notifier.example.md",
    ]
    for relative in expected:
        path = apply_root / relative
        if path.is_file():
            report.pass_("Optional Disaster Monitoring Scaffold", relative, "exists")
        else:
            report.fail("Optional Disaster Monitoring Scaffold", relative, "missing")


def run_optional_skillopt(report: Report) -> None:
    script = ROOT / LHE_SCRIPTS / "audit_skill_optimization_readiness.py"
    if not script.is_file():
        report.warn("Optional SkillOpt Readiness", "readiness script", "not present; skipped")
        return
    result = run_command([PYTHON, str(script), "--help"])
    if result.returncode == 0:
        report.pass_("Optional SkillOpt Readiness", "help", summarize_output(result))
    else:
        report.fail("Optional SkillOpt Readiness", "help", summarize_output(result))

    result = run_command([PYTHON, str(script)])
    if result.returncode == 0:
        report.pass_("Optional SkillOpt Readiness", "default run", summarize_output(result))
    else:
        report.fail("Optional SkillOpt Readiness", "default run", summarize_output(result))


def run_python_compile(report: Report) -> None:
    scripts = sorted((ROOT / LHE_SCRIPTS).glob("*.py"))
    scripts_dir = ROOT / "scripts"
    if scripts_dir.is_dir():
        scripts.extend(sorted(scripts_dir.glob("*.py")))
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(TMP_ROOT / "codex-pycache")
    args = [PYTHON, "-m", "py_compile", *[str(path) for path in scripts]]
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        report.pass_("Python Compile", "py_compile", f"compiled {len(scripts)} scripts")
    else:
        report.fail("Python Compile", "py_compile", summarize_output(result))


def run_bidi_scan(report: Report) -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for index, char in enumerate(text):
            if char in BIDI_CONTROLS:
                findings.append(f"{path.relative_to(ROOT)}: U+{ord(char):04X} at char {index}")
    if findings:
        report.fail("Static Checks", "bidi control scan", "\n".join(findings[:20]))
    else:
        report.pass_("Static Checks", "bidi control scan", "No bidi control characters found.")


def run_static_checks(report: Report) -> None:
    result = run_command(["git", "diff", "--check"])
    if result.returncode == 0:
        report.pass_("Static Checks", "git diff --check", "clean")
    else:
        report.fail("Static Checks", "git diff --check", summarize_output(result))

    prompt_style_dirs = sorted(ROOT.glob(".agents/skills/*/prompt-styles"))
    if prompt_style_dirs:
        report.pass_(
            "Static Checks",
            "skill-local prompt-styles",
            ", ".join(str(path.relative_to(ROOT)) for path in prompt_style_dirs),
        )
    else:
        report.warn("Static Checks", "skill-local prompt-styles", "no prompt-styles directories found")
    if (ROOT / "prompts").exists():
        report.fail("Static Checks", "canonical prompt style directory", "root prompts/ exists")
    else:
        report.pass_("Static Checks", "canonical prompt style directory", "no root prompts/ directory")
    if (ROOT / "tests" / "expected-triggers.json").is_file():
        report.pass_("Static Checks", "canonical trigger fixture", "tests/expected-triggers.json exists")
    else:
        report.fail("Static Checks", "canonical trigger fixture", "tests/expected-triggers.json missing")


def check_ci_coverage(report: Report) -> None:
    workflow = ROOT / ".github/workflows/check-skill.yml"
    if not workflow.is_file():
        report.warn("CI Coverage", "workflow", "missing .github/workflows/check-skill.yml")
        return
    text = workflow.read_text(encoding="utf-8")
    for label, fragments in CI_EXPECTED:
        if all(fragment in text for fragment in fragments):
            report.pass_("CI Coverage", label, "covered")
        else:
            report.partial("CI Coverage", label, "not found in workflow")


def print_report(report: Report) -> None:
    print("# Full Codex Skill Validation Report")
    ordered_sections = [
        "Repository State",
        "Required File Checks",
        "Optional Integration Checks",
        "Core Command Results",
        "Update / Install Smoke Test",
        "Installed Project Smoke Test",
        "Optional Disaster Monitoring Scaffold",
        "Optional SkillOpt Readiness",
        "Python Compile",
        "Static Checks",
        "CI Coverage",
    ]
    sections = report.by_section()
    for section in ordered_sections:
        print(f"\n## {section}")
        checks = sections.get(section, [])
        if not checks:
            print("- WARN: no checks recorded")
            continue
        for check in checks:
            detail = f" - {check.detail}" if check.detail else ""
            print(f"- {check.status}: {check.name}{detail}")

    print("\n## Warnings")
    warnings = report.warnings()
    if warnings:
        for check in warnings:
            print(f"- {check.section}: {check.name} - {check.detail}")
    else:
        print("- None")

    print("\n## Failures")
    failures = report.failures()
    if failures:
        for check in failures:
            print(f"- {check.section}: {check.name} - {check.detail}")
    else:
        print("- None")

    print("\n## Final Verdict")
    verdict = report.verdict()
    if verdict == "PASS":
        print("PASS: all required checks passed")
    elif verdict == "PASS_WITH_WARNINGS":
        print("PASS_WITH_WARNINGS: required checks passed, optional warnings remain")
    else:
        print("FAIL: one or more required checks failed")


def main() -> int:
    report = Report()
    required_by_checker = load_required_from_check_script()

    check_repo_state(report)
    check_files(
        report,
        "Required File Checks",
        REQUIRED_CORE_FILES,
        required_by_checker=required_by_checker,
        fail_missing=True,
    )
    check_files(
        report,
        "Optional Integration Checks",
        PRODUCTIZED_FILES,
        required_by_checker=required_by_checker,
        fail_missing=False,
    )
    check_files(
        report,
        "Optional Integration Checks",
        CONTENT_RESEARCH_DESIGN_FILES,
        required_by_checker=required_by_checker,
        fail_missing=False,
    )
    check_optional_group(report, "SkillOpt integration", SKILLOPT_FILES, required_by_checker)
    check_optional_group(report, "Disaster monitoring integration", DISASTER_FILES, required_by_checker)
    run_core_commands(report)
    run_update_smoke(report)
    run_installed_project_smoke(report)
    run_optional_disaster(report)
    run_optional_skillopt(report)
    run_python_compile(report)
    run_static_checks(report)
    run_bidi_scan(report)
    check_ci_coverage(report)

    print_report(report)
    return 0 if not report.failures() else 1


if __name__ == "__main__":
    raise SystemExit(main())
