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
                        "version": "0.1.0",
                        "installedPath": str(installed),
                    }))
                else:
                    print(f"Installed {plugin_name}.")
                raise SystemExit(0)

            if argv[:2] == ["plugin", "list"]:
                installed = codex_home / "plugins" / plugin_name
                if "--json" in argv:
                    if scenario == "plugin_list_available_only":
                        print(json.dumps({"installed": [], "available": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.1.0"}]}))
                        raise SystemExit(0)
                    if scenario == "plugin_list_wrong_version":
                        print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "9.9.9", "installed": installed.exists()}]}))
                        raise SystemExit(0)
                    print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.1.0", "installed": installed.exists()}]}))
                elif scenario == "plugin_list_text_substring":
                    print(f"{plugin_name}-old {marketplace_name} 0.1.0 installed")
                else:
                    print(f"{plugin_name} {marketplace_name} 0.1.0 installed")
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
