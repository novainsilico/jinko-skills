#!/usr/bin/env python3
"""Create a Jinkō advanced output set (scoring design).

Dry-run by default. Pass --apply to create the ScoringDesign project item.
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
        from jinko.exceptions import JinkoError, ValidationError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError, ValidationError


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


def parse_id_colon_value(
    entries: list[str] | None, *, flag: str, value_field: str
) -> list[dict[str, str]]:
    parsed = []
    for entry in entries or ():
        if ":" not in entry:
            raise ValueError(f"{flag} expects 'id:{value_field}', got {entry!r}")
        component_id, value = entry.split(":", 1)
        if not component_id or not value:
            raise ValueError(
                f"{flag} expects a non-empty id and {value_field}, got {entry!r}"
            )
        parsed.append({"id": component_id, value_field: value})
    return parsed


def load_components_from_json(path: Path) -> dict[str, list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("--from-json must contain a JSON object")
    return {
        "constraints": data.get("constraints", []),
        "scalars": data.get("scalars", []),
        "objectives": data.get("objectives", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Jinkō advanced output set.")
    parser.add_argument(
        "--from-json",
        help="Path to a JSON file with {constraints, scalars, objectives} lists.",
    )
    parser.add_argument(
        "--constraint",
        action="append",
        dest="constraints",
        help="Shorthand 'id:expr' constraint, e.g. 'adults:age >= 18'. Repeatable.",
    )
    parser.add_argument(
        "--scalar",
        action="append",
        dest="scalars",
        help="Shorthand 'id:formula' scalar, e.g. 'auc:AUC_drug'. Repeatable.",
    )
    parser.add_argument("--name", default="sdk-advanced-output-set")
    parser.add_argument(
        "--description", default="Advanced output set created with the Jinkō SDK."
    )
    parser.add_argument(
        "--show-validation",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Print a validation report before creating. Defaults to notebook detection.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the advanced output set."
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

    try:
        if args.from_json:
            path = Path(args.from_json)
            if not path.exists():
                print(f"--from-json file does not exist: {path}", file=sys.stderr)
                return 1
            components = load_components_from_json(path)
        else:
            components = {
                "constraints": parse_id_colon_value(
                    args.constraints, flag="--constraint", value_field="constraint"
                ),
                "scalars": parse_id_colon_value(
                    args.scalars, flag="--scalar", value_field="formula"
                ),
                "objectives": [],
            }
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    constraints = components["constraints"]
    scalars = components["scalars"]
    objectives = components["objectives"]

    if not args.apply:
        print(
            f"Would create advanced output set named {args.name!r} with "
            f"{len(constraints)} constraint(s), {len(scalars)} scalar(s), "
            f"{len(objectives)} objective(s)."
        )
        for constraint in constraints:
            print(f"  constraint {constraint['id']!r}: {constraint['constraint']}")
        for scalar in scalars:
            print(f"  scalar {scalar['id']!r}: {scalar['formula']}")
        for objective in objectives:
            print(f"  objective {objective['id']!r}: weight={objective.get('weight')}")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to create the advanced output set.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError, ValidationError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)

        scoring_design = client.create_advanced_output_set(
            constraints=constraints,
            scalars=scalars,
            objectives=objectives,
            show_validation=args.show_validation,
            folder=folder,
            name=args.name,
            description=args.description,
        )

        print(f"Created advanced output set {scoring_design.sid}")
        if folder is not None:
            print(f"Folder: {client.folders.get_path(folder)}")
        if getattr(scoring_design, "url", None):
            print(scoring_design.url)

        diagnostics = scoring_design.diagnostics
        print(
            f"Diagnostics: {len(diagnostics.errors())} error(s), "
            f"{len(diagnostics.warnings())} warning(s)"
        )
        return 0
    except ValidationError as exc:
        print(f"Advanced output set validation failed: {exc}", file=sys.stderr)
        return 2
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
