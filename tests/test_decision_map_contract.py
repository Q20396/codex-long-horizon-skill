import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LHE = ROOT / ".agents" / "skills" / "long-horizon-engineering"
REFERENCE = LHE / "references" / "decision-map-and-frontier.md"
TEMPLATE = LHE / "templates" / "DECISION_MAP_TEMPLATE.md"
SCRIPT = LHE / "scripts" / "compute_frontier.py"
DECISION_MAP_SCHEMA = LHE / "schemas" / "decision-map.schema.json"
FRONTIER_SCHEMA = LHE / "schemas" / "frontier.schema.json"
PACKAGE_CHECKER = LHE / "scripts" / "check_skill_package.py"

spec = importlib.util.spec_from_file_location("compute_frontier", SCRIPT)
compute_frontier_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compute_frontier_module)


class DecisionMapContractTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"Missing required file: {path}")
        return path.read_text(encoding="utf-8")

    def assert_contains_all(self, text: str, phrases: list[str]) -> None:
        normalized_text = " ".join(text.split())
        for phrase in phrases:
            self.assertIn(" ".join(phrase.split()), normalized_text)

    def base_map(self) -> dict:
        return {
            "metadata": {"schema_version": "1.0", "updated_at": "2026-07-24"},
            "destination": {
                "outcome": "Ship a small planning layer.",
                "success_criteria": ["Frontier is deterministic."],
            },
            "decisions": [],
            "unknowns": [],
            "out_of_scope": [],
            "work_items": [
                {"id": "WORK-001", "title": "Design", "status": "completed"},
                {"id": "WORK-002", "title": "Implement", "status": "pending"},
                {"id": "WORK-003", "title": "Review", "status": "pending"},
            ],
            "dependencies": [
                {"work_item": "WORK-002", "depends_on": "WORK-001"},
                {"work_item": "WORK-003", "depends_on": "WORK-002"},
            ],
            "frontier": ["WORK-002"],
        }

    def compute(self, decision_map: dict) -> list[str]:
        return compute_frontier_module.compute_frontier(decision_map)

    def assert_invalid(self, decision_map: dict, phrase: str) -> None:
        with self.assertRaisesRegex(compute_frontier_module.DecisionMapError, phrase):
            self.compute(decision_map)

    def test_reference_defines_planning_only_boundary(self) -> None:
        text = self.read(REFERENCE)
        self.assert_contains_all(
            text,
            [
                "planning layer only",
                "does not execute work",
                "grant write permission",
                "replace checkpoints",
                "Frontier MUST be generated",
                "Planning is not execution",
                "Frontier is not permission",
                "Recommendation is not approval",
                "Decision Map is optional",
                "Existing checkpoint, resume, authority, rollback, validation, and independent review protocols remain valid",
            ],
        )

    def test_template_and_skill_route_are_present(self) -> None:
        template = self.read(TEMPLATE)
        skill = self.read(LHE / "SKILL.md")
        self.assert_contains_all(
            template,
            [
                "Destination",
                "Decisions",
                "Unknowns",
                "Out Of Scope",
                "Work Items",
                "Dependencies",
                "Computed Frontier",
                "Do not edit manually",
                "Frontier is not permission",
            ],
        )
        self.assert_contains_all(
            skill,
            [
                "decision-map-and-frontier.md",
                "planning-only Decision Map",
                "not execution permission",
            ],
        )

    def test_schema_files_are_valid_json(self) -> None:
        for path in [DECISION_MAP_SCHEMA, FRONTIER_SCHEMA]:
            data = json.loads(self.read(path))
            self.assertEqual(data["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("properties", data)

    def test_decision_map_files_are_package_required(self) -> None:
        checker = self.read(PACKAGE_CHECKER)
        self.assert_contains_all(
            checker,
            [
                "references/decision-map-and-frontier.md",
                "templates/DECISION_MAP_TEMPLATE.md",
                "scripts/compute_frontier.py",
                "schemas/decision-map.schema.json",
                "schemas/frontier.schema.json",
            ],
        )

    def test_simple_graph_and_stable_order(self) -> None:
        decision_map = self.base_map()
        decision_map["work_items"].append(
            {"id": "WORK-004", "title": "Docs", "status": "pending"}
        )
        decision_map["frontier"] = ["WORK-002", "WORK-004"]
        self.assertEqual(self.compute(decision_map), ["WORK-002", "WORK-004"])

    def test_multiple_branches(self) -> None:
        decision_map = self.base_map()
        decision_map["work_items"] = [
            {"id": "A", "title": "A", "status": "completed"},
            {"id": "B", "title": "B", "status": "completed"},
            {"id": "C", "title": "C", "status": "pending"},
            {"id": "D", "title": "D", "status": "pending"},
        ]
        decision_map["dependencies"] = [
            {"work_item": "C", "depends_on": "A"},
            {"work_item": "D", "depends_on": "B"},
        ]
        decision_map["frontier"] = ["C", "D"]
        self.assertEqual(self.compute(decision_map), ["C", "D"])

    def test_deep_dependency_chain(self) -> None:
        decision_map = self.base_map()
        decision_map["work_items"] = [
            {"id": "A", "title": "A", "status": "completed"},
            {"id": "B", "title": "B", "status": "completed"},
            {"id": "C", "title": "C", "status": "pending"},
            {"id": "D", "title": "D", "status": "pending"},
        ]
        decision_map["dependencies"] = [
            {"work_item": "B", "depends_on": "A"},
            {"work_item": "C", "depends_on": "B"},
            {"work_item": "D", "depends_on": "C"},
        ]
        decision_map["frontier"] = ["C"]
        self.assertEqual(self.compute(decision_map), ["C"])

    def test_cycle_detection(self) -> None:
        decision_map = self.base_map()
        decision_map["dependencies"].append({"work_item": "WORK-001", "depends_on": "WORK-003"})
        self.assert_invalid(decision_map, "cycle")

    def test_duplicate_node_detection(self) -> None:
        decision_map = self.base_map()
        decision_map["work_items"].append(
            {"id": "WORK-002", "title": "Duplicate", "status": "pending"}
        )
        self.assert_invalid(decision_map, "Duplicate")

    def test_missing_dependency_detection(self) -> None:
        decision_map = self.base_map()
        decision_map["dependencies"].append({"work_item": "WORK-002", "depends_on": "MISSING"})
        self.assert_invalid(decision_map, "unknown prerequisite")

    def test_empty_frontier_for_blocked_or_completed_project(self) -> None:
        decision_map = self.base_map()
        decision_map["work_items"] = [
            {"id": "DONE", "title": "Done", "status": "completed"},
            {"id": "BLOCKED", "title": "Blocked", "status": "blocked"},
        ]
        decision_map["dependencies"] = []
        decision_map["frontier"] = []
        self.assertEqual(self.compute(decision_map), [])

    def test_manual_frontier_mismatch_is_rejected(self) -> None:
        decision_map = self.base_map()
        decision_map["frontier"] = ["WORK-003"]
        self.assert_invalid(decision_map, "does not match computed frontier")

    def test_cli_outputs_frontier_json(self) -> None:
        decision_map = self.base_map()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decision-map.json"
            path.write_text(json.dumps(decision_map), encoding="utf-8")
            loaded = compute_frontier_module.load_decision_map(path)
        self.assertEqual(self.compute(loaded), ["WORK-002"])


if __name__ == "__main__":
    unittest.main()
