#!/usr/bin/env python3
"""Inspect or explicitly assemble a manifest-selected skill profile.

The default mode is read-only: it reports the selected paths and any internal
Markdown references that would be absent from that profile.  ``--apply`` is
required before copying into an empty, caller-specified output directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LHE_PREFIX = ".agents/skills/long-horizon-engineering/"
MANIFEST_PATH = ROOT / LHE_PREFIX / "package-manifest.json"
REFERENCE_RE = re.compile(
    r"(?:references|templates|prompt-styles)/[A-Za-z0-9_.-]+\.md"
)
OPTIONAL_REFERENCE_MARKER = "<!-- profile-optional-reference -->"


class ProfileError(ValueError):
    """A profile is malformed or cannot be assembled safely."""


def load_manifest() -> dict[str, object]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ProfileError("package manifest must be an object")
    return value


def validate_package_path(value: object) -> str:
    """Return one safe manifest-relative path or fail closed."""
    if not isinstance(value, str) or not value:
        raise ProfileError("package path must be a non-empty string")
    if "\\" in value:
        raise ProfileError(f"package path must use forward slashes: {value!r}")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProfileError(f"unsafe package path: {value!r}")
    return value


def selected_paths(manifest: dict[str, object], profile: str) -> list[str]:
    profiles = manifest.get("profiles")
    components = manifest.get("components")
    separate_skills = manifest.get("separate_skills")
    if not isinstance(profiles, dict) or not isinstance(components, dict):
        raise ProfileError("package manifest profile data is malformed")
    selected = profiles.get(profile)
    if not isinstance(selected, dict):
        raise ProfileError(f"unknown profile: {profile}")
    component_ids = selected.get("components")
    separate_ids = selected.get("separate_skills")
    if not isinstance(component_ids, list) or not isinstance(separate_ids, list):
        raise ProfileError(f"profile is malformed: {profile}")

    paths: list[str] = []
    for component_id in component_ids:
        component = components.get(component_id)
        if not isinstance(component_id, str) or not isinstance(component, dict):
            raise ProfileError(f"unknown component in profile: {component_id}")
        component_paths = component.get("paths")
        if not isinstance(component_paths, list):
            raise ProfileError(f"component paths are malformed: {component_id}")
        paths.extend(validate_package_path(item) for item in component_paths)

    if not isinstance(separate_skills, list):
        raise ProfileError("package manifest separate_skills is malformed")
    by_id = {
        item.get("skill_id"): item
        for item in separate_skills
        if isinstance(item, dict) and isinstance(item.get("skill_id"), str)
    }
    for skill_id in separate_ids:
        skill = by_id.get(skill_id)
        if not isinstance(skill_id, str) or not isinstance(skill, dict):
            raise ProfileError(f"unknown separate skill in profile: {skill_id}")
        skill_paths = skill.get("paths")
        if not isinstance(skill_paths, list):
            raise ProfileError(f"separate skill paths are malformed: {skill_id}")
        paths.extend(validate_package_path(item) for item in skill_paths)
    if len(paths) != len(set(paths)):
        raise ProfileError(f"profile contains duplicate paths: {profile}")
    return sorted(paths)


def source_path(relative: str) -> Path:
    """Resolve a selected source file without allowing symlink escape."""
    candidate = ROOT / validate_package_path(relative)
    resolved = candidate.resolve(strict=False)
    root = ROOT.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ProfileError(f"selected source path escapes repository: {relative}")
    return candidate


def lhe_selected_relative_paths(paths: list[str]) -> set[str]:
    return {
        path.removeprefix(LHE_PREFIX)
        for path in paths
        if path.startswith(LHE_PREFIX)
    }


def all_lhe_relative_paths(manifest: dict[str, object]) -> set[str]:
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        raise ProfileError("package manifest profile data is malformed")
    known: set[str] = set()
    for profile in profiles:
        known.update(lhe_selected_relative_paths(selected_paths(manifest, profile)))
    return known


def unresolved_lhe_references(
    paths: list[str], manifest: dict[str, object]
) -> list[dict[str, str]]:
    selected = lhe_selected_relative_paths(paths)
    known = all_lhe_relative_paths(manifest)
    core_paths = lhe_selected_relative_paths(selected_paths(manifest, "core-only"))
    unresolved: list[dict[str, str]] = []
    for relative in sorted(selected):
        if not relative.endswith(".md"):
            continue
        source = source_path(LHE_PREFIX + relative)
        if not source.is_file():
            raise ProfileError(f"selected source path is missing: {relative}")
        text = source.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for reference in sorted(set(REFERENCE_RE.findall(line))):
                if OPTIONAL_REFERENCE_MARKER in line:
                    if reference not in known:
                        raise ProfileError(
                            "profile-optional reference is not declared in the "
                            f"manifest: {relative}:{line_number}: {reference}"
                        )
                    if reference in core_paths:
                        raise ProfileError(
                            "profile-optional reference must not hide a core "
                            f"resource: {relative}:{line_number}: {reference}"
                        )
                    continue
                if reference not in selected:
                    unresolved.append({"source": relative, "reference": reference})
    return unresolved


def validate_output_root(output_root: Path) -> Path:
    output = output_root.expanduser().resolve(strict=False)
    source = ROOT.resolve(strict=True)
    if output == source or source in output.parents or output in source.parents:
        raise ProfileError("output root must be outside the source repository")
    if output.exists() and not output.is_dir():
        raise ProfileError("output root must be a directory when it exists")
    if output.exists() and any(output.iterdir()):
        raise ProfileError("output root must be empty")
    return output


def render_markdown(text: str, selected: set[str], profile: str) -> str:
    """Replace unavailable optional links in an assembled profile entrypoint."""
    rendered: list[str] = []
    for line in text.splitlines(keepends=True):
        if OPTIONAL_REFERENCE_MARKER not in line:
            rendered.append(line)
            continue
        unavailable = {
            reference
            for reference in REFERENCE_RE.findall(line)
            if reference not in selected
        }
        if not unavailable:
            rendered.append(line)
            continue
        for reference in sorted(unavailable):
            token = f"`{reference}`"
            if token not in line:
                raise ProfileError(
                    "cannot safely render unavailable optional reference: "
                    f"{reference}"
                )
            line = line.replace(
                token,
                f"`optional extension not included in profile {profile}`",
            )
        rendered.append(line.replace(f" {OPTIONAL_REFERENCE_MARKER}", ""))
    return "".join(rendered)


def assemble(paths: list[str], output_root: Path, profile: str) -> None:
    output = validate_output_root(output_root)
    selected = lhe_selected_relative_paths(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".profile-assembly-", dir=output.parent))
    try:
        for relative in paths:
            source = source_path(relative)
            if not source.is_file():
                raise ProfileError(f"selected source path is missing: {relative}")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == ".md":
                target.write_text(
                    render_markdown(
                        source.read_text(encoding="utf-8"), selected, profile
                    ),
                    encoding="utf-8",
                )
                shutil.copystat(source, target)
            else:
                shutil.copy2(source, target)
        if output.exists():
            output.rmdir()
        stage.replace(output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.apply and args.output_root is None:
        print("ERROR: --apply requires --output-root", file=sys.stderr)
        return 2
    if args.output_root is not None and not args.apply:
        print("ERROR: --output-root requires --apply", file=sys.stderr)
        return 2
    try:
        paths = selected_paths(load_manifest(), args.profile)
        unresolved = unresolved_lhe_references(paths, load_manifest())
        result = {
            "profile": args.profile,
            "selected_path_count": len(paths),
            "unresolved_lhe_references": unresolved,
            "applied": False,
        }
        if unresolved:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1
        if args.apply:
            assert args.output_root is not None
            assemble(paths, args.output_root, args.profile)
            result["applied"] = True
            result["output_root"] = str(args.output_root.expanduser().resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ProfileError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
