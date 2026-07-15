#!/usr/bin/env python3
"""Create a minimal Jinkō model through high-level SDK component methods.

Dry-run by default. Pass --apply to create or edit Jinkō project items.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


PREFERRED_UNIT_CHECK = "UnitCheckAndConvertAllSpeciesToExtentUnits"


def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def load_sdk():
    try:
        from jinko import JinkoClient
        from jinko.exceptions import JinkoError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def print_plan(name: str) -> None:
    print(f"Would create empty model: {name}")
    print(f"Would set unitCheck: {PREFERRED_UNIT_CHECK}")
    print(
        "Would batch-create: compartment, parameters, categorical parameter, species, dosing event, ODE, baseline check"
    )
    print("Run again with --apply to create the model.")


def resolve_folder(client: Any, folder_ref: str | None, *, create: bool) -> Any | None:
    if folder_ref is None:
        return None

    folder = client.get_folder(folder_ref)
    if folder is not None:
        return folder

    folder = client.get_folder_by_name(folder_ref, exact_match_only=True)
    if folder is not None:
        return folder

    if not create:
        raise ValueError(
            f"Folder {folder_ref!r} was not found. Pass --create-folder to create it."
        )

    return client.create_folder(folder_ref)


def report_diagnostics(model: Any) -> bool:
    diagnostics = model.diagnostics.errors()
    if not diagnostics:
        return False

    print("Model diagnostics contain errors:", file=sys.stderr)
    for entry in diagnostics:
        diagnostic = entry.diagnostic
        print(
            f"- {entry.component.id}: {diagnostic.code} ({diagnostic.severity}) {diagnostic.message}",
            file=sys.stderr,
        )
    return True


def report_simple_solve(model: Any, timeseries_id: str) -> bool:
    result = model.simple_solve(timeseries_ids=[timeseries_id])
    if result.error:
        print(f"simple_solve failed: {result.error}", file=sys.stderr)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a minimal SDK-authored Jinkō model."
    )
    parser.add_argument(
        "--name", default="sdk-minimal-model", help="Name for the new model."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create and edit the model."
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip diagnostics and simple_solve after creation.",
    )
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new model.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    if not args.apply:
        print_plan(args.name)
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        model = client.create_empty_model(
            args.name,
            folder=folder,
            description="Minimal SDK-created model with intentional unit checking.",
        )
        model = model.edit_solving_options(
            {
                "unitCheck": PREFERRED_UNIT_CHECK,
                "extentUnits": "mol",
            },
            version="set unit policy",
        )

        with model.components.batch(version="minimal model components") as batch:
            batch.create_compartment(id="central", volume=1.0, unit="L", constant=True)
            batch.create_parameter(id="Dose", formula=1.0, unit="mol", constant=True)
            batch.create_parameter(id="k_elim", formula=0.1, unit="1/h", constant=True)
            batch.create_categorical_parameter(
                id="route",
                level="iv",
                available_levels=["iv", "po"],
            )
            batch.create_parameter(
                id="bioavailability",
                formula="case route of { iv -> 1; po -> 0.5; _ -> 1 }",
                unit="dimensionless",
                constant=False,
            )
            batch.create_species(
                id="Drug",
                compartment="central",
                initial_condition=0.0,
                unit="mol",
            )
            batch.create_event(
                id="dose_start",
                updates={"Drug": "Dose * bioavailability"},
                time_trigger_first_time="0 * u(h)",
            )
            batch.create_ode(
                id="drug_elimination",
                left_side="Drug",
                right_side="-k_elim * Drug",
            )
            batch.create_baseline_check(id="valid_dose", condition="Dose >= 0")

        model = client.get_model(model.sid)
        failed = False
        if not args.skip_validation:
            failed = report_diagnostics(model) or report_simple_solve(model, "Drug")

        print(f"Created model {model.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(model, "url", None):
            print(model.url)
        return 1 if failed else 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
