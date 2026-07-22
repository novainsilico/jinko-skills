#!/usr/bin/env python3
"""Create a Jinkō simple output set (measure design) from a model.

Dry-run by default. Pass --apply to create the MeasureDesign project item.
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Jinkō simple output set.")
    parser.add_argument(
        "--model-sid", required=True, help="Model SID, for example cm-..."
    )
    parser.add_argument(
        "--output-id",
        action="append",
        dest="output_ids",
        help="Model output id to measure. Repeat for multiple ids. "
        "Defaults to model.time_dependent_ids() when omitted.",
    )
    parser.add_argument("--name", default="sdk-simple-output-set")
    parser.add_argument(
        "--description", default="Simple output set created with the Jinkō SDK."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the simple output set."
    )
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new output set.",
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
        if args.output_ids:
            print(f"Would measure output ids: {', '.join(args.output_ids)}")
        else:
            print(
                "No --output-id given: would call model.time_dependent_ids() "
                "to discover output ids (requires --apply and a live model)."
            )
        print(f"Would create simple output set named {args.name!r}.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to create the simple output set.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        model = client.get_model(args.model_sid)
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        output_ids = args.output_ids or model.time_dependent_ids()

        output_set = client.create_simple_output_set(
            model,
            output_ids,
            folder=folder,
            name=args.name,
            description=args.description,
        )

        print(f"Created simple output set {output_set.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(output_set, "url", None):
            print(output_set.url)
        print(f"Measures: {len(output_set.measures)}")
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
