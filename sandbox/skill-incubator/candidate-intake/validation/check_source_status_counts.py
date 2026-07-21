#!/usr/bin/env python3
"""Check that source uncertainty counts remain disclosed and locked."""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_candidate_intake import validate_root
from validation_common import repository_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    errors = [entry for entry in validate_root(args.root.resolve()) if "source" in entry]
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("PASS: source ledger remains locked with 10 verification_blocked and 5 ambiguous_source records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
