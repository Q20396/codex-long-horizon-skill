from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "selfcheck_installed_skill.py"


def load_selfcheck_module():
    spec = importlib.util.spec_from_file_location("selfcheck_immutable_ref_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SELF = load_selfcheck_module()


def run_main(argv: list[str], fake_runner) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = SELF.main(argv, git_runner=fake_runner)
    return code, stdout.getvalue(), stderr.getvalue()


class SelfCheckImmutableRefTests(unittest.TestCase):
    def test_full_exact_commit_sha_is_accepted_syntactically(self) -> None:
        value = "a" * 40
        self.assertEqual(SELF.validate_full_sha(value), value)

    def test_abbreviated_sha_is_rejected(self) -> None:
        with self.assertRaises(SELF.PolicyError):
            SELF.validate_full_sha("a" * 12)

    def test_mutable_refs_are_rejected(self) -> None:
        for value in ("main", "master", "latest", "HEAD", "refs/heads/main"):
            with self.subTest(value=value):
                with self.assertRaises(SELF.PolicyError):
                    SELF.validate_full_sha(value)
                with self.assertRaises(SELF.PolicyError):
                    SELF.validate_tag_name(value)

    def test_tag_mode_without_expected_sha_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            installed = Path(temp_name) / "installed"
            installed.mkdir()

            def forbidden_runner(args, cwd):
                raise AssertionError("Network helper must not be called for invalid tag mode.")

            code, _stdout, stderr = run_main(
                [
                    "--installed-dir",
                    str(installed),
                    "--repository-url",
                    "https://github.com/example/repo.git",
                    "--source-tag",
                    "v1.0.0",
                    "--skill-path",
                    ".agents/skills/long-horizon-engineering",
                    "--allow-network",
                ],
                forbidden_runner,
            )

            self.assertEqual(code, SELF.EXIT_INVALID)
            self.assertIn("Tag mode requires --expected-commit", stderr)

    def test_tag_resolution_mismatch_reports_possible_tag_movement(self) -> None:
        expected = "a" * 40
        moved = "b" * 40
        with tempfile.TemporaryDirectory() as temp_name:
            installed = Path(temp_name) / "installed"
            installed.mkdir()

            def fake_runner(args, cwd):
                if args[:2] == ["ls-remote", "--tags"]:
                    return f"{moved}\trefs/tags/v1.0.0\n".encode()
                raise AssertionError(f"Unexpected git call: {args}")

            code, _stdout, stderr = run_main(
                [
                    "--installed-dir",
                    str(installed),
                    "--repository-url",
                    "https://github.com/example/repo.git",
                    "--source-tag",
                    "v1.0.0",
                    "--expected-commit",
                    expected,
                    "--skill-path",
                    ".agents/skills/long-horizon-engineering",
                    "--allow-network",
                ],
                fake_runner,
            )

            self.assertEqual(code, SELF.EXIT_REFERENCE)
            self.assertIn("Possible tag movement", stderr)
            self.assertIn("No files were modified.", stderr)
            self.assertIn("No update was applied.", stderr)

    def test_matching_tag_records_requested_expected_and_resolved_sha(self) -> None:
        sha = "c" * 40
        calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temp_name:
            installed = Path(temp_name) / "installed"
            installed.mkdir()
            (installed / "SKILL.md").write_text("reference skill\n", encoding="utf-8")

            def fake_runner(args, cwd):
                calls.append(args)
                if args[:2] == ["ls-remote", "--tags"]:
                    return f"{sha}\trefs/tags/v1.0.0\n".encode()
                if args[0] == "init":
                    return b""
                if args[:3] == ["-C", args[1], "remote"]:
                    return b""
                if args[:3] == ["-C", args[1], "fetch"]:
                    return b""
                if args[:4] == ["-C", args[1], "ls-tree", "-r"]:
                    return b"100644 blob blob-skill\tSKILL.md\0"
                if args[:3] == ["-C", args[1], "cat-file"]:
                    return b"reference skill\n"
                raise AssertionError(f"Unexpected git call: {args}")

            code, stdout, stderr = run_main(
                [
                    "--installed-dir",
                    str(installed),
                    "--repository-url",
                    "https://github.com/example/repo.git",
                    "--source-tag",
                    "v1.0.0",
                    "--expected-commit",
                    sha,
                    "--skill-path",
                    ".agents/skills/long-horizon-engineering",
                    "--allow-network",
                    "--format",
                    "json",
                ],
                fake_runner,
            )

            self.assertEqual(code, SELF.EXIT_EQUIVALENT, stderr)
            payload = json.loads(stdout)
            identity = payload["reference_identity"]
            self.assertEqual(payload["comparison_mode"], "tag_resolved_to_commit")
            self.assertEqual(identity["requested_tag"], "v1.0.0")
            self.assertEqual(identity["expected_sha"], sha)
            self.assertEqual(identity["resolved_sha"], sha)
            self.assertTrue(any(call[:2] == ["ls-remote", "--tags"] for call in calls))
            self.assertFalse(any("submodule" in call for call in calls for call in call))


if __name__ == "__main__":
    unittest.main()
