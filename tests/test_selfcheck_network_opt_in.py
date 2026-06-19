from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "long-horizon-engineering" / "scripts" / "selfcheck_installed_skill.py"


def load_selfcheck_module():
    spec = importlib.util.spec_from_file_location("selfcheck_network_opt_in_under_test", SCRIPT)
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


class SelfCheckNetworkOptInTests(unittest.TestCase):
    def test_network_mode_without_allow_network_is_rejected_without_git_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            installed = Path(temp_name) / "installed"
            installed.mkdir()

            def forbidden_runner(args, cwd):
                raise AssertionError("Network helper must not be called without --allow-network.")

            code, _stdout, stderr = run_main(
                [
                    "--installed-dir",
                    str(installed),
                    "--repository-url",
                    "https://github.com/example/repo.git",
                    "--source-commit",
                    "a" * 40,
                    "--skill-path",
                    ".agents/skills/long-horizon-engineering",
                ],
                forbidden_runner,
            )

            self.assertEqual(code, SELF.EXIT_INVALID)
            self.assertIn("Network mode requires --allow-network", stderr)

    def test_public_https_url_is_accepted_syntactically(self) -> None:
        value = "https://github.com/example/repo.git"
        self.assertEqual(SELF.validate_repository_url(value), value)

    def test_unsafe_repository_urls_are_rejected(self) -> None:
        rejected = [
            "https://user:token@github.com/example/repo.git",
            "git@github.com:example/repo.git",
            "ssh://github.com/example/repo.git",
            "git://github.com/example/repo.git",
            "file:///tmp/repo",
            "/tmp/repo",
            "https://localhost/example/repo.git",
        ]
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(SELF.PolicyError):
                    SELF.validate_repository_url(value)

    def test_run_git_uses_shell_false_timeout_and_noninteractive_environment(self) -> None:
        captured: dict[str, object] = {}
        original_run = SELF.subprocess.run

        class Result:
            returncode = 0
            stdout = b"ok"
            stderr = b""

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured.update(kwargs)
            return Result()

        try:
            SELF.subprocess.run = fake_run
            with tempfile.TemporaryDirectory() as temp_name:
                output = SELF.run_git(["status"], Path(temp_name))
        finally:
            SELF.subprocess.run = original_run

        self.assertEqual(output, b"ok")
        self.assertIs(captured["shell"], False)
        self.assertEqual(captured["timeout"], SELF.GIT_TIMEOUT_SECONDS)
        self.assertIs(captured["check"], False)
        self.assertIs(captured["capture_output"], True)
        self.assertIs(captured["text"], False)
        command = captured["command"]
        self.assertIsInstance(command, list)
        self.assertIn("-c", command)
        env = captured["env"]
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GIT_ASKPASS"], "/bin/false")
        self.assertEqual(env["SSH_ASKPASS"], "/bin/false")

    def test_exact_commit_network_mode_uses_injected_runner_only(self) -> None:
        sha = "d" * 40
        calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temp_name:
            installed = Path(temp_name) / "installed"
            installed.mkdir()
            (installed / "SKILL.md").write_text("same\n", encoding="utf-8")

            def fake_runner(args, cwd):
                calls.append(args)
                if args[0] == "init":
                    return b""
                if args[:3] == ["-C", args[1], "remote"]:
                    return b""
                if args[:3] == ["-C", args[1], "fetch"]:
                    return b""
                if args[:4] == ["-C", args[1], "ls-tree", "-r"]:
                    return b"100644 blob blob-skill\tSKILL.md\0"
                if args[:3] == ["-C", args[1], "cat-file"]:
                    return b"same\n"
                raise AssertionError(f"Unexpected git call: {args}")

            code, stdout, stderr = run_main(
                [
                    "--installed-dir",
                    str(installed),
                    "--repository-url",
                    "https://github.com/example/repo.git",
                    "--source-commit",
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
            self.assertIn('"comparison_mode": "exact_commit"', stdout)
            self.assertTrue(any(call[0] == "init" for call in calls))
            self.assertFalse(any("checkout" in call for call in calls for call in call))
            self.assertFalse(any("submodule" in call for call in calls for call in call))


if __name__ == "__main__":
    unittest.main()
