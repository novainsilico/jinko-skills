#!/usr/bin/env python3
"""Merge and rank references from multiple literature-search angle directories."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from common import normalize_doi, write_json
except ImportError:  # pragma: no cover
    from .common import normalize_doi, write_json


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc


def parse_angle(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Invalid --angle {value!r}; expected LABEL=DIRECTORY")
    label, raw_path = value.split("=", 1)
    if not label or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
        raise ValueError(f"Invalid angle label {label!r}")
    return label, Path(raw_path)


def identity(reference: dict[str, Any]) -> tuple[str, str]:
    pmid = str(reference.get("pmid") or "").strip()
    doi = normalize_doi(str(reference.get("doi") or ""))
    return pmid, doi


def merge_missing(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in {"query_provenance", "triangulation_count"}:
            continue
        if not target.get(key) and value:
            target[key] = value
    for key in ("is_referenced_by_count", "icite_citation_count"):
        target[key] = max(int(target.get(key) or 0), int(source.get(key) or 0))
    if len(str(source.get("abstract") or "")) > len(str(target.get("abstract") or "")):
        target["abstract"] = source["abstract"]


def compile_results(angles: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_pmid: dict[str, dict[str, Any]] = {}
    by_doi: dict[str, dict[str, Any]] = {}

    for label, directory in angles:
        references = load_json(directory / "references.json")
        manifest = load_json(directory / "manifest.json")
        if not isinstance(references, list):
            raise ValueError(f"{directory / 'references.json'} must contain an array")
        query = str(manifest.get("query") or "") if isinstance(manifest, dict) else ""
        for reference in references:
            if not isinstance(reference, dict):
                raise ValueError(
                    f"{directory / 'references.json'} contains a non-object"
                )
            pmid, doi = identity(reference)
            if not pmid and not doi:
                continue
            current = by_pmid.get(pmid) if pmid else None
            if current is None and doi:
                current = by_doi.get(doi)
            if current is None:
                current = dict(reference)
                current["query_provenance"] = []
                merged.append(current)
            else:
                merge_missing(current, reference)
            provenance = {"angle": query, "label": label}
            if provenance not in current["query_provenance"]:
                current["query_provenance"].append(provenance)
            if pmid:
                by_pmid[pmid] = current
            if doi:
                by_doi[doi] = current

    for reference in merged:
        reference["triangulation_count"] = len(reference["query_provenance"])
    return sorted(
        merged,
        key=lambda ref: (
            int(ref.get("triangulation_count") or 0),
            int(ref.get("is_referenced_by_count") or 0),
        ),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--angle", action="append", required=True, help="Angle as LABEL=DIRECTORY."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        angles = [parse_angle(value) for value in args.angle]
        labels = [label for label, _ in angles]
        if len(labels) != len(set(labels)):
            raise ValueError("Angle labels must be unique")
        references = compile_results(angles)
        write_json(args.output, references)
        print(json.dumps({"candidates": len(references), "output": str(args.output)}))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
