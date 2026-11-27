#!/usr/bin/env python3
"""Import a Heta platform into Jinkō: convert, then create the items.

The skill calls these commands. They are an implementation detail, not a CLI
for users to learn.

- ``convert <export> --dir <dir>``: converts the table export of the Heta
  compiler with the ``heta2jinko`` package of the SDK, then checks the result
  offline. Nothing reaches Jinkō. A construct outside the converter's subset
  stops the conversion and writes nothing.
- ``apply --dir <dir> --folder <name>``: creates the model in Jinkō, with its
  solving options and tags, and checks that it solves. When the platform
  declares scenarios, it also creates the protocol design, the simple output
  set, and the trial. ``--run`` runs the trial.

The run directory holds the converter files (``jinko-model.json``,
``tags.json``, ``conversion-report.md``, and, with scenarios,
``protocol-design.json`` and ``output-set.json``), then ``items.json``, the
created items.

Exit status: 0 done - 1 the conversion or a check failed - 2 the step could
not run.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

MODEL = "jinko-model.json"
TAGS = "tags.json"
REPORT = "conversion-report.md"
PROTOCOL = "protocol-design.json"
OUTPUT_SET = "output-set.json"
ITEMS = "items.json"
RUN = "run.json"  # the inputs of the conversion, for the check
TABLE = "table.xlsx"  # the export and the scenario table, merged for the converter
CHECK = "check"

SOLVE_BATCH = 9  # simple_solve takes at most 10 series, Time included
CONVERTER_REFUSED_OVERWRITE = 3  # exit status of `heta2jinko convert`

EXTENT_UNITS_CHECK = "UnitCheckAndConvertAllSpeciesToExtentUnits"
NO_UNIT_CHECK = "NoUnitCheck"

# A unit atom that carries a volume: `liter`, `mliter`, `meter`, `cmeter`, ...
VOLUME_ATOM = re.compile(r"\b[a-z]*(?:liter|meter)\b")


class CouldNotRun(Exception):
    """A precondition failed, so the step gives no verdict."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CouldNotRun(f"no {path.name} in {path.parent}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise CouldNotRun(f"{path} is not readable JSON: {exc}") from None


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Offline checks
# --------------------------------------------------------------------------- #


def load_conversion(directory: Path) -> dict[str, Any]:
    """Read the converter files of one run directory."""
    model = read_json(directory / MODEL)
    tags = read_json(directory / TAGS) if (directory / TAGS).exists() else {}
    protocol = (
        read_json(directory / PROTOCOL) if (directory / PROTOCOL).exists() else None
    )
    output_set = (
        read_json(directory / OUTPUT_SET) if (directory / OUTPUT_SET).exists() else None
    )
    return {
        "model": model,
        "tags": tags,
        "protocol": protocol,
        "output_set": output_set,
    }


def component_ids(doc: dict[str, Any]) -> set[str]:
    return {
        entry["args"]["id"]
        for entry in doc.get("components", [])
        if (entry.get("args") or {}).get("id")
    }


def check_tags(tags: dict[str, list[str]], doc: dict[str, Any]) -> list[str]:
    """A tag on an unknown id would apply to nothing, silently."""
    known = component_ids(doc)
    return [
        f"{TAGS}: names unknown component {cid!r}"
        for cid in sorted(tags)
        if cid not in known
    ]


def check_unit_mode(doc: dict[str, Any]) -> list[str]:
    """Refuse a mode that breaks the `(S / V)` rewrite of the converter.

    The converter makes each species state an amount and writes `(S / V)` for
    its concentration. Under any mode other than the two below, a
    concentration species stays a concentration, the rewrite divides twice,
    and every nonlinear rate law is wrong by a compartment volume.
    """
    species = [
        entry["args"]
        for entry in doc.get("components", [])
        if entry.get("method") == "create_species"
    ]
    if not species:
        return []
    mode = (doc.get("solving_options") or {}).get("unit_check")
    if mode == EXTENT_UNITS_CHECK:
        return []
    concentrations = [
        args["id"]
        for args in species
        if VOLUME_ATOM.search(str(args.get("unit") or ""))
    ]
    if mode == NO_UNIT_CHECK and not concentrations:
        return []
    return [
        f"unit_check is {mode!r}, which does not keep the species as amounts "
        "that the converter's `(S / V)` rewrite needs. Convert again rather "
        "than editing the mode."
    ]


def check_conversion(conversion: dict[str, Any]) -> list[str]:
    """The offline checks of the converter, then the two of the import."""
    from heta2jinko.emit_jinko import check_arms, check_components, check_measures

    doc = conversion["model"]
    problems = check_components(doc.get("components") or [])
    if conversion["protocol"] is not None:
        problems += check_arms(conversion["protocol"])
    if conversion["output_set"] is not None:
        problems += check_measures(conversion["output_set"], doc)
    problems += check_tags(conversion["tags"], doc)
    problems += check_unit_mode(doc)
    return problems


def plan(conversion: dict[str, Any]) -> list[str]:
    """The items that `apply` creates, one line each."""
    doc = conversion["model"]
    lines = [f"model         {doc['model_name']} ({len(doc['components'])} components)"]
    if conversion["protocol"] is not None:
        arms = conversion["protocol"]["args"]["arms"]
        lines.append(
            f"protocol      {conversion['protocol'].get('protocol_name')}: "
            + ", ".join(arm["armName"] for arm in arms)
        )
        if conversion["output_set"] is not None:
            measures = conversion["output_set"]["args"]["measures"]
            lines.append(
                "output set    "
                + ", ".join(
                    m if isinstance(m, str) else m["timeseriesId"] for m in measures
                )
            )
        lines.append("trial         the model, the protocol, and the output set")
    return lines


# --------------------------------------------------------------------------- #
# convert
# --------------------------------------------------------------------------- #


def convert(args: argparse.Namespace) -> int:
    try:
        from heta2jinko.convert import main as heta2jinko_convert
    except ImportError:
        print(
            "COULD NOT RUN\n  heta2jinko is not importable: "
            'pip install "jinko-sdk[heta2jinko]"',
            file=sys.stderr,
        )
        return 2

    directory = Path(args.dir)
    source = Path(args.export)
    if args.scenarios:
        from heta2jinko.scenarios import (
            ScenarioError,
            merge_into_table,
            read_scenario_table,
        )

        try:
            source = merge_into_table(
                source, read_scenario_table(args.scenarios), directory / TABLE
            )
        except (ScenarioError, OSError) as exc:
            print(f"STOPPED      the scenario table cannot be read: {exc}")
            return 1
    argv = [str(source), "-o", str(directory)]
    if args.t_max_days is not None:
        argv += ["--t-max-days", str(args.t_max_days)]
    if args.t_step_days is not None:
        argv += ["--t-step-days", str(args.t_step_days)]
    if args.model_name:
        argv += ["--model-name", args.model_name]
    if args.force:
        argv.append("--force")

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors):
        status = heta2jinko_convert(argv)
    if status == CONVERTER_REFUSED_OVERWRITE:
        print(errors.getvalue().rstrip(), file=sys.stderr)
        return 2
    if status != 0:
        print("STOPPED      the conversion wrote nothing; nothing reached Jinkō")
        print(errors.getvalue().rstrip())
        return 1

    try:
        conversion = load_conversion(directory)
        problems = check_conversion(conversion)
    except CouldNotRun as exc:
        print(f"COULD NOT RUN\n  {exc}", file=sys.stderr)
        return 2
    if problems:
        print("INVALID      the converter output fails the offline checks")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    write_json(
        directory / RUN,
        {
            "export": str(Path(args.export).resolve()),
            "scenarios": str(Path(args.scenarios).resolve())
            if args.scenarios
            else None,
        },
    )
    print(f"report       {directory / REPORT}")
    print("apply creates:")
    for line in plan(conversion):
        print(f"  {line}")
    return 0


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #


def jinko_client():
    try:
        from jinko import JinkoClient
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise CouldNotRun("cannot import jinko-sdk; run jinko-sdk-setup") from exc
    return JinkoClient()


def resolve_folder(client, name: str, *, create: bool, parent: str | None):
    parent_folder = None
    if parent:
        parent_folder = client.get_folder_by_name(parent, exact_match_only=True)
        if parent_folder is None:
            if not create:
                raise CouldNotRun(f"no folder named {parent!r}; pass --create-folder")
            parent_folder = client.create_folder(parent)
    folder = client.get_folder_by_name(
        name, exact_match_only=True, parent=parent_folder
    )
    if folder is None:
        if not create:
            raise CouldNotRun(f"no folder named {name!r}; pass --create-folder")
        folder = client.create_folder(name, parent=parent_folder)
    return folder


def create_model(
    client, doc: dict[str, Any], tags: dict[str, list[str]], *, name, folder
):
    """Create the model: tags first, so that each component carries its own."""
    model = client.create_empty_model(name, folder=folder)
    existing = {tag.id for tag in model.tags}
    for tag_id in sorted({tag for group in tags.values() for tag in group} - existing):
        model.create_tag(tag_id)

    batch = model.components.batch()
    for entry in doc["components"]:
        arguments = dict(entry["args"])
        if arguments["id"] in tags:
            arguments["tags"] = list(tags[arguments["id"]])
        getattr(batch, entry["method"])(**arguments)
    batch.commit()

    options = doc["solving_options"]
    model.set_unit_check(options["unit_check"])
    # `outputParameters` is not sent: the `output` tag selects the outputs.
    model.edit_solving_options({
        "extentUnits": options["extent_units"],
        "discontinuityEvents": options["discontinuity_events"],
        "odeSolverRelativeTolerance": options["ode_solver_relative_tolerance"],
        "odeSolverAbsoluteTolerance": options["ode_solver_absolute_tolerance"],
    })
    times = options["solving_times"]
    model.set_solving_times(
        t_min=timedelta(days=times.get("t_min_days", 0.0)),
        t_max=timedelta(days=times["t_max_days"]),
        t_step=timedelta(days=times["t_step_days"]),
    )
    return model


def solve_series(doc: dict[str, Any], tags: dict[str, list[str]], model) -> list[str]:
    """The `output` series, or the model's time-dependent series without them."""
    outputs = [
        entry["args"]["id"]
        for entry in doc["components"]
        if "output" in tags.get(entry["args"]["id"], [])
    ]
    if outputs:
        return outputs
    return [cid for cid in model.time_dependent_ids() if cid != "Time"][:SOLVE_BATCH]


def sanity_check(model, series: list[str]) -> list[str]:
    """Empty diagnostics, and a solve that returns each series asked for."""
    problems = [f"diagnostic: {error}" for error in model.diagnostics.errors()]
    if problems:
        return problems
    for start in range(0, len(series), SOLVE_BATCH):
        asked = series[start : start + SOLVE_BATCH]
        result = model.simple_solve(timeseries_ids=asked, raise_on_error=False)
        if result.error:
            return [f"simple_solve: {result.error}"]
        returned = {item.id for item in result.results if item.values}
        problems += [
            f"simple_solve returned no values for {cid!r}"
            for cid in asked
            if cid not in returned
        ]
    return problems


def item_record(item) -> dict[str, Any]:
    return {"sid": item.sid, "url": item.url}


def apply(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    try:
        conversion = load_conversion(directory)
        problems = check_conversion(conversion)
    except CouldNotRun as exc:
        print(f"COULD NOT RUN\n  {exc}", file=sys.stderr)
        return 2
    if problems:
        print("INVALID      nothing was created")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    doc, tags = conversion["model"], conversion["tags"]
    name = args.name or doc["model_name"]
    items: dict[str, Any] = {"model_name": name, "folder": args.folder}
    status = 0
    try:
        client = jinko_client()
        folder = resolve_folder(
            client, args.folder, create=args.create_folder, parent=args.parent_folder
        )
        model = create_model(client, doc, tags, name=name, folder=folder)
        items["model"] = item_record(model)
        print(f"model        {model.url}")

        series = solve_series(doc, tags, model)
        problems = sanity_check(model, series)
        items["sanity"] = {
            "verdict": "FAIL" if problems else "PASS",
            "series": series,
            "problems": problems,
        }
        print(f"sanity       {items['sanity']['verdict']} on {', '.join(series)}")
        for problem in problems:
            print(f"  - {problem}")
        if problems:
            status = 1
        elif conversion["protocol"] is not None:
            status = create_trial(model, conversion, folder, name, items, run=args.run)
    except CouldNotRun as exc:
        print(f"COULD NOT RUN\n  {exc}", file=sys.stderr)
        status = 2
    except Exception as exc:
        print(f"COULD NOT RUN\n  {type(exc).__name__}: {exc}", file=sys.stderr)
        status = 2
    finally:
        if "model" in items:
            # Keep a partial run: deleting it is the user's decision.
            write_json(directory / ITEMS, items)
            print(f"items        {directory / ITEMS}")

    if status == 0:
        print("claim        Jinkō accepts and solves the model")
    return status


def create_trial(model, conversion, folder, name, items, *, run: bool) -> int:
    protocol_doc = conversion["protocol"]
    protocol = model.create_protocol_design(
        protocol_doc["args"]["arms"],
        folder=folder,
        name=protocol_doc.get("protocol_name") or f"{name} scenarios",
    )
    items["protocol"] = item_record(protocol)
    print(f"protocol     {protocol.url}")

    output_set = None
    if conversion["output_set"] is not None:
        output_set = model.create_simple_output_set(
            conversion["output_set"]["args"]["measures"],
            folder=folder,
            name=f"{name} observables",
        )
        items["output_set"] = item_record(output_set)
        print(f"output set   {output_set.url}")

    trial = model.create_trial(
        protocol=protocol,
        simple_output_set=output_set,
        folder=folder,
        name=f"{name} scenarios",
    )
    items["trial"] = item_record(trial)
    print(f"trial        {trial.url}")
    if not run:
        print("trial run    not started; pass --run")
        return 0

    result = trial.run_and_wait_until_completed(show_progress=False)
    state = result.get("status") if isinstance(result, dict) else str(result)
    items["trial"]["status"] = state
    print(f"trial run    {state}")
    return 0 if state == "completed" else 1


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #


def check(args: argparse.Namespace) -> int:
    try:
        from heta2jinko.check import CheckError, run_check
    except ImportError as exc:
        print(f"COULD NOT RUN\n  {exc}", file=sys.stderr)
        return 2

    directory = Path(args.dir)
    out = Path(args.out) if args.out else directory / CHECK
    try:
        result = run_check(
            directory,
            Path(args.platform),
            out,
            client=jinko_client(),
            series_ids=args.series or None,
            julia=args.julia,
        )
    except (CheckError, CouldNotRun) as exc:
        print(f"NOT RUN      {exc}")
        print("claim        Jinkō accepts and solves the model")
        return 2
    for arm, verdict in result["arms"].items():
        print(f"arm          {arm}: {verdict}")
    for cid, reason in result["not_compared"].items():
        print(f"not compared {cid}: {reason}")
    print(f"verdict      {result['verdict']}")
    print(f"comparison   {out / 'comparison.md'}")
    print(f"claim        {result['claim']}")
    return 0 if result["verdict"] == "PASS" else 1


# --------------------------------------------------------------------------- #


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = root.add_subparsers(dest="command", required=True)

    command = commands.add_parser("convert", help="convert offline and check")
    command.add_argument("export", help="table export of the Heta compiler")
    command.add_argument("--dir", required=True, help="run directory")
    command.add_argument("--t-max-days", type=float)
    command.add_argument("--t-step-days", type=float)
    command.add_argument("--model-name")
    command.add_argument(
        "--scenarios", help="HetaSimulator scenario table (scenarios.csv)"
    )
    command.add_argument(
        "--force", action="store_true", help="replace the files in --dir"
    )
    command.set_defaults(handler=convert)

    command = commands.add_parser("apply", help="create the items in Jinkō")
    command.add_argument("--dir", required=True, help="run directory of convert")
    command.add_argument("--folder", required=True, help="destination folder name")
    command.add_argument("--parent-folder", help="folder that holds --folder")
    command.add_argument("--create-folder", action="store_true")
    command.add_argument("--name", help="model name; defaults to the platform's")
    command.add_argument("--run", action="store_true", help="run the trial")
    command.set_defaults(handler=apply)

    command = commands.add_parser("check", help="compare with HetaSimulator.jl")
    command.add_argument("--dir", required=True, help="run directory of apply")
    command.add_argument("--platform", required=True, help="Heta platform folder")
    command.add_argument("--out", help="check folder; defaults to <dir>/check")
    command.add_argument("--series", nargs="*", help="series to compare")
    command.add_argument("--julia", help="Julia executable")
    command.set_defaults(handler=check)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
