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
from unittest import mock


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
FULL_VALIDATION = load_module(
    "full_skill_validation_under_test",
    ROOT / "scripts" / "full_skill_validation.py",
)
FRESH_INSTALL = load_module(
    "test_fresh_install_under_test",
    ROOT / "scripts" / "test_fresh_install.py",
)
RELEASE_READINESS = load_module(
    "check_release_readiness_under_test",
    ROOT / "scripts" / "check_release_readiness.py",
)
FORMAL_VALIDATOR = load_module(
    "validate_formal_schemas_release_evidence_under_test",
    ROOT / "scripts" / "validate_formal_schemas.py",
)


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
                        "version": "0.4.1",
                        "installedPath": str(installed),
                    }))
                else:
                    print(f"Installed {plugin_name}.")
                raise SystemExit(0)

            if argv[:2] == ["plugin", "list"]:
                installed = codex_home / "plugins" / plugin_name
                if "--json" in argv:
                    if scenario == "plugin_list_available_only":
                        print(json.dumps({"installed": [], "available": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.4.1"}]}))
                        raise SystemExit(0)
                    if scenario == "plugin_list_wrong_version":
                        print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "9.9.9", "installed": installed.exists()}]}))
                        raise SystemExit(0)
                    print(json.dumps({"installed": [{"name": plugin_name, "marketplaceName": marketplace_name, "version": "0.4.1", "installed": installed.exists()}]}))
                elif scenario == "plugin_list_text_substring":
                    print(f"{plugin_name}-old {marketplace_name} 0.2.1 installed")
                else:
                    print(f"{plugin_name} {marketplace_name} 0.4.1 installed")
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
        self.assertIn(
            "marketplace source.ref must match immutable release tag 'v0.4.1'",
            output,
        )

    def test_fresh_install_static_marketplace_requires_matching_tag(self) -> None:
        for index, bad_ref in enumerate(
            ["main", "master", "latest", "v0.2.5", "release-candidate", None]
        ):
            with self.subTest(ref=bad_ref):
                repo = self.temp / f"fresh-marketplace-ref-{index}"
                shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                marketplace = repo / ".agents" / "plugins" / "marketplace.json"
                data = json.loads(marketplace.read_text(encoding="utf-8"))
                if bad_ref is None:
                    data["plugins"][0]["source"].pop("ref")
                else:
                    data["plugins"][0]["source"]["ref"] = bad_ref
                marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                self.assertIsNone(
                    FRESH_INSTALL.verify_marketplace_root(
                        repo,
                        marketplace_name="codex-long-horizon-skills",
                        plugin_name="codex-long-horizon-skill",
                        version="0.4.1",
                        boundary=self.temp,
                    )
                )

    def test_fresh_install_static_marketplace_accepts_matching_prospective_tag(self) -> None:
        repo = self.temp / "fresh-marketplace-matching-tag"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.assertEqual(
            FRESH_INSTALL.verify_marketplace_root(
                repo,
                marketplace_name="codex-long-horizon-skills",
                plugin_name="codex-long-horizon-skill",
                version="0.4.1",
                boundary=self.temp,
            ),
            str(repo.resolve()),
        )


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
        release_state: str = "final",
    ) -> subprocess.CompletedProcess[str]:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            [
                sys.executable,
                "scripts/check_release_readiness.py",
                "--version",
                "0.4.1",
                "--release-state",
                release_state,
                *args,
            ],
            cwd=repo,
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def set_candidate_state(self, repo: Path) -> None:
        release_notes = self.release_notes(repo)
        release_notes.write_text(
            release_notes.read_text(encoding="utf-8").replace(
                "Release state: final",
                "Release state: candidate",
                1,
            ),
            encoding="utf-8",
        )
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        marketplace_data = json.loads(marketplace.read_text(encoding="utf-8"))
        marketplace_data["plugins"][0]["policy"]["installation"] = "NOT_AVAILABLE"
        marketplace.write_text(
            json.dumps(marketplace_data, indent=2) + "\n",
            encoding="utf-8",
        )

        for skill_name in ("long-horizon-engineering", "ai-video-production"):
            skill = repo / ".agents" / "skills" / skill_name / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "update_channel: stable",
                    "update_channel: candidate",
                    1,
                ),
                encoding="utf-8",
            )
            release_manifest = repo / "releases" / skill_name / "latest.json"
            manifest_data = json.loads(release_manifest.read_text(encoding="utf-8"))
            manifest_data["channel"] = "candidate"
            manifest_data["released"] = False
            manifest_data["risk"] = "not-assessed"
            release_manifest.write_text(
                json.dumps(manifest_data, indent=2) + "\n",
                encoding="utf-8",
            )

        latest = repo / "releases" / "latest.json"
        latest_data = json.loads(latest.read_text(encoding="utf-8"))
        latest_data["channel"] = "candidate"
        latest_data["released"] = False
        latest.write_text(
            json.dumps(latest_data, indent=2) + "\n",
            encoding="utf-8",
        )

    def release_notes(self, repo: Path) -> Path:
        return repo / "docs" / "releases" / "v0.4.1.md"

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
        subprocess.run(["git", "tag", "v0.4.1"], cwd=repo, check=True, capture_output=True, text=True)

    def init_committed_repo(self, repo: Path) -> tuple[str, str]:
        subprocess.run(
            ["git", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "candidate",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "show", "-s", "--format=%T", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return head, tree

    def write_formal_result(
        self,
        repo: Path,
        *,
        status: str = "PASS",
        artifact_override: list[dict] | None = None,
    ) -> Path:
        head, tree = self.init_committed_repo(repo)
        result = {
            "status": status,
            "gate": "formal-draft-2020-12",
            "draft": "https://json-schema.org/draft/2020-12/schema",
            "candidate_commit": head,
            "candidate_tree": tree,
            "python_version": "3.11.15",
            "system": "Linux",
            "machine": "x86_64",
            "schema_count": 21,
            "validator_sha256": RELEASE_READINESS.sha256_file(
                repo / "scripts" / "validate_formal_schemas.py"
            ),
            "lock_sha256": RELEASE_READINESS.sha256_file(
                repo / "requirements-release.txt"
            ),
            "artifacts": (
                RELEASE_READINESS.FORMAL_SCHEMA_ARTIFACTS
                if artifact_override is None
                else artifact_override
            ),
        }
        path = self.temp / f"{repo.name}-formal-result.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def assert_failed_without_traceback(self, result: subprocess.CompletedProcess[str], expected: str) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(expected, output)
        self.assertNotIn("Traceback", output)

    def test_candidate_release_notes_pass_static_consistency(self) -> None:
        repo = self.copy_repo("publishable")
        self.set_candidate_state(repo)
        result = self.run_readiness(
            repo, "--allow-existing-tag", release_state="candidate"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allow-existing-tag", result.stdout)
        self.assertIn("release-state=candidate", result.stdout)

    def test_release_notes_state_must_match_requested_state(self) -> None:
        repo = self.copy_repo("release-notes-state-mismatch")
        release_notes = self.release_notes(repo)
        release_notes.write_text(
            release_notes.read_text(encoding="utf-8").replace(
                "Release state: final",
                "Release state: candidate",
                1,
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(
            result,
            "release notes state 'candidate' does not match 'final'",
        )

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
            self.changelog(repo).read_text(encoding="utf-8").replace("## 0.4.1 - 2026-08-01", "## 0.4.1"),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG missing dated version section")

    def test_empty_dated_changelog_section_fails(self) -> None:
        repo = self.copy_repo("empty-changelog")
        self.changelog(repo).write_text(
            "# Changelog\n\nAll notable changes to this project are summarized here.\n\n"
            "## Unreleased\n\nNo unreleased changes.\n\n"
            "## 0.4.1 - 2026-08-01\n\n"
            "## 2026-06-15\n\n- Older work.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG version section is empty")

    def test_valid_dated_changelog_section_passes(self) -> None:
        repo = self.copy_repo("valid-changelog")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_notes_match_formal_schema_inventory(self) -> None:
        notes = self.release_notes(ROOT).read_text(encoding="utf-8")
        normalized = " ".join(notes.split())
        schema_count = len(FORMAL_VALIDATOR.SCHEMA_INVENTORY)
        fixture_count = len(FORMAL_VALIDATOR.FIXTURE_VALIDATED_SCHEMAS)
        syntax_only_count = len(FORMAL_VALIDATOR.SYNTAX_ONLY_SCHEMAS)

        self.assertEqual(schema_count, fixture_count + syntax_only_count)
        self.assertIn(
            f"contains {schema_count} Draft 2020-12 schemas",
            normalized,
        )
        self.assertIn(
            f"{fixture_count} schemas have explicit positive and negative "
            "instance fixtures",
            normalized,
        )
        self.assertIn(
            f"remaining {syntax_only_count} are explicitly syntax-only",
            normalized,
        )

    def test_installation_docs_bind_v033_final_state(self) -> None:
        for relative_path in (
            "README.md",
            "INSTALL.md",
            "UPGRADE_GUIDE.md",
            "docs/plugin-install.md",
        ):
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("--ref v0.4.1", text)
                self.assertNotIn("--ref v0.3.0", text)
                self.assertIn("AVAILABLE", text)

    def test_v031_release_truth_includes_profile_assembly_boundary(self) -> None:
        notes = " ".join(
            (ROOT / "docs" / "releases" / "v0.3.1.md").read_text(
                encoding="utf-8"
            ).split()
        )
        changelog = " ".join(
            self.changelog(ROOT).read_text(encoding="utf-8").split()
        )

        self.assertIn("profile-assembly tooling merged by PR #92", notes)
        self.assertIn("default mode is read-only", notes)
        self.assertIn(
            "empty caller-selected output directory outside the source repository",
            notes,
        )
        self.assertIn("does not install or activate a profile", notes)
        self.assertIn("profile-assembly validation from PR #92", changelog)

    def test_v030_release_notes_remain_historical_candidate(self) -> None:
        notes = (
            ROOT / "docs" / "releases" / "v0.3.0.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Phase A static release-prep candidate", notes)
        self.assertIn("policy.installation` to `NOT_AVAILABLE", notes)

    def test_release_docs_preserve_single_acquisition_boundary(self) -> None:
        notes = self.release_notes(ROOT).read_text(encoding="utf-8")
        checklist = (
            ROOT / "docs" / "maintainers" / "release-checklist.md"
        ).read_text(encoding="utf-8")
        normalized_notes = " ".join(notes.split())
        normalized_checklist = " ".join(checklist.split())
        combined = normalized_notes + " " + normalized_checklist

        self.assertIn("one approved online acquisition", normalized_notes)
        self.assertIn("one approved online acquisition", normalized_checklist)
        self.assertIn(
            "does not perform a second live acquisition",
            normalized_notes,
        )
        self.assertIn(
            "must not issue a second live acquisition",
            normalized_checklist,
        )
        self.assertIn("consumes the same raw evidence", combined)
        self.assertNotIn("live-recomputed acquisition", combined)
        self.assertNotIn("rechecks the acquisition receipt against", combined)

    def test_release_docs_record_action_and_security_provenance(self) -> None:
        checklist = (
            ROOT / "docs" / "maintainers" / "release-checklist.md"
        ).read_text(encoding="utf-8")
        release_notes = (
            ROOT / "docs" / "releases" / "v0.3.0.md"
        ).read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        normalized_checklist = " ".join(checklist.split())
        normalized_release_notes = " ".join(release_notes.split())
        normalized_security = " ".join(security.split())

        self.assertIn("11d5960a326750d5838078e36cf38b85af677262", checklist)
        self.assertIn("a26af69be951a213d495a4c3e4e4022e16d87065", checklist)
        self.assertIn("20be877a16bf41e3817c8d173aa58053adc02cdc", checklist)
        self.assertIn("Official-source verification completed", normalized_checklist)
        self.assertIn("v4.4.0", checklist)
        self.assertIn("v5.6.0", checklist)
        self.assertIn(
            "https://github.com/actions/checkout/commit/"
            "11d5960a326750d5838078e36cf38b85af677262",
            checklist,
        )
        self.assertIn(
            "https://github.com/actions/setup-python/commit/"
            "a26af69be951a213d495a4c3e4e4022e16d87065",
            checklist,
        )
        self.assertIn("GitHub security-advisories API returned an empty list", normalized_checklist)
        self.assertIn("not proof that the Actions are vulnerability-free", normalized_checklist)
        self.assertIn("rechecked on 2026-08-01 without identity drift", normalized_checklist)
        self.assertIn("ubuntu:24.04", normalized_release_notes)
        self.assertIn("CPython 3.11.15", normalized_release_notes)
        self.assertIn("all 36 positive and 13 negative fixture cases passed", normalized_release_notes)
        self.assertIn("content validation only", normalized_release_notes)
        self.assertIn("did not produce a candidate-bound formal release receipt", normalized_release_notes)
        self.assertIn("remains PENDING", normalized_release_notes)
        self.assertIn("still not release-ready", normalized_release_notes)
        self.assertIn("release/0.2.x", security)
        self.assertIn("Retired maintenance line", security)
        self.assertIn("maintenance window ended on 2026-07-31", security)
        self.assertIn("No routine security or feature backports", security)
        self.assertNotIn("Security-maintenance only", security)
        for control in (
            "private vulnerability reporting",
            "Code Scanning",
            "Dependabot",
            "Secret Scanning",
            "push protection",
        ):
            self.assertIn(control.lower(), normalized_security.lower())
            self.assertIn(control.lower(), normalized_checklist.lower())

    def test_full_validation_reports_timeout_without_traceback(self) -> None:
        timeout = subprocess.TimeoutExpired(
            ["python3", "slow.py"],
            7,
            output="partial output\n",
            stderr="partial error\n",
        )
        with mock.patch.object(FULL_VALIDATION.subprocess, "run", side_effect=timeout):
            result = FULL_VALIDATION.run_command(["python3", "slow.py"], timeout=7)

        self.assertEqual(124, result.returncode)
        self.assertIn("partial output", result.stdout)
        self.assertIn("partial error", result.stderr)
        self.assertIn("command timed out after 7 seconds", result.stderr)

    def test_full_validation_gives_unittest_discovery_extended_budget(self) -> None:
        calls: list[tuple[list[str], int]] = []

        def fake_run(
            command: list[str],
            *,
            timeout: int,
        ) -> subprocess.CompletedProcess[str]:
            calls.append((command, timeout))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        report = FULL_VALIDATION.Report()
        with mock.patch.object(FULL_VALIDATION, "run_command", side_effect=fake_run):
            FULL_VALIDATION.run_core_commands(report)

        timeout_by_command = {tuple(command): timeout for command, timeout in calls}
        self.assertEqual(
            FULL_VALIDATION.FULL_UNITTEST_TIMEOUT_SECONDS,
            timeout_by_command[tuple(FULL_VALIDATION.FULL_UNITTEST_COMMAND)],
        )
        self.assertGreater(
            FULL_VALIDATION.FULL_UNITTEST_TIMEOUT_SECONDS,
            FULL_VALIDATION.DEFAULT_COMMAND_TIMEOUT_SECONDS,
        )

    def test_release_hygiene_binds_origin_main_clean_linked_worktree(self) -> None:
        expected = "a" * 40
        commands = {
            ("git", "rev-parse", f"{expected}^{{commit}}"): expected,
            (
                "git",
                "rev-parse",
                "refs/remotes/origin/main^{commit}",
            ): expected,
            ("git", "merge-base", expected, "HEAD"): expected,
            ("git", "status", "--porcelain=v1", "--untracked-files=all"): "",
            (
                "git",
                "rev-parse",
                "--path-format=absolute",
                "--git-dir",
            ): "/repo/.git/worktrees/release",
            (
                "git",
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ): "/repo/.git",
        }

        def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=commands[tuple(command)] + "\n",
                stderr="",
            )

        with mock.patch.object(RELEASE_READINESS, "run", side_effect=fake_run):
            errors: list[str] = []
            RELEASE_READINESS.release_hygiene_errors(expected, errors)
        self.assertEqual([], errors)

    def test_release_hygiene_rejects_stale_dirty_or_primary_worktree(self) -> None:
        expected = "a" * 40
        base_commands = {
            ("git", "rev-parse", f"{expected}^{{commit}}"): expected,
            (
                "git",
                "rev-parse",
                "refs/remotes/origin/main^{commit}",
            ): expected,
            ("git", "merge-base", expected, "HEAD"): expected,
            ("git", "status", "--porcelain=v1", "--untracked-files=all"): "",
            (
                "git",
                "rev-parse",
                "--path-format=absolute",
                "--git-dir",
            ): "/repo/.git/worktrees/release",
            (
                "git",
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ): "/repo/.git",
        }
        mutations = (
            (
                ("git", "rev-parse", "refs/remotes/origin/main^{commit}"),
                "b" * 40,
                "does not match local origin/main",
            ),
            (
                ("git", "status", "--porcelain=v1", "--untracked-files=all"),
                "?? untracked.txt",
                "requires a clean worktree",
            ),
            (
                ("git", "rev-parse", "--path-format=absolute", "--git-dir"),
                "/repo/.git",
                "requires an isolated linked worktree",
            ),
        )
        for key, value, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                commands = dict(base_commands)
                commands[key] = value

                def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=commands[tuple(command)] + "\n",
                        stderr="",
                    )

                with mock.patch.object(
                    RELEASE_READINESS,
                    "run",
                    side_effect=fake_run,
                ):
                    errors: list[str] = []
                    RELEASE_READINESS.release_hygiene_errors(expected, errors)
                self.assertTrue(any(expected_error in error for error in errors))

    def test_release_hygiene_is_valid_only_for_static_release_prep(self) -> None:
        repo = self.copy_repo("release-hygiene-mode")
        result = self.run_readiness(
            repo,
            "--allow-existing-tag",
            "--release-hygiene-base",
            "a" * 40,
        )
        self.assert_failed_without_traceback(
            result,
            "release hygiene base is valid only with --pre-tag-static",
        )

    def test_release_warning_gate_allows_only_known_optional_omissions(self) -> None:
        report = FULL_VALIDATION.Report()
        section, name, detail = next(iter(FULL_VALIDATION.ALLOWED_RELEASE_WARNINGS))
        report.warn(section, name, detail)
        FULL_VALIDATION.enforce_release_warning_allowlist(report)
        self.assertEqual(report.failures(), [])
        waivers = report.by_section()["Release Warning Waivers"]
        self.assertEqual(len(waivers), 1)
        self.assertIn("_", waivers[0].detail.split(":", 1)[0])
        self.assertNotEqual(waivers[0].detail.split(":", 1)[-1].strip(), "")

    def test_all_optional_warning_waivers_are_explicit_and_visible(self) -> None:
        self.assertEqual(len(FULL_VALIDATION.OPTIONAL_WARNING_WAIVERS), 11)
        report = FULL_VALIDATION.Report()
        for section, name, detail in FULL_VALIDATION.OPTIONAL_WARNING_WAIVERS:
            report.warn(section, name, detail)

        FULL_VALIDATION.enforce_release_warning_allowlist(report)

        waivers = report.by_section()["Release Warning Waivers"]
        self.assertEqual(len(waivers), 11)
        self.assertEqual(report.failures(), [])
        for check in waivers:
            reason_code, rationale = check.detail.split(":", 1)
            self.assertRegex(reason_code, r"^[A-Z][A-Z0-9_]+$")
            self.assertGreaterEqual(len(rationale.strip()), 40)

    def test_release_warning_gate_rejects_new_warning(self) -> None:
        report = FULL_VALIDATION.Report()
        report.warn("Unexpected", "new warning", "not allowlisted")
        FULL_VALIDATION.enforce_release_warning_allowlist(report)
        self.assertEqual(len(report.failures()), 1)

    def test_manifest_version_mismatch_fails(self) -> None:
        repo = self.copy_repo("manifest-mismatch")
        manifest = repo / ".codex-plugin" / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "plugin version '9.9.9' does not match '0.4.1'")

    def test_marketplace_ref_must_match_release_version(self) -> None:
        for index, bad_ref in enumerate(
            ["main", "master", "latest", "v0.2.5", "release-candidate", None]
        ):
            with self.subTest(ref=bad_ref):
                repo = self.copy_repo(f"marketplace-ref-mismatch-{index}")
                marketplace = repo / ".agents" / "plugins" / "marketplace.json"
                data = json.loads(marketplace.read_text(encoding="utf-8"))
                if bad_ref is None:
                    data["plugins"][0]["source"].pop("ref")
                else:
                    data["plugins"][0]["source"]["ref"] = bad_ref
                marketplace.write_text(
                    json.dumps(data, indent=2) + "\n",
                    encoding="utf-8",
                )
                result = self.run_readiness(repo, "--allow-existing-tag")
                self.assert_failed_without_traceback(
                    result,
                    "does not match immutable release tag 'v0.4.1'",
                )

    def test_unreleased_candidate_marketplace_is_not_installable(self) -> None:
        repo = self.copy_repo("marketplace-policy-installable")
        self.set_candidate_state(repo)
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        data["plugins"][0]["policy"]["installation"] = "AVAILABLE"
        marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            release_state="candidate",
        )
        self.assert_failed_without_traceback(
            result,
            "marketplace policy.installation must be 'NOT_AVAILABLE' for "
            "release state 'candidate'",
        )

    def test_release_manifests_cannot_self_report_stable_release(self) -> None:
        repo = self.copy_repo("release-manifest-stable")
        self.set_candidate_state(repo)
        manifest = repo / "releases/long-horizon-engineering/latest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["channel"] = "stable"
        data["released"] = True
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            release_state="candidate",
        )
        self.assert_failed_without_traceback(
            result,
            "must describe release state 'candidate'",
        )

    def test_unreleased_candidate_risk_cannot_self_report_low(self) -> None:
        for skill_name in (
            "long-horizon-engineering",
            "ai-video-production",
        ):
            with self.subTest(skill=skill_name):
                repo = self.copy_repo(f"release-risk-{skill_name}")
                self.set_candidate_state(repo)
                manifest = repo / "releases" / skill_name / "latest.json"
                data = json.loads(manifest.read_text(encoding="utf-8"))
                self.assertEqual(data["risk"], "not-assessed")
                data["risk"] = "low"
                manifest.write_text(
                    json.dumps(data, indent=2) + "\n",
                    encoding="utf-8",
                )
                result = self.run_readiness(
                    repo,
                    "--pre-tag-static",
                    release_state="candidate",
                )
                self.assert_failed_without_traceback(
                    result,
                    "risk must be 'not-assessed' for release state 'candidate'",
                )

    def test_skill_cannot_self_report_stable_update_channel(self) -> None:
        repo = self.copy_repo("skill-stable-channel")
        self.set_candidate_state(repo)
        skill = repo / ".agents/skills/long-horizon-engineering/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "update_channel: candidate",
                "update_channel: stable",
                1,
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            release_state="candidate",
        )
        self.assert_failed_without_traceback(
            result,
            "must declare update_channel: candidate for release state 'candidate'",
        )

    def test_skill_version_must_match_release_version(self) -> None:
        repo = self.copy_repo("skill-version-mismatch")
        skill = repo / ".agents" / "skills" / "ai-video-production" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "version: 0.4.1",
                "version: 9.9.9",
                1,
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(
            result,
            "ai-video-production/SKILL.md version '9.9.9' does not match '0.4.1'",
        )

    def test_release_manifest_date_must_match_release_notes(self) -> None:
        repo = self.copy_repo("release-manifest-date-mismatch")
        manifest = repo / "releases" / "long-horizon-engineering" / "latest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["release_date"] = "2026-07-26"
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(
            result,
            "release_date '2026-07-26' does not match '2026-08-01'",
        )

    def test_release_note_date_must_match_changelog_date(self) -> None:
        repo = self.copy_repo("mismatched-release-date")
        self.changelog(repo).write_text(
            self.changelog(repo).read_text(encoding="utf-8").replace(
                "## 0.4.1 - 2026-08-01",
                "## 0.4.1 - 2026-07-23",
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(repo, "--allow-existing-tag")
        self.assert_failed_without_traceback(result, "CHANGELOG missing dated version section")

    def test_pre_tag_static_passes_without_formal_schema_gate(self) -> None:
        repo = self.copy_repo("pre-tag-static")
        self.set_candidate_state(repo)
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            release_state="candidate",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("formal Draft 2020-12 schema validation is UNVERIFIED", result.stdout)
        self.assertIn("not release-ready", result.stdout)

    def test_pre_tag_static_rejects_final_release_state(self) -> None:
        repo = self.copy_repo("pre-tag-static-final")
        result = self.run_readiness(
            repo, "--pre-tag-static", release_state="final"
        )
        self.assert_failed_without_traceback(
            result,
            "final release state is forbidden with --pre-tag-static",
        )

    def test_final_release_state_requires_exact_stable_contract(self) -> None:
        mutations = (
            (
                ".agents/plugins/marketplace.json",
                lambda data: data["plugins"][0]["policy"].update(
                    installation="NOT_AVAILABLE"
                ),
                "must be 'AVAILABLE' for release state 'final'",
            ),
            (
                "releases/long-horizon-engineering/latest.json",
                lambda data: data.update(channel="candidate", released=False),
                "must describe release state 'final'",
            ),
            (
                "releases/ai-video-production/latest.json",
                lambda data: data.update(risk="not-assessed"),
                "risk must be 'reviewed' for release state 'final'",
            ),
            (
                "releases/latest.json",
                lambda data: data.update(channel="candidate", released=False),
                "releases/latest.json must describe release state 'final'",
            ),
        )
        for index, (relative_path, mutate, expected) in enumerate(mutations):
            with self.subTest(path=relative_path):
                repo = self.copy_repo(f"final-state-mutation-{index}")
                path = repo / relative_path
                data = json.loads(path.read_text(encoding="utf-8"))
                mutate(data)
                path.write_text(
                    json.dumps(data, indent=2) + "\n",
                    encoding="utf-8",
                )
                result = self.run_readiness(
                    repo, "--allow-existing-tag", release_state="final"
                )
                self.assert_failed_without_traceback(result, expected)

    def test_final_release_state_requires_stable_skill_channels(self) -> None:
        repo = self.copy_repo("final-state-skill-channel")
        skill = repo / ".agents/skills/long-horizon-engineering/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "update_channel: stable",
                "update_channel: candidate",
                1,
            ),
            encoding="utf-8",
        )
        result = self.run_readiness(
            repo, "--allow-existing-tag", release_state="final"
        )
        self.assert_failed_without_traceback(
            result,
            "must declare update_channel: stable for release state 'final'",
        )

    def test_pre_tag_is_blocked_until_formal_schema_gate(self) -> None:
        repo = self.copy_repo("pre-tag-formal-blocked")
        result = self.run_readiness(repo, "--pre-tag")
        self.assert_failed_without_traceback(
            result,
            "formal Draft 2020-12 schema gate is UNVERIFIED",
        )

    def test_pre_tag_rejects_handwritten_pass_receipt(self) -> None:
        repo = self.copy_repo("pre-tag-handwritten-pass")
        result_path = self.write_formal_result(repo)
        result = self.run_readiness(
            repo,
            "--pre-tag",
            "--formal-schema-result",
            str(result_path),
            "--formal-schema-pip-report",
            str(self.temp / "pip-report.json"),
            "--formal-schema-acquisition-result",
            str(self.temp / "acquisition.json"),
            "--formal-schema-evidence-dir",
            str(self.temp / "formal-evidence"),
            "--formal-schema-candidate-base",
            "a" * 40,
            release_state="final",
        )
        self.assert_failed_without_traceback(
            result,
            "prewritten PASS receipts are not accepted",
        )

    def test_pre_tag_rejects_dirty_candidate_before_formal_execution(self) -> None:
        repo = self.copy_repo("pre-tag-dirty-candidate")
        result_path = self.write_formal_result(repo)
        result_path.unlink()
        readme = repo / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\nDirty formal probe.\n",
            encoding="utf-8",
        )
        result = self.run_readiness(
            repo,
            "--pre-tag",
            "--formal-schema-result",
            str(result_path),
            "--formal-schema-pip-report",
            str(self.temp / "pip-report.json"),
            "--formal-schema-acquisition-result",
            str(self.temp / "acquisition.json"),
            "--formal-schema-evidence-dir",
            str(self.temp / "formal-evidence"),
            "--formal-schema-candidate-base",
            "a" * 40,
        )
        self.assert_failed_without_traceback(
            result,
            "formal gate requires a clean candidate worktree",
        )

    def test_pre_tag_requires_all_controlled_formal_inputs(self) -> None:
        repo = self.copy_repo("pre-tag-formal-inputs")
        result_path = self.temp / "new-formal-result.json"
        result = self.run_readiness(
            repo,
            "--pre-tag",
            "--formal-schema-result",
            str(result_path),
        )
        self.assert_failed_without_traceback(
            result,
            "--formal-schema-pip-report",
        )

    def test_pre_tag_requires_job_local_evidence_directory(self) -> None:
        repo = self.copy_repo("pre-tag-formal-evidence-dir")
        result = self.run_readiness(
            repo,
            "--pre-tag",
            "--formal-schema-result",
            str(self.temp / "formal-result.json"),
            "--formal-schema-pip-report",
            str(self.temp / "pip-report.json"),
            "--formal-schema-acquisition-result",
            str(self.temp / "acquisition.json"),
        )
        self.assert_failed_without_traceback(
            result,
            "--formal-schema-evidence-dir",
        )

    def test_pre_tag_requires_current_descendant_candidate_base(self) -> None:
        repo = self.copy_repo("pre-tag-candidate-base")
        result = self.run_readiness(
            repo,
            "--pre-tag",
            "--formal-schema-result",
            str(self.temp / "formal-result.json"),
            "--formal-schema-pip-report",
            str(self.temp / "pip-report.json"),
            "--formal-schema-acquisition-result",
            str(self.temp / "acquisition.json"),
            "--formal-schema-evidence-dir",
            str(self.temp / "formal-evidence"),
        )
        self.assert_failed_without_traceback(
            result,
            "--formal-schema-candidate-base",
        )

    def test_non_formal_mode_rejects_formal_schema_result(self) -> None:
        repo = self.copy_repo("static-with-formal-result")
        self.set_candidate_state(repo)
        result_path = self.temp / "unused-formal-result.json"
        result_path.write_text("{}", encoding="utf-8")
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            "--formal-schema-result",
            str(result_path),
            release_state="candidate",
        )
        self.assert_failed_without_traceback(
            result,
            "formal schema inputs are forbidden with --pre-tag-static",
        )

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
        result = self.run_readiness(repo, "--pre-tag-static", "--allow-existing-tag")
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

    def test_static_mode_performs_no_git_or_network_check(self) -> None:
        repo = self.copy_repo("static-no-remote-check")
        self.set_candidate_state(repo)
        fake_bin = self.temp / "fake-bin-static"
        fake_bin.mkdir()
        fake_git = fake_bin / "git"
        fake_git.write_text("#!/bin/sh\necho git should not run >&2\nexit 99\n", encoding="utf-8")
        fake_git.chmod(0o755)
        env = {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
        result = self.run_readiness(
            repo,
            "--pre-tag-static",
            env=env,
            release_state="candidate",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_release_content_under_unreleased_fails(self) -> None:
        repo = self.copy_repo("duplicated-changelog")
        text = self.changelog(repo).read_text(encoding="utf-8")
        duplicated = (
            "- Changed the default source-package profile to `local-governance-core` while\n"
            "  retaining `legacy-full` as an explicit compatibility profile.\n"
        )
        unreleased_heading = "## Unreleased\n"
        if unreleased_heading in text:
            text = text.replace(unreleased_heading, unreleased_heading + "\n" + duplicated, 1)
        else:
            text = text.replace(
                "# Changelog\n",
                "# Changelog\n\n" + unreleased_heading + "\n" + duplicated,
                1,
            )
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
