#!/usr/bin/env python3
"""Create a Jinkō subsampling design from a completed Trial.

Dry-run by default. Pass --apply to create the remote design. The script
supports a deliberately small scalar workflow; use the typed SDK builders for
advanced target families described in the skill references.
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


def parse_filter(spec: str) -> tuple[str, str, float, str | None]:
    parts = spec.split(":")
    if len(parts) not in (3, 4):
        raise ValueError(
            "--numeric-filter must be descriptor:Eq|Neq|Lt|Lte|Gt|Gte:value[:arm]"
        )
    descriptor, operator, raw_value, *arm = parts
    if operator not in {"Eq", "Neq", "Lt", "Lte", "Gt", "Gte"}:
        raise ValueError(f"Unsupported numeric filter operator {operator!r}")
    return descriptor, operator, float(raw_value), arm[0] if arm else None


def parse_normal(spec: str) -> tuple[str, float, float, str | None]:
    parts = spec.split(":")
    if len(parts) not in (3, 4):
        raise ValueError(
            "--marginal-normal must be descriptor:mean:standard_deviation[:arm]"
        )
    descriptor, mean, stdev, *arm = parts
    return descriptor, float(mean), float(stdev), arm[0] if arm else None


def scalar(trial: Any, descriptor_id: str, arm: str | None) -> Any:
    return trial.descriptors.scalars.get(descriptor_id, arm=arm)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Jinkō subsampling design.")
    parser.add_argument(
        "--trial-sid", required=True, help="Completed source Trial SID."
    )
    parser.add_argument("--numeric-filter", action="append", default=[])
    parser.add_argument("--marginal-normal", action="append", default=[])
    parser.add_argument(
        "--observable", action="append", default=[], help="descriptor[:arm]"
    )
    parser.add_argument("--name", default="sdk-subsampling-design")
    parser.add_argument(
        "--description", default="Subsampling design created with the Jinkō SDK."
    )
    parser.add_argument("--folder", help="Existing folder id or exact folder name.")
    parser.add_argument("--create-folder", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1
    try:
        filters = [parse_filter(value) for value in args.numeric_filter]
        marginals = [parse_normal(value) for value in args.marginal_normal]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Source trial: {args.trial_sid}")
    print(f"Numeric filters: {filters or '<none>'}")
    print(f"Normal marginals: {marginals or '<none>'}")
    print(f"Observables: {args.observable or '<none>'}")
    print(f"Folder: {args.folder or '<none>'}")
    if not args.apply:
        print(f"Would create subsampling design named {args.name!r}.")
        print("Run again with --apply to create the project item.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk
    try:
        client = JinkoClient()
        trial = client.get_trial(args.trial_sid)
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        filter_builders = []
        for descriptor_id, operator, value, arm in filters:
            descriptor = scalar(trial, descriptor_id, arm)
            filter_builders.append(getattr(descriptor, operator.lower())(value))
        marginal_builders = [
            scalar(trial, descriptor_id, arm).normal(
                mean=mean, standard_deviation=stdev
            )
            for descriptor_id, mean, stdev, arm in marginals
        ]
        observables = []
        for value in args.observable:
            descriptor_id, *arm = value.split(":", maxsplit=1)
            observables.append(scalar(trial, descriptor_id, arm[0] if arm else None))
        design = trial.create_subsampling_design(
            numeric_filters=filter_builders,
            marginals=marginal_builders,
            observables=observables,
            folder=folder,
            name=args.name,
            description=args.description,
        )
        print(f"Created subsampling design {design.sid}")
        print(design.url)
        diagnostics = design.diagnostics
        print(diagnostics.explain())
        return 0 if not diagnostics.errors() else 3
    except (ValueError, RuntimeError, JinkoError) as exc:
        print(f"Subsampling-design creation failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(
            f"Subsampling-design creation failed unexpectedly: {exc}", file=sys.stderr
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
