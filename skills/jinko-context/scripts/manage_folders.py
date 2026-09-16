#!/usr/bin/env python3
"""List a Jinkō project's folders, render its tree, and explicitly create a folder."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jinko import JinkoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create",
        metavar="NAME",
        help="Create a folder with this name after the read-only folder inventory.",
    )
    parser.add_argument(
        "--parent-id",
        metavar="SID",
        help="Optional parent folder SID for --create.",
    )
    args = parser.parse_args()
    if args.parent_id and not args.create:
        parser.error("--parent-id requires --create")
    return args


def print_folder_inventory(client: "JinkoClient") -> None:
    folders = client.list_folders(recursive=True)
    print("Folders:")
    if not folders:
        print("  <none>")
    for folder in sorted(
        folders, key=lambda item: ((item.parent_id or ""), item.name, item.id)
    ):
        parent = folder.parent_id or "<root>"
        print(f"  {folder.id}\tparent={parent}\t{folder.name}")

    print("\nFolder tree:")
    tree = client.folder_tree(include_project_items=False, return_as_str=True)
    print(tree or "  <none>")


def create_folder(client: "JinkoClient", name: str, parent_id: str | None) -> None:
    siblings = client.list_folders(parent=parent_id, name=name)
    if any(folder.name == name for folder in siblings):
        location = parent_id or "the project root"
        raise SystemExit(
            f"Refusing to create duplicate folder {name!r} below {location}; "
            "use the existing folder SID from the inventory."
        )

    created = client.create_folder(name, parent=parent_id)
    print(f"Created folder: {created.name} ({created.id})")


def main() -> None:
    args = parse_args()
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise SystemExit(
            "python-dotenv is required to load .env; install the jinko-sdk setup dependencies."
        ) from exc
    try:
        from jinko import JinkoClient
    except ImportError as exc:
        raise SystemExit(
            "jinko-sdk is required; run the jinko-sdk-setup skill before this example."
        ) from exc

    load_dotenv(".env")
    client = JinkoClient()
    print_folder_inventory(client)
    if args.create:
        create_folder(client, args.create, args.parent_id)


if __name__ == "__main__":
    main()
