#!/usr/bin/env python3
"""Convert a NONMEM control stream into a Jinkō computational model.

Reads a control stream (.mod/.ctl/.cfl) or an output listing (.lst), optionally
with its .ext final estimates and its data set, and emits the equivalent Jinkō
model. Prints a conversion report naming every inferred unit, every renamed
symbol and every construct that could not be converted.

Dry-run by default. Pass --apply to create the model in the Jinkō project.

The conversion itself lives in ``nonmem2jinko``, which ships with the SDK. This
file is the command line over it and nothing else: no translation rule belongs
here, because a rule expressed in a script is a rule the test suite does not
reach.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nonmem2jinko import platform
from nonmem2jinko.convert import ConversionError, Options, convert
from nonmem2jinko.emit import apply as apply_module


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
        description="Convert a NONMEM control stream into a Jinkō model."
    )
    parser.add_argument(
        "control_stream", help="Path to the .mod, .ctl, .cfl or .lst file."
    )
    parser.add_argument("--ext", help="Path to the .ext final estimates file.")
    parser.add_argument("--data", help="Path to the NONMEM data set.")
    parser.add_argument(
        "--drug",
        default="Drug",
        help="Drug name used in state names, for example Warfarin.",
    )
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
        "--vpop-mode",
        choices=["etas", "parameters"],
        default="etas",
        help="Represent the target distribution on random effects or parameters.",
    )
    parser.add_argument("--report", help="Write the conversion report to this file.")
    parser.add_argument("--script", help="Write a runnable creation script here.")
    parser.add_argument("--json", help="Write the emitted plan as JSON here.")
    parser.add_argument(
        "--json-out", help="Write the created model's SID and URL as JSON here."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing --report, --script, --json, or --json-out files.",
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
        help="Apply even when the model reports blocking conversion errors.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create the model in Jinkō."
    )
    return parser


def plan_as_json(plan) -> str:
    return (
        json.dumps(
            {
                "name": plan.name,
                "description": plan.description,
                "unitCheck": plan.unit_check,
                "components": [
                    {
                        "kind": c.kind,
                        "id": c.id,
                        "arguments": c.arguments,
                        "description": c.description,
                        "tags": list(c.tags),
                        "origin": c.origin,
                    }
                    for c in plan.components
                ],
                "outputs": plan.outputs,
                "vpopInputs": plan.vpop_inputs,
                "protocolInputs": plan.protocol_inputs,
                "issues": plan.issues,
            },
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )


def main() -> int:
    args = build_parser().parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1
    outputs = [
        Path(path)
        for path in (args.report, args.script, args.json, args.json_out)
        if path
    ]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.overwrite:
        print(
            "refusing to overwrite: "
            + ", ".join(str(path) for path in existing)
            + "\nPass --overwrite to replace them.",
            file=sys.stderr,
        )
        return 1

    try:
        conversion = convert(
            args.control_stream,
            ext=args.ext,
            data=args.data,
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
            ),
            trial=False,
        )
    except ConversionError as error:
        print(error, file=sys.stderr)
        return 1

    for note in conversion.notes:
        print(f"note: {note}", file=sys.stderr)
    print(conversion.report)

    if args.report:
        Path(args.report).write_text(conversion.report)
    if args.script:
        Path(args.script).write_text(
            apply_module.to_script(conversion.plan, folder=args.folder)
        )
    if args.json:
        Path(args.json).write_text(plan_as_json(conversion.plan))

    if conversion.blocking_issues and not args.allow_issues:
        print("\nThis model cannot be converted faithfully:", file=sys.stderr)
        for issue in conversion.blocking_issues:
            print(f"  {issue}", file=sys.stderr)
        print(
            "Fix the control stream, or pass --allow-issues to convert anyway.",
            file=sys.stderr,
        )
        return 1

    if not args.apply:
        print("\nRun again with --apply to create the model in Jinkō.")
        return 0

    client = platform.try_client_from_env()
    if client is None:
        return 1
    folder = platform.nested_folder(
        client, args.parent_folder, args.folder, create=args.create_folder
    )

    try:
        model, result = platform.create_model(client, conversion, folder=folder)
    except platform.ModelRejected:
        return 1
    if args.json_out:
        target = Path(args.json_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"model": {"sid": model.sid, "url": model.url, "name": model.name}},
                indent=2,
            )
            + "\n"
        )
    print(f"\nCreated {len(result.created)} components")
    print(f"Model: {model.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
