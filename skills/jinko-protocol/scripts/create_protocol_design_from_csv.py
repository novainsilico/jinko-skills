#!/usr/bin/env python3
"""Create a Jinkō protocol design from CSV-defined scenario arms.

The CSV is posted as-is; the platform parses and validates it against its
own protocol design CSV schema.

Dry-run by default. Pass --apply to create the ProtocolDesign project item.
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
    if row_count == 0:
        raise ValueError("CSV must contain at least one arm row")
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
    parser = argparse.ArgumentParser(
        description="Create a Jinkō protocol design from CSV-defined arms."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="CSV path matching the platform's protocol design CSV schema.",
    )
    parser.add_argument("--name", default="sdk-csv-protocol")
    parser.add_argument(
        "--description", default="Protocol design created from SDK CSV upload."
    )
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new protocol design.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the protocol design."
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

    print(f"CSV columns: {', '.join(header)}")
    print(f"CSV arms: {row_count}")

    if not args.apply:
        print(f"Would create protocol design named {args.name!r}.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to create the protocol design.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        protocol = client.create_protocol_design_from_csv(
            csv_file_path=csv_path,
            folder=folder,
            name=args.name,
            description=args.description,
        )
        print(f"Created protocol design {protocol.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(protocol, "url", None):
            print(protocol.url)
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Protocol design creation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
