#!/usr/bin/env python3
"""Create a Jinkō Vpop from CSV or a pandas DataFrame.

Dry-run by default. Pass --apply to create the Vpop project item.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

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


def read_csv_summary(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV is empty") from None
        row_count = sum(1 for _ in reader)
    if not header or header[0] != "patientIndex":
        raise ValueError("CSV first column should be patientIndex")
    if row_count == 0:
        raise ValueError("CSV must contain at least one patient row")
    return header, row_count


def resolve_folder(client, folder_ref: str | None, *, create: bool):
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
    parser = argparse.ArgumentParser(description="Create a Jinkō Vpop from CSV.")
    parser.add_argument(
        "--csv",
        required=True,
        help="CSV path with patientIndex and descriptor columns.",
    )
    parser.add_argument("--name", default="sdk-toy-vpop")
    parser.add_argument("--description", default="Vpop created from SDK CSV upload.")
    parser.add_argument("--method", choices=["csv", "dataframe"], default="csv")
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new Vpop.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the Vpop."
    )
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    csv_path = Path(args.csv)
    try:
        header, row_count = read_csv_summary(csv_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    descriptors = header[1:]
    print(f"CSV patients: {row_count}")
    print(f"CSV descriptors: {', '.join(descriptors) if descriptors else '<none>'}")

    if not args.apply:
        print(f"Would create Vpop named {args.name!r} using {args.method} method.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to upload the Vpop.")
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
            vpop = client.create_vpop_from_csv(
                csv_file_path=str(csv_path),
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
            df = pd.read_csv(csv_path)
            vpop = client.create_vpop_from_dataframe(
                df,
                folder=folder,
                name=args.name,
                description=args.description,
            )
        print(f"Created Vpop {vpop.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(vpop, "url", None):
            print(vpop.url)
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
