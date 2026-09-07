#!/usr/bin/env python3
"""Convert a whole NONMEM run into a Jinkō trial.

Builds the computational model, the virtual population, the protocol design and
the output set from one NONMEM run, then optionally binds and runs the trial.
Prints a conversion report naming every inference and every construct that
could not be converted.

Dry-run by default. Pass --apply to create the project items, and --run to
execute the trial.

The conversion and the item creation both live in ``nonmem2jinko``, which ships
with the SDK: ``nonmem2jinko.convert`` reads the run, and
``nonmem2jinko.platform`` creates what it describes. This file is the command
line over them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nonmem2jinko import platform
from nonmem2jinko.convert import ConversionError, Options, convert


def pairs(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        key, separator, value = item.partition("=")
        if not separator or not key or not value:
            raise ConversionError(f"expected KEY=VALUE, got {item!r}")
        parsed[key] = value
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a NONMEM run into a Jinko trial."
    )
    parser.add_argument(
        "control_stream", help="Path to the .mod, .ctl, .cfl or .lst file."
    )
    parser.add_argument("--ext", help="Path to the .ext final estimates file.")
    parser.add_argument("--phi", help="Path to the .phi individual estimates file.")
    parser.add_argument("--data", help="Path to the NONMEM data set.")
    parser.add_argument("--drug", default="Drug", help="Drug name used in state names.")
    parser.add_argument("--time-unit", default="h", help="Time unit, default h.")
    parser.add_argument("--amount-unit", default="mg", help="Amount unit, default mg.")
    parser.add_argument("--volume-unit", default="L", help="Volume unit, default L.")
    parser.add_argument(
        "--rename",
        action="append",
        default=[],
        metavar="NONMEM=jinkoId",
        help="Override one symbol's generated name. Repeatable.",
    )
    parser.add_argument(
        "--unit",
        action="append",
        default=[],
        metavar="SYMBOL=unit",
        help="Override one component's inferred unit. Repeatable.",
    )
    parser.add_argument(
        "--state-unit",
        action="append",
        default=[],
        metavar="N=unit",
        help=(
            "Declare what compartment N holds. Every compartment is an amount "
            "by default, which is what PREDPP means by A(n). A general ODE "
            "model need not agree -- a turnover system holds a concentration "
            "in one compartment and a rate in another, and NONMEM does not "
            "care because units there are the modeller's business. Repeatable."
        ),
    )
    parser.add_argument(
        "--population",
        choices=["design", "phi", "sampled"],
        default="design",
        help=(
            "design: a Jinko vpop design (default). "
            "phi: replay the fitted subjects from the .phi file. "
            "sampled: draw from OMEGA's full covariance; the finite sample has "
            "sampling error."
        ),
    )
    parser.add_argument(
        "--vpop-mode",
        choices=["etas", "parameters"],
        default="etas",
        help=(
            "etas: represent OMEGA through random-effect marginals and "
            "correlations (default). parameters: put marginals on the derived "
            "parameters."
        ),
    )
    parser.add_argument(
        "--dosing",
        choices=["auto", "arms", "per-patient"],
        default="auto",
        help=(
            "arms: one arm per distinct dosing history. per-patient: every "
            "patient carries its own dose times and amounts in the vpop, for a "
            "data set where each subject has an individualised schedule. auto "
            "(default): arms when the data set has an arm structure, "
            "per-patient when it does not."
        ),
    )
    parser.add_argument("--size", type=int, default=100, help="Population size.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    parser.add_argument(
        "--eps-clones",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Expand each patient into N clones differing only in their residual "
            "error draw, giving a per-patient uncertainty cone. Requires "
            "--population phi or sampled."
        ),
    )
    parser.add_argument("--report", help="Write the conversion report here.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing --report file.",
    )
    parser.add_argument(
        "--json-out",
        help=(
            "Write the created items' SIDs and URLs here as JSON. Chaining the "
            "next step needs the SIDs, and scraping them back out of this "
            "script's prose is how a pipeline breaks silently."
        ),
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
        "--allow-issues",
        action="store_true",
        help="Apply even when the conversion reports blocking errors.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create the project items."
    )
    parser.add_argument(
        "--run", action="store_true", help="Run the trial after creating it."
    )
    parser.add_argument(
        "--delete-on-error",
        action="store_true",
        help=(
            "Delete the created model if the platform reports diagnostic "
            "errors. Off by default: a rejected model is usually the most "
            "useful thing to look at, and the diagnostics are readable in the "
            "UI. Turn it on for an unattended run, where the alternative is a "
            "project filling up with broken models."
        ),
    )
    parser.add_argument(
        "--timeout", type=int, default=1800, help="Seconds to wait for the trial."
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
    if args.run and not args.apply:
        print("--run requires --apply", file=sys.stderr)
        return 1
    if args.report and Path(args.report).exists() and not args.overwrite:
        print(
            f"refusing to overwrite {args.report}. Pass --overwrite to replace it.",
            file=sys.stderr,
        )
        return 1

    try:
        conversion = convert(
            args.control_stream,
            ext=args.ext,
            data=args.data,
            phi=args.phi,
            options=Options(
                drug=args.drug,
                time_unit=args.time_unit,
                amount_unit=args.amount_unit,
                volume_unit=args.volume_unit,
                renames=pairs(args.rename),
                unit_overrides=pairs(args.unit),
                state_units={
                    int(key): value for key, value in pairs(args.state_unit).items()
                },
                vpop_mode=args.vpop_mode,
                population=args.population,
                dosing=args.dosing,
                size=args.size,
                seed=args.seed,
                eps_clones=args.eps_clones,
            ),
        )
    except ConversionError as error:
        print(error, file=sys.stderr)
        return 1

    for note in conversion.notes:
        print(f"note: {note}", file=sys.stderr)
    print(conversion.report)
    if args.report:
        Path(args.report).write_text(conversion.report)

    if conversion.blocking_issues and not args.allow_issues:
        print("\nThis run cannot be converted faithfully:", file=sys.stderr)
        for issue in conversion.blocking_issues:
            print(f"  {issue}", file=sys.stderr)
        print("Pass --allow-issues to convert anyway.", file=sys.stderr)
        return 1

    if not args.apply:
        print("\nRun again with --apply to create the project items.")
        return 0

    client = platform.try_client_from_env()
    if client is None:
        return 1
    folder = platform.nested_folder(
        client, args.parent_folder, args.folder, create=args.create_folder
    )

    print()
    try:
        created = platform.create_trial(
            client,
            conversion,
            folder=folder,
            delete_on_error=args.delete_on_error,
        )
    except platform.ModelRejected:
        if not args.delete_on_error:
            print(
                "Pass --delete-on-error to remove a rejected model instead of "
                "leaving it.",
                file=sys.stderr,
            )
        return 1

    made = created.record()
    made["name"] = conversion.plan.name
    made["source"] = conversion.source
    made["outputs"] = list(conversion.plan.outputs)
    made["arms"] = [arm.name for arm in conversion.protocol.arms]
    made["population_size"] = conversion.population_size
    write_json(args.json_out, made)

    problems = platform.sanity_problems(created.trial.sanity())
    if problems:
        print("\nTrial sanity reported problems:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        if not args.allow_issues:
            return 1

    if not args.run:
        print("\nRun again with --run to execute the trial.")
        return 0

    print()
    summary = platform.run_trial(created.trial, timeout=args.timeout)
    made["completed"] = True
    made["result_arms"] = summary.get("arms")
    write_json(args.json_out, made)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
