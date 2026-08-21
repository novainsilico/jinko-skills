#!/usr/bin/env python3
"""Create a Jinkō data table from CSV, SQLite, or pandas DataFrame.

Dry-run by default. Pass --apply to create the DataTable project item.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


POINT_REQUIRED = {"obsId", "time", "value"}
RANGE_REQUIRED = {"obsId", "time", "narrowRangeLowBound", "narrowRangeHighBound"}
NUMERIC_COLUMNS = {
    "value",
    "narrowRangeLowBound",
    "narrowRangeHighBound",
    "wideRangeLowBound",
    "wideRangeHighBound",
    "weight",
}
ISO_DURATION = re.compile(
    r"^P(?=.+)(?:\d+(?:\.\d+)?[YMWD])*(?:T(?:\d+(?:\.\d+)?[HMS])*)?$"
)


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


def summarize_csv(
    path: Path,
    *,
    allowed_obs_ids: set[str] | None = None,
    require_experiment_ref: bool = False,
    require_unit: bool = False,
) -> tuple[list[str], int, str, set[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = list(reader)
    if len(columns) != len(set(columns)):
        raise ValueError("CSV column names must be unique")
    column_set = set(columns)
    has_point_shape = POINT_REQUIRED.issubset(column_set)
    has_range_shape = RANGE_REQUIRED.issubset(column_set)
    if has_point_shape and has_range_shape:
        raise ValueError("CSV cannot mix point-value and range columns")
    if has_point_shape:
        row_type = "point-value"
        required = POINT_REQUIRED
    elif has_range_shape:
        row_type = "range"
        required = RANGE_REQUIRED
    else:
        raise ValueError(
            "CSV must include either obsId,time,value or "
            "obsId,time,narrowRangeLowBound,narrowRangeHighBound"
        )
    if not rows:
        raise ValueError("CSV must contain at least one data row")

    obs_ids = set()
    for line_number, row in enumerate(rows, start=2):
        missing = sorted(key for key in required if not str(row.get(key) or "").strip())
        if missing:
            raise ValueError(
                f"CSV line {line_number} is missing required values: "
                + ", ".join(missing)
            )
        obs_id = str(row["obsId"]).strip()
        obs_ids.add(obs_id)
        time = str(row["time"]).strip()
        if not ISO_DURATION.fullmatch(time) or time.endswith("T"):
            raise ValueError(
                f"CSV line {line_number} has invalid ISO-8601 time {time!r}"
            )
        for column in NUMERIC_COLUMNS.intersection(column_set):
            raw = str(row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(
                    f"CSV line {line_number} has non-numeric {column}={raw!r}"
                ) from exc
            if not math.isfinite(value):
                raise ValueError(f"CSV line {line_number} requires finite {column}")
            if column == "weight" and value < 0:
                raise ValueError(f"CSV line {line_number} has negative weight")
        if row_type == "range":
            narrow_low = float(row["narrowRangeLowBound"])
            narrow_high = float(row["narrowRangeHighBound"])
            if narrow_low >= narrow_high:
                raise ValueError(
                    f"CSV line {line_number} requires narrowRangeLowBound "
                    "< narrowRangeHighBound"
                )
            wide_low = str(row.get("wideRangeLowBound") or "").strip()
            wide_high = str(row.get("wideRangeHighBound") or "").strip()
            if bool(wide_low) != bool(wide_high):
                raise ValueError(
                    f"CSV line {line_number} must provide both wide range bounds"
                )
            if wide_low and not (
                float(wide_low) < narrow_low < narrow_high < float(wide_high)
            ):
                raise ValueError(
                    f"CSV line {line_number} wide bounds must strictly contain "
                    "the narrow range"
                )
        else:
            point_value = float(row["value"])
            wide_low = str(row.get("wideRangeLowBound") or "").strip()
            wide_high = str(row.get("wideRangeHighBound") or "").strip()
            if bool(wide_low) != bool(wide_high):
                raise ValueError(
                    f"CSV line {line_number} must provide both wide range bounds"
                )
            if wide_low and not float(wide_low) < point_value < float(wide_high):
                raise ValueError(
                    f"CSV line {line_number} wide bounds must strictly contain value"
                )
        if require_experiment_ref and not str(row.get("experimentRef") or "").strip():
            raise ValueError(f"CSV line {line_number} requires experimentRef")
        if require_unit and not str(row.get("unit") or "").strip():
            raise ValueError(f"CSV line {line_number} requires unit")

    if allowed_obs_ids is not None:
        unexpected = sorted(obs_ids - allowed_obs_ids)
        if unexpected:
            raise ValueError(
                "CSV contains unexpected obsId values: " + ", ".join(unexpected)
            )
    return columns, len(rows), row_type, obs_ids


def valid_for_fitness_from_content(content: Any) -> bool | None:
    if isinstance(content, dict):
        public = (content.get("metadata") or {}).get("public") or {}
        return public.get("validForFitnessFunction")

    metadata = getattr(content, "metadata", None)
    public = getattr(metadata, "public", None)
    return getattr(public, "validForFitnessFunction", None)


def print_fitness_status(table: Any) -> bool | None:
    try:
        content = table.content()
        valid = valid_for_fitness_from_content(content)
    except Exception as exc:  # noqa: BLE001 - diagnostic helper should stay concise
        print(f"Could not read data-table metadata: {exc}", file=sys.stderr)
        return None

    if valid is None:
        print("validForFitnessFunction: <not reported>")
    else:
        print(f"validForFitnessFunction: {valid}")
    return valid


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Jinkō data table.")
    parser.add_argument("--source", required=True, help="CSV or SQLite source path.")
    parser.add_argument(
        "--method", choices=["csv", "sqlite", "dataframe"], default="csv"
    )
    parser.add_argument("--name", default="sdk-data-table")
    parser.add_argument(
        "--description", default="Data table created with the Jinkō SDK."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the DataTable."
    )
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new data table.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--allowed-obs-id",
        action="append",
        help="Allowed obsId value. May be repeated; rejects any other obsId.",
    )
    parser.add_argument(
        "--require-experiment-ref",
        action="store_true",
        help="Require a non-empty experimentRef on every CSV row.",
    )
    parser.add_argument(
        "--require-unit",
        action="store_true",
        help="Require a non-empty unit on every CSV row.",
    )
    parser.add_argument(
        "--require-fitness",
        action="store_true",
        help="After creation, fail unless validForFitnessFunction is explicitly true.",
    )
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    source = Path(args.source)
    if not source.exists():
        print(f"Source file does not exist: {source}", file=sys.stderr)
        return 1

    if args.method == "sqlite" and (
        args.allowed_obs_id or args.require_experiment_ref or args.require_unit
    ):
        print(
            "--allowed-obs-id, --require-experiment-ref, and --require-unit "
            "require CSV or dataframe input",
            file=sys.stderr,
        )
        return 1

    if args.method in {"csv", "dataframe"}:
        try:
            columns, row_count, row_type, obs_ids = summarize_csv(
                source,
                allowed_obs_ids=set(args.allowed_obs_id)
                if args.allowed_obs_id
                else None,
                require_experiment_ref=args.require_experiment_ref,
                require_unit=args.require_unit,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"CSV rows: {row_count}")
        print(f"CSV row type: {row_type}")
        print(f"CSV columns: {', '.join(columns)}")
        print(f"CSV obsIds: {', '.join(sorted(obs_ids))}")
    else:
        print(f"SQLite bytes: {source.stat().st_size}")

    if not args.apply:
        print(f"Would create DataTable named {args.name!r} using {args.method} method.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to create the data table.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        if args.method == "csv":
            table = client.create_data_table_from_csv(
                csv_file_path=str(source),
                folder=folder,
                name=args.name,
                description=args.description,
            )
        elif args.method == "sqlite":
            table = client.create_data_table_from_sqlite(
                sqlite_file_path=str(source),
                folder=folder,
                name=args.name,
                description=args.description,
            )
        else:
            try:
                import pandas as pd
            except ImportError:
                print(
                    "DataFrame method requires pandas: pip install pandas",
                    file=sys.stderr,
                )
                return 1
            table = client.create_data_table_from_dataframe(
                pd.read_csv(source),
                folder=folder,
                name=args.name,
                description=args.description,
            )

        print(f"Created DataTable {table.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(table, "url", None):
            print(table.url)
        fitness = print_fitness_status(table)
        if args.require_fitness and fitness is not True:
            print(
                "Created DataTable is not confirmed valid for a fitness function",
                file=sys.stderr,
            )
            return 3
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
