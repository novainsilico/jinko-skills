#!/usr/bin/env python3
"""Export a Jinkō model and check the export numerically against Jinkō.

The skill calls these commands for deterministic file handling, solving, and
comparison. They are an implementation detail, not a CLI for users to learn.

Run directory layout, one directory per export:

- ``export-manifest.json``: model, target, files with hashes, warnings.
- ``jinko.json``: the Jinkō reference series (``reference``).
- ``other.json``: the same series from the target tool (a runner).
- ``comparison.json`` and ``comparison.md``: the result (``compare``), and
  ``aligned.json``, the compared points.
- ``report.md`` and ``plots/``: the optional report (``report``).

``jinko.json`` and ``other.json`` share one shape::

    {"time": {"unit": "s", "values": [...]},
     "series": [{"id": "Tissue.Drug", "unit": "mol", "values": [...]}]}

A series unit of ``null`` in ``other.json`` means "the Jinkō unit".
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TARGETS: dict[str, dict[str, str]] = {
    "sbml": {"flag": "cm_in_sbml", "suffix": ".xml"},
    "simbiology-code": {"flag": "cm_in_simbiology_code", "suffix": ".m"},
    "simbiology-xlsx": {"flag": "cm_in_simbiology_xlsx", "suffix": ".xlsx"},
    "julia": {"flag": "cm_in_julia", "suffix": ".jl"},
    "nlmixr2": {"flag": "cm_in_nlmixr", "suffix": ".R"},
}
MANIFEST = "export-manifest.json"
JINKO = "jinko.json"
OTHER = "other.json"
ALIGNED = "aligned.json"
SOLVE_BATCH = 9  # simple_solve takes at most 10 series, Time included
# The other solver runs tight, so the check tests the exported equations and
# not solver settings. Exports hold species as amounts, often tiny in mol, so
# Jinkō's absolute tolerance would be meaningless there.
RELATIVE_TOLERANCE = 1e-10
ABSOLUTE_TOLERANCE = 1e-18
LEFT = 1e-7  # runners also sample t - LEFT * max(1, |t|): the state before an event


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def refuse_overwrite(paths: list[Path], *, overwrite: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not overwrite:
        raise ValueError(
            "refusing to overwrite " + ", ".join(existing) + "; pass --overwrite"
        )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_extract(bundle: bytes, destination: Path) -> list[Path]:
    """Extract ordinary ZIP members only: no absolute paths, traversal, or links."""
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            is_link = (member.external_attr >> 16) & 0o170000 == 0o120000
            if Path(member.filename).is_absolute() or root not in target.parents:
                raise ValueError(f"unsafe ZIP member: {member.filename}")
            if is_link:
                raise ValueError(
                    f"ZIP symbolic links are not supported: {member.filename}"
                )
        archive.extractall(root)
        return [root / name for name in archive.namelist() if not name.endswith("/")]


def load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / MANIFEST
    if not path.is_file():
        raise ValueError(f"no {MANIFEST} in {directory}; run export first")
    return read_json(path)


def exported_file(directory: Path, manifest: dict[str, Any]) -> Path:
    path = directory / manifest["model_file"]
    if sha256(path) != manifest["files"][manifest["model_file"]]:
        raise ValueError(f"{path.name} changed since the export; export again")
    return path


def solving_options(directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return read_json(directory / manifest["solving_options_file"])


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #


def unit_registry():
    try:
        import pint
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("the comparison needs pint: pip install pint") from exc
    registry = pint.UnitRegistry()
    registry.define("substance_count = mol / avogadro_number = item")
    return registry


def convert(
    registry,
    values: list[float],
    unit: str,
    target: str,
    factors: list[tuple[list[float], str]],
) -> list[float]:
    """Convert ``values`` to ``target``, using a species' molar mass or volume.

    Exports carry species as amounts in the extent unit. Jinkō reports them in
    their declared unit, often a concentration. ``factors`` are the series
    that bridge the two (molar mass, compartment volume); the first product of
    them that gives the target dimension is used.
    """
    wanted = registry.Unit(target)
    quantity = registry.Quantity(1.0, unit)
    if quantity.dimensionality == wanted.dimensionality:
        scale = quantity.to(wanted).magnitude
        return [value * scale for value in values]
    (molar_mass, mass_unit), (volume, volume_unit) = factors
    candidates = [
        (molar_mass, None, mass_unit, None),
        (None, volume, None, volume_unit),
        (molar_mass, volume, mass_unit, volume_unit),
    ]
    for mass_values, volume_values, m_unit, v_unit in candidates:
        probe = quantity
        if m_unit:
            probe = probe * registry.Quantity(1.0, m_unit)
        if v_unit:
            probe = probe / registry.Quantity(1.0, v_unit)
        if probe.dimensionality != wanted.dimensionality:
            continue
        scale = probe.to(wanted).magnitude
        return [
            value
            * scale
            * (mass_values[index] if mass_values else 1.0)
            / (volume_values[index] if volume_values else 1.0)
            for index, value in enumerate(values)
        ]
    raise ValueError(f"cannot convert {unit} to {target}")


# --------------------------------------------------------------------------- #
# Jinkō side
# --------------------------------------------------------------------------- #


def jinko_client():
    try:
        from jinko import JinkoClient
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("cannot import jinko-sdk; run jinko-sdk-setup") from exc
    return JinkoClient()


def export(args: argparse.Namespace) -> int:
    directory = Path(args.output_dir).resolve()
    refuse_overwrite([directory / MANIFEST], overwrite=args.overwrite)
    spec = TARGETS[args.target]
    model = jinko_client().get_model(args.cm)
    flags = {
        "cm_in_json": False,
        "cm_in_sbml": args.target == "sbml",
        "solving_options_in_json": True,
        spec["flag"]: True,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bundle = model.download_as_zip(**flags)
    files = safe_extract(bundle, directory)
    (directory / "bundle.zip").write_bytes(bundle)
    model_files = [path for path in files if path.suffix == spec["suffix"]]
    options = [path for path in files if path.name.startswith("SolvingOptions_")]
    if len(model_files) != 1 or not model_files[0].stat().st_size:
        raise ValueError(
            f"expected one non-empty {spec['suffix']} file in the bundle, got "
            + ", ".join(path.name for path in files)
        )
    manifest = {
        "cm": args.cm,
        "core_id": model.core_id,
        "snapshot_id": model.snapshot_id,
        "target": args.target,
        "model_file": model_files[0].name,
        "solving_options_file": options[0].name if options else None,
        "files": {path.name: sha256(path) for path in files},
        "warnings": [str(item.message) for item in caught],
        "exported_at": datetime.now(UTC).isoformat(),
    }
    write_json(directory / MANIFEST, manifest)
    print(json.dumps(manifest, indent=2))
    return 0


def list_series(args: argparse.Namespace) -> int:
    model = jinko_client().get_model(args.cm)
    for identifier in model.time_dependent_ids():
        if identifier != "Time":
            print(identifier)
    return 0


def reference(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / JINKO], overwrite=args.overwrite)
    manifest = load_manifest(directory)
    model = jinko_client().get_model(manifest["cm"])
    species = {item.id: item for item in model.components.list_species()}

    bridges: dict[str, dict[str, Any]] = {}
    needed: list[str] = list(dict.fromkeys(args.ids))
    for identifier in args.ids:
        if identifier in species:
            item = species[identifier]
            bridges[identifier] = {
                "compartment": item.compartment,
                "molar_mass": item.molar_mass,
            }
            needed.append(item.compartment)
            if isinstance(item.molar_mass, str):
                needed.append(item.molar_mass)
    needed = list(dict.fromkeys(needed))

    time: list[float] | None = None
    series: list[dict[str, Any]] = []
    for start in range(0, len(needed), SOLVE_BATCH):
        output = model.simple_solve(
            timeseries_ids=["Time", *needed[start : start + SOLVE_BATCH]]
        )
        if output.error:
            raise ValueError(f"the Jinkō solve failed: {output.error}")
        by_id = {result.id: result for result in output.results}
        clock = by_id["Time"]
        if time is None:
            time = list(clock.values)
        elif list(clock.values) != time:
            raise ValueError("the Jinkō solves returned different time grids")
        for identifier in needed[start : start + SOLVE_BATCH]:
            result = by_id.get(identifier)
            if result is None:
                raise ValueError(f"Jinkō returned no series for {identifier}")
            values = list(result.values)
            if len(values) == 1 and result.size > 1:
                values = values * result.size
            series.append({"id": identifier, "unit": result.unit, "values": values})

    write_json(
        directory / JINKO,
        {
            "cm": manifest["cm"],
            "compared_ids": list(dict.fromkeys(args.ids)),
            "species": bridges,
            "time": {"unit": "s", "values": time},
            "series": series,
        },
    )
    print(f"wrote {directory / JINKO}: {len(time or [])} time points")
    return 0


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #


def _number(value: float) -> str:
    """A number as people write it: 1e-5, not 1e-05."""
    return re.sub(r"e([+-])0*(\d)", r"e\1\2", f"{value:g}").replace("e+", "e")


def _series(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in payload["series"]}


def _value_at(times: list[float], values: list[float], when: float) -> float | None:
    """The value at ``when``, after its event when ``times`` holds it twice.

    None when no time point matches ``when``.
    """
    from jinko._comparison import values_at

    try:
        return values_at(times, values, [when])[0]
    except ValueError:
        return None


def _align(
    jinko_time: list[float],
    jinko_values: list[float],
    other_time: list[float],
    values: list[float],
    tolerance: float,
) -> tuple[list[float], list[float], int]:
    """Read the other solver at each Jinkō time point.

    At an event time, one solver may report the state before the event and
    the other the state after it; both are valid conventions. Runners sample
    each time point and a point just before it. Where the two differ (a
    discontinuity), the one closer to Jinkō is compared. Smooth points always
    use the value at the time point itself.

    The first time point is not compared: no solver can be sampled before
    it, and Jinkō reports the state before the events of that time.
    """
    from jinko._comparison import FLOOR_FRACTION

    peak = max((abs(value) for value in jinko_values), default=0.0)
    floor = max(peak * FLOOR_FRACTION, 1e-300)
    times: list[float] = []
    picked: list[float] = []
    events = 0
    for when in sorted(set(jinko_time))[1:]:
        value = _value_at(other_time, values, when)
        if value is None:
            continue
        before = _value_at(other_time, values, when - LEFT * max(1.0, abs(when)))
        if before is not None:
            jinko_value = _value_at(jinko_time, jinko_values, when)
            if abs(before - value) > tolerance * max(abs(value), abs(before), floor):
                events += 1
                if abs(before - jinko_value) < abs(value - jinko_value):
                    value = before
        times.append(when)
        picked.append(value)
    return times, picked, events


def compare(args: argparse.Namespace) -> int:
    from jinko._comparison import FLOOR_FRACTION, values_at
    from jinko.types import SimpleSolveOutput, SolvedSeries

    directory = Path(args.dir).resolve()
    outputs = [
        directory / "comparison.json",
        directory / "comparison.md",
        directory / ALIGNED,
    ]
    refuse_overwrite(outputs, overwrite=args.overwrite)
    jinko = read_json(directory / JINKO)
    other = read_json(directory / OTHER)
    registry = unit_registry()

    jinko_series = _series(jinko)
    other_series = _series(other)
    time_scale = registry.Quantity(1.0, other["time"]["unit"]).to("s").magnitude
    other_time = [value * time_scale for value in other["time"]["values"]]
    jinko_time = jinko["time"]["values"]

    rows: list[dict[str, Any]] = []
    aligned: dict[str, dict[str, list[float]]] = {}
    passed = True
    for identifier in jinko["compared_ids"]:
        reference_item = jinko_series[identifier]
        item = other_series.get(identifier)
        if identifier in other.get("unavailable", []):
            rows.append({
                "id": identifier,
                "status": "NOT CHECKED: not in the solver output",
            })
            continue
        if item is None:
            rows.append({"id": identifier, "status": "MISSING"})
            passed = False
            continue
        values = [float(value) for value in item["values"]]
        if not all(math.isfinite(value) for value in values):
            rows.append({"id": identifier, "status": "NON-FINITE"})
            passed = False
            continue
        conversion = None
        if item.get("unit") and item["unit"] != reference_item["unit"]:
            bridge = jinko["species"].get(identifier, {})
            values = convert(
                registry,
                values,
                item["unit"],
                reference_item["unit"],
                _bridge_factors(jinko_series, bridge, jinko_time, other_time),
            )
            conversion = f"{item['unit']} -> {reference_item['unit']}"
        times, values, events = _align(
            jinko_time, reference_item["values"], other_time, values, args.tolerance
        )
        if not times:
            rows.append({"id": identifier, "status": "NO SHARED TIMES"})
            passed = False
            continue
        output = SimpleSolveOutput(
            error=None,
            results=[
                SolvedSeries("Time", "s", len(jinko_time), jinko_time),
                SolvedSeries(
                    identifier,
                    reference_item["unit"],
                    len(reference_item["values"]),
                    reference_item["values"],
                ),
            ],
        )
        result = output.compare(
            {identifier: values}, times=times, tolerance=args.tolerance
        )[identifier]
        passed = passed and result.passes
        aligned[identifier] = {
            "times": times,
            "jinko": values_at(jinko_time, reference_item["values"], times),
            "other": values,
        }
        rows.append({
            "id": identifier,
            "status": "PASS" if result.passes else "FAIL",
            "unit": reference_item["unit"],
            "conversion": conversion,
            "points": result.points,
            "event_points": events,
            "max_relative_error": result.max_relative_error,
            "max_absolute_error": result.max_absolute_error,
            "cmax_relative_error": result.cmax_relative_error,
            "auc_relative_error": result.auc_relative_error,
            "note": result.note,
        })

    summary = {
        "status": "PASS" if passed else "FAIL",
        "tolerance": args.tolerance,
        "rule": (
            f"max point-wise relative error against Jinkō, floor {_number(FLOOR_FRACTION)} x "
            "Jinkō peak, after the first time point"
        ),
        "series": rows,
    }
    write_json(outputs[0], summary)
    write_json(outputs[2], aligned)
    outputs[1].write_text(_markdown(summary), encoding="utf-8")
    print(outputs[1].read_text(encoding="utf-8"))
    return 0 if passed else 1


def _bridge_factors(
    jinko_series: dict[str, dict[str, Any]],
    bridge: dict[str, Any],
    jinko_time: list[float],
    other_time: list[float],
) -> list[tuple[list[float], str]]:
    """Molar mass and volume series, read at the other solver's time points."""

    def at_other_times(identifier: str) -> tuple[list[float], str]:
        item = jinko_series[identifier]
        return _interpolate(jinko_time, item["values"], other_time), item["unit"]

    mass = bridge.get("molar_mass")
    if isinstance(mass, str):
        molar_mass = at_other_times(mass)
    elif isinstance(mass, (int, float)):
        molar_mass = ([float(mass)] * len(other_time), "kg / mol")
    else:
        molar_mass = ([1.0] * len(other_time), "dimensionless")
    compartment = bridge.get("compartment")
    volume = (
        at_other_times(compartment)
        if compartment
        else ([1.0] * len(other_time), "dimensionless")
    )
    return [molar_mass, volume]


def _interpolate(
    times: list[float], values: list[float], wanted: list[float]
) -> list[float]:
    """Linear interpolation, last value at a repeated time (after an event)."""
    from jinko._comparison import TIME_MATCH

    picked: list[float] = []
    for when in wanted:
        index = max(
            (
                i
                for i, t in enumerate(times)
                if t <= when + TIME_MATCH * max(1.0, abs(when))
            ),
            default=0,
        )
        if index + 1 < len(times) and times[index + 1] > times[index]:
            fraction = (when - times[index]) / (times[index + 1] - times[index])
            fraction = min(max(fraction, 0.0), 1.0)
            picked.append(
                values[index] + fraction * (values[index + 1] - values[index])
            )
        else:
            picked.append(values[index])
    return picked


def report(args: argparse.Namespace) -> int:
    from jinko.comparison_report import render_comparison_report, save_comparison_plot

    directory = Path(args.dir).resolve()
    target = directory / "report.md"
    refuse_overwrite([target], overwrite=args.overwrite)
    manifest = load_manifest(directory)
    jinko = read_json(directory / JINKO)
    other = read_json(directory / OTHER)
    summary = read_json(directory / "comparison.json")
    aligned = read_json(directory / ALIGNED)
    units = {item["id"]: item["unit"] for item in jinko["series"]}
    solver = other.get("solver") or manifest["target"]

    plots: dict[str, str] = {}
    for identifier, points in aligned.items():
        image = Path("plots") / f"{identifier}.png"
        save_comparison_plot(
            directory / image,
            points["times"],
            points["jinko"],
            points["other"],
            series=identifier,
            unit=units.get(identifier),
            reference_label=solver,
        )
        plots[identifier] = image.as_posix()
    target.write_text(
        render_comparison_report(
            summary,
            title=args.title
            or f"Export check of {manifest['cm']} ({manifest['target']})",
            model_url=_model_url(manifest["cm"]),
            solver=solver,
            plots=plots,
            warnings=manifest.get("warnings") or [],
        ),
        encoding="utf-8",
    )
    print(f"wrote {target}")
    return 0


def _model_url(cm: str) -> str | None:
    try:
        return str(jinko_client().get_model(cm).url)
    except Exception:  # noqa: BLE001 - the report is still useful without the card
        return None


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"**{summary['status']}**: {summary['rule']}, tolerance {summary['tolerance']:g}.",
        "",
        "| Series | Status | Points | Event points | Max relative error | Max absolute error | Cmax | AUC | Unit conversion |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["series"]:
        if "points" not in row:
            lines.append(f"| {row['id']} | {row['status']} | | | | | | | |")
            continue
        lines.append(
            f"| {row['id']} | {row['status']} | {row['points']} | {row['event_points']} | "
            f"{row['max_relative_error']:.3e} | {row['max_absolute_error']:.3e} | "
            f"{row['cmax_relative_error']:.3e} | {row['auc_relative_error']:.3e} | "
            f"{row['conversion'] or ''} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Runners: produce other.json from the exported file
# --------------------------------------------------------------------------- #


def _compared(directory: Path) -> tuple[dict[str, Any], list[float]]:
    """The Jinkō series, and the times to sample: each time point and just before."""
    jinko = read_json(directory / JINKO)
    grid = sorted(set(jinko["time"]["values"]))
    times = set(grid)
    times.update(when - LEFT * max(1.0, abs(when)) for when in grid[1:])
    return jinko, sorted(times)


def _species_unit(jinko: dict[str, Any], identifier: str, extent: str) -> str | None:
    """Exports hold species as amounts in the extent unit; other series as in Jinkō."""
    return extent if identifier in jinko["species"] else None


def _model_time_scale_seconds(options: dict[str, Any]) -> float:
    """Seconds per unit of the exported program's time axis.

    Jinkō's reference time grid is always in seconds, but the SBML, Julia, and
    nlmixr2 exports write their equations and events in the model's own
    solving-step unit (for example Day, when ``tStep`` is ``P1D``): rate
    constants, dosing schedules, and event times are plain numbers in that
    unit, not seconds. Feeding the raw second values to those exports as a
    time axis stretches the integration horizon by this factor, which blows
    up or crashes the solver instead of comparing the exported equations.
    """
    from jinko.iso8601 import Duration

    seconds = Duration.parse(options["solvingTimes"][0]["tStep"]).total_seconds()
    if not seconds:
        raise ValueError("the model's solving step (tStep) is zero")
    return seconds


def run_sbml(args: argparse.Namespace) -> int:
    try:
        import roadrunner
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "the SBML check needs libroadrunner: pip install libroadrunner"
        ) from exc

    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / OTHER], overwrite=args.overwrite)
    manifest = load_manifest(directory)
    options = solving_options(directory, manifest)
    jinko, times = _compared(directory)

    runner = roadrunner.RoadRunner(str(exported_file(directory, manifest)))
    runner.integrator.absolute_tolerance = ABSOLUTE_TOLERANCE
    runner.integrator.relative_tolerance = RELATIVE_TOLERANCE
    known = set(runner.model.getFloatingSpeciesIds()) | set(
        runner.model.getBoundarySpeciesIds()
    )
    known |= set(runner.model.getGlobalParameterIds()) | set(
        runner.model.getCompartmentIds()
    )
    names = {
        identifier: identifier.replace(".", "_DOT_")
        for identifier in jinko["compared_ids"]
    }
    missing = [identifier for identifier, name in names.items() if name not in known]
    if missing:
        raise ValueError("not in the SBML model: " + ", ".join(missing))
    runner.timeCourseSelections = ["time", *names.values()]
    scale = _model_time_scale_seconds(options)
    result = runner.simulate(times=[t / scale for t in times])
    write_json(
        directory / OTHER,
        {
            "solver": f"libRoadRunner {roadrunner.__version__}",
            "time": {"unit": "s", "values": [float(t) * scale for t in result[:, 0]]},
            "series": [
                {
                    "id": identifier,
                    "unit": _species_unit(jinko, identifier, options["extentUnits"]),
                    "values": [float(v) for v in result[:, column + 1]],
                }
                for column, identifier in enumerate(names)
            ],
        },
    )
    print(f"wrote {directory / OTHER}")
    return 0


def _run(command: list[str], *, cwd: Path, label: str) -> None:
    if shutil.which(command[0]) is None:
        raise RuntimeError(f"{command[0]} is not installed; see the target reference")
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"{label} failed:\n{completed.stderr[-4000:]}")


def _csv_to_other(
    path: Path, jinko: dict[str, Any], names: dict[str, str], extent: str, solver: str
) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    return {
        "solver": solver,
        "time": {"unit": "s", "values": [float(row["time"]) for row in rows]},
        "series": [
            {
                "id": identifier,
                "unit": _species_unit(jinko, identifier, extent),
                "values": [float(row[name]) for row in rows],
            }
            for identifier, name in names.items()
        ],
    }


JULIA_DROPPED = re.compile(
    r"^(using (Plots|TerminalLoggers)|using Logging|global_logger\()"
)


def julia_driver(
    source: str, names: dict[str, str], times: list[float], options: dict, scale: float
) -> str:
    """The exported program, solved on the Jinkō grid, written to CSV.

    Plotting and printing are dropped. The solver and callbacks stay as
    exported; only the tolerances and the save times are set. ``times`` and
    ``scale`` are in seconds; the exported equations run on the model's own
    time unit, so the grid is fed in that unit and the output time column is
    converted back to seconds (see ``_model_time_scale_seconds``).
    """
    labels = re.search(r"plot\(sol, label=\[(.*?)\]\)", source)
    if not labels:
        raise ValueError("the Julia export has no state label list")
    states = re.findall(r'"([^"]+)"', labels.group(1))
    for identifier in [identifier for identifier in names if identifier not in states]:
        del names[identifier]  # the program saves states only
    if not names:
        raise ValueError("none of the compared series is a state of the Julia export")
    head, separator, _ = source.partition("\nsol = solve(")
    if not separator:
        raise ValueError("the Julia export has no solve call")
    head = "\n".join(
        line for line in head.splitlines() if not JULIA_DROPPED.match(line)
    )
    solve_line = re.search(r"\nsol = solve\((.*)\)\n", source).group(1)
    solve_line = re.sub(r"progress(_steps)?=[^,]*,\s*", "", solve_line)
    grid = ", ".join(repr(float(t) / scale) for t in times)
    columns = ", ".join(f'"{names[identifier]}"' for identifier in names)
    indices = ", ".join(str(states.index(identifier) + 1) for identifier in names)
    return (
        f"{head}\n"
        f"sol = solve({solve_line}, abstol={ABSOLUTE_TOLERANCE!r}, "
        f"reltol={RELATIVE_TOLERANCE!r}, saveat=[{grid}])\n"
        'open("other.csv", "w") do io\n'
        f'    println(io, join(["time", {columns}], ","))\n'
        "    for i in 1:length(sol.t)\n"
        "        state = sol.u[i].x[1]\n"
        f'        println(io, join(vcat([sol.t[i] * {scale!r}], [state[k] for k in [{indices}]]), ","))\n'
        "    end\n"
        "end\n"
    )


def run_julia(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / OTHER], overwrite=args.overwrite)
    manifest = load_manifest(directory)
    options = solving_options(directory, manifest)
    jinko, times = _compared(directory)
    names = {
        identifier: identifier.replace(".", "_") for identifier in jinko["compared_ids"]
    }
    source = exported_file(directory, manifest).read_text(encoding="utf-8")
    driver = directory / "check_julia.jl"
    scale = _model_time_scale_seconds(options)
    driver.write_text(
        julia_driver(source, names, times, options, scale), encoding="utf-8"
    )
    _run([args.julia, str(driver)], cwd=directory, label="Julia")
    other = _csv_to_other(
        directory / "other.csv", jinko, names, options["extentUnits"], "Julia export"
    )
    other["unavailable"] = [i for i in jinko["compared_ids"] if i not in names]
    write_json(directory / OTHER, other)
    print(f"wrote {directory / OTHER}")
    return 0


def nlmixr2_driver(
    source: str, names: dict[str, str], times: list[float], options: dict, scale: float
) -> str:
    """The exported model definition, solved by rxode2 on the Jinkō grid.

    The export's own driver (from ``test_params``) is dropped: it solves on its
    own grid and only plots. ``times`` and ``scale`` are in seconds; the
    exported equations run on the model's own time unit, so the grid is fed
    in that unit and the output time column is converted back to seconds (see
    ``_model_time_scale_seconds``).
    """
    definition, separator, _ = source.partition("\ntest_params <- c(")
    if not separator:
        raise ValueError("the nlmixr2 export has no test_params block")
    definition = "\n".join(
        line
        for line in definition.splitlines()
        if not re.match(r"^library\((dplyr|ggplot2|patchwork)\)", line)
    )
    grid = ", ".join(repr(float(t) / scale) for t in times)
    columns = ", ".join(f'"{name}"' for name in names.values())
    return (
        f"{definition}\n"
        f"out <- rxSolve(nlmixrModel, events = et(c({grid})), "
        f"atol = {ABSOLUTE_TOLERANCE!r}, rtol = {RELATIVE_TOLERANCE!r}, "
        'returnType = "data.frame")\n'
        f"out$time <- out$time * {scale!r}\n"
        f'write.csv(out[, c("time", {columns})], "other.csv", row.names = FALSE)\n'
    )


def run_nlmixr2(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / OTHER], overwrite=args.overwrite)
    manifest = load_manifest(directory)
    options = solving_options(directory, manifest)
    jinko, times = _compared(directory)
    names = {
        identifier: identifier.replace(".", "_") for identifier in jinko["compared_ids"]
    }
    source = exported_file(directory, manifest).read_text(encoding="utf-8")
    driver = directory / "check_nlmixr2.R"
    scale = _model_time_scale_seconds(options)
    driver.write_text(
        nlmixr2_driver(source, names, times, options, scale), encoding="utf-8"
    )
    _run([args.rscript, str(driver)], cwd=directory, label="R")
    other = _csv_to_other(
        directory / "other.csv",
        jinko,
        names,
        options["extentUnits"],
        "nlmixr2/rxode2 export",
    )
    write_json(directory / OTHER, other)
    print(f"wrote {directory / OTHER}")
    return 0


def matlab_driver(script: str, units: dict[str, str | None], times: list[float]) -> str:
    """Run the SimBiology code on the Jinkō grid and write other.json.

    The exported script builds ``model``, ``cs`` and ``doses``, then simulates.
    The driver simulates again with the Jinkō output times, in seconds.
    """
    grid = " ".join(repr(float(t)) for t in times)
    ids = "{" + ", ".join(f"'{identifier}'" for identifier in units) + "}"
    unit_cells = (
        "{" + ", ".join(f"'{unit}'" if unit else "[]" for unit in units.values()) + "}"
    )
    return f"""run('{script}');
cs.TimeUnits = 'second';
cs.SolverOptions.OutputTimes = [{grid}];
simData = sbiosimulate(model, cs, doses);
ids = {ids};
units = {unit_cells};
[t, x] = selectbyname(simData, ids);
series = struct('id', ids, 'unit', units, 'values', num2cell(x, 1));
result = struct('solver', ['SimBiology ' version('-release')], ...
    'time', struct('unit', 'second', 'values', t'), 'series', series);
fid = fopen('other.json', 'w');
fprintf(fid, '%s', jsonencode(result));
fclose(fid);
"""


def prepare_matlab(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    manifest = load_manifest(directory)
    if manifest["target"] != "simbiology-code":
        raise ValueError("prepare-matlab needs a simbiology-code export")
    jinko, times = _compared(directory)
    script = exported_file(directory, manifest).name
    driver = directory / "check_simbiology.m"
    refuse_overwrite([driver], overwrite=args.overwrite)
    extent = solving_options(directory, manifest)["extentUnits"]
    units = {
        identifier: _species_unit(jinko, identifier, extent)
        for identifier in jinko["compared_ids"]
    }
    driver.write_text(matlab_driver(script, units, times), encoding="utf-8")
    print(f"wrote {driver}; run it in MATLAB from {directory}")
    return 0


# --------------------------------------------------------------------------- #


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = root.add_subparsers(dest="command", required=True)

    command = commands.add_parser("export", help="download one target")
    command.add_argument("cm")
    command.add_argument("--target", choices=sorted(TARGETS), required=True)
    command.add_argument("--output-dir", required=True)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=export)

    command = commands.add_parser("list-series", help="time-dependent ids")
    command.add_argument("cm")
    command.set_defaults(handler=list_series)

    command = commands.add_parser("reference", help="solve in Jinkō")
    command.add_argument("--dir", required=True)
    command.add_argument("--ids", nargs="+", required=True)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=reference)

    for name, handler, extra in (
        ("run-sbml", run_sbml, None),
        ("run-julia", run_julia, ("--julia", "julia")),
        ("run-nlmixr2", run_nlmixr2, ("--rscript", "Rscript")),
        ("prepare-matlab", prepare_matlab, None),
    ):
        command = commands.add_parser(name)
        command.add_argument("--dir", required=True)
        command.add_argument("--overwrite", action="store_true")
        if extra:
            command.add_argument(extra[0], default=extra[1])
        command.set_defaults(handler=handler)

    command = commands.add_parser("compare", help="compare other.json with jinko.json")
    command.add_argument("--dir", required=True)
    from jinko._comparison import TOLERANCE

    command.add_argument("--tolerance", type=float, default=TOLERANCE)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=compare)

    command = commands.add_parser("report", help="render the optional report")
    command.add_argument("--dir", required=True)
    command.add_argument("--title")
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=report)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except FileNotFoundError as error:
        print(
            f"error: {error.filename} is missing; run the previous step first",
            file=sys.stderr,
        )
        return 2
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
