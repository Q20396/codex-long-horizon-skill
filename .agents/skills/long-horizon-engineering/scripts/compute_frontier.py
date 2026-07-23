#!/usr/bin/env python3
"""Validate an LHE Decision Map and compute its deterministic Frontier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXECUTABLE_STATUS = "pending"
NON_EXECUTABLE_STATUSES = {
    "in_progress",
    "blocked",
    "completed",
    "cancelled",
    "out_of_scope",
}
VALID_STATUSES = {EXECUTABLE_STATUS, *NON_EXECUTABLE_STATUSES}


class DecisionMapError(ValueError):
    """Raised when the Decision Map is structurally invalid."""


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionMapError(f"{label} must be an object.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DecisionMapError(f"{label} must be a list.")
    return value


def _duplicate(values: list[str]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def _visit(
    node: str,
    graph: dict[str, list[str]],
    visiting: set[str],
    visited: set[str],
) -> None:
    if node in visited:
        return
    if node in visiting:
        raise DecisionMapError(f"Dependency cycle detected at {node}.")
    visiting.add(node)
    for dependency in graph.get(node, []):
        _visit(dependency, graph, visiting, visited)
    visiting.remove(node)
    visited.add(node)


def compute_frontier(decision_map: dict[str, Any]) -> list[str]:
    """Return executable work item IDs in source order.

    Executable means pending and all dependencies are completed.
    """

    _require_object(decision_map, "Decision Map")
    work_items = _require_list(decision_map.get("work_items"), "work_items")
    dependencies = _require_list(decision_map.get("dependencies"), "dependencies")
    supplied_frontier = _require_list(decision_map.get("frontier"), "frontier")

    item_ids: list[str] = []
    status_by_id: dict[str, str] = {}
    for index, raw_item in enumerate(work_items):
        item = _require_object(raw_item, f"work_items[{index}]")
        item_id = item.get("id")
        status = item.get("status")
        if not isinstance(item_id, str) or not item_id:
            raise DecisionMapError(f"work_items[{index}].id must be a non-empty string.")
        if status not in VALID_STATUSES:
            raise DecisionMapError(f"{item_id} has invalid status: {status!r}.")
        item_ids.append(item_id)
        status_by_id[item_id] = status

    duplicate_item = _duplicate(item_ids)
    if duplicate_item:
        raise DecisionMapError(f"Duplicate work item ID: {duplicate_item}.")

    known_ids = set(item_ids)
    graph: dict[str, list[str]] = {item_id: [] for item_id in item_ids}
    for index, raw_dependency in enumerate(dependencies):
        dependency = _require_object(raw_dependency, f"dependencies[{index}]")
        work_item = dependency.get("work_item")
        depends_on = dependency.get("depends_on")
        if work_item not in known_ids:
            raise DecisionMapError(f"Dependency references unknown work item: {work_item!r}.")
        if depends_on not in known_ids:
            raise DecisionMapError(f"Dependency references unknown prerequisite: {depends_on!r}.")
        graph[work_item].append(depends_on)

    visited: set[str] = set()
    for item_id in item_ids:
        _visit(item_id, graph, set(), visited)

    frontier = [
        item_id
        for item_id in item_ids
        if status_by_id[item_id] == EXECUTABLE_STATUS
        and all(status_by_id[dependency] == "completed" for dependency in graph[item_id])
    ]

    for index, item_id in enumerate(supplied_frontier):
        if not isinstance(item_id, str) or not item_id:
            raise DecisionMapError(f"frontier[{index}] must be a non-empty string.")
    if supplied_frontier != frontier:
        raise DecisionMapError(
            "Supplied frontier does not match computed frontier: "
            f"supplied={supplied_frontier!r}, computed={frontier!r}."
        )

    return frontier


def load_decision_map(path: Path) -> dict[str, Any]:
    return _require_object(json.loads(path.read_text(encoding="utf-8")), "Decision Map")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decision_map", type=Path, help="Path to a Decision Map JSON file.")
    parser.add_argument(
        "--frontier-only",
        action="store_true",
        help="Print only the JSON frontier object.",
    )
    args = parser.parse_args()

    decision_map = load_decision_map(args.decision_map)
    frontier = compute_frontier(decision_map)
    output = {"frontier": frontier}
    if args.frontier_only:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print("Decision Map valid.")
        print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (DecisionMapError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
