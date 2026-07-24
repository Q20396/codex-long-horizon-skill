from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("validate_plugin_package_under_test", ROOT / "scripts" / "validate_plugin_package.py")


def write_fake_codex(bin_dir: Path) -> Path:
    fake = bin_dir / "codex"
    fake.write_text(
        textwrap.dedent(
            r'''
            #!/usr/bin/env python3
            import json
            import os
            import shutil
            import sys
            from pathlib import Path

            scenario = os.environ.get("FAKE_CODEX_SCENARIO", "old")
            argv = sys.argv[1:]
            home = Path(os.environ["HOME"])
            codex_home = Path(os.environ["CODEX_HOME"])
            codex_home.mkdir(parents=True, exist_ok=True)
            log = Path(os.environ.get("FAKE_CODEX_LOG", codex_home / "commands.log"))
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as handle:
                handle.write(" ".join(argv) + "\n")

            marketplace_name = "codex-long-horizon-skills"
            plugin_name = "codex-long-horizon-skill"

            def state_path():
                return codex_home / "marketplaces.json"

            def load_state():
                if state_path().is_file():
                    return json.loads(state_path().read_text(encoding="utf-8"))
                return {}

            def save_state(data):
                state_path().write_text(json.dumps(data), encoding="utf-8")

            def source_arg(args):
                values = [arg for arg in args if not arg.startswith("-")]
                return values[-1] if values else ""

            def supports_list():
                return scenario in {
                    "modern",
                    "list_failure",
                    "plugin_failure",
                    "json_wrong_root",
                    "json_outside_root",
                    "json_invalid_registered_root",
                    "text_list_good",
                    "text_list_name_only",
                    "text_list_wrong_root",
                    "plugin_non_json",
                    "plugin_source_only",
                    "plugin_ambiguous",
                    "snapshot_source_only",
                    "snapshot_plus_install",
                    "plugin_list_available_only",
                    "plugin_list_wrong_version",
                    "plugin_list_text_substring",
                }

            def supports_plugin():
                return scenario in {
                    "modern",
                    "plugin_failure",
                    "plugin_non_json",
                    "plugin_source_only",
                    "plugin_ambiguous",
                    "snapshot_source_only",
                    "snapshot_plus_install",
                    "plugin_list_available_only",
                    "plugin_list_wrong_version",
                    "plugin_list_text_substring",
                }

            def supports_json(command):
                if scenario in {
                    "text_list_good",
                    "text_list_name_only",
                    "text_list_wrong_root",
                    "plugin_non_json",
                    "plugin_source_only",
                    "plugin_ambiguous",
                    "snapshot_source_only",
                    "snapshot_plus_install",
                    "plugin_list_text_substring",
                }:
                    return command == "marketplace_add"
                return scenario in {
                    "modern",
                    "list_failure",
                    "plugin_failure",
                    "json_wrong_root",
                    "json_outside_root",
                    "json_invalid_registered_root",
                    "plugin_list_available_only",
                    "plugin_list_wrong_version",
                }

            if argv == ["--version"]:
                print("codex-cli fake-1.0.0")
                raise SystemExit(0)

            if argv == ["plugin", "--help"]:
                print("Commands:\n  marketplace")
                if supports_plugin():
                    print("  add\n  list")
                raise SystemExit(0)

            if argv == ["plugin", "marketplace", "--help"]:
                print("Commands:\n  add")
                if supports_list():
                    print("  list")
                raise SystemExit(0)

            if argv == ["plugin", "marketplace", "add", "--help"]:
                print("Usage: codex plugin marketplace add [OPTIONS] <SOURCE>")
                if supports_json("marketplace_add"):
                    print("Options:\n  --json")
                raise SystemExit(0)

            if argv == ["plugin", "marketplace", "list", "--help"]:
                if not supports_list():
                    print("error: unrecognized subcommand 'list'", file=sys.stderr)
                    raise SystemExit(2)
                print("Usage: codex plugin marketplace list")
                if supports_json("marketplace_list"):
                    print("Options:\n  --json")
                raise SystemExit(0)

            if argv == ["plugin", "add", "--help"]:
                if not supports_plugin():
                    print("error: unrecognized subcommand 'add'", file=sys.stderr)
                    raise SystemExit(2)
                print("Usage: codex plugin add <plugin[@marketplace]>")
                if supports_json("plugin_add"):
                    print("Options:\n  --json")
                raise SystemExit(0)

            if argv == ["plugin", "list", "--help"]:
                if not supports_plugin():
                    print("error: unrecognized subcommand 'list'", file=sys.stderr)
                    raise SystemExit(2)
                print("Usage: codex plugin list")
                if supports_json("plugin_list"):
                    print("Options:\n  --json")
                raise SystemExit(0)

            if argv[:3] == ["plugin", "marketplace", "add"]:
                if scenario == "add_failure":
                    print("fake marketplace add failed", file=sys.stderr)
                    raise SystemExit(7)
                source = source_arg(argv[3:])
                installed_root = codex_home / "marketplaces" / marketplace_name
                if scenario == "json_invalid_registered_root":
                    installed_root = codex_home / "invalid-marketplace"
                if scenario != "no_evidence":
                    if scenario in {"snapshot_source_only", "snapshot_plus_install"}:
                        if installed_root.exists():
                            shutil.rmtree(installed_root)
                        shutil.copytree(source, installed_root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                    else:
                        installed_root.mkdir(parents=True, exist_ok=True)
                    save_state({"name": marketplace_name, "source": source, "installedRoot": str(installed_root)})
                if "--json" in argv:
                    data = {"marketplaceName": marketplace_name, "installedRoot": str(installed_root)}
                    print(json.dumps(data))
                else:
                    print(f"Added marketplace `{marketplace_name}` from {source}.")
                raise SystemExit(0)

            if argv[:3] == ["plugin", "marketplace", "list"]:
                if scenario == "list_failure":
                    print("fake marketplace list failed", file=sys.stderr)
                    raise SystemExit(8)
                state = load_state()
                root = state.get("source", "")
                if scenario == "json_wrong_root":
                    wrong = codex_home / "wrong-marketplace"
                    wrong.mkdir(parents=True, exist_ok=True)
                    root = str(wrong)
                if scenario == "json_invalid_registered_root":
                    root = state.get("installedRoot", "")
                if scenario == "json_outside_root":
                    root = "/tmp/codex-outside-marketplace"
                if "--json" in argv:
                    print(json.dumps({"marketplaces": [{"name": state.get("name", marketplace_name), "root": root, "marketplaceSource": {"source": state.get("source", "")}}]}))
                elif scenario == "text_list_name_only":
                    print(state.get("name", marketplace_name))
                elif scenario == "text_list_wrong_root":
                    print(f"{state.get('name', marketplace_name)} {codex_home / 'wrong-marketplace'}")
                else:
                    print(f"{state.get('name', marketplace_name)} {root}")
                raise SystemExit(0)

            if argv[:2] == ["plugin", "add"]:
                if scenario == "plugin_failure":
                    print("fake plugin add failed", file=sys.stderr)
                    raise SystemExit(9)
                state = load_state()
                source = Path(state["source"])
                installed = codex_home / "plugins" / plugin_name
                if scenario in {"plugin_source_only", "snapshot_source_only"}:
                    print(f"Installed {plugin_name}.")
                    raise SystemExit(0)
                if scenario == "plugin_ambiguous":
                    for suffix in ["a", "b"]:
                        target = codex_home / "plugins" / f"{plugin_name}-{suffix}"
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                    print(f"Installed {plugin_name}.")
                    raise SystemExit(0)
                if installed.exists():
                    shutil.rmtree(installed)
                shutil.copytree(source, installed, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                if "--json" in argv:
                    print(json.dumps({
                        "pluginId": f"{plugin_name}@{marketplace_name}",
                        "name": plugin_name,
                        "marketplaceName": marketplace_name,
                        "version": "0.2.4",
                        "installedPath": str(installed),
                    }))
                else:
                    print(f"Installed {plugin_name}.")
                raise SystemExit(0)

            if argv[:2] == ["plugin", "list"]:
                installed = codex_home / "plugins" / plugin_name
                if "--json" in argv:
                    if scenario == "plugin_list_available_only":
                        print(json.dumps({"installed": [], "available": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.2.4"}]}))
                        raise SystemExit(0)
                    if scenario == "plugin_list_wrong_version":
                        print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "9.9.9", "installed": installed.exists()}]}))
                        raise SystemExit(0)
                    print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.2.4", "installed": installed.exists()}]}))
                elif scenario == "plugin_list_text_substring":
                    print(f"{plugin_name}-old {marketplace_name} 0.2.1 installed")
                else:
                    print(f"{plugin_name} {marketplace_name} 0.2.4 installed")
                raise SystemExit(0)

            print(f"unhandled fake codex command: {argv}", file=sys.stderr)
            raise SystemExit(64)
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


class FrontMatterParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="frontmatter-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def skill_file(self, text: str | bytes) -> Path:
        path = self.temp / "skill" / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def test_valid_lf_front_matter(self) -> None:
        path = self.skill_file("---\nname: demo\n---\nBody\n")
        self.assertEqual(VALIDATOR.parse_skill_frontmatter(path, self.temp)["name"], "demo")

    def test_valid_crlf_front_matter(self) -> None:
        path = self.skill_file("---\r\nname: demo\r\n---\r\nBody\r\n")
        self.assertEqual(VALIDATOR.parse_skill_frontmatter(path, self.temp)["name"], "demo")

    def test_missing_opening_delimiter(self) -> None:
        path = self.skill_file("name: demo\n---\nBody\n")
        with self.assertRaisesRegex(ValueError, "missing opening delimiter"):
            VALIDATOR.parse_skill_frontmatter(path, self.temp)

    def test_missing_closing_delimiter(self) -> None:
        path = self.skill_file("---\nname: demo\nBody\n")
        with self.assertRaisesRegex(ValueError, "missing closing delimiter"):
            VALIDATOR.parse_skill_frontmatter(path, self.temp)

    def test_missing_name(self) -> None:
        path = self.skill_file("---\ndescription: demo\n---\nBody\n")
        with self.assertRaisesRegex(ValueError, "missing name"):
            VALIDATOR.parse_skill_frontmatter(path, self.temp)

    def test_empty_name(self) -> None:
        path = self.skill_file("---\nname:  \n---\nBody\n")
        with self.assertRaisesRegex(ValueError, "name is empty"):
            VALIDATOR.parse_skill_frontmatter(path, self.temp)

    def test_invalid_utf8(self) -> None:
        path = self.skill_file(b"---\nname: \xff\n---\n")
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            VALIDATOR.parse_skill_frontmatter(path, self.temp)

    def test_duplicate_valid_skill_names(self) -> None:
        skills_root = self.temp / "skills"
        for dirname in ["one", "two"]:
            path = skills_root / dirname / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("---\nname: duplicate\n---\nBody\n", encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.bundled_skill_names(skills_root, errors, self.temp)
        self.assertIn("duplicate bundled skill name: duplicate", errors)

    def test_validator_exits_cleanly_without_traceback(self) -> None:
        repo = self.temp / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        skill = repo / ".agents" / "skills" / "long-horizon-engineering" / "SKILL.md"
        skill.write_text("name: broken\n---\nBody\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/validate_plugin_package.py"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR:", output)
        self.assertIn("missing opening delimiter", output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("IndexError", output)

    def test_validator_rejects_root_local_marketplace_source(self) -> None:
        repo = self.temp / "repo-local-source"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        data["plugins"][0]["source"] = {"source": "local", "path": "./"}
        marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/validate_plugin_package.py"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("marketplace source.source must be url for root plugin CLI installs", output)

    def test_validator_rejects_wrong_marketplace_url(self) -> None:
        repo = self.temp / "repo-wrong-url"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        data["plugins"][0]["source"]["url"] = "https://github.com/example/not-this-plugin.git"
        marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/validate_plugin_package.py"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("marketplace source.url must be https://github.com/Q20396/codex-long-horizon-skill.git", output)

    def test_validator_rejects_wrong_marketplace_ref(self) -> None:
        repo = self.temp / "repo-wrong-ref"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        data["plugins"][0]["source"]["ref"] = "release-candidate"
        marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/validate_plugin_package.py"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("marketplace source.ref must be main", output)


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="release-readiness-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def copy_repo(self, name: str) -> Path:
        repo = self.temp / name
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return repo

    def run_readiness(
        self,
        repo: Path,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            [sys.executable, "scripts/check_release_readiness.py", "--version", "0.2.4", *args],
            cwd=repo,
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def release_notes(self, repo: Path) -> Path:
        return repo / "docs" / "releases" / "v0.2.4.md"

    def changelog(self, repo: Path) -> Path:
        return repo / "CHANGELOG.md"

    def init_repo_with_tag(self, repo: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "tag", "v0.2.4"], cwd=repo, check=True, capture_output=True, text=True)

    def assert_failed_without_traceback(self, result: subprocess.CompletedProcess[str], expected: str) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(expected, output)
        self.assertNotIn("Traceback", output)

    def test_publishable_final_release_notes_pass(self) -> None:
        repo = self.copy_repo("publishable")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allow-existing-tag", result.stdout)

    def test_prepared_not_released_marker_fails(self) -> None:
        repo = self.copy_repo("prepared-marker")
        self.release_notes(repo).write_text(
            self.release_notes(repo).read_text(encoding="utf-8") + "\nStatus: prepared, not released.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "prepared, not released")

    def test_not_yet_released_marker_fails(self) -> None:
        repo = self.copy_repo("not-yet-marker")
        self.release_notes(repo).write_text(
            self.release_notes(repo).read_text(encoding="utf-8") + "\nThis is not yet released.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "not yet released")

    def test_release_should_happen_only_after_marker_fails(self) -> None:
        repo = self.copy_repo("release-after-marker")
        self.release_notes(repo).write_text(
            self.release_notes(repo).read_text(encoding="utf-8") + "\nRelease should happen only after review.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "release should happen only after")

    def test_do_not_publish_yet_marker_fails(self) -> None:
        repo = self.copy_repo("do-not-publish-marker")
        self.release_notes(repo).write_text(
            self.release_notes(repo).read_text(encoding="utf-8") + "\nDo not publish yet.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "do not publish yet")

    def test_missing_dated_changelog_heading_fails(self) -> None:
        repo = self.copy_repo("missing-changelog-heading")
        self.changelog(repo).write_text(
            self.changelog(repo).read_text(encoding="utf-8").replace("## 0.2.4 - 2026-07-24", "## 0.2.4"),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG missing dated version section")

    def test_empty_dated_changelog_section_fails(self) -> None:
        repo = self.copy_repo("empty-changelog")
        self.changelog(repo).write_text(
            "# Changelog\n\nAll notable changes to this project are summarized here.\n\n"
            "## Unreleased\n\nNo unreleased changes.\n\n"
            "## 0.2.4 - 2026-07-24\n\n"
            "## 2026-06-15\n\n- Older work.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG version section is empty")

    def test_valid_dated_changelog_section_passes(self) -> None:
        repo = self.copy_repo("valid-changelog")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_manifest_version_mismatch_fails(self) -> None:
        repo = self.copy_repo("manifest-mismatch")
        manifest = repo / ".codex-plugin" / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "plugin version '9.9.9' does not match '0.2.4'")

    def test_release_note_date_must_match_changelog_date(self) -> None:
        repo = self.copy_repo("mismatched-release-date")
        self.changelog(repo).write_text(
            self.changelog(repo).read_text(encoding="utf-8").replace(
                "## 0.2.4 - 2026-07-24",
                "## 0.2.4 - 2026-07-23",
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG missing dated version section")

    def test_pre_tag_passes_without_local_tag(self) -> None:
        repo = self.copy_repo("pre-tag-no-tag")
        result = self.run_readiness(repo, "--pre-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pre_tag_fails_with_local_tag(self) -> None:
        repo = self.copy_repo("pre-tag-with-tag")
        self.init_repo_with_tag(repo)
        result = self.run_readiness(repo, "--pre-tag")
        self.assert_failed_without_traceback(result, "local tag already exists")

    def test_allow_existing_tag_passes_without_local_tag(self) -> None:
        repo = self.copy_repo("allow-no-tag")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_allow_existing_tag_passes_with_local_tag(self) -> None:
        repo = self.copy_repo("allow-with-tag")
        self.init_repo_with_tag(repo)
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_mode_matches_allow_existing_tag(self) -> None:
        repo = self.copy_repo("default-with-tag")
        self.init_repo_with_tag(repo)
        result = self.run_readiness(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allow-existing-tag", result.stdout)

    def test_both_mode_flags_fail_cleanly(self) -> None:
        repo = self.copy_repo("both-flags")
        result = self.run_readiness(repo, "--pre-tag", "--allow-existing-tag")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not allowed with argument", output)
        self.assertNotIn("Traceback", output)

    def test_routine_mode_performs_no_remote_or_network_check(self) -> None:
        repo = self.copy_repo("no-remote-check")
        fake_bin = self.temp / "fake-bin"
        fake_bin.mkdir()
        fake_git = fake_bin / "git"
        fake_git.write_text("#!/bin/sh\necho git should not run >&2\nexit 99\n", encoding="utf-8")
        fake_git.chmod(0o755)
        env = {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
        result = self.run_readiness(repo, "--allow-existing-tag", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_release_content_under_unreleased_fails(self) -> None:
        repo = self.copy_repo("duplicated-changelog")
        text = self.changelog(repo).read_text(encoding="utf-8")
        duplicated = (
            "- Added a proposal-only renderer runtime sandbox protocol and approval card for\n"
            "  AI video work. Environment inspection, dependency installation, preview,\n"
            "  final render, external processing, and sharing remain separate approvals.\n"
        )
        unreleased_heading = "## Unreleased\n"
        self.assertIn(unreleased_heading, text)
        text = text.replace(unreleased_heading, unreleased_heading + "\n" + duplicated, 1)
        self.changelog(repo).write_text(text, encoding="utf-8")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG duplicates release content under Unreleased")

    def test_malformed_release_inputs_fail_without_traceback(self) -> None:
        repo = self.copy_repo("malformed-release")
        self.release_notes(repo).write_bytes(b"# bad\n\xff\n")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "release notes are not valid UTF-8")


class FreshInstallCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="fresh-cli-test-"))
        self.bin = self.temp / "bin"
        self.bin.mkdir()
        write_fake_codex(self.bin)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def run_fresh(self, scenario: str, *args: str, with_codex: bool = True) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["FAKE_CODEX_SCENARIO"] = scenario
        env["FAKE_CODEX_LOG"] = str(self.temp / f"{scenario}.log")
        env["PATH"] = str(self.bin) if with_codex else str(self.temp / "empty-bin")
        if with_codex:
            env["PATH"] = str(self.bin) + os.pathsep + os.environ.get("PATH", "")
        return subprocess.run(
            [sys.executable, "scripts/test_fresh_install.py", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_add_runs_when_list_is_unavailable(self) -> None:
        result = self.run_fresh("old", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Marketplace registration: passed", output)
        self.assertIn("Marketplace listing: skipped_unavailable", output)
        self.assertIn("Plugin installation: skipped_unavailable", output)
        self.assertIn("plugin marketplace add", (self.temp / "old.log").read_text(encoding="utf-8"))

    def test_add_failure_is_failed_not_skipped(self) -> None:
        result = self.run_fresh("add_failure", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace registration: failed", output)
        self.assertNotIn("Marketplace registration: skipped_unavailable", output)

    def test_add_success_without_evidence_fails(self) -> None:
        result = self.run_fresh("no_evidence", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no durable isolated registration evidence", output)

    def test_modern_cli_verifies_registration_and_plugin_install(self) -> None:
        result = self.run_fresh("modern", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Marketplace registration: passed", output)
        self.assertIn("Marketplace listing: passed", output)
        self.assertIn("Plugin installation: passed", output)
        self.assertIn("Plugin listing: passed", output)

    def test_json_list_wrong_root_fails(self) -> None:
        result = self.run_fresh("json_wrong_root", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)
        self.assertIn("did not identify the isolated registered marketplace", output)

    def test_json_list_outside_root_fails(self) -> None:
        result = self.run_fresh("json_outside_root", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)

    def test_json_list_registered_root_still_requires_package_identity(self) -> None:
        result = self.run_fresh("json_invalid_registered_root", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)

    def test_text_list_with_verified_root_passes(self) -> None:
        result = self.run_fresh("text_list_good", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Marketplace listing: passed", output)

    def test_text_list_name_only_fails(self) -> None:
        result = self.run_fresh("text_list_name_only", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)

    def test_text_list_wrong_root_fails(self) -> None:
        result = self.run_fresh("text_list_wrong_root", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)

    def test_advertised_list_failure_fails(self) -> None:
        result = self.run_fresh("list_failure", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Marketplace listing: failed", output)

    def test_advertised_plugin_add_failure_fails(self) -> None:
        result = self.run_fresh("plugin_failure", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Plugin installation: failed", output)

    def test_non_json_plugin_install_discovers_nested_root(self) -> None:
        result = self.run_fresh("plugin_non_json", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Plugin installation: passed", output)
        self.assertIn("installed plugin files verified", output)

    def test_source_tree_only_plugin_manifest_is_rejected(self) -> None:
        result = self.run_fresh("plugin_source_only", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plugin add succeeded but installed package was not verified", output)

    def test_marketplace_snapshot_is_not_plugin_install(self) -> None:
        result = self.run_fresh("snapshot_source_only", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plugin add succeeded but installed package was not verified", output)

    def test_marketplace_snapshot_plus_separate_plugin_install_passes(self) -> None:
        result = self.run_fresh("snapshot_plus_install", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Plugin installation: passed", output)

    def test_ambiguous_plugin_roots_fail(self) -> None:
        result = self.run_fresh("plugin_ambiguous", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous plugin roots", output)

    def test_plugin_list_available_only_fails(self) -> None:
        result = self.run_fresh("plugin_list_available_only", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Plugin listing: failed", output)
        self.assertIn("exact installed plugin identity", output)

    def test_plugin_list_wrong_version_fails(self) -> None:
        result = self.run_fresh("plugin_list_wrong_version", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Plugin listing: failed", output)
        self.assertIn("exact installed plugin identity", output)

    def test_plugin_list_text_substring_fails(self) -> None:
        result = self.run_fresh("plugin_list_text_substring", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Plugin listing: failed", output)
        self.assertIn("exact installed plugin identity", output)

    def test_explicit_skip_does_not_run_cli(self) -> None:
        result = self.run_fresh("old", "--skip-codex-cli", "--verbose")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Marketplace registration: skipped_by_flag", output)
        self.assertFalse((self.temp / "old.log").exists())

    def test_strict_mode_fails_when_codex_unavailable(self) -> None:
        result = self.run_fresh("old", "--require-codex-cli", "--verbose", with_codex=False)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Codex CLI not installed", output)

    def test_require_plugin_install_fails_when_plugin_add_unavailable(self) -> None:
        result = self.run_fresh("old", "--require-plugin-install", "--verbose")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("actual plugin installation command is unavailable", output)


if __name__ == "__main__":
    unittest.main()
