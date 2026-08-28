#!/usr/bin/env python3
"""Run comprehensive local validation for the Codex skill package."""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
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
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
FULL_UNITTEST_TIMEOUT_SECONDS = 300

REQUIRED_CORE_FILES = [
    LHE / "SKILL.md",
    LHE / "catalog/local-capability-catalog.json",
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
    Path("CODE_OF_CONDUCT.md"),
    Path("COMMUNITY_SKILLS.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path(".github/ISSUE_TEMPLATE/bug_report.md"),
    Path(".github/ISSUE_TEMPLATE/config.yml"),
    Path(".github/ISSUE_TEMPLATE/feature_request.md"),
    Path(".github/ISSUE_TEMPLATE/skill_proposal.md"),
    Path(".github/pull_request_template.md"),
    Path("docs/demo/README.md"),
    Path("docs/demo/recording-script.md"),
    Path("docs/evals/live-routing.md"),
    Path("docs/first-contribution.md"),
    Path("docs/maintainers/release-checklist.md"),
    Path("docs/plugin-install.md"),
    Path("docs/customer-guided-workflow.md"),
    Path("docs/high-stakes-customer-workflows.md"),
    Path("docs/releases/v0.1.0.md"),
    Path("docs/releases/v0.2.0.md"),
    Path("docs/releases/v0.2.1.md"),
    Path("docs/releases/v0.2.2.md"),
    Path("docs/releases/v0.2.3.md"),
    Path("docs/releases/v0.2.4.md"),
    Path("docs/releases/v0.3.0.md"),
    Path("docs/releases/v0.3.1.md"),
    Path("docs/releases/v0.3.2.md"),
    Path("examples/bug-investigation/expected-output.md"),
    Path("examples/bug-investigation/prompt.md"),
    Path("examples/bug-investigation/workflow.md"),
    Path("examples/large-refactor/expected-output.md"),
    Path("examples/large-refactor/prompt.md"),
    Path("examples/large-refactor/workflow.md"),
    Path("examples/repository-migration/expected-output.md"),
    Path("examples/repository-migration/prompt.md"),
    Path("examples/repository-migration/workflow.md"),
    Path("examples/resume-work/expected-output.md"),
    Path("examples/resume-work/prompt.md"),
    Path("examples/resume-work/workflow.md"),
    Path("examples/customer-guided-decision/expected-output.md"),
    Path("examples/customer-guided-decision/prompt.md"),
    Path("examples/customer-guided-decision/workflow.md"),
    Path("examples/high-stakes-customer-workflows.md"),
    Path("sandbox/skill-incubator/architecture/local-capability-catalog.md"),
    Path("sandbox/skill-incubator/architecture/local-case-evidence-provider.json"),
    Path("sandbox/skill-incubator/architecture/local-case-evidence-provider.md"),
    Path("sandbox/skill-incubator/schemas/local-capability-catalog.schema.json"),
    Path("sandbox/skill-incubator/schemas/local-case-evidence-provider.schema.json"),
    Path("scripts/generate_skill_catalog.py"),
    Path("scripts/validate_plugin_package.py"),
    Path("scripts/test_fresh_install.py"),
    Path("scripts/check_release_readiness.py"),
    Path("scripts/assemble_skill_profile.py"),
    Path("scripts/skill_update_selfcheck.py"),
    Path("scripts/test_skill_update_selfcheck.py"),
    Path("scripts/test_assemble_skill_profile.py"),
    Path("releases/latest.json"),
    Path("releases/long-horizon-engineering/latest.json"),
    Path("releases/ai-video-production/latest.json"),
    Path("tests/test_release_tooling.py"),
    Path(".codex-plugin/plugin.json"),
    Path(".agents/plugins/marketplace.json"),
    Path("prompts/bug-investigation.md"),
    Path("prompts/large-refactor.md"),
    Path("prompts/pr-review.md"),
    Path("prompts/repository-migration.md"),
    Path("prompts/resume-work.md"),
    Path("prompts/customer-guided-decision.md"),
    Path("templates/findings-report.md"),
    Path("templates/migration-report.md"),
    Path("templates/project-plan.md"),
    Path("templates/validation-report.md"),
]

PRODUCTIZED_FILES = [
    LHE / "references/repomix-codebase-context.md",
    LHE / "references/skill-authoring-methodology.md",
    LHE / "references/external-search-protocol.md",
    LHE / "references/explicit-only-extensions.md",
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
    [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
    [PYTHON, "scripts/generate_skill_catalog.py", "--check"],
    [PYTHON, "scripts/validate_plugin_package.py"],
    [PYTHON, "scripts/test_fresh_install.py", "--skip-codex-cli"],
    [
        PYTHON,
        "scripts/check_release_readiness.py",
        "--version",
        "0.6.1",
        "--release-state",
        "__RELEASE_STATE__",
        "--allow-existing-tag",
    ],
    [PYTHON, "scripts/test_skill_update_selfcheck.py"],
    [PYTHON, "scripts/test_assemble_skill_profile.py"],
    ["git", "diff", "--check"],
]

FULL_UNITTEST_COMMAND = [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

CI_EXPECTED = [
    ("check_skill_package.py", ["check_skill_package.py"]),
    ("doctor.py", ["doctor.py"]),
    ("test_expected_triggers.py", ["test_expected_triggers.py"]),
    ("audit_skill_descriptions.py", ["audit_skill_descriptions.py"]),
    ("update_installed_skill.py --list-skills", ["update_installed_skill.py", "--list-skills"]),
    ("release tooling unit tests", ["unittest", "discover"]),
    ("generate_skill_catalog.py --check", ["generate_skill_catalog.py", "--check"]),
    ("validate_plugin_package.py", ["validate_plugin_package.py"]),
    ("test_fresh_install.py --skip-codex-cli", ["test_fresh_install.py", "--skip-codex-cli"]),
    ("skill_update_selfcheck.py --help", ["skill_update_selfcheck.py", "--help"]),
    ("test_skill_update_selfcheck.py", ["test_skill_update_selfcheck.py"]),
    ("test_assemble_skill_profile.py", ["test_assemble_skill_profile.py"]),
    ("Python compile check", ["py_compile"]),
    ("git diff --check", ["git", "diff", "--check"]),
    ("update dry-run smoke test", ["update_installed_skill.py", "--target-root"]),
]


def _workflow_steps(text: str) -> list[str]:
    steps: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("      - name:"):
            if current is not None:
                steps.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        steps.append(current)
    return ["\n".join(step) for step in steps]


def release_gate_workflow_errors(text: str) -> list[str]:
    """Validate dynamic release-state gates against their event contexts."""
    errors: list[str] = []
    if "  pull_request:" not in text:
        errors.append("workflow must retain pull_request coverage")
    if "  push:" not in text or "      - main" not in text:
        errors.append("workflow must retain push-to-main coverage")

    jobs: dict[str, str] = {}
    in_jobs = False
    current_job: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if in_jobs and re.fullmatch(r"  [A-Za-z0-9_-]+:", line):
            if current_job is not None:
                jobs[current_job] = "\n".join(current_lines)
            current_job = line.strip()[:-1]
            current_lines = [line]
            continue
        if current_job is not None:
            current_lines.append(line)
    if current_job is not None:
        jobs[current_job] = "\n".join(current_lines)

    for job_name in ("check-skill", "formal-schema-gate"):
        if job_name not in jobs:
            errors.append(f"workflow must retain {job_name} job")

    dynamic_state = '--release-state "${{ steps.release-state.outputs.state }}"'

    def readiness_steps(job_text: str) -> list[str]:
        return [
            step
            for step in _workflow_steps(job_text)
            if "scripts/check_release_readiness.py" in step
            and "--release-state" in step
        ]

    def has_state_resolver(job_text: str) -> bool:
        return any(
            "id: release-state" in step
            and "scripts/full_skill_validation.py --print-release-state" in step
            for step in _workflow_steps(job_text)
        )

    check_steps = readiness_steps(jobs.get("check-skill", ""))
    formal_steps = readiness_steps(jobs.get("formal-schema-gate", ""))
    if not has_state_resolver(jobs.get("check-skill", "")):
        errors.append("check-skill job must resolve Release state through the shared parser")
    if not has_state_resolver(jobs.get("formal-schema-gate", "")):
        errors.append("formal-schema-gate job must resolve Release state through the shared parser")

    check_pr_steps = [
        step for step in check_steps if "if: github.event_name == 'pull_request'" in step
    ]
    if not check_pr_steps:
        errors.append("check-skill pull_request readiness gate is missing")
    else:
        step = check_pr_steps[0]
        if dynamic_state not in step:
            errors.append("pull_request readiness gate must use the shared dynamic Release state")
        if "--allow-existing-tag" not in step:
            errors.append("pull_request readiness gate must use --allow-existing-tag")
        if "--pre-tag" in step or "--pre-tag-static" in step:
            errors.append("pull_request readiness gate must not use a pre-tag mode")

    check_main_steps = [
        step
        for step in check_steps
        if "if: github.event_name == 'push'" in step and "refs/heads/main" in step
    ]
    if not check_main_steps:
        errors.append("check-skill final readiness gate must be scoped to push on main")
    else:
        step = check_main_steps[0]
        if "--release-state final" not in step:
            errors.append("push-main check-skill gate must use final release state")
        if "--allow-existing-tag" not in step:
            errors.append("push-main check-skill gate must use --allow-existing-tag")

    formal_pr_steps = [
        step for step in formal_steps if "if: github.event_name == 'pull_request'" in step
    ]
    if not formal_pr_steps:
        errors.append("formal-schema-gate pull_request readiness gate is missing")
    else:
        step = formal_pr_steps[0]
        if dynamic_state not in step:
            errors.append("formal pull_request gate must use the shared dynamic Release state")
        if "--allow-existing-tag" not in step:
            errors.append("formal pull_request gate must use --allow-existing-tag")
        if "--pre-tag" in step or "--pre-tag-static" in step:
            errors.append("formal pull_request gate must not use a pre-tag mode")

    formal_main_steps = [
        step
        for step in formal_steps
        if "if: github.event_name == 'push'" in step and "refs/heads/main" in step
    ]
    if not formal_main_steps:
        errors.append("formal main readiness gate must be scoped to push on main")
    elif dynamic_state not in formal_main_steps[0]:
        errors.append("formal main gate must use the shared dynamic Release state")

    for job_name, job_text in jobs.items():
        for step in readiness_steps(job_text):
            is_pull_request = "if: github.event_name == 'pull_request'" in step
            is_main_push = (
                "if: github.event_name == 'push'" in step
                and "refs/heads/main" in step
            )
            if not (is_pull_request or is_main_push):
                errors.append(f"readiness gate in {job_name} has no allowed event context")
            if is_pull_request and ("--pre-tag" in step or "--pre-tag-static" in step):
                errors.append(f"{job_name} pull_request gate must not invoke a pre-tag mode")

    if "--pre-tag" in text or "--pre-tag-static" in text:
        errors.append("workflow must not invoke --pre-tag or --pre-tag-static")
    return errors


def check_skill_formal_evidence_workflow_errors(text: str) -> list[str]:
    """Validate the ordinary CI formal evidence path and its retained artifact."""
    errors: list[str] = []
    executable = "\n".join(line.split("#", 1)[0].rstrip() for line in text.splitlines())
    match = re.search(r"(?ms)^  formal-schema-gate:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", executable)
    if match is None:
        return ["check-skill formal-schema-gate job is missing"]
    job = match.group("body")
    steps = _workflow_steps(job)
    named = {step.splitlines()[0].strip(): step for step in steps if step.splitlines()}
    identity = [step for step in steps if step.strip().startswith("- name: Record formal runner identity")]
    acquire = [step for step in steps if "--verify-acquisition" in step]
    upload = [step for step in steps if "actions/upload-artifact@" in step]
    if len(identity) != 1:
        errors.append("formal-schema-gate must have exactly one formal runner identity step")
    if len(acquire) != 1 or job.count("--verify-acquisition") != 1:
        errors.append("formal-schema-gate must perform exactly one acquisition")
    if len(upload) != 1:
        errors.append("formal-schema-gate must have exactly one formal evidence upload step")
    if "runs-on: ubuntu-24.04" not in job or "permissions:\n      contents: read" not in job:
        errors.append("formal-schema-gate runner or permissions contract is missing")
    for action, sha in {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    }.items():
        if f"{action}@{sha}" not in job:
            errors.append(f"formal-schema-gate missing approved action pin: {action}")
    if identity:
        step = identity[0]
        if 'RUNNER_IDENTITY="$RUNNER_TEMP/formal-schema-runner-identity.json"' not in step:
            errors.append("formal runner identity path is not fixed")
        if 'WORKFLOW_SHA256="$(sha256sum "$WORKFLOW_PATH" | awk' not in step:
            errors.append("formal runner identity workflow SHA must come from the checked-out file")
        heredoc = re.search(r"<<'PY'\n(?P<body>.*?)\n\s*PY", step, re.S)
        if heredoc is None:
            errors.append("formal runner identity must contain a Python heredoc")
        else:
            try:
                tree = ast.parse(textwrap.dedent(heredoc.group("body")))
                payloads = [node for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "payload" for t in node.targets)]
                dumps = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "dump"]
                if len(payloads) != 1 or not isinstance(payloads[0].value, ast.Dict):
                    errors.append("formal runner identity payload must be one dict")
                else:
                    pairs = {k.value: v for k, v in zip(payloads[0].value.keys, payloads[0].value.values) if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                    if set(pairs) != {"github_run_id", "github_run_attempt", "workflow_ref", "job", "repository", "event_target_sha", "release_commit", "candidate_base", "workflow_identity", "actions"}:
                        errors.append("formal runner identity payload keys are not closed")
                    for key, env_name in (("repository", "FORMAL_REPOSITORY"), ("event_target_sha", "FORMAL_EVENT_TARGET_SHA")):
                        node = pairs.get(key)
                        if not (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) and node.value.value.id == "os" and node.value.attr == "environ" and isinstance(node.slice, ast.Constant) and node.slice.value == env_name):
                            errors.append(f"runner identity {key} must come from {env_name}")
                    for key, expected in {
                        "candidate_base": ("FORMAL_CANDIDATE_BASE", "candidate_base must come from FORMAL_CANDIDATE_BASE"),
                    }.items():
                        node = pairs.get(key)
                        if not (
                            isinstance(node, ast.Subscript)
                            and isinstance(node.value, ast.Attribute)
                            and isinstance(node.value.value, ast.Name)
                            and node.value.value.id == "os"
                            and node.value.attr == "environ"
                            and isinstance(node.slice, ast.Constant)
                            and node.slice.value == expected[0]
                        ):
                            errors.append(expected[1])
                    if "formal-release-gate.yml" in text:
                        release_node = pairs.get("release_commit")
                        if not (isinstance(release_node, ast.Name) and release_node.id == "release_commit"):
                            errors.append("release_commit must come from the same-step explicit release_commit argument")
                        if '"$release_commit"' not in step:
                            errors.append("runner identity must receive release_commit explicitly in the same step")
                    actions = pairs.get("actions")
                    action_pairs = {} if not isinstance(actions, ast.Dict) else {k.value: v.value for k, v in zip(actions.keys, actions.values) if isinstance(k, ast.Constant) and isinstance(k.value, str) and isinstance(v, ast.Constant) and isinstance(v.value, str)}
                    if action_pairs != {"checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1", "setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97", "upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02"}:
                        errors.append("formal runner identity actions are not the approved closed set")
                    workflow_identity = pairs.get("workflow_identity")
                    if not isinstance(workflow_identity, ast.Dict) or not any(isinstance(k, ast.Constant) and k.value == "path" and isinstance(v, ast.Name) and v.id == "workflow_path" for k, v in zip(workflow_identity.keys, workflow_identity.values)):
                        errors.append("formal runner identity workflow path is not bound to workflow_path")
                if len(dumps) != 1 or not dumps[0].args or not isinstance(dumps[0].args[0], ast.Name) or dumps[0].args[0].id != "payload":
                    errors.append("formal runner identity must json.dump(payload, handle) exactly once")
            except SyntaxError as exc:
                errors.append(f"formal runner identity heredoc is invalid: {exc}")
    if acquire:
        step = acquire[0]
        for fragment in ('--action-provenance-file "$RUNNER_TEMP/formal-schema-runner-identity.json"', '--workflow-sha256 "$WORKFLOW_SHA256"', '--workflow-path ".github/workflows/check-skill.yml"', '--candidate-base "$FORMAL_CANDIDATE_BASE"'):
            if fragment not in step:
                errors.append(f"acquisition missing required fragment: {fragment}")
    for context in ("if: github.event_name == 'pull_request'", "if: github.event_name == 'push' && github.ref == 'refs/heads/main'"):
        paths = [step for step in steps if context in step and "check_release_readiness.py" in step]
        required = (
            '--formal-schema-action-provenance-file "$RUNNER_TEMP/formal-schema-runner-identity.json"',
            '--formal-schema-workflow-sha256 "$WORKFLOW_SHA256"',
            '--formal-schema-workflow-path ".github/workflows/check-skill.yml"',
            '--formal-schema-event-target-sha "$FORMAL_EVENT_TARGET_SHA"',
            '--formal-schema-repository "$FORMAL_REPOSITORY"',
        )
        if len(paths) != 1 or any(fragment not in paths[0] for fragment in required):
            errors.append(f"readiness path missing action provenance for context: {context}")
    if upload:
        step = upload[0]
        for fragment in ("if: always()", "retention-days: 90", "if-no-files-found: error", "formal-schema-runner-identity.json", "formal-schema-result.json", "formal-schema-evidence", "formal-schema-pip-report.json"):
            if fragment not in step:
                errors.append(f"formal evidence upload missing required fragment: {fragment}")
    if "--pre-tag" in job or "git tag" in job or "git push" in job or "gh release" in job or "update_installed_skill.py --apply" in job or "marketplace" in job.lower():
        errors.append("ordinary formal CI must not publish, install, or use pre-tag")
    validator_path = ROOT / "scripts/validate_formal_schemas.py"
    if validator_path.is_file():
        source = validator_path.read_text(encoding="utf-8")
        preflight = source.find("preflight_acquisition_context(")
        acquisition = source.find("errors, payload = acquire_evidence(", preflight + 1)
        guarded = source.find("if preflight_errors:", preflight + 1)
        if preflight < 0 or acquisition < 0 or guarded < 0 or not (preflight < guarded < acquisition):
            errors.append("verify-acquisition must fail closed through preflight before acquisition")
    else:
        errors.append("formal validator source is missing for acquisition preflight contract")
    return errors


def formal_release_evidence_workflow_errors(text: str) -> list[str]:
    """Validate the manual Phase B workflow as a small fail-closed YAML shape."""
    errors: list[str] = []
    executable = "\n".join(
        line.split("#", 1)[0].rstrip() for line in text.splitlines()
    )
    lines = executable.splitlines()
    step_lines = executable.splitlines()
    try:
        start = next(i for i, line in enumerate(step_lines) if line.strip() == "- name: Record runner identity and initialize retained evidence paths")
        end = next((i for i in range(start + 1, len(step_lines)) if step_lines[i].startswith("      - name:")), len(step_lines))
        identity_step = "\n".join(step_lines[start:end])
    except StopIteration:
        identity_step = ""
        errors.append("runner identity recording step is missing")
    if identity_step:
        heredoc = re.search(r"<<'PY'\n(?P<body>.*?)\n\s*PY", identity_step, re.S)
        if heredoc is None:
            errors.append("runner identity step must contain a Python heredoc")
        else:
            try:
                tree = ast.parse(textwrap.dedent(heredoc.group("body")))
                payload_assignments = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "payload" for target in node.targets)
                ]
                if len(payload_assignments) != 1 or not isinstance(payload_assignments[0].value, ast.Dict):
                    errors.append("runner identity must define exactly one payload dict")
                else:
                    payload = payload_assignments[0].value
                    pairs = {
                        key.value: value
                        for key, value in zip(payload.keys, payload.values)
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }
                    action_node = pairs.get("actions")
                    if not isinstance(action_node, ast.Dict):
                        errors.append("runner identity payload actions must be a dict")
                    else:
                        action_pairs = {
                            key.value: value.value
                            for key, value in zip(action_node.keys, action_node.values)
                            if isinstance(key, ast.Constant) and isinstance(key.value, str)
                            and isinstance(value, ast.Constant) and isinstance(value.value, str)
                        }
                        if action_pairs != {
                            "checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
                            "setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
                            "upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
                        }:
                            errors.append("runner identity payload actions are not the exact approved closed set")
                    candidate_node = pairs.get("candidate_base")
                    if not (
                        isinstance(candidate_node, ast.Subscript)
                        and isinstance(candidate_node.value, ast.Attribute)
                        and isinstance(candidate_node.value.value, ast.Name)
                        and candidate_node.value.value.id == "os"
                        and candidate_node.value.attr == "environ"
                        and isinstance(candidate_node.slice, ast.Constant)
                        and candidate_node.slice.value == "CANDIDATE_BASE"
                    ):
                        errors.append("runner identity candidate_base must be os.environ[\"CANDIDATE_BASE\"]")
                dumps = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "dump"
                ]
                if len(dumps) != 1 or not dumps[0].args or not isinstance(dumps[0].args[0], ast.Name) or dumps[0].args[0].id != "payload":
                    errors.append("runner identity must json.dump(payload, handle) exactly once")
            except SyntaxError as exc:
                errors.append(f"runner identity heredoc is not valid Python: {exc}")
        if 'python3 - "$RUNNER_IDENTITY"' not in identity_step or 'with open(path, "w"' not in identity_step:
            errors.append("runner identity step must write the declared runner identity path")
        identity_assignment = 'RUNNER_IDENTITY="$RUNNER_TEMP/lhe-v0.6.1-runner-identity.json"'
        persistence = "printf 'RUNNER_IDENTITY=%s\\n' \"$RUNNER_IDENTITY\" >> \"$GITHUB_ENV\""
        if identity_step.count(identity_assignment) != 1:
            errors.append("RUNNER_IDENTITY must have exactly one definition")
        assignments = re.findall(r"(?m)^\s*RUNNER_IDENTITY=", identity_step)
        if len(assignments) != 1:
            errors.append("RUNNER_IDENTITY must not be reassigned")
        if identity_step.count(persistence) != 1:
            errors.append("RUNNER_IDENTITY persistence writer is missing or duplicated")
        if 'test -s "$RUNNER_IDENTITY"' not in identity_step:
            errors.append("runner identity must be non-empty before persistence")
        if identity_step.find('test -s "$RUNNER_IDENTITY"') > identity_step.find(persistence):
            errors.append("RUNNER_IDENTITY persistence must follow identity validation")
        if 'export RUNNER_IDENTITY=' in executable or '${RUNNER_IDENTITY:-' in executable:
            errors.append("RUNNER_IDENTITY must not have export or fallback reassignment")
    if executable.count('with open(path, "w"') != 1:
        errors.append("runner identity must have exactly one writer")
    if executable.count("printf 'RUNNER_IDENTITY=%s\\n'") != 1:
        errors.append("formal evidence workflow must have exactly one RUNNER_IDENTITY GITHUB_ENV writer")
    if 'RUNNER_IDENTITY="$RUNNER_TEMP/lhe-v0.6.1-runner-identity.json"' in executable:
        consumers = [
            line for line in lines
            if '--action-provenance-file "$RUNNER_IDENTITY"' in line
            or '--formal-schema-action-provenance-file "$RUNNER_IDENTITY"' in line
        ]
        if len(consumers) != 2:
            errors.append("acquisition and replay must consume the persisted RUNNER_IDENTITY")
        if '${{ runner.temp }}/lhe-v0.6.1-runner-identity.json' not in executable:
            errors.append("artifact must include the persisted runner identity")
    if executable.count("  workflow_dispatch:") != 1 or any(
        f"  {event}:" in executable
        for event in ("push", "pull_request", "schedule", "repository_dispatch")
    ):
        errors.append("formal evidence workflow must only use workflow_dispatch")
    try:
        permission_start = lines.index("permissions:")
        permission_end = next(
            index for index in range(permission_start + 1, len(lines))
            if lines[index] and not lines[index].startswith(" ")
        )
        body = [line for line in lines[permission_start + 1:permission_end] if line]
    except (ValueError, StopIteration):
        body = []
    if body:
        if body != ["  contents: read"]:
            errors.append("formal evidence workflow permissions must be exactly contents: read")
    else:
        errors.append("formal evidence workflow permissions are missing")
    if any(token in executable for token in ("actions: write", "contents: write", "id-token: write")):
        errors.append("formal evidence workflow grants write permissions")
    if executable.count("permissions:") != 1:
        errors.append("formal evidence workflow must have exactly one permissions block")
    if "permissions:\n  contents: read" not in executable:
        errors.append("formal evidence workflow must grant only contents: read")
    for fragment in (
        "runs-on: ubuntu-24.04",
        'python-version: "3.11.15"',
        "architecture: x64",
        "fetch-depth: 0",
        "persist-credentials: false",
        "ref: ${{ github.sha }}",
        'RELEASE_VERSION: "0.6.1"',
        'RELEASE_TAG: "v0.6.1"',
        "--verify-acquisition",
        "--pre-tag",
        "--workflow-sha256",
        "--workflow-path .github/workflows/formal-release-gate.yml",
        "--formal-schema-result",
        "--formal-schema-acquisition-result",
        "--formal-schema-pip-report",
        "--formal-schema-evidence-dir",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "retention-days: 90",
        "if-no-files-found: error",
        "test ! -e \"$EVIDENCE_DIR\"",
        "sha256sum .github/workflows/formal-release-gate.yml",
        'WORKFLOW_SHA256="$(sha256sum .github/workflows/formal-release-gate.yml | awk',
        'RUNNER_IDENTITY="$RUNNER_TEMP/lhe-v0.6.1-runner-identity.json"',
        'test "$GITHUB_REF" = "refs/heads/main"',
        'release_commit="$GITHUB_SHA"',
        'parent_line="$(git rev-list --parents -n 1 "$release_commit")"',
        'test "$#" -eq 2',
        'candidate_base="$2"',
        'test "$(git merge-base "$candidate_base" "$release_commit")" = "$candidate_base"',
        '--workflow-sha256 "$WORKFLOW_SHA256"',
        '${{ runner.temp }}/lhe-v0.6.1-runner-identity.json',
    ):
        if fragment not in text:
            errors.append(f"formal evidence workflow missing required fragment: {fragment}")
    if text.count("--verify-acquisition") != 1:
        errors.append("formal evidence workflow must perform exactly one acquisition")
    if "--allow-existing-tag" in executable or re.search(r"(?m)^\s*git (tag|push)\b", executable) or "gh release" in executable or "gh workflow run" in executable:
        errors.append("formal evidence workflow must not tag, push, release, or use allow-existing-tag")
    if "update_installed_skill.py --apply" in executable or "marketplace" in executable.lower() or "codex plugin" in executable.lower():
        errors.append("formal evidence workflow must not update installed skills or marketplace")
    if "if: always()" not in executable:
        errors.append("formal evidence upload must run after failure")
    if "path: |" not in executable or "runner-identity.json" not in executable:
        errors.append("formal evidence artifact must include runner identity")
    for artifact in ("formal-result.json", "acquisition-receipt.json", "formal-schema-pip-report.json", "formal-schema-evidence-"):
        if artifact not in executable:
            errors.append(f"formal evidence artifact is missing {artifact}")
    if executable.count("--verify-acquisition") != 1:
        errors.append("formal evidence workflow must perform exactly one acquisition")
    if executable.count("--pre-tag") != 1 or "--pre-tag-static" in executable:
        errors.append("formal evidence workflow must use exactly one offline --pre-tag replay")
    if "workflow_dispatch:" in executable and "inputs:" in executable:
        errors.append("formal evidence workflow must not accept override inputs")
    if "${{ inputs." in executable or "${{ github.ref_name" in executable or "${{ github.ref }}" in executable:
        errors.append("formal evidence workflow identity must not be overrideable by dispatch input or branch ref")
    action_refs = re.findall(r"(?m)^\s*uses:\s*(actions/[^@\s]+)@([^\s]+)", executable)
    expected_actions = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    }
    for action, ref in action_refs:
        if action not in expected_actions or ref != expected_actions[action]:
            errors.append(f"formal evidence action is not pinned to its reviewed full SHA: {action}@{ref}")
    action_identity = {
        "checkout": expected_actions.get("actions/checkout"),
        "setup-python": expected_actions.get("actions/setup-python"),
        "upload-artifact": expected_actions.get("actions/upload-artifact"),
    }
    identity_lines = {
        key: re.search(rf'"{re.escape(key)}":\s*"([0-9a-f]{{40}})"', executable)
        for key in action_identity
    }
    if any(match is None for match in identity_lines.values()):
        errors.append("runner identity must define all approved action SHA fields")
    else:
        found_identity = {key: match.group(1) for key, match in identity_lines.items()}
        if set(found_identity) != set(action_identity) or found_identity != {
            "checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            "upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
        }:
            errors.append("runner identity action SHA values are not the approved closed set")
    if '"actions": {' not in executable:
        errors.append("runner identity must define an actions object")
    if '"actions": {' in executable:
        action_block = executable.split('"actions": {', 1)[1].split("}", 1)[0]
        keys = re.findall(r'"([^\"]+)":\s*"[0-9a-f]{40}"', action_block)
        if set(keys) != {"checkout", "setup-python", "upload-artifact"}:
            errors.append("runner identity actions keys must be exactly the approved set")
    uses_to_identity = {
        "actions/checkout": "checkout",
        "actions/setup-python": "setup-python",
        "actions/upload-artifact": "upload-artifact",
    }
    for action, ref in action_refs:
        key = uses_to_identity.get(action)
        if key and f'"{key}": "{ref}"' not in executable:
            errors.append(f"runner identity does not match {action} action ref")
    if 'release_commit="$GITHUB_SHA"' not in executable:
        errors.append("formal release commit must derive from GITHUB_SHA")
    if 'candidate_base="$2"' not in executable:
        errors.append("formal candidate base must derive from the unique first parent")
    if executable.count('candidate_base="$2"') != 1:
        errors.append("formal candidate base must have exactly one derivation")
    if executable.count("printf 'CANDIDATE_BASE=%s\\n' \"$candidate_base\" >> \"$GITHUB_ENV\"") != 1:
        errors.append("formal candidate base must have exactly one GITHUB_ENV export")
    if re.search(r'(?m)^\s*(?:export\s+)?CANDIDATE_BASE\s*=', executable):
        errors.append("formal candidate base must not be reassigned")
    env_writers = re.findall(r'(?:printf|echo).*CANDIDATE_BASE=.*>>\s*\"\$GITHUB_ENV\"', executable)
    if len(env_writers) != 1:
        errors.append("formal candidate base must not have a second GITHUB_ENV writer")
    if executable.count("--candidate-base") != 1 or not re.search(r'--candidate-base\s+"\$CANDIDATE_BASE"', executable):
        errors.append("acquisition must use exactly --candidate-base \"$CANDIDATE_BASE\"")
    if executable.count("--formal-schema-candidate-base") != 1 or not re.search(r'--formal-schema-candidate-base\s+"\$CANDIDATE_BASE"', executable):
        errors.append("replay must use exactly --formal-schema-candidate-base \"$CANDIDATE_BASE\"")
    if re.search(r'--(?:candidate-base|formal-schema-candidate-base)\s+"?\$\{CANDIDATE_BASE(?::-[^}]*)?\}', executable):
        errors.append("formal candidate base must not use fallback or alternate expansion")
    if re.search(r'(?m)^\s*(RELEASE_COMMIT|CANDIDATE_BASE)\s*:', executable):
        errors.append("formal release identity must not be hardcoded in workflow env")
    return errors


OPTIONAL_WARNING_WAIVERS = {
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/scripts/audit_skill_optimization_readiness.py",
        "optional related file missing",
    ): (
        "SKILLOPT_RUNNER_NOT_BUNDLED: the retained SkillOpt material is "
        "documentation-only; adding an executable optimizer runner requires a "
        "separate implementation and dependency review."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/references/disaster-monitoring-protocol.md",
        "optional related file missing",
    ): (
        "DISASTER_MONITORING_INCOMPLETE: enablement guidance is retained for "
        "reference, but no complete monitoring capability is bundled or claimed."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/scripts/enable_disaster_monitoring.py",
        "optional related file missing",
    ): (
        "DISASTER_AUTOMATION_NOT_BUNDLED: no installer or state-writing "
        "monitoring automation is included."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/situation-report.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/source-reliability-table.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/incident-timeline.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/affected-area-summary.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/public-safety-communication-checklist.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Integration Checks",
        ".agents/skills/long-horizon-engineering/templates/public-alert-draft.md",
        "optional related file missing",
    ): (
        "DISASTER_TEMPLATE_NOT_BUNDLED: the optional monitoring scaffold is "
        "intentionally incomplete and non-callable."
    ),
    (
        "Optional Disaster Monitoring Scaffold",
        "scaffold",
        "not present; skipped",
    ): (
        "DISASTER_AUTOMATION_NOT_BUNDLED: the missing enablement script keeps "
        "the optional monitoring workflow non-executable."
    ),
    (
        "Optional SkillOpt Readiness",
        "readiness script",
        "not present; skipped",
    ): (
        "SKILLOPT_RUNNER_NOT_BUNDLED: readiness execution is unavailable until "
        "a separately reviewed runner exists."
    ),
}
ALLOWED_RELEASE_WARNINGS = set(OPTIONAL_WARNING_WAIVERS)

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


def subprocess_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_command(
    args: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = subprocess_text(exc.stdout)
        stderr = subprocess_text(exc.stderr)
        message = f"command timed out after {timeout} seconds"
        stderr = f"{stderr.rstrip()}\n{message}\n" if stderr else f"{message}\n"
        return subprocess.CompletedProcess(args, 124, stdout=stdout, stderr=stderr)


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


def release_state_for_validation() -> str:
    """Read exactly one supported release state from the active release note."""
    notes = ROOT / "docs/releases/v0.6.1.md"
    try:
        text = notes.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read active release note: {exc}") from exc
    states = re.findall(r"^Release state:\s*(candidate|final)\s*$", text, re.MULTILINE)
    if len(states) != 1:
        raise ValueError("active release note must contain exactly one supported Release state")
    return states[0]


def run_core_commands(report: Report) -> None:
    try:
        release_state = release_state_for_validation()
    except ValueError as exc:
        report.fail("Core Command Results", "release-state selector", str(exc))
        return

    commands = [
        [release_state if arg == "__RELEASE_STATE__" else arg for arg in args]
        for args in CORE_COMMANDS
    ]
    for args in commands:
        timeout = (
            FULL_UNITTEST_TIMEOUT_SECONDS
            if args == FULL_UNITTEST_COMMAND
            else DEFAULT_COMMAND_TIMEOUT_SECONDS
        )
        result = run_command(args, timeout=timeout)
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
    for skill in ["long-horizon-engineering", "ai-video-production"]:
        result = run_command(
            [
                PYTHON,
                str(update_script),
                "--target-root",
                str(target),
                "--skill",
                skill,
                "--apply",
            ]
        )
        if result.returncode == 0:
            report.pass_("Installed Project Smoke Test", f"install {skill}", summarize_output(result))
        else:
            report.fail("Installed Project Smoke Test", f"install {skill}", summarize_output(result))

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
    ai_video_scripts = ROOT / AI_VIDEO / "scripts"
    if ai_video_scripts.is_dir():
        scripts.extend(sorted(ai_video_scripts.glob("*.py")))
    scripts_dir = ROOT / "scripts"
    if scripts_dir.is_dir():
        scripts.extend(sorted(scripts_dir.glob("*.py")))
    tests_dir = ROOT / "tests"
    if tests_dir.is_dir():
        scripts.extend(sorted(tests_dir.glob("*.py")))
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
    prompt_library = ROOT / "prompts"
    if prompt_library.is_dir() and any(prompt_library.glob("*.md")):
        report.pass_("Static Checks", "root prompt library", "prompts/ contains copy-paste prompts")
    else:
        report.fail("Static Checks", "root prompt library", "prompts/ is missing markdown prompts")
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
    yaml_check = subprocess.run(
        [
            "ruby", "-e",
            'require "yaml"; ARGV.each { |path| YAML.load_file(path) }',
            str(workflow),
            str(ROOT / ".github/workflows/formal-release-gate.yml"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if yaml_check.returncode != 0:
        report.fail("CI Coverage", "workflow YAML syntax", summarize_output(yaml_check))
    else:
        report.pass_("CI Coverage", "workflow YAML syntax", "Ruby Psych parsed both workflows")
    for label, fragments in CI_EXPECTED:
        if all(fragment in text for fragment in fragments):
            report.pass_("CI Coverage", label, "covered")
        else:
            report.partial("CI Coverage", label, "not found in workflow")
    gate_errors = release_gate_workflow_errors(text)
    if gate_errors:
        for error in gate_errors:
            report.fail("CI Coverage", "release readiness lifecycle gates", error)
    else:
        report.pass_(
            "CI Coverage",
            "release readiness lifecycle gates",
            "candidate PR and main final contexts covered",
        )
    formal_ci_errors = check_skill_formal_evidence_workflow_errors(text)
    if formal_ci_errors:
        for error in formal_ci_errors:
            report.fail("CI Coverage", "formal-schema-gate evidence chain", error)
    else:
        report.pass_("CI Coverage", "formal-schema-gate evidence chain", "runner provenance and retained artifact covered")
    formal_workflow = ROOT / ".github/workflows/formal-release-gate.yml"
    if not formal_workflow.is_file():
        report.fail("CI Coverage", "formal release evidence gate", "workflow is missing")
    else:
        formal_errors = formal_release_evidence_workflow_errors(
            formal_workflow.read_text(encoding="utf-8")
        )
        if formal_errors:
            for error in formal_errors:
                report.fail("CI Coverage", "formal release evidence gate", error)
        else:
            report.pass_("CI Coverage", "formal release evidence gate", "fixed manual Phase B contract covered")


def enforce_release_warning_allowlist(report: Report) -> None:
    for check in list(report.warnings()):
        key = (check.section, check.name, check.detail)
        waiver = OPTIONAL_WARNING_WAIVERS.get(key)
        if waiver is None:
            report.fail(
                "Release Warning Gate",
                check.name,
                f"unapproved warning from {check.section}: {check.detail}",
            )
        else:
            report.pass_("Release Warning Waivers", check.name, waiver)


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
        "Release Warning Waivers",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-release-state",
        action="store_true",
        help="print the single active release-note state and perform no other checks",
    )
    args = parser.parse_args(argv)
    if args.print_release_state:
        try:
            print(release_state_for_validation())
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        return 0

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
    enforce_release_warning_allowlist(report)

    print_report(report)
    return 0 if not report.failures() else 1


if __name__ == "__main__":
    raise SystemExit(main())
