#!/usr/bin/env python3
"""Validate shortlist candidates against the bundled JSON Schema subset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc


def validate(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors = []
    expected = schema.get("type")
    if expected in TYPE_MAP:
        type_matches = isinstance(value, TYPE_MAP[expected])
        if expected == "integer":
            type_matches = type_matches and not isinstance(value, bool)
        if not type_matches:
            return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(validate(child, properties[key], f"{path}.{key}"))
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets/shortlist-schema.json",
    )
    args = parser.parse_args()
    try:
        shortlist = load_json(args.shortlist)
        schema = load_json(args.schema)
        if not isinstance(shortlist, list):
            raise ValueError("Shortlist must be a JSON array")
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a JSON object")
        errors = []
        for index, candidate in enumerate(shortlist):
            errors.extend(validate(candidate, schema, f"$[{index}]"))
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"Validated {len(shortlist)} shortlist candidate(s).")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
