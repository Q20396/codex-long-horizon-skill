"""Contract tests for the explicit-only Obsidian knowledge workflow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "obsidian-knowledge-workflow.md"
TEMPLATE = LHE / "templates" / "OBSIDIAN_ARTIFACT_PLAN_TEMPLATE.md"
VALIDATOR = LHE / "scripts" / "validate_json_canvas.py"


class ObsidianKnowledgeWorkflowContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized)

    def run_validator(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--json", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_protocol_is_explicit_only_and_privacy_first(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "explicitly asks",
                "Workflow mode: `PROPOSAL_ONLY`",
                "Vault read approval: `NO`",
                "Vault write approval: `NO`",
                "exact vault root",
                "Do not read:",
                "an entire vault by default",
                "files reached through a symlink outside the approved vault root",
                "A plan, preview, or readable draft is not permission to write.",
                "automatic vault indexing",
                "cloud synchronization",
            ],
        )

    def test_template_keeps_writes_pending_and_requires_rollback(self) -> None:
        text = self.read(TEMPLATE)
        self.assert_contains_all(
            text,
            [
                "Proposal status: `PROPOSAL_ONLY`",
                "Vault read approval: `NO`",
                "Vault write approval: `NO`",
                "Exact target artifact path: `PENDING`",
                "Background scan/index/sync: `NO`",
                "Sensitive-content assessment:",
                "Backup required before replacement:",
                "Changes applied: `NO`",
            ],
        )

    def test_validator_accepts_valid_canvas_and_rejects_invalid_structure(self) -> None:
        valid = {
            "nodes": [
                {
                    "id": "goal",
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 320,
                    "height": 160,
                    "text": "# Goal",
                },
                {
                    "id": "evidence",
                    "type": "text",
                    "x": 420,
                    "y": 0,
                    "width": 320,
                    "height": 160,
                    "text": "Confirmed evidence",
                },
            ],
            "edges": [
                {
                    "id": "supports",
                    "fromNode": "evidence",
                    "toNode": "goal",
                    "label": "supports",
                }
            ],
        }
        invalid = {
            "nodes": [
                {
                    "id": "duplicate",
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 320,
                    "height": 160,
                    "text": "One",
                },
                {
                    "id": "duplicate",
                    "type": "text",
                    "x": 0,
                    "y": 200,
                    "width": 320,
                    "height": 160,
                    "text": "Two",
                },
            ],
            "edges": [
                {"id": "edge", "fromNode": "duplicate", "toNode": "missing"}
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_path = root / "valid.canvas"
            invalid_path = root / "invalid.canvas"
            valid_path.write_text(json.dumps(valid), encoding="utf-8")
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

            valid_result = self.run_validator(valid_path)
            invalid_result = self.run_validator(invalid_path)

        self.assertEqual(valid_result.returncode, 0, valid_result.stderr)
        self.assertEqual(json.loads(valid_result.stdout), {"ok": True, "errors": []})
        self.assertEqual(invalid_result.returncode, 1)
        errors = json.loads(invalid_result.stdout)["errors"]
        self.assertIn("Node 1 has a duplicate id.", errors)
        self.assertIn("Edge 0 references a missing node.", errors)

    def test_validator_rejects_symlink_without_exposing_canvas_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.canvas"
            link = root / "link.canvas"
            target.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
            try:
                link.symlink_to(target)
            except OSError as error:
                self.skipTest(f"Symlinks are unavailable: {error}")
            result = self.run_validator(link)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"], ["Refusing to validate a symlinked canvas file."])

    def test_validator_rejects_a_named_pipe_before_opening_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipe = Path(directory) / "input.canvas"
            try:
                os.mkfifo(pipe)
            except OSError as error:
                self.skipTest(f"Named pipes are unavailable: {error}")
            result = self.run_validator(pipe)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(result.stdout)["errors"],
            ["Canvas input must be a regular file."],
        )

    def test_skill_docs_and_checks_reference_the_protocol(self) -> None:
        skill = self.read(LHE / "SKILL.md")
        readme = self.read(ROOT / "README.md")
        extensions = self.read(LHE / "references" / "explicit-only-extensions.md")
        checker = self.read(LHE / "scripts" / "check_skill_package.py")
        doctor = self.read(LHE / "scripts" / "doctor.py")
        workflow = self.read(ROOT / ".github" / "workflows" / "check-skill.yml")
        self.assertIn("obsidian-knowledge-workflow.md", skill)
        self.assertIn("Optional Obsidian Knowledge Workflow", readme)
        self.assertIn("obsidian-knowledge-workflow.md", extensions)
        for text in (checker, doctor):
            self.assertIn("obsidian-knowledge-workflow.md", text)
            self.assertIn("OBSIDIAN_ARTIFACT_PLAN_TEMPLATE.md", text)
            self.assertIn("validate_json_canvas.py", text)
        self.assertIn("validate_json_canvas.py --help", workflow)


if __name__ == "__main__":
    unittest.main()
