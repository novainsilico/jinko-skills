#!/usr/bin/env python3
"""Merge normalized ClinicalTrials.gov angle outputs by NCT ID."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from common import write_json
except ImportError:  # pragma: no cover
    from .common import write_json


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc


def parse_angle(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Invalid --angle {value!r}; expected LABEL=FILE")
    label, raw_path = value.split("=", 1)
    if not label or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
        raise ValueError(f"Invalid angle label {label!r}")
    return label, Path(raw_path)


def merge_missing(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in {"query_provenance", "triangulation_count"}:
            continue
        if not target.get(key) and value:
            target[key] = value
    target["record_completeness"] = max(
        int(target.get("record_completeness") or 0),
        int(source.get("record_completeness") or 0),
    )


def compile_trials(angles: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_nct: dict[str, dict[str, Any]] = {}
    for label, path in angles:
        payload = load_json(path)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("records"), list
        ):
            raise ValueError(f"{path} must contain a records array")
        query = str(payload.get("query") or "")
        for record in payload["records"]:
            if not isinstance(record, dict):
                raise ValueError(f"{path} contains a non-object record")
            nct_id = str(record.get("nct_id") or "").strip().upper()
            if not nct_id:
                continue
            current = by_nct.get(nct_id)
            if current is None:
                current = dict(record)
                current["query_provenance"] = []
                by_nct[nct_id] = current
                merged.append(current)
            else:
                merge_missing(current, record)
            provenance = {"angle": query, "label": label}
            if provenance not in current["query_provenance"]:
                current["query_provenance"].append(provenance)

    for record in merged:
        record["triangulation_count"] = len(record["query_provenance"])
    return sorted(
        merged,
        key=lambda record: (
            int(record.get("triangulation_count") or 0),
            bool(record.get("has_results")),
            int(record.get("record_completeness") or 0),
        ),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--angle", action="append", required=True, help="Angle as LABEL=FILE."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        angles = [parse_angle(value) for value in args.angle]
        labels = [label for label, _ in angles]
        if len(labels) != len(set(labels)):
            raise ValueError("Angle labels must be unique")
        records = compile_trials(angles)
        write_json(args.output, records)
        print(json.dumps({"candidates": len(records), "output": str(args.output)}))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
