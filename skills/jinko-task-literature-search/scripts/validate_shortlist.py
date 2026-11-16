#!/usr/bin/env python3
"""Validate shortlist structure and publication citations against retrieved records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import normalize_doi

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
        expected_type = TYPE_MAP[expected]
        type_matches = isinstance(value, expected_type)
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


def validate_publication(
    candidate: dict[str, Any],
    references: list[dict[str, Any]] | None,
    path: str,
) -> list[str]:
    pmid = str(candidate.get("pmid") or "").strip()
    doi = normalize_doi(candidate.get("doi"))
    if not pmid and not doi:
        if candidate.get("nct_id"):
            return []  # Registry-only records keep their existing schema checks.
        return [f"{path}: publication requires a PMID or DOI"]
    if references is None:
        return [f"{path}: publication validation requires --references"]

    if any(
        (not pmid or pmid == str(record.get("pmid") or "").strip())
        and (not doi or doi == normalize_doi(str(record.get("doi") or "")))
        and all(
            candidate[field] == record.get(field)
            for field in ("title", "citation_ama")
            if field in candidate
        )
        for record in references
    ):
        return []
    return [f"{path}: citation does not match a retrieved record"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument(
        "--references",
        type=Path,
        help="Retrieved merged_references.json; required for publication candidates.",
    )
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
        references = None
        if args.references:
            references = load_json(args.references)
            if not isinstance(references, list) or any(
                not isinstance(record, dict) for record in references
            ):
                raise ValueError("References must be a JSON array of objects")
        errors = []
        for index, candidate in enumerate(shortlist):
            path = f"$[{index}]"
            candidate_errors = validate(candidate, schema, path)
            errors.extend(candidate_errors)
            if not candidate_errors:
                errors.extend(validate_publication(candidate, references, path))
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
