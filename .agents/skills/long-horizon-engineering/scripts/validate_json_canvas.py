#!/usr/bin/env python3
"""Read-only structural validation for a JSON Canvas file."""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
from pathlib import Path
from typing import Any


MAX_BYTES = 5 * 1024 * 1024
NODE_TYPES = {"text", "file", "link", "group"}
SIDES = {"top", "right", "bottom", "left"}
ENDS = {"none", "arrow"}


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def read_regular_file(path: Path) -> bytes:
    """Read one small regular file without following a symlink when supported."""
    if path.is_symlink():
        raise ValueError("Refusing to validate a symlinked canvas file.")
    try:
        path_metadata = path.lstat()
    except OSError as error:
        raise ValueError("Unable to inspect the canvas file safely.") from error
    if not stat.S_ISREG(path_metadata.st_mode):
        raise ValueError("Canvas input must be a regular file.")

    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags |= nofollow
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError("Unable to open the canvas file safely.") from error

    with os.fdopen(descriptor, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Canvas input must be a regular file.")
        if metadata.st_size > MAX_BYTES:
            raise ValueError("Canvas input exceeds the 5 MiB validation limit.")
        return handle.read()


def validate_canvas(payload: Any) -> list[str]:
    """Return structural errors without echoing canvas content."""
    if not isinstance(payload, dict):
        return ["Canvas root must be a JSON object."]

    errors: list[str] = []
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    if not isinstance(nodes, list):
        errors.append("Canvas nodes must be an array when present.")
        nodes = []
    if not isinstance(edges, list):
        errors.append("Canvas edges must be an array when present.")
        edges = []

    known_node_ids: set[str] = set()
    known_ids: set[str] = set()
    for index, node in enumerate(nodes):
        label = f"Node {index}"
        if not isinstance(node, dict):
            errors.append(f"{label} must be an object.")
            continue

        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"{label} must have a non-empty string id.")
        elif node_id in known_ids:
            errors.append(f"{label} has a duplicate id.")
        else:
            known_ids.add(node_id)
            known_node_ids.add(node_id)

        node_type = node.get("type")
        if node_type not in NODE_TYPES:
            errors.append(f"{label} has an unsupported type.")

        for field in ("x", "y", "width", "height"):
            if not is_number(node.get(field)):
                errors.append(f"{label} must have a finite numeric {field}.")

        required_field = {
            "text": "text",
            "file": "file",
            "link": "url",
        }.get(node_type)
        if required_field and (
            not isinstance(node.get(required_field), str)
            or not node[required_field].strip()
        ):
            errors.append(f"{label} must have a non-empty {required_field} value.")

    for index, edge in enumerate(edges):
        label = f"Edge {index}"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object.")
            continue

        edge_id = edge.get("id")
        if not isinstance(edge_id, str) or not edge_id:
            errors.append(f"{label} must have a non-empty string id.")
        elif edge_id in known_ids:
            errors.append(f"{label} has a duplicate id.")
        else:
            known_ids.add(edge_id)

        for field in ("fromNode", "toNode"):
            target = edge.get(field)
            if not isinstance(target, str) or not target:
                errors.append(f"{label} must have a non-empty {field} value.")
            elif target not in known_node_ids:
                errors.append(f"{label} references a missing node.")

        for field in ("fromSide", "toSide"):
            value = edge.get(field)
            if value is not None and value not in SIDES:
                errors.append(f"{label} has an invalid {field} value.")
        for field in ("fromEnd", "toEnd"):
            value = edge.get(field)
            if value is not None and value not in ENDS:
                errors.append(f"{label} has an invalid {field} value.")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate JSON Canvas structure without modifying files, following "
            "symlinks, or making network calls."
        )
    )
    parser.add_argument("canvas", type=Path, help="Path to one JSON Canvas file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable result without echoing canvas content.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = read_regular_file(args.canvas)
        payload = json.loads(raw.decode("utf-8"))
        errors = validate_canvas(payload)
    except UnicodeDecodeError:
        errors = ["Canvas input must be UTF-8 JSON."]
    except json.JSONDecodeError:
        errors = ["Canvas input is not valid JSON."]
    except ValueError as error:
        errors = [str(error)]

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("JSON Canvas validation passed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
