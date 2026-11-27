#!/usr/bin/env python3
"""Compare a model imported into Jinkō with its source tool.

The skill calls these commands for deterministic file handling, solving, and
comparison. They are an implementation detail, not a CLI for users to learn.

Run directory layout, one directory per comparison:

- ``jinko.json``: the Jinkō series (``reference``).
- ``source.json``: the same series from the source tool (``run-sbml``,
  ``check_simbiology.m`` written by ``prepare-matlab``, or ``from-csv``).
- ``comparison.json`` and ``comparison.md``: the result (``compare``), and
  ``aligned.json``, the compared points.
- ``report.md`` and ``plots/``: the optional report (``report``).

``jinko.json`` and ``source.json`` share one shape::

    {"time": {"unit": "s", "values": [...]},
     "series": [{"id": "A", "unit": "mmol / L", "values": [...]}]}

A series unit of ``null`` in ``source.json`` means "the Jinkō unit".
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

JINKO = "jinko.json"
SOURCE = "source.json"
ALIGNED = "aligned.json"
SOLVE_BATCH = 9  # simple_solve takes at most 10 series, Time included
TIME_MATCH = 1e-9
# The source solver runs tight, so the check tests the imported equations and
# not solver settings.
RELATIVE_TOLERANCE = 1e-10
ABSOLUTE_TOLERANCE = 1e-14


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


def unit_registry():
    try:
        import pint
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("the comparison needs pint: pip install pint") from exc
    return pint.UnitRegistry()


def seconds_per(registry, unit: str) -> float:
    return registry.Quantity(1.0, unit).to("s").magnitude


def is_concentration(registry, unit: str | None) -> bool:
    if not unit:
        return False
    dimensions = registry.Quantity(1.0, unit).dimensionality
    return dimensions.get("[length]", 0) == -3 and (
        dimensions.get("[substance]", 0) or dimensions.get("[mass]", 0)
    )


# --------------------------------------------------------------------------- #
# Jinkō side
# --------------------------------------------------------------------------- #


def jinko_client():
    try:
        from jinko import JinkoClient
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("cannot import jinko-sdk; run jinko-sdk-setup") from exc
    return JinkoClient()


def list_series(args: argparse.Namespace) -> int:
    model = jinko_client().get_model(args.cm)
    for identifier in model.time_dependent_ids():
        if identifier != "Time":
            print(identifier)
    return 0


def reference(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / JINKO], overwrite=args.overwrite)
    model = jinko_client().get_model(args.cm)
    ids = list(dict.fromkeys(args.ids))
    time_parameter = next(
        (item for item in model.components.list_parameters() if item.id == "time"),
        None,
    )

    time: list[float] | None = None
    series: list[dict[str, Any]] = []
    for start in range(0, len(ids), SOLVE_BATCH):
        batch = ids[start : start + SOLVE_BATCH]
        output = model.simple_solve(
            timeseries_ids=["Time", *batch], raise_on_error=False
        )
        if output.error:
            raise ValueError(f"the Jinkō solve failed: {output.error}")
        by_id = {result.id: result for result in output.results}
        if time is None:
            time = list(by_id["Time"].values)
        elif list(by_id["Time"].values) != time:
            raise ValueError("the Jinkō solves returned different time grids")
        for identifier in batch:
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
            "cm": args.cm,
            "url": str(model.url),
            # The import keeps the source's time unit on the `time` parameter.
            "model_time_unit": time_parameter.unit if time_parameter else None,
            "compared_ids": ids,
            "time": {"unit": "s", "values": time},
            "series": series,
        },
    )
    print(f"wrote {directory / JINKO}: {len(time or [])} time points")
    return 0


def _source_time_unit(jinko: dict[str, Any], given: str | None) -> str:
    unit = given or jinko.get("model_time_unit")
    if not unit:
        raise ValueError(
            "the imported model does not record its time unit; "
            "pass --time-unit with the time unit of the source"
        )
    return unit


# --------------------------------------------------------------------------- #
# Source side
# --------------------------------------------------------------------------- #


def sbml_selection(identifier: str, jinko_unit: str | None, registry) -> str:
    """libRoadRunner reads a species id as an amount and ``[id]`` as a concentration.

    The import keeps the unit kind of the SBML: a species that Jinkō reports as
    a concentration is read as a concentration, any other one as an amount.
    """
    return f"[{identifier}]" if is_concentration(registry, jinko_unit) else identifier


def run_sbml(args: argparse.Namespace) -> int:
    try:
        import roadrunner
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "the SBML check needs libroadrunner: pip install libroadrunner"
        ) from exc

    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / SOURCE], overwrite=args.overwrite)
    jinko = read_json(directory / JINKO)
    registry = unit_registry()
    scale = seconds_per(registry, _source_time_unit(jinko, args.time_unit))

    runner = roadrunner.RoadRunner(str(Path(args.source).resolve()))
    runner.integrator.absolute_tolerance = ABSOLUTE_TOLERANCE
    runner.integrator.relative_tolerance = RELATIVE_TOLERANCE
    species = set(runner.model.getFloatingSpeciesIds()) | set(
        runner.model.getBoundarySpeciesIds()
    )
    known = (
        species
        | set(runner.model.getGlobalParameterIds())
        | set(runner.model.getCompartmentIds())
    )
    units = {item["id"]: item["unit"] for item in jinko["series"]}
    missing = [i for i in jinko["compared_ids"] if i not in known]
    if missing:
        raise ValueError(
            "not in the SBML model: " + ", ".join(missing) + "; the import "
            "renamed them, compare the series under their source ids"
        )
    selections = [
        sbml_selection(i, units[i], registry) if i in species else i
        for i in jinko["compared_ids"]
    ]
    runner.timeCourseSelections = ["time", *selections]
    grid = sorted(set(jinko["time"]["values"]))
    result = runner.simulate(times=[t / scale for t in grid])
    write_json(
        directory / SOURCE,
        {
            "solver": f"libRoadRunner {roadrunner.__version__}",
            "time": {"unit": "s", "values": [float(t) * scale for t in result[:, 0]]},
            "series": [
                {
                    "id": identifier,
                    "unit": None,
                    "values": [float(v) for v in result[:, column + 1]],
                }
                for column, identifier in enumerate(jinko["compared_ids"])
            ],
        },
    )
    print(f"wrote {directory / SOURCE}")
    return 0


def matlab_driver(project: str, ids: list[str], times: list[float]) -> str:
    """Simulate the user's SimBiology project on the Jinkō grid, write source.json.

    The project stays as saved: the driver changes the configset in memory
    only. Times are in seconds, like the Jinkō grid.
    """
    grid = " ".join(repr(float(t)) for t in times)
    cells = "{" + ", ".join(f"'{identifier}'" for identifier in ids) + "}"
    return f"""items = struct2cell(sbioloadproject('{project}'));
model = items{{find(cellfun(@(item) isa(item, 'SimBiology.Model'), items), 1)}};
cs = getconfigset(model, 'active');
cs.TimeUnits = 'second';
cs.SolverOptions.OutputTimes = [{grid}];
cs.SolverOptions.RelativeTolerance = {RELATIVE_TOLERANCE!r};
cs.SolverOptions.AbsoluteTolerance = {ABSOLUTE_TOLERANCE!r};
simData = sbiosimulate(model, cs, getdose(model));
ids = {cells};
[t, x] = selectbyname(simData, ids);
units = cell(size(ids));
for k = 1:numel(ids)
    for j = 1:numel(simData.DataInfo)
        if strcmp(simData.DataInfo{{j}}.Name, ids{{k}})
            units{{k}} = simData.DataInfo{{j}}.Units;
            break;
        end
    end
end
series = struct('id', ids, 'unit', units, 'values', num2cell(x, 1));
result = struct('solver', ['SimBiology ' version('-release')], ...
    'time', struct('unit', 'second', 'values', t'), 'series', series);
fid = fopen('{SOURCE}', 'w');
fprintf(fid, '%s', jsonencode(result));
fclose(fid);
"""


def prepare_matlab(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    jinko = read_json(directory / JINKO)
    driver = directory / "check_simbiology.m"
    refuse_overwrite([driver], overwrite=args.overwrite)
    times = sorted(set(jinko["time"]["values"]))
    driver.write_text(
        matlab_driver(args.project, jinko["compared_ids"], times), encoding="utf-8"
    )
    print(f"wrote {driver}; run it in MATLAB from {directory}")
    return 0


def _pairs(items: list[str], flag: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in items or []:
        key, separator, value = item.partition("=")
        if not separator or not key or not value:
            raise ValueError(f"{flag} expects JINKO_ID=VALUE, got {item!r}")
        pairs[key] = value
    return pairs


def from_csv(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    refuse_overwrite([directory / SOURCE], overwrite=args.overwrite)
    jinko = read_json(directory / JINKO)
    columns = _pairs(args.column, "--column")
    units = _pairs(args.unit, "--unit")
    with Path(args.csv).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"{args.csv} has no rows")
    header = rows[0].keys()
    if args.time_column not in header:
        raise ValueError(f"{args.csv} has no {args.time_column!r} column")
    series = []
    unavailable = []
    for identifier in jinko["compared_ids"]:
        column = columns.get(identifier, identifier)
        if column not in header:
            unavailable.append(identifier)
            continue
        series.append({
            "id": identifier,
            "unit": units.get(identifier),
            "values": [float(row[column]) for row in rows],
        })
    if not series:
        raise ValueError("none of the compared series is a column of the CSV")
    scale = seconds_per(unit_registry(), args.time_unit)
    write_json(
        directory / SOURCE,
        {
            "solver": args.solver,
            "time": {
                "unit": "s",
                "values": [float(row[args.time_column]) * scale for row in rows],
            },
            "series": series,
            "unavailable": unavailable,
        },
    )
    print(f"wrote {directory / SOURCE}")
    return 0


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #


def shared_points(
    jinko_time: list[float], times: list[float], values: list[float]
) -> tuple[list[float], list[float]]:
    """Keep the source points that fall on the Jinkō grid, on Jinkō's times."""
    grid = sorted(set(jinko_time))
    kept_times: list[float] = []
    kept_values: list[float] = []
    for when, value in zip(times, values):
        slack = TIME_MATCH * max(1.0, abs(when))
        match = next((t for t in grid if abs(t - when) <= slack), None)
        if match is not None:
            kept_times.append(match)
            kept_values.append(value)
    return kept_times, kept_values


def at(times: list[float], values: list[float], when: float) -> float:
    """The Jinkō value at a grid time: after the event when it is reported twice."""
    return values[max(i for i, t in enumerate(times) if t == when)]


def compare(args: argparse.Namespace) -> int:
    from jinko.types import SimpleSolveOutput, SolvedSeries

    directory = Path(args.dir).resolve()
    outputs = [
        directory / "comparison.json",
        directory / "comparison.md",
        directory / ALIGNED,
    ]
    refuse_overwrite(outputs, overwrite=args.overwrite)
    jinko = read_json(directory / JINKO)
    source = read_json(directory / SOURCE)
    registry = unit_registry()
    jinko_series = {item["id"]: item for item in jinko["series"]}
    source_series = {item["id"]: item for item in source["series"]}
    jinko_time = jinko["time"]["values"]
    source_time = [
        value * seconds_per(registry, source["time"]["unit"])
        for value in source["time"]["values"]
    ]

    rows: list[dict[str, Any]] = []
    aligned: dict[str, dict[str, list[float]]] = {}
    passed = True
    for identifier in jinko["compared_ids"]:
        expected = jinko_series[identifier]
        item = source_series.get(identifier)
        if identifier in source.get("unavailable", []):
            rows.append({"id": identifier, "status": "NOT CHECKED: not in the source"})
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
        if item.get("unit") and item["unit"] != expected["unit"]:
            try:
                scale = (
                    registry.Quantity(1.0, item["unit"]).to(expected["unit"]).magnitude
                )
            except Exception:  # pint raises several error types
                rows.append({
                    "id": identifier,
                    "status": f"UNIT MISMATCH: {item['unit']} vs {expected['unit']}",
                })
                passed = False
                continue
            values = [value * scale for value in values]
            conversion = f"{item['unit']} -> {expected['unit']}"
        times, values = shared_points(jinko_time, source_time, values)
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
                    expected["unit"],
                    len(expected["values"]),
                    expected["values"],
                ),
            ],
        )
        result = output.compare(
            {identifier: values}, times=times, tolerance=args.tolerance
        )[identifier]
        passed = passed and result.passes
        aligned[identifier] = {
            "times": times,
            "jinko": [at(jinko_time, expected["values"], when) for when in times],
            "source": values,
        }
        rows.append({
            "id": identifier,
            "status": "PASS" if result.passes else "FAIL",
            "unit": expected["unit"],
            "conversion": conversion,
            "points": result.points,
            "max_relative_error": result.max_relative_error,
            "max_absolute_error": result.max_absolute_error,
            "cmax_relative_error": result.cmax_relative_error,
            "auc_relative_error": result.auc_relative_error,
            "note": result.note,
        })

    summary = {
        "status": "PASS" if passed else "FAIL",
        "cm": jinko["cm"],
        "source": source.get("solver"),
        "tolerance": args.tolerance,
        "rule": "max point-wise relative error against Jinkō, floor 1e-5 x Jinkō peak",
        "series": rows,
    }
    write_json(outputs[0], summary)
    write_json(outputs[2], aligned)
    outputs[1].write_text(_markdown(summary), encoding="utf-8")
    print(outputs[1].read_text(encoding="utf-8"))
    return 0 if passed else 1


def report(args: argparse.Namespace) -> int:
    from jinko.comparison_report import render_comparison_report, save_comparison_plot

    directory = Path(args.dir).resolve()
    target = directory / "report.md"
    refuse_overwrite([target], overwrite=args.overwrite)
    jinko = read_json(directory / JINKO)
    summary = read_json(directory / "comparison.json")
    aligned = read_json(directory / ALIGNED)
    units = {item["id"]: item["unit"] for item in jinko["series"]}

    plots: dict[str, str] = {}
    for identifier, points in aligned.items():
        image = Path("plots") / f"{identifier}.png"
        save_comparison_plot(
            directory / image,
            points["times"],
            points["jinko"],
            points["source"],
            series=identifier,
            unit=units.get(identifier),
            reference_label=summary.get("source") or "Source tool",
        )
        plots[identifier] = image.as_posix()
    target.write_text(
        render_comparison_report(
            summary,
            title=args.title or f"Import check of {jinko['cm']}",
            model_url=jinko.get("url"),
            solver=summary.get("source"),
            plots=plots,
            warnings=args.warning or [],
        ),
        encoding="utf-8",
    )
    print(f"wrote {target}")
    return 0


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"**{summary['status']}** against {summary['source']}: {summary['rule']}, "
        f"tolerance {summary['tolerance']:g}.",
        "",
        "| Series | Status | Points | Max relative error | Max absolute error | Cmax | AUC | Unit conversion |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["series"]:
        if "points" not in row:
            lines.append(f"| {row['id']} | {row['status']} | | | | | | |")
            continue
        lines.append(
            f"| {row['id']} | {row['status']} | {row['points']} | "
            f"{row['max_relative_error']:.3e} | {row['max_absolute_error']:.3e} | "
            f"{row['cmax_relative_error']:.3e} | {row['auc_relative_error']:.3e} | "
            f"{row['conversion'] or ''} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = root.add_subparsers(dest="command", required=True)

    command = commands.add_parser("list-series", help="time-dependent ids")
    command.add_argument("cm")
    command.set_defaults(handler=list_series)

    command = commands.add_parser("reference", help="solve in Jinkō")
    command.add_argument("cm")
    command.add_argument("--dir", required=True)
    command.add_argument("--ids", nargs="+", required=True)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=reference)

    command = commands.add_parser("run-sbml", help="solve the source SBML")
    command.add_argument("--dir", required=True)
    command.add_argument("--source", required=True)
    command.add_argument("--time-unit")
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=run_sbml)

    command = commands.add_parser("prepare-matlab", help="write the SimBiology driver")
    command.add_argument("--dir", required=True)
    command.add_argument("--project", required=True)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=prepare_matlab)

    command = commands.add_parser("from-csv", help="read the source tool's results")
    command.add_argument("--dir", required=True)
    command.add_argument("--csv", required=True)
    command.add_argument("--time-unit", required=True)
    command.add_argument("--time-column", default="time")
    command.add_argument("--column", action="append", metavar="JINKO_ID=COLUMN")
    command.add_argument("--unit", action="append", metavar="JINKO_ID=UNIT")
    command.add_argument("--solver", default="source tool CSV")
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=from_csv)

    command = commands.add_parser("compare", help="compare source.json with jinko.json")
    command.add_argument("--dir", required=True)
    command.add_argument("--tolerance", type=float, default=1e-3)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=compare)

    command = commands.add_parser("report", help="render the optional report")
    command.add_argument("--dir", required=True)
    command.add_argument("--title")
    command.add_argument("--warning", action="append", help="an import warning")
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
