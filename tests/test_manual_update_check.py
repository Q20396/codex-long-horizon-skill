from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "long-horizon-engineering"
    / "scripts"
    / "check_for_updates.py"
)
LOCAL_SHA = "a" * 40
REMOTE_SHA = "b" * 40
TAG_OBJECT_SHA = "c" * 40
PEELED_SHA = "d" * 40
PUBLIC_IP = "93.184.216.34"
PRIVATE_IP = "10.0.0.1"


def load_update_check_module():
    spec = importlib.util.spec_from_file_location("check_for_updates_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_for_updates_under_test"] = module
    spec.loader.exec_module(module)
    return module


class FakeGit:
    def __init__(
        self,
        tag_sha: str = LOCAL_SHA,
        local_sha: str = LOCAL_SHA,
        tag_output: str | None = None,
    ) -> None:
        self.tag_sha = tag_sha
        self.local_sha = local_sha
        self.tag_output = tag_output
        self.calls: list[tuple[list[str], Path, int]] = []

    def __call__(self, args: list[str], cwd: Path, timeout_seconds: int) -> str:
        self.calls.append((args, cwd, timeout_seconds))
        if args == ["rev-parse", "HEAD"]:
            return self.local_sha
        if args == ["remote", "get-url", "origin"]:
            return "https://github.com/Q20396/codex-long-horizon-skill.git"
        if args[:2] == ["ls-remote", "--tags"]:
            if self.tag_output is not None:
                return self.tag_output
            tag_ref = args[-2]
            tag = tag_ref.removeprefix("refs/tags/")
            return f"{self.tag_sha}\trefs/tags/{tag}\n"
        raise AssertionError(f"unexpected git call: {args}")

    def remote_calls(self) -> list[tuple[list[str], Path, int]]:
        return [call for call in self.calls if call[0][:2] == ["ls-remote", "--tags"]]


def public_resolver(hostname: str, port: int) -> list[str]:
    return [PUBLIC_IP]


def private_resolver(hostname: str, port: int) -> list[str]:
    return [PRIVATE_IP]


def forbidden_resolver(hostname: str, port: int) -> list[str]:
    raise AssertionError("resolver should not be called")


class ManualUpdateCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_update_check_module()

    def run_main(
        self,
        args: list[str],
        fake_git: FakeGit,
        resolver=public_resolver,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(args, runner=fake_git, resolver=resolver)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_help_performs_no_network_action(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Manually check", result.stdout)

    def test_tag_requires_explicit_network_authorization(self) -> None:
        fake_git = FakeGit()
        code, stdout, stderr = self.run_main(
            ["--source-tag", "v0.2.0", "--expected-commit", LOCAL_SHA],
            fake_git,
            resolver=forbidden_resolver,
        )
        self.assertEqual(code, self.module.POLICY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("--source-tag requires --allow-network", stderr)
        self.assertEqual(fake_git.remote_calls(), [])

    def test_tag_requires_expected_commit(self) -> None:
        fake_git = FakeGit()
        code, _stdout, stderr = self.run_main(
            ["--source-tag", "v0.2.0", "--allow-network"],
            fake_git,
            resolver=forbidden_resolver,
        )
        self.assertEqual(code, self.module.POLICY_ERROR)
        self.assertIn("--expected-commit", stderr)
        self.assertEqual(fake_git.remote_calls(), [])

    def test_mutable_refs_are_rejected(self) -> None:
        for source_ref in [
            "main",
            "master",
            "latest",
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "origin/main",
        ]:
            with self.subTest(source_ref=source_ref):
                fake_git = FakeGit()
                code, _stdout, stderr = self.run_main(
                    [
                        "--source-tag",
                        source_ref,
                        "--expected-commit",
                        LOCAL_SHA,
                        "--allow-network",
                    ],
                    fake_git,
                    resolver=forbidden_resolver,
                )
                self.assertEqual(code, self.module.POLICY_ERROR)
                self.assertIn("mutable refs", stderr)
                self.assertEqual(fake_git.remote_calls(), [])

    def test_url_and_host_rejections(self) -> None:
        rejected_urls = [
            "https://user@example.com/repo",
            "https://user:pass@example.com/repo",
            "ssh://git@github.com/Q20396/codex-long-horizon-skill",
            "git@github.com:Q20396/codex-long-horizon-skill",
            "git://github.com/Q20396/codex-long-horizon-skill",
            "file:///tmp/repo",
            "/Users/private/repo",
            "../repo",
            "https://github.com:bad/repo",
            "https://github.com/repo#fragment",
            "https://localhost/repo",
            "https://localhost.example/repo",
            "https://workstation/repo",
            "https://example.local/repo",
            "https://metadata.google.internal/repo",
            "https://127.0.0.1/repo",
            "https://10.0.0.1/repo",
            "https://172.16.0.1/repo",
            "https://192.168.1.1/repo",
            "https://169.254.169.254/repo",
            "https://[::1]/repo",
            "https://[fc00::1]/repo",
            "https://[fe80::1]/repo",
            "https://example.com:444/repo",
        ]
        for url in rejected_urls:
            with self.subTest(url=url):
                with self.assertRaises(self.module.PolicyError):
                    self.module.validate_remote_url(url, resolve_dns=False)

    def test_dns_private_address_is_rejected(self) -> None:
        with self.assertRaisesRegex(self.module.PolicyError, "public routable"):
            self.module.validate_remote_url(
                "https://example.com/repo",
                resolve_dns=True,
                resolver=private_resolver,
            )

    def test_public_https_and_public_dns_are_accepted(self) -> None:
        self.module.validate_remote_url(
            "https://example.com/repo",
            resolve_dns=True,
            resolver=public_resolver,
        )
        self.module.validate_remote_url("https://93.184.216.34/repo", resolve_dns=False)

    def test_offline_url_validation_does_not_resolve_dns(self) -> None:
        self.module.validate_remote_url(
            "https://example.com/repo",
            resolve_dns=False,
            resolver=forbidden_resolver,
        )

    def test_matching_tag_reports_up_to_date_without_applying_update(self) -> None:
        fake_git = FakeGit(tag_sha=LOCAL_SHA, local_sha=LOCAL_SHA)
        code, stdout, stderr = self.run_main(
            [
                "--source-tag",
                "v0.2.0",
                "--expected-commit",
                LOCAL_SHA,
                "--allow-network",
            ],
            fake_git,
        )
        self.assertEqual(code, 0, stderr)
        self.assertIn("Network: allowed for one read-only remote tag lookup", stdout)
        self.assertIn("Remote identity verified: yes", stdout)
        self.assertIn("Status: up to date with the approved source.", stdout)
        self.assertIn("No files were changed.", stdout)
        self.assertIn("No update was applied.", stdout)
        remote_calls = fake_git.remote_calls()
        self.assertEqual(len(remote_calls), 1)
        self.assertFalse(str(remote_calls[0][1]).startswith(str(ROOT)))

    def test_moved_or_unexpected_tag_is_blocked(self) -> None:
        fake_git = FakeGit(tag_sha=REMOTE_SHA, local_sha=LOCAL_SHA)
        code, stdout, stderr = self.run_main(
            [
                "--source-tag",
                "v0.2.0",
                "--expected-commit",
                LOCAL_SHA,
                "--allow-network",
            ],
            fake_git,
        )
        self.assertEqual(code, self.module.REFERENCE_VERIFICATION_ERROR)
        self.assertIn(f"Expected commit: {LOCAL_SHA}", stdout)
        self.assertIn(f"Resolved tag commit: {REMOTE_SHA}", stdout)
        self.assertIn("possible tag movement", stderr)
        self.assertIn("No update was applied.", stderr)

    def test_exact_commit_mode_does_not_call_remote_or_resolver(self) -> None:
        fake_git = FakeGit(local_sha=LOCAL_SHA)
        code, stdout, stderr = self.run_main(
            ["--source-commit", LOCAL_SHA],
            fake_git,
            resolver=forbidden_resolver,
        )
        self.assertEqual(code, 0, stderr)
        self.assertIn("Network: not used for exact-commit comparison", stdout)
        self.assertIn("Remote identity verified: no", stdout)
        self.assertIn("Status: up to date with the approved source.", stdout)
        self.assertEqual(fake_git.remote_calls(), [])

    def test_resolve_lightweight_tag(self) -> None:
        output = f"{LOCAL_SHA}\trefs/tags/v0.1.0\n"
        self.assertEqual(self.module.parse_tag_output(output, "v0.1.0"), LOCAL_SHA)

    def test_resolve_annotated_tag_uses_peeled_commit(self) -> None:
        output = (
            f"{TAG_OBJECT_SHA}\trefs/tags/v0.1.0\n"
            f"{PEELED_SHA}\trefs/tags/v0.1.0^{{}}\n"
        )
        self.assertEqual(self.module.parse_tag_output(output, "v0.1.0"), PEELED_SHA)

    def test_tag_parse_rejections(self) -> None:
        cases = {
            "": "tag not found",
            "not a valid line": "malformed",
            f"{LOCAL_SHA}\trefs/tags/other\n": "unexpected ref",
            f"notasha\trefs/tags/v0.1.0\n": "invalid SHA",
            (
                f"{LOCAL_SHA}\trefs/tags/v0.1.0\n"
                f"{REMOTE_SHA}\trefs/tags/v0.1.0\n"
            ): "conflicting tag refs",
            (
                f"{TAG_OBJECT_SHA}\trefs/tags/v0.1.0\n"
                f"{LOCAL_SHA}\trefs/tags/v0.1.0^{{}}\n"
                f"{REMOTE_SHA}\trefs/tags/v0.1.0^{{}}\n"
            ): "conflicting peeled refs",
            f"{PEELED_SHA}\trefs/tags/v0.1.0^{{}}\n": "peeled tag result",
        }
        for output, message in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(self.module.RemoteCheckError, message):
                    self.module.parse_tag_output(output, "v0.1.0")

    def test_git_subprocess_is_isolated(self) -> None:
        captured: dict[str, object] = {}

        class Result:
            returncode = 0
            stdout = "ok\n"
            stderr = ""

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return Result()

        with mock.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://proxy.invalid",
                "HTTPS_PROXY": "http://proxy.invalid",
                "ALL_PROXY": "http://proxy.invalid",
                "GIT_CONFIG_COUNT": "1",
            },
            clear=False,
        ):
            with mock.patch.object(self.module.subprocess, "run", fake_run):
                result = self.module.run_git(["ls-remote", "https://example.com/repo"], Path("/private/tmp"), 7)

        self.assertEqual(result, "ok")
        command = captured["command"]
        kwargs = captured["kwargs"]
        self.assertEqual(command[0], "git")
        self.assertIn("http.followRedirects=false", command)
        self.assertIn("protocol.file.allow=never", command)
        self.assertIn("protocol.ext.allow=never", command)
        self.assertFalse(kwargs["shell"])
        self.assertIs(kwargs["stdin"], self.module.subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 7)
        self.assertEqual(kwargs["cwd"], Path("/private/tmp"))
        env = kwargs["env"]
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GIT_ASKPASS"], "/bin/false")
        self.assertEqual(env["SSH_ASKPASS"], "/bin/false")
        self.assertEqual(env["GCM_INTERACTIVE"], "Never")
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(env["GIT_CONFIG_SYSTEM"], os.devnull)
        self.assertNotEqual(env["HOME"], os.environ.get("HOME"))
        self.assertNotEqual(env["XDG_CONFIG_HOME"], os.environ.get("XDG_CONFIG_HOME"))
        self.assertFalse(str(env["HOME"]).startswith(str(ROOT)))
        for name in self.module.PROXY_ENV_NAMES:
            self.assertNotIn(name, env)

    def test_subprocess_errors_are_sanitized(self) -> None:
        class Result:
            returncode = 128
            stdout = ""
            stderr = "/Users/private/path secret-token"

        with mock.patch.object(self.module.subprocess, "run", lambda *args, **kwargs: Result()):
            with self.assertRaises(self.module.RemoteCheckError) as context:
                self.module.run_git(["ls-remote", "https://example.com/repo"], Path("/private/tmp"), 7)
        message = str(context.exception)
        self.assertIn("exit code 128", message)
        self.assertNotIn("/Users/private", message)
        self.assertNotIn("secret-token", message)

    def test_policy_errors_do_not_expose_private_absolute_paths(self) -> None:
        fake_git = FakeGit()
        code, _stdout, stderr = self.run_main(
            ["--remote-url", "/Users/private/repo", "--source-commit", LOCAL_SHA],
            fake_git,
        )
        self.assertEqual(code, self.module.POLICY_ERROR)
        self.assertNotIn("/Users/private/repo", stderr)
        self.assertEqual(fake_git.remote_calls(), [])


if __name__ == "__main__":
    unittest.main()
