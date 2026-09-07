#!/usr/bin/env python3
"""Upload a trial's population as Jinkō data tables, and overlay them.

Produces two tables from one solved trial:

* **individual** -- one row per patient, per arm, per time, unchanged. The raw
  material for inspecting single profiles.
* **summary** -- one row per arm and time holding the population median with
  wide bounds at the 2.5th and 97.5th percentiles. Point-value rows with wide
  bounds, which is the shape a trial visualisation overlays and a calibration
  objective scores against, so this is the one that must satisfy the schema
  exactly.

The summary table can then be attached to a trial visualisation's data overlay,
either an existing one or a new one created here.

``obsId`` must name a real trial output and ``armScope`` a real arm, or the
overlay resolves to nothing and the visualisation renders as though no data had
been supplied. Both are checked against the trial before anything is uploaded.

Dry-run by default. Pass --apply to create the project items.

The uploading, binding and overlay glue lives in
``nonmem2jinko.platform.data_tables``, which ships with the SDK. Two facts it
carries are the reason this is a library rather than a script: the trial, not
the visualisation, is what holds a data table; and binding one creates a new
trial snapshot that has never been launched, so the results the table was built
from stop resolving unless the trial is re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nonmem2jinko import platform
from nonmem2jinko.emit import data_tables as dt
from nonmem2jinko.platform.data_tables import (
    attach_overlay,
    bind_to_trial,
    dose_times,
    fetch_curves,
    previously_uploaded,
    upload,
    valid_for_fitness,
    validate_against_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a trial population as Jinkō data tables."
    )
    parser.add_argument("--trial-sid", required=True, help="Completed trial SID.")
    parser.add_argument(
        "--output",
        action="append",
        required=True,
        metavar="ID",
        help=(
            "Trial output id to summarise, for example cDrugCentral. "
            "Repeatable: a visualisation warns about any selected output the "
            "overlay has no rows for, so cover every output it displays."
        ),
    )
    parser.add_argument("--unit", default="", help="Unit recorded on each row.")
    parser.add_argument(
        "--time-points",
        type=int,
        default=-1,
        help=(
            "Time points per curve. -1 (default) chooses from the dosing: "
            "about ten for a single dose, up to forty for a multiple-dose "
            "profile. 0 keeps the solver's own grid, which is uniform and so "
            "spends most of its points on a flat elimination tail."
        ),
    )
    parser.add_argument("--name-prefix", default="", help="Prefix for the table names.")
    parser.add_argument(
        "--low", type=float, default=0.025, help="Lower wide-bound percentile."
    )
    parser.add_argument(
        "--high", type=float, default=0.975, help="Upper wide-bound percentile."
    )
    parser.add_argument(
        "--skip-individual",
        action="store_true",
        help="Upload only the summary table.",
    )
    parser.add_argument(
        "--max-individual-rows",
        type=int,
        default=20000,
        help=(
            "Skip the individual table above this many rows. It is one row per "
            "patient, per arm, per time, per output, and a trial with a fine "
            "solving grid reaches tens of thousands of rows per output -- past "
            "which the upload loses its connection rather than completing. Set "
            "0 to try regardless. The skip is always reported."
        ),
    )
    parser.add_argument(
        "--trial-visualization",
        help="Existing trial visualization SID to attach the summary table to.",
    )
    parser.add_argument(
        "--summary-table-sid",
        help=(
            "Attach an already-uploaded summary table instead of building and "
            "uploading a new one. Use this to wire an overlay without "
            "duplicating a table."
        ),
    )
    parser.add_argument(
        "--create-visualization",
        action="store_true",
        help="Create a new trial visualization carrying the overlay.",
    )
    parser.add_argument("--folder", help="Existing folder id or exact folder name.")
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--parent-folder",
        help=(
            "Folder to nest --folder inside, created alongside it. Used to "
            "keep one run's items together: a dated run folder holding one "
            "subfolder per model."
        ),
    )
    parser.add_argument(
        "--csv-out", help="Write both tables as CSV into this directory."
    )
    parser.add_argument(
        "--json-out",
        help="Write the created tables' and visualisation's SIDs here as JSON.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing CSV files instead of refusing.",
    )
    parser.add_argument(
        "--no-rerun",
        dest="rerun",
        action="store_false",
        help=(
            "Do not re-run the trial after binding the table. Binding creates "
            "a new trial snapshot that has never been launched, so the trial's "
            "results stop resolving; without a re-run it is left in that state."
        ),
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help=(
            "Ignore a same-trial --json-out ledger and upload new tables. "
            "Display-name matches are never reused because they do not prove "
            "the table came from this trial."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help=(
            "Request timeout in seconds. The individual table can run to tens "
            "of thousands of rows, which exceeds the SDK's 30 s default."
        ),
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create the project items."
    )
    return parser


def write_json(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def main() -> int:
    args = build_parser().parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    client = platform.try_client_from_env()
    if client is None:
        return 1
    client.set_timeout(args.timeout)
    trial = client.get_trial(args.trial_sid)

    entries = trial.output_ids()
    available = [entry["id"] for entry in entries]
    missing = [name for name in args.output if name not in available]
    if missing:
        print(
            f"not outputs of this trial: {', '.join(missing)}. An overlay on a "
            "missing output renders as though no data had been supplied.\n"
            f"Available: {', '.join(i for i in available if not i.startswith('__'))}",
            file=sys.stderr,
        )
        return 1

    summary = dt.TablePlan(columns=dt.POINT_VALUE_COLUMNS)
    individual_rows: list[dict] = []
    arms: list[str] = []

    administered = dose_times(trial)
    if administered:
        print(
            "dose times read from the model: "
            + ", ".join(f"{time:g}" for time in administered[:8])
            + (" ..." if len(administered) > 8 else "")
        )

    for name in args.output:
        unit = args.unit or next(
            (e.get("unit", "") for e in entries if e["id"] == name), ""
        )
        arms, curves = fetch_curves(trial, name)
        if not curves:
            print(f"the trial returned no patient curves for {name}", file=sys.stderr)
            return 1
        if args.time_points != 0:
            curves, grid = dt.thin(
                curves,
                doses=administered,
                budget=args.time_points if args.time_points > 0 else None,
            )
            print(
                f"{name}: reported on {len(grid)} time points, chosen to keep "
                "the administration times, the peak after each, and the tail"
            )
        one = dt.individual(curves, obs_id=name, unit=unit)
        individual_rows.extend(one.rows)
        part = dt.summarised(
            curves, obs_id=name, unit=unit, low=args.low, high=args.high
        )
        if not part.rows:
            print(
                f"the summary contains no usable rows for {name}; refusing to "
                "upload an incomplete overlay",
                file=sys.stderr,
            )
            return 1
        summary.rows.extend(part.rows)
        summary.notes.extend(f"`{name}`: {note}" for note in part.notes)

    individual = dt.TablePlan(columns=dt.INDIVIDUAL_COLUMNS, rows=individual_rows)
    individual.notes.append(
        f"{len(individual_rows)} rows across {len(args.output)} output(s): "
        f"{', '.join(args.output)}."
    )
    prefix = args.name_prefix or trial.name or "trial"
    table_prefix = f"{prefix} [{args.trial_sid}]"

    print(dt.describe(individual, summary))
    print()

    for plan, label in ((individual, "individual"), (summary, "summary")):
        problems = dt.validate(plan)
        if problems:
            print(f"{label} table fails the schema:", file=sys.stderr)
            for problem in problems[:10]:
                print(f"  {problem}", file=sys.stderr)
            return 1
    print("Both tables satisfy the point-value schema.")

    # armScope must name a real arm, or the overlay silently matches nothing.
    scopes = {row["armScope"] for row in summary.rows}
    unknown = scopes - set(arms)
    if unknown:
        print(
            f"armScope values not present in the trial: {', '.join(sorted(unknown))}",
            file=sys.stderr,
        )
        return 1
    print(f"armScope values all resolve: {', '.join(sorted(scopes))}")

    if args.csv_out:
        directory = Path(args.csv_out)
        targets = [
            directory / f"{prefix}-individual.csv",
            directory / f"{prefix}-summary.csv",
        ]
        existing = [path for path in targets if path.exists()]
        if existing and not args.overwrite:
            print(
                "refusing to overwrite: "
                + ", ".join(str(path) for path in existing)
                + "\nPass --overwrite to replace them.",
                file=sys.stderr,
            )
            return 1
        directory.mkdir(parents=True, exist_ok=True)
        for path, plan in zip(targets, (individual, summary)):
            path.write_text(plan.to_csv())
        print(f"CSV written to {directory}")

    if not args.apply:
        print("\nRun again with --apply to upload the tables.")
        return 0

    folder = platform.nested_folder(
        client, args.parent_folder, args.folder, create=args.create_folder
    )

    made: dict[str, object] = {"trial": args.trial_sid, "outputs": list(args.output)}
    # A dropped connection part-way through is common here: an individual table
    # runs to tens of thousands of rows. Recording each upload as it lands, and
    # reusing what a previous attempt already created, is what stops a retry
    # leaving two copies of the same table in the project.
    already = previously_uploaded(args.json_out, args.trial_sid)
    if already:
        made.update(already)
        print(
            "reusing from a previous attempt: "
            + ", ".join(sorted(already))
            + f" (delete {args.json_out} to upload fresh copies)"
        )

    def overlay_for(table):
        return attach_overlay(
            client,
            trial,
            table,
            folder=folder,
            visualization_sid=args.trial_visualization,
            outputs=list(args.output),
            high_percentile=args.high,
            name_prefix=args.name_prefix or None,
        )

    if args.summary_table_sid:
        existing = client.get_data_table(args.summary_table_sid)
        problems = validate_against_plan(existing, summary)
        if problems:
            print(
                "the supplied summary table does not match this trial:", file=sys.stderr
            )
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        if valid_for_fitness(existing) is not True:
            print(
                "the supplied summary table is not valid for a fitness function",
                file=sys.stderr,
            )
            return 1
        print(f"reusing     {existing.url}")
        made["summary"] = {"sid": existing.sid, "url": existing.url}
        try:
            bind_to_trial(
                client, trial, existing, rerun=args.rerun, timeout=args.timeout
            )
        except RuntimeError as error:
            made["error"] = str(error)
            write_json(args.json_out, made)
            print(error, file=sys.stderr)
            return 1
        made["bound_to_trial"] = True
        trial = client.get_trial(args.trial_sid)
        try:
            visualization = overlay_for(existing)
        except RuntimeError as error:
            made["error"] = str(error)
            write_json(args.json_out, made)
            print(error, file=sys.stderr)
            return 1
        if visualization is not None:
            made["visualization"] = {
                "sid": visualization.sid,
                "url": visualization.url,
            }
        write_json(args.json_out, made)
        return 0

    uploaded = {}
    individual_name = f"{table_prefix} — individual profiles"
    summary_name = f"{table_prefix} — population summary"

    skip_individual = args.skip_individual
    if (
        not skip_individual
        and args.max_individual_rows
        and len(individual) > args.max_individual_rows
    ):
        skip_individual = True
        print(
            f"individual  skipped: {len(individual)} rows exceeds "
            f"--max-individual-rows {args.max_individual_rows}. Individual "
            "profiles of a population this size are read in the trial "
            "visualisation rather than as a data table; pass "
            "--max-individual-rows 0 to upload anyway."
        )

    if not skip_individual:
        uploaded["individual"] = upload(
            client,
            recorded=already.get("individual"),
            name=individual_name,
            frame=individual.to_dataframe,
            rows=len(individual),
            description=(
                "One row per patient, per arm, per time for "
                f"{', '.join(args.output)}, unchanged from source trial "
                f"{args.trial_sid}."
            ),
            folder=folder,
            label="individual",
            force_new=args.force_new,
        )
        if already.get("individual") and not args.force_new:
            problems = validate_against_plan(uploaded["individual"], individual)
            if problems:
                print(
                    "the recorded individual table does not match this request:",
                    file=sys.stderr,
                )
                for problem in problems:
                    print(f"  {problem}", file=sys.stderr)
                return 1
        made["individual"] = {
            "sid": uploaded["individual"].sid,
            "url": uploaded["individual"].url,
        }
        write_json(args.json_out, made)

    uploaded["summary"] = upload(
        client,
        recorded=already.get("summary"),
        name=summary_name,
        frame=summary.to_dataframe,
        rows=len(summary),
        description=(
            f"Median of {', '.join(args.output)} with wide bounds at the "
            f"{args.low:.1%} and {args.high:.1%} population percentiles, per "
            f"arm and time, generated from source trial {args.trial_sid}."
        ),
        folder=folder,
        label="summary",
        force_new=args.force_new,
    )
    if already.get("summary") and not args.force_new:
        problems = validate_against_plan(uploaded["summary"], summary)
        if problems:
            print(
                "the recorded summary table does not match this request:",
                file=sys.stderr,
            )
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
    made["summary"] = {
        "sid": uploaded["summary"].sid,
        "url": uploaded["summary"].url,
    }
    write_json(args.json_out, made)

    # The trial carries the data tables. A visualisation overlay that names a
    # table the trial does not carry draws nothing.
    try:
        bind_to_trial(
            client, trial, uploaded["summary"], rerun=args.rerun, timeout=args.timeout
        )
    except RuntimeError as error:
        made["error"] = str(error)
        write_json(args.json_out, made)
        print(error, file=sys.stderr)
        return 1
    made["bound_to_trial"] = True
    write_json(args.json_out, made)
    trial = client.get_trial(args.trial_sid)

    # Only the summary is checked. Reading the flag means downloading the
    # table's whole content, and an individual table of tens of thousands of
    # rows takes longer to fetch back than it took to upload -- for a flag that
    # means nothing on a table nobody scores against.
    summary_table = uploaded.get("summary")
    if summary_table is not None:
        valid = valid_for_fitness(summary_table)
        print(f"summary     validForFitnessFunction = {valid}")
        if valid is not True:
            print(
                "  The summary table is meant to be scorable; a false value "
                "here means a calibration objective would refuse it.",
                file=sys.stderr,
            )
            made["error"] = "summary table is not valid for a fitness function"
            write_json(args.json_out, made)
            return 1

    if args.trial_visualization or args.create_visualization:
        try:
            visualization = overlay_for(uploaded["summary"])
        except RuntimeError as error:
            made["error"] = str(error)
            write_json(args.json_out, made)
            print(error, file=sys.stderr)
            return 1
        if visualization is not None:
            made["visualization"] = {
                "sid": visualization.sid,
                "url": visualization.url,
            }

    write_json(args.json_out, made)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
