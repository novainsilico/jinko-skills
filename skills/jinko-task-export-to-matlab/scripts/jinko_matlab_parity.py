#!/usr/bin/env python3
"""Internal helpers for the Jinkō-to-SimBiology parity workflow.

The skill invokes this file for repeatable file handling and comparison maths;
it is not a user-facing replacement for the guided MATLAB workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

AVOGADRO = 6.02214076e23
POINT_ABS_TOL = 1e-8
POINT_REL_TOL = 1e-6
AUC_WARN_REL_TOL = 0.01


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def require_available_outputs(paths: list[Path], *, overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        raise ValueError(
            "Refusing to overwrite: "
            + ", ".join(str(path) for path in existing)
            + ". Pass --overwrite to replace them."
        )


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_zip(bundle: Path, destination: Path) -> None:
    """Extract ordinary ZIP members only, rejecting path traversal and links."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(bundle) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            resolved = (root / member_path).resolve()
            is_symlink = (member.external_attr >> 16) & 0o170000 == 0o120000
            if (
                member_path.is_absolute()
                or root not in resolved.parents
                and resolved != root
            ):
                raise ValueError(f"Unsafe ZIP member: {member.filename}")
            if is_symlink:
                raise ValueError(
                    f"ZIP symbolic links are not supported: {member.filename}"
                )
        archive.extractall(root)


def discover_artifacts(directory: Path) -> tuple[Path, Path]:
    workbooks = sorted(path for path in directory.rglob("*.xlsx") if path.is_file())
    if len(workbooks) != 1:
        raise ValueError(
            f"Expected exactly one SimBiology workbook, found {len(workbooks)}"
        )
    workbook = workbooks[0]
    expected = f"SimulationSettings_{workbook.stem}.yaml"
    settings = [path for path in directory.rglob(expected) if path.is_file()]
    if len(settings) != 1:
        raise ValueError(f"Expected exactly one {expected}, found {len(settings)}")
    return workbook, settings[0]


def load_settings(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_settings(payload)


def validate_settings(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Simulation settings must be a YAML mapping")
    required = {
        "CompileOptions": [
            "DefaultSpeciesDimension",
            "DimensionalAnalysis",
            "UnitConversion",
        ],
        "SolverOptions": ["AbsoluteTolerance", "RelativeTolerance"],
        "SolverType": [],
        "StopTime": [],
        "TimeUnits": [],
    }
    for section in ("CompileOptions", "SolverOptions"):
        if section in payload and not isinstance(payload[section], dict):
            raise ValueError(f"Simulation settings {section} must be a mapping")
    missing = [
        f"{section}.{key}" if key else section
        for section, keys in required.items()
        for key in ([""] if not keys else keys)
        if section not in payload or (key and key not in payload[section])
    ]
    if missing:
        raise ValueError("Simulation settings missing: " + ", ".join(missing))
    for field in ("SolverType", "TimeUnits"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Simulation settings {field} must be a non-empty string")
    for container, field, allow_zero in (
        (payload["SolverOptions"], "AbsoluteTolerance", False),
        (payload["SolverOptions"], "RelativeTolerance", False),
        (payload, "StopTime", True),
    ):
        value = container[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Simulation settings {field} must be numeric")
        if (
            not math.isfinite(float(value))
            or value < 0
            or (not allow_zero and value == 0)
        ):
            raise ValueError(f"Simulation settings {field} must be finite and positive")
    return payload


def artifact_record(path: Path, root: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def validate_manifest(path: Path, cm_sid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = read_json(path)
    if manifest.get("cm_sid") != cm_sid:
        raise ValueError("The parity manifest belongs to a different CM")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("The parity manifest is missing artifact records")
    root = path.parent.resolve()
    resolved: dict[str, Path] = {}
    for name in ("bundle", "workbook", "simulation_settings"):
        record = artifacts.get(name)
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError(f"The parity manifest is missing the {name} path")
        candidate = (root / record["path"]).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"The parity manifest {name} path escapes its run directory"
            ) from exc
        if not candidate.is_file() or sha256_file(candidate) != record.get("sha256"):
            raise ValueError(f"The parity manifest {name} hash does not match")
        resolved[name] = candidate
    settings = load_settings(resolved["simulation_settings"])
    if manifest.get("settings") != settings:
        raise ValueError("The parity manifest settings do not match the exported YAML")
    return manifest, settings


def load_sdk() -> tuple[Any, Any]:
    try:
        from jinko import JinkoClient
        from jinko.exceptions import JinkoError
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Cannot import jinko-sdk; configure the approved SDK environment."
        ) from exc
    return JinkoClient, JinkoError


def export_model(args: argparse.Namespace) -> int:
    root = Path(args.output_dir).resolve()
    manifest_path = root / "parity-manifest.json"
    require_available_outputs([manifest_path], overwrite=args.overwrite)
    root.mkdir(parents=True, exist_ok=True)
    previous_manifest = read_json(manifest_path) if manifest_path.exists() else {}
    previous = (
        previous_manifest.get("artifacts")
        if previous_manifest.get("cm_sid") == args.cm_sid
        else None
    )
    JinkoClient, _ = load_sdk()
    client = JinkoClient()
    client.auth_check()
    model = client.get_model(args.cm_sid)
    bundle = model.download_as_zip(
        cm_in_json=False,
        cm_in_sbml=False,
        cm_in_simbiology_xlsx=True,
        solving_options_in_json=False,
    )
    bundle_hash = hashlib.sha256(bundle).hexdigest()
    exports = root / "exports"
    bundle_path = exports / f"{bundle_hash}.zip"
    extraction = exports / bundle_hash
    with tempfile.TemporaryDirectory(dir=root, prefix="bundle-") as staging_text:
        staging = Path(staging_text)
        staged_bundle = staging / "bundle.zip"
        staged_bundle.write_bytes(bundle)
        staged_contents = staging / "contents"
        safe_extract_zip(staged_bundle, staged_contents)
        staged_workbook, staged_settings = discover_artifacts(staged_contents)
        load_settings(staged_settings)
        if extraction.exists():
            workbook, settings_file = discover_artifacts(extraction)
            if sha256_file(workbook) != sha256_file(staged_workbook) or sha256_file(
                settings_file
            ) != sha256_file(staged_settings):
                raise ValueError(
                    "Existing content-addressed export differs from the downloaded bundle"
                )
        else:
            extraction.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_contents), extraction)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    if bundle_path.exists() and sha256_file(bundle_path) != bundle_hash:
        raise ValueError("Existing content-addressed bundle has been modified")
    if not bundle_path.exists():
        bundle_path.write_bytes(bundle)
    workbook, settings_file = discover_artifacts(extraction)
    settings = load_settings(settings_file)
    artifacts = {
        "bundle": artifact_record(bundle_path, root),
        "workbook": artifact_record(workbook, root),
        "simulation_settings": artifact_record(settings_file, root),
    }
    reuse = {
        "workbook_unchanged": bool(
            previous
            and previous.get("workbook", {}).get("sha256")
            == artifacts["workbook"]["sha256"]
        ),
        "settings_unchanged": bool(
            previous
            and previous.get("simulation_settings", {}).get("sha256")
            == artifacts["simulation_settings"]["sha256"]
        ),
    }
    manifest = {
        "schema_version": 1,
        "cm_sid": args.cm_sid,
        "exported_at": utc_now(),
        "artifacts": artifacts,
        "previous_artifacts": previous,
        "reuse": reuse,
        "settings": settings,
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "reuse": reuse,
                "workbook": artifacts["workbook"],
            },
            indent=2,
        )
    )
    return 0


def list_series(args: argparse.Namespace) -> int:
    if args.output:
        require_available_outputs([Path(args.output)], overwrite=args.overwrite)
    JinkoClient, _ = load_sdk()
    client = JinkoClient()
    client.auth_check()
    model = client.get_model(args.cm_sid)
    ids = [
        identifier for identifier in model.time_dependent_ids() if identifier != "Time"
    ]
    payload = {"cm_sid": args.cm_sid, "time_series_id": "Time", "eligible_series": ids}
    if args.output:
        write_json(Path(args.output), payload)
    print(json.dumps(payload, indent=2))
    return 0


def solve(args: argparse.Namespace) -> int:
    require_available_outputs([Path(args.output)], overwrite=args.overwrite)
    selected = list(args.series)
    if not 1 <= len(selected) <= 10:
        raise ValueError(
            "Select from one to ten series; Time is supplied automatically."
        )
    if "Time" in selected or len(set(selected)) != len(selected):
        raise ValueError("Select unique output IDs and do not include Time")
    _, settings = validate_manifest(Path(args.manifest), args.cm_sid)
    JinkoClient, _ = load_sdk()
    client = JinkoClient()
    client.auth_check()
    result = client.get_model(args.cm_sid).simple_solve(
        timeseries_ids=["Time", *selected]
    )
    if result.error:
        raise RuntimeError(f"Jinkō simple_solve failed: {result.error}")
    series = [
        {"id": item.id, "unit": item.unit, "size": item.size, "values": item.values}
        for item in result.results
    ]
    returned = {item["id"] for item in series}
    missing = {"Time", *selected} - returned
    if missing:
        raise ValueError(
            "Jinkō simple_solve did not return: " + ", ".join(sorted(missing))
        )
    matlab_time = matlab_time_grid(series, settings)
    payload = {
        "schema_version": 1,
        "cm_sid": args.cm_sid,
        "created_at": utc_now(),
        "requested_series": selected,
        "simple_solve_payload": ["Time", *selected],
        "matlab_output_times": matlab_time,
        "series": series,
    }
    write_json(Path(args.output), payload)
    print(f"Wrote {args.output}")
    return 0


def unit_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower().replace(" ", "_")
    return None


def value_conversion(source: Any, target: Any) -> tuple[float, str]:
    source_name, target_name = unit_name(source), unit_name(target)
    if source_name is None or target_name is None:
        raise ValueError("Both MATLAB and Jinkō series units are required")
    if source_name == target_name:
        return 1.0, "identity"
    if source_name == "mole" and target_name in {"substance_count", "substance"}:
        return AVOGADRO, "mole_to_substance_count"
    if source_name in {"substance_count", "substance"} and target_name == "mole":
        return 1 / AVOGADRO, "substance_count_to_mole"
    raise ValueError(
        f"Cannot normalize MATLAB unit {source!r} to Jinkō unit {target!r}"
    )


def time_conversion(source: Any, target: Any) -> float:
    factors = {
        "second": 1,
        "seconds": 1,
        "s": 1,
        "minute": 60,
        "minutes": 60,
        "min": 60,
        "hour": 3600,
        "hours": 3600,
        "h": 3600,
        "day": 86400,
        "days": 86400,
        "d": 86400,
    }
    source_name, target_name = unit_name(source), unit_name(target)
    if source_name not in factors or target_name not in factors:
        raise ValueError(
            f"Cannot normalize MATLAB time unit {source!r} to Jinkō time unit {target!r}"
        )
    return factors[source_name] / factors[target_name]


def matlab_time_grid(
    series: list[dict[str, Any]], settings: dict[str, Any]
) -> dict[str, Any]:
    time_item = next((item for item in series if item.get("id") == "Time"), None)
    if time_item is None:
        raise ValueError("Jinkō results are missing the required Time series")
    source_unit = time_item.get("unit") or "second"
    target_unit = settings.get("TimeUnits")
    factor = time_conversion(source_unit, target_unit)
    values = finite_values(time_item.get("values"), label="Jinkō Time")
    return {
        "unit": target_unit,
        "values": [value * factor for value in values],
        "source_unit": source_unit,
        "source_unit_basis": "response" if time_item.get("unit") else "Jinkō seconds",
    }


def index_series(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = payload.get("series")
    if not isinstance(items, list):
        raise ValueError("Result JSON must contain a series array")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Each series needs an id")
        if item["id"] in result:
            raise ValueError(f"Duplicate series id: {item['id']}")
        result[item["id"]] = item
    return result


def collapse_jinko_time(
    series: dict[str, dict[str, Any]], selected: list[str]
) -> tuple[list[float], dict[str, list[float]], int]:
    time_item = series.get("Time")
    if time_item is None:
        raise ValueError("Jinkō results are missing the required Time series")
    raw_time = finite_values(time_item.get("values"), label="Jinkō Time")
    if len(raw_time) < 2:
        raise ValueError("Time requires at least two samples")
    missing = [identifier for identifier in selected if identifier not in series]
    if missing:
        raise ValueError("Jinkō results are missing: " + ", ".join(missing))
    raw_values = {
        identifier: finite_values(
            series[identifier].get("values"), label=f"Jinkō {identifier}"
        )
        for identifier in selected
    }
    if any(len(values) != len(raw_time) for values in raw_values.values()):
        raise ValueError("Jinkō output length does not match Time")
    keep: list[int] = []
    for index, current in enumerate(raw_time):
        if index and current < raw_time[index - 1]:
            raise ValueError("Jinkō Time must be nondecreasing")
        if keep and current == raw_time[keep[-1]]:
            keep[-1] = index  # final sample is the post-event state
        else:
            keep.append(index)
    return (
        [raw_time[index] for index in keep],
        {
            identifier: [values[index] for index in keep]
            for identifier, values in raw_values.items()
        },
        len(raw_time) - len(keep),
    )


def align_matlab_time(target: list[float], matlab_time: list[float]) -> list[int]:
    if len(matlab_time) < 2:
        raise ValueError("MATLAB Time requires at least two samples")
    if any(
        current < previous for previous, current in zip(matlab_time, matlab_time[1:])
    ):
        raise ValueError("MATLAB Time must be nondecreasing")
    matches: list[int] = []
    cursor = 0
    for wanted in target:
        tolerance = 1e-9 * max(1.0, abs(wanted))
        while cursor < len(matlab_time) and matlab_time[cursor] < wanted - tolerance:
            cursor += 1
        candidates: list[int] = []
        while (
            cursor < len(matlab_time) and abs(matlab_time[cursor] - wanted) <= tolerance
        ):
            candidates.append(cursor)
            cursor += 1
        if not candidates:
            raise ValueError(f"MATLAB output is missing requested time {wanted}")
        matches.append(candidates[-1])
    return matches


def trapezoid(time: list[float], values: list[float]) -> float:
    return sum(
        (time[index] - time[index - 1]) * (values[index] + values[index - 1]) / 2
        for index in range(1, len(time))
    )


def finite_values(values: Any, *, label: str) -> list[float]:
    if not isinstance(values, list):
        raise ValueError(f"{label} values must be an array")
    try:
        converted = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} values must be numeric") from exc
    if not all(math.isfinite(value) for value in converted):
        raise ValueError(f"{label} values must be finite")
    return converted


def format_number(value: float | None) -> str:
    return "n/a" if value is None or not math.isfinite(value) else f"{value:.6g}"


def compare(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    require_available_outputs(
        [
            output_dir / "comparison.json",
            output_dir / "comparison.csv",
            output_dir / "comparison.md",
        ],
        overwrite=args.overwrite,
    )
    jinko = read_json(Path(args.jinko_json))
    matlab = read_json(Path(args.matlab_json))
    selected = jinko.get("requested_series")
    if not isinstance(selected, list) or not all(
        isinstance(item, str) for item in selected
    ):
        raise ValueError("Jinkō result JSON is missing requested_series")
    if (
        not 1 <= len(selected) <= 10
        or len(set(selected)) != len(selected)
        or "Time" in selected
    ):
        raise ValueError(
            "requested_series must contain one to ten unique IDs, excluding Time"
        )
    jinko_series = index_series(jinko)
    matlab_series = index_series(matlab)
    target_time, jinko_values, duplicates = collapse_jinko_time(jinko_series, selected)
    matlab_time_payload = matlab.get("time")
    if not isinstance(matlab_time_payload, dict):
        raise ValueError("MATLAB result JSON must contain time")
    jinko_time_unit = jinko_series["Time"].get("unit")
    matlab_time_factor = time_conversion(
        matlab_time_payload.get("unit"), jinko_time_unit
    )
    matlab_time = [
        value * matlab_time_factor
        for value in finite_values(
            matlab_time_payload.get("values"), label="MATLAB Time"
        )
    ]
    indices = align_matlab_time(target_time, matlab_time)
    rows: list[dict[str, Any]] = []
    for identifier in selected:
        if identifier not in matlab_series:
            raise ValueError(f"MATLAB result is missing {identifier}")
        factor, conversion = value_conversion(
            matlab_series[identifier].get("unit"), jinko_series[identifier].get("unit")
        )
        raw_matlab = finite_values(
            matlab_series[identifier].get("values"), label=f"MATLAB {identifier}"
        )
        if len(raw_matlab) != len(matlab_time):
            raise ValueError(f"MATLAB values for {identifier} do not match MATLAB Time")
        matlab_values = [raw_matlab[index] * factor for index in indices]
        reference = jinko_values[identifier]
        absolute = [
            abs(actual - expected)
            for actual, expected in zip(matlab_values, reference, strict=True)
        ]
        relative = [
            error / abs(expected)
            for error, expected in zip(absolute, reference, strict=True)
            if expected != 0
        ]
        failed = sum(
            error > POINT_ABS_TOL + POINT_REL_TOL * abs(expected)
            for error, expected in zip(absolute, reference, strict=True)
        )
        jinko_auc = trapezoid(target_time, reference)
        matlab_auc = trapezoid(target_time, matlab_values)
        auc_absolute = abs(matlab_auc - jinko_auc)
        auc_relative = auc_absolute / abs(jinko_auc) if jinko_auc != 0 else None
        auc_status = (
            "N/A"
            if auc_relative is None
            else ("WARN" if auc_relative > AUC_WARN_REL_TOL else "PASS")
        )
        rows.append({
            "id": identifier,
            "points": len(target_time),
            "pointwise_max_abs": max(absolute),
            "pointwise_max_rel": max(relative) if relative else None,
            "pointwise_mismatches": failed,
            "jinko_auc": jinko_auc,
            "matlab_auc": matlab_auc,
            "auc_abs_error": auc_absolute,
            "auc_rel_error": auc_relative,
            "auc_status": auc_status,
            "jinko_unit": jinko_series[identifier].get("unit"),
            "matlab_unit": matlab_series[identifier].get("unit"),
            "matlab_conversion": conversion,
        })
    statuses = [row["auc_status"] for row in rows]
    overall = "WARN" if "WARN" in statuses else ("N/A" if "N/A" in statuses else "PASS")
    result = {
        "schema_version": 1,
        "created_at": utc_now(),
        "overall_auc_status": overall,
        "selected_series": selected,
        "simple_solve_payload": jinko.get("simple_solve_payload"),
        "dose_decision": matlab.get("dose_decision"),
        "alignment": {
            "duplicate_jinko_points_discarded": duplicates,
            "duplicate_policy": "last/post-event",
            "points_compared": len(target_time),
            "time_unit": jinko_time_unit,
        },
        "series": rows,
    }
    write_json(output_dir / "comparison.json", result)
    with (output_dir / "comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "id",
                "points",
                "pointwise_max_abs",
                "pointwise_max_rel",
                "pointwise_mismatches",
                "jinko_auc",
                "matlab_auc",
                "auc_abs_error",
                "auc_rel_error",
                "auc_status",
                "jinko_unit",
                "matlab_unit",
                "matlab_conversion",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    header = "| Series | Points | Pointwise max abs | Pointwise max rel | Mismatches | Jinkō AUC | MATLAB AUC | AUC rel. error | AUC |"
    divider = "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    lines = [header, divider]
    for row in rows:
        relative = (
            "n/a" if row["auc_rel_error"] is None else f"{row['auc_rel_error']:.3%}"
        )
        lines.append(
            f"| {row['id']} | {row['points']} | {format_number(row['pointwise_max_abs'])} | {format_number(row['pointwise_max_rel'])} | {row['pointwise_mismatches']} | {format_number(row['jinko_auc'])} | {format_number(row['matlab_auc'])} | {relative} | {row['auc_status']} |"
        )
    (output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote comparison artifacts to {output_dir}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Export and fingerprint a CM bundle")
    export.add_argument("cm_sid")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--overwrite", action="store_true")
    export.set_defaults(handler=export_model)
    listing = commands.add_parser(
        "list-series", help="List selectable time-dependent outputs"
    )
    listing.add_argument("cm_sid")
    listing.add_argument("--output")
    listing.add_argument("--overwrite", action="store_true")
    listing.set_defaults(handler=list_series)
    solve_parser = commands.add_parser(
        "solve", help="Run simple_solve with Time included"
    )
    solve_parser.add_argument("cm_sid")
    solve_parser.add_argument("--series", nargs="+", required=True)
    solve_parser.add_argument("--manifest", required=True)
    solve_parser.add_argument("--output", required=True)
    solve_parser.add_argument("--overwrite", action="store_true")
    solve_parser.set_defaults(handler=solve)
    comparison = commands.add_parser(
        "compare", help="Compare prepared Jinkō and MATLAB JSON results"
    )
    comparison.add_argument("--jinko-json", required=True)
    comparison.add_argument("--matlab-json", required=True)
    comparison.add_argument("--output-dir", required=True)
    comparison.add_argument("--overwrite", action="store_true")
    comparison.set_defaults(handler=compare)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except Exception as exc:  # noqa: BLE001 - CLI should give a single actionable failure
        print(f"jinko-matlab parity helper failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
