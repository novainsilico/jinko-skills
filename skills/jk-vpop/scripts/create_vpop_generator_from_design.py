#!/usr/bin/env python3
"""Create a Jinkō Vpop design from marginal distributions.

Dry-run by default. Pass --apply to create the VpopDesign project item.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
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
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def load_marginal_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Design JSON must be a list of marginal entries")
    for index, entry in enumerate(data):
        if (
            not isinstance(entry, dict)
            or "id" not in entry
            or "distribution" not in entry
        ):
            raise ValueError(f"Marginal entry {index} must contain id and distribution")
    return data


def marginal_mapping(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | float | str]:
    return {entry["id"]: entry["distribution"] for entry in entries}


def resolve_folder(client: Any, folder_ref: str | None, *, create: bool) -> Any | None:
    if folder_ref is None:
        return None

    folder = client.folders.get_by_id(folder_ref)
    if folder is not None:
        return folder

    folder = client.folders.get_by_name(folder_ref, exact_match_only=True)
    if folder is not None:
        return folder

    if not create:
        raise ValueError(
            f"Folder {folder_ref!r} was not found. Pass --create-folder to create it."
        )

    return client.folders.create(folder_ref)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Vpop design from marginal distributions."
    )
    parser.add_argument(
        "--design", required=True, help="JSON list of {id, distribution} entries."
    )
    parser.add_argument(
        "--model-sid",
        help="Optional model SID to bind the design to model descriptors.",
    )
    parser.add_argument("--name", default="sdk-toy-vpop-design")
    parser.add_argument(
        "--description", default="Vpop design created from SDK marginal distributions."
    )
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new Vpop design and generated Vpop.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the Vpop design."
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a Vpop after creating the design.",
    )
    parser.add_argument("--vpop-name", default="sdk-generated-vpop")
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variance-reduction", action="store_true")
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    try:
        entries = load_marginal_list(Path(args.design))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid design JSON: {exc}", file=sys.stderr)
        return 1

    print(f"Marginal descriptors: {', '.join(entry['id'] for entry in entries)}")
    if args.model_sid:
        print(f"Model binding: {args.model_sid}")
    else:
        print("Model binding: none")

    if not args.apply:
        print(f"Would create Vpop design named {args.name!r}.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        if args.generate:
            print(
                f"Would generate Vpop named {args.vpop_name!r} with size={args.size}, seed={args.seed}."
            )
        print("Run again with --apply to create project items.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        model = client.get_model(args.model_sid) if args.model_sid else None
        generator = client.create_vpop_generator_from_design(
            model=model,
            marginal_distributions=marginal_mapping(entries),
            folder=folder,
            name=args.name,
            description=args.description,
        )
        print(f"Created Vpop design {generator.sid}")
        if folder is not None:
            print(f"Folder: {client.folders.get_path(folder)}")
        if getattr(generator, "url", None):
            print(generator.url)

        if args.generate:
            vpop = generator.generate_vpop_by_design(
                size=args.size,
                seed=args.seed,
                variance_reduction=args.variance_reduction,
                folder=folder,
                name=args.vpop_name,
                description=f"Generated from Vpop design {generator.sid}.",
            )
            print(f"Generated Vpop {vpop.sid}")
            if getattr(vpop, "url", None):
                print(vpop.url)
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
