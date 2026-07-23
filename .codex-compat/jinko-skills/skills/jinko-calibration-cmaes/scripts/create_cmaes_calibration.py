#!/usr/bin/env python3
"""Create a Jinkō CMA-ES calibration.

Dry-run by default. Pass --apply to create the project item. Does not run it
(see run_calibration.py). Carries no business-logic defaults: every
CalibrationOptions value is passed through as given, or omitted (SDK/API
default applies).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


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


def valid_for_fitness_from_content(content: Any) -> bool | None:
    if isinstance(content, dict):
        public = (content.get("metadata") or {}).get("public") or {}
        return public.get("validForFitnessFunction")
    metadata = getattr(content, "metadata", None)
    public = getattr(metadata, "public", None)
    return getattr(public, "validForFitnessFunction", None)


def ensure_data_tables_can_attach(data_tables: list[Any]) -> None:
    invalid = [
        dt.sid
        for dt in data_tables
        if valid_for_fitness_from_content(dt.content()) is False
    ]
    if invalid:
        raise RuntimeError(
            "Data tables attached through dataTableDesigns must report "
            "metadata.public.validForFitnessFunction=True: " + ", ".join(invalid)
        )


def parse_parameter(spec: str) -> dict[str, Any]:
    parts = spec.split(":")
    if len(parts) < 5:
        raise ValueError(f"--parameter {spec!r} must be id:mean:std:min:max[:log]")
    id_, mean, std, min_bound, max_bound, *rest = parts
    param: dict[str, Any] = {
        "id": id_,
        "mean": float(mean),
        "std": float(std),
        "min_bound": float(min_bound),
        "max_bound": float(max_bound),
    }
    if rest and rest[0] == "log":
        param["log_transform"] = True
    return param


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Jinkō CMA-ES calibration.")
    parser.add_argument("--model-sid", required=True)
    parser.add_argument("--data-table-sid", action="append", default=[])
    parser.add_argument(
        "--parameter",
        action="append",
        default=[],
        required=True,
        help="id:mean:std:min:max[:log], may be repeated",
    )
    parser.add_argument("--protocol-design-sid")
    parser.add_argument(
        "--scoring-sid", help="Advanced output set (ScoringDesign) SID."
    )
    parser.add_argument(
        "--simple-output-set-sid", help="Simple output set (MeasureDesign) SID."
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--threshold-weighted-score", type=float)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--population-size", type=int)
    parser.add_argument("--name", default="sdk-calibration")
    parser.add_argument(
        "--description", default="Calibration created with the Jinkō SDK."
    )
    parser.add_argument("--folder", help="Existing folder id or exact folder name.")
    parser.add_argument("--create-folder", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    try:
        parameters = [parse_parameter(spec) for spec in args.parameter]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Model: {args.model_sid}")
    print(f"Data tables: {', '.join(args.data_table_sid) or '<none>'}")
    print(f"Protocol: {args.protocol_design_sid or '<none>'}")
    print(f"Advanced scoring: {args.scoring_sid or '<none>'}")
    print(f"Simple output set: {args.simple_output_set_sid or '<none>'}")
    print(f"Parameters: {json.dumps(parameters)}")
    print(
        "CalibrationOptions: "
        f"seed={args.seed}, thresholdWeightedScore={args.threshold_weighted_score}, "
        f"numberOfIterations={args.iterations}, populationSize={args.population_size} "
        "(unset values fall through to the SDK/API default)"
    )
    print(f"Folder: {args.folder or '<none>'}")

    if not args.apply:
        print(f"Would create calibration named {args.name!r}.")
        print("Run again with --apply to create the project item.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        model = client.get_model(args.model_sid)
        data_tables = [client.get_data_table(sid) for sid in args.data_table_sid]
        ensure_data_tables_can_attach(data_tables)
        protocol = (
            client.get_protocol_design(args.protocol_design_sid)
            if args.protocol_design_sid
            else None
        )
        scoring = (
            client.get_advanced_output_set(args.scoring_sid)
            if args.scoring_sid
            else None
        )
        simple_output_set = (
            client.get_simple_output_set(args.simple_output_set_sid)
            if args.simple_output_set_sid
            else None
        )

        calibration = model.create_calibration(
            data_tables=data_tables,
            parameters=parameters,
            protocol=protocol,
            advanced_output_set=scoring,
            simple_output_set=simple_output_set,
            folder=folder,
            name=args.name,
            description=args.description,
            calib_seed=args.seed,
            calib_threshold_weighted_score=args.threshold_weighted_score,
            calib_number_of_iterations=args.iterations,
            calib_population_size=args.population_size,
        )
        print(f"Created calibration {calibration.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        print(calibration.url)
        return 0
    except (ValueError, RuntimeError, JinkoError) as exc:
        print(f"Calibration creation failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep diagnostics concise
        print(f"Calibration creation failed unexpectedly: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
