#!/usr/bin/env python3
"""Generate a Vpop from a Jinkō subsampling design.

Dry-run by default. Pass --apply to validate the design and create the
immutable Vpop.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - environment dependent
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
    if folder is None:
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
        description="Generate a Vpop from a subsampling design."
    )
    parser.add_argument("--subsampling-design-sid", required=True)
    parser.add_argument("--num-samples", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--num-iterations", type=int, required=True)
    parser.add_argument("--iters-fixed-temperature", type=int, required=True)
    parser.add_argument("--replacement-rate", type=float, required=True)
    parser.add_argument("--boltzmann-constant", type=float, required=True)
    parser.add_argument("--name", default="sdk-subsampled-vpop")
    parser.add_argument(
        "--description", default="Vpop generated through Jinkō SDK subsampling."
    )
    parser.add_argument("--folder", help="Existing folder id or exact folder name.")
    parser.add_argument("--create-folder", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    print(f"Subsampling design: {args.subsampling_design_sid}")
    print(
        "Options: "
        + ", ".join(
            f"{key}={getattr(args, key)}"
            for key in (
                "num_samples",
                "seed",
                "num_iterations",
                "iters_fixed_temperature",
                "replacement_rate",
                "boltzmann_constant",
            )
        )
    )
    if not args.apply:
        print(f"Would create Vpop named {args.name!r}.")
        print("Run again with --apply to validate and generate the Vpop.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk
    try:
        client = JinkoClient()
        design = client.get_subsampling_design(args.subsampling_design_sid)
        errors = design.diagnostics.errors()
        if errors:
            print(errors.explain(), file=sys.stderr)
            return 3
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        vpop = design.generate_vpop(
            num_samples=args.num_samples,
            seed=args.seed,
            num_iterations=args.num_iterations,
            iters_fixed_temperature=args.iters_fixed_temperature,
            replacement_rate=args.replacement_rate,
            boltzmann_constant=args.boltzmann_constant,
            folder=folder,
            name=args.name,
            description=args.description,
        )
        print(f"Generated Vpop {vpop.sid}")
        print(vpop.url)
        return 0
    except (ValueError, RuntimeError, JinkoError) as exc:
        print(f"Vpop generation failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Vpop generation failed unexpectedly: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
