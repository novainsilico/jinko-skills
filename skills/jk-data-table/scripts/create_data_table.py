#!/usr/bin/env python3
"""Create a Jinkō data table from CSV, SQLite, or pandas DataFrame.

Dry-run by default. Pass --apply to create the DataTable project item.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


POINT_REQUIRED = {"obsId", "time", "value"}
RANGE_REQUIRED = {"obsId", "time", "narrowRangeLowBound", "narrowRangeHighBound"}


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


def summarize_csv(path: Path) -> tuple[list[str], int, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        row_count = sum(1 for _ in reader)
    column_set = set(columns)
    if POINT_REQUIRED.issubset(column_set):
        row_type = "point-value"
    elif RANGE_REQUIRED.issubset(column_set):
        row_type = "range"
    else:
        raise ValueError(
            "CSV must include either obsId,time,value or "
            "obsId,time,narrowRangeLowBound,narrowRangeHighBound"
        )
    if row_count == 0:
        raise ValueError("CSV must contain at least one data row")
    return columns, row_count, row_type


def valid_for_fitness_from_content(content: Any) -> bool | None:
    if isinstance(content, dict):
        public = (content.get("metadata") or {}).get("public") or {}
        return public.get("validForFitnessFunction")

    metadata = getattr(content, "metadata", None)
    public = getattr(metadata, "public", None)
    return getattr(public, "validForFitnessFunction", None)


def print_fitness_status(table: Any) -> None:
    try:
        content = table.content()
        valid = valid_for_fitness_from_content(content)
    except Exception as exc:  # noqa: BLE001 - diagnostic helper should stay concise
        print(f"Could not read data-table metadata: {exc}", file=sys.stderr)
        return

    if valid is None:
        print("validForFitnessFunction: <not reported>")
    else:
        print(f"validForFitnessFunction: {valid}")


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
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    source = Path(args.source)
    if not source.exists():
        print(f"Source file does not exist: {source}", file=sys.stderr)
        return 1

    if args.method in {"csv", "dataframe"}:
        try:
            columns, row_count, row_type = summarize_csv(source)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"CSV rows: {row_count}")
        print(f"CSV row type: {row_type}")
        print(f"CSV columns: {', '.join(columns)}")
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
        print_fitness_status(table)
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
