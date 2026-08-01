#!/usr/bin/env python3
"""Contract tests for manifest-selected profile assembly."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_skill_profile.py"
COMMIT = subprocess.run(
    ["git", "rev-parse", "HEAD^{commit}"], cwd=ROOT, check=True,
    capture_output=True, text=True,
).stdout.strip()
TREE = subprocess.run(
    ["git", "show", "-s", "--format=%T", "HEAD"], cwd=ROOT, check=True,
    capture_output=True, text=True,
).stdout.strip()


def load_module():
    spec = importlib.util.spec_from_file_location("assemble_skill_profile", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ASSEMBLER = load_module()


def tree_digest(root: Path) -> str:
    """Return a deterministic digest of an assembled profile tree."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class ProfileAssemblyTests(unittest.TestCase):
    def test_all_declared_profiles_have_reference_closure(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        for profile in manifest["profiles"]:
            with self.subTest(profile=profile):
                paths = ASSEMBLER.selected_paths(manifest, profile)
                self.assertEqual([], ASSEMBLER.unresolved_lhe_references(paths, manifest))

    def test_core_only_apply_creates_only_selected_paths(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "core-only")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", str(output), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            actual = {
                str(path.relative_to(output))
                for path in output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(set(paths), actual)
            assembled_skill = (
                output / ".agents/skills/long-horizon-engineering/SKILL.md"
            ).read_text(encoding="utf-8")
            selected = ASSEMBLER.lhe_selected_relative_paths(paths)
            self.assertNotIn(ASSEMBLER.OPTIONAL_REFERENCE_MARKER, assembled_skill)
            self.assertIn("optional extension not included in this assembled profile", assembled_skill)
            self.assertEqual(
                [],
                [
                    reference
                    for reference in ASSEMBLER.REFERENCE_RE.findall(assembled_skill)
                    if reference not in selected
                ],
            )

    def test_local_governance_core_assembly_is_deterministic_and_excludes_optional_content(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "local-governance-core")
        optional_paths = set(
            ASSEMBLER.selected_paths(manifest, "lhe-bundled")
        ) - set(paths)
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            for output in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--profile",
                        "local-governance-core",
                        "--output-root",
                        str(output),
                        "--apply",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(tree_digest(first), tree_digest(second))
            actual = {
                str(path.relative_to(first))
                for path in first.rglob("*")
                if path.is_file()
            }
            self.assertEqual(set(paths), actual)
            self.assertFalse(actual & optional_paths)
            self.assertFalse(any(path.startswith("sandbox/") for path in actual))
            self.assertFalse(
                any("ai-video-production" in path for path in actual)
            )

    def test_receipt_is_deterministic_binds_explicit_identity_and_omits_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outputs = (root / "first", root / "second")
            receipts = (root / "first-receipt.json", root / "second-receipt.json")
            payloads = []
            for output, receipt in zip(outputs, receipts):
                result = subprocess.run(
                    [
                        sys.executable, str(SCRIPT), "--profile", "local-governance-core",
                        "--output-root", str(output), "--receipt-file", str(receipt),
                        "--source-commit", COMMIT, "--source-tree", TREE, "--apply",
                    ],
                    cwd=ROOT, text=True, capture_output=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                payloads.append(json.loads(receipt.read_text(encoding="utf-8")))
            self.assertEqual(payloads[0], payloads[1])
            self.assertEqual(COMMIT, payloads[0]["declared_source_commit"])
            self.assertEqual(TREE, payloads[0]["declared_source_tree"])
            self.assertFalse(payloads[0]["source_identity_verified"])
            self.assertNotIn(str(root), json.dumps(payloads[0]))
            paths = [entry["path"] for entry in payloads[0]["files"]]
            self.assertEqual(sorted(paths), paths)
            self.assertFalse(any(path.startswith("/") for path in paths))
            self.assertFalse(any("ai-video-production" in path for path in paths))
            self.assertFalse(any(path.startswith("sandbox/") for path in paths))

    def test_equivalent_core_profiles_share_artifact_digest_but_keep_profile_identity(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "core-only")
        self.assertEqual(paths, ASSEMBLER.selected_paths(manifest, "local-governance-core"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipts = []
            for profile in ("core-only", "local-governance-core"):
                output = root / profile
                receipt = root / f"{profile}.json"
                result = subprocess.run(
                    [
                        sys.executable, str(SCRIPT), "--profile", profile,
                        "--output-root", str(output), "--receipt-file", str(receipt),
                        "--source-commit", COMMIT, "--source-tree", TREE, "--apply",
                    ], cwd=ROOT, text=True, capture_output=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                receipts.append(json.loads(receipt.read_text(encoding="utf-8")))
            self.assertNotEqual(receipts[0]["profile"], receipts[1]["profile"])
            self.assertEqual(receipts[0]["files"], receipts[1]["files"])
            self.assertEqual(receipts[0]["artifact_tree_sha256"], receipts[1]["artifact_tree_sha256"])

    def test_invalid_receipt_request_publishes_neither_artifact_nor_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "profile"
            receipt = root / "receipt.json"
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--profile", "core-only",
                    "--output-root", str(output), "--receipt-file", str(receipt),
                    "--source-commit", "not-a-sha", "--source-tree", TREE, "--apply",
                ], cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())

    def test_release_grade_rejects_a_well_formed_but_wrong_source_identity(self) -> None:
        completed = [
            subprocess.CompletedProcess([], 0, stdout=COMMIT + "\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=TREE + "\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        with mock.patch.object(ASSEMBLER.subprocess, "run", side_effect=completed):
            with self.assertRaisesRegex(ASSEMBLER.ProfileError, "source commit must match"):
                ASSEMBLER.verified_source_identity("a" * 40, TREE)

    def test_receipt_is_published_only_after_the_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "profile"
            receipt = root / "receipt.json"
            original_replace = Path.replace

            def fail_receipt_publish(path: Path, target: Path):
                if path.name.startswith(".profile-receipt-"):
                    raise OSError("simulated receipt publish failure")
                return original_replace(path, target)

            with mock.patch.object(Path, "replace", fail_receipt_publish):
                with self.assertRaisesRegex(OSError, "simulated receipt"):
                    ASSEMBLER.assemble(
                        ASSEMBLER.selected_paths(ASSEMBLER.load_manifest(), "core-only"),
                        output,
                        "core-only",
                        source_commit=COMMIT,
                        source_tree=TREE,
                        receipt_file=receipt,
                    )
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())

    def test_artifact_digest_changes_when_one_file_changes_and_captures_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            path = stage / "example.txt"
            path.write_text("first", encoding="utf-8")
            path.chmod(0o640)
            first = ASSEMBLER.artifact_receipt(stage, ["example.txt"], "core-only", COMMIT, TREE)
            path.write_text("second", encoding="utf-8")
            second = ASSEMBLER.artifact_receipt(stage, ["example.txt"], "core-only", COMMIT, TREE)
            self.assertNotEqual(first["artifact_tree_sha256"], second["artifact_tree_sha256"])
            self.assertEqual("0640", first["files"][0]["mode"])

    def test_full_profile_keeps_marked_source_text_unchanged(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        paths = ASSEMBLER.selected_paths(manifest, "legacy-full")
        source = (
            ROOT / ".agents/skills/long-horizon-engineering/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            source,
            ASSEMBLER.render_markdown(
                source, ASSEMBLER.lhe_selected_relative_paths(paths), "legacy-full"
            ),
        )

    def test_apply_rejects_nonempty_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            output.mkdir()
            (output / "existing.txt").write_text("x", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", str(output), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("output root must be empty", result.stderr)

    def test_output_root_requires_explicit_apply(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", "core-only", "--output-root", "/tmp/profile"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--output-root requires --apply", result.stderr)

    def test_manifest_paths_fail_closed_before_source_or_output_access(self) -> None:
        manifest = ASSEMBLER.load_manifest()
        for unsafe in ("../outside.md", "/tmp/outside.md", "dir\\file.md"):
            with self.subTest(unsafe=unsafe):
                tampered = json.loads(json.dumps(manifest))
                tampered["components"]["core"]["paths"][0] = unsafe
                with self.assertRaisesRegex(ASSEMBLER.ProfileError, "package path"):
                    ASSEMBLER.selected_paths(tampered, "core-only")

    def test_unavailable_reference_must_be_safe_to_render(self) -> None:
        with self.assertRaisesRegex(ASSEMBLER.ProfileError, "cannot safely render"):
            ASSEMBLER.render_markdown(
                "references/example.md <!-- profile-optional-reference -->\n",
                set(),
                "core-only",
            )

    def test_failed_assembly_does_not_create_a_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile"
            with self.assertRaisesRegex(ASSEMBLER.ProfileError, "selected source path"):
                ASSEMBLER.assemble(["missing.md"], output, "core-only")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
