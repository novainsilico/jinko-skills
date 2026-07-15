#!/usr/bin/env python3
"""Add components to an existing Jinkō advanced output set.

Dry-run by default. Pass --apply to actually add the components. Each
addition creates a new versioned snapshot of the advanced output set.
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
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError, ValidationError


def parse_constraint(entry: str) -> dict[str, Any]:
    parts = entry.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"--add-constraint expects 'id:expr[:filter]', got {entry!r}")
    component_id, constraint = parts[0], parts[1]
    filter_expr = parts[2] if len(parts) == 3 else None
    if not component_id or not constraint:
        raise ValueError(
            f"--add-constraint expects a non-empty id and expr, got {entry!r}"
        )
    return {"id": component_id, "constraint": constraint, "filter": filter_expr}


def parse_scalar(entry: str) -> dict[str, Any]:
    parts = entry.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"--add-scalar expects 'id:formula[:unit]', got {entry!r}")
    component_id, formula = parts[0], parts[1]
    unit = parts[2] if len(parts) == 3 else None
    if not component_id or not formula:
        raise ValueError(
            f"--add-scalar expects a non-empty id and formula, got {entry!r}"
        )
    return {"id": component_id, "formula": formula, "unit": unit}


def parse_objective(entry: str) -> dict[str, Any]:
    parts = entry.split(":")
    if len(parts) != 7:
        raise ValueError(
            "--add-objective expects "
            "'id:target:narrow_low:narrow_high:wide_low:wide_high:weight', "
            f"got {entry!r}"
        )
    component_id, target, narrow_low, narrow_high, wide_low, wide_high, weight = parts
    if not component_id:
        raise ValueError(f"--add-objective expects a non-empty id, got {entry!r}")
    try:
        return {
            "id": component_id,
            "formula_target": target or None,
            "narrow_range_low_bound": float(narrow_low),
            "narrow_range_high_bound": float(narrow_high),
            "wide_range_low_bound": float(wide_low),
            "wide_range_high_bound": float(wide_high),
            "weight": float(weight),
        }
    except ValueError as exc:
        raise ValueError(
            f"--add-objective has a non-numeric bound or weight: {entry!r}"
        ) from exc


def load_objective_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "id" not in data:
        raise ValueError("--add-objective-json must contain an object with an 'id' key")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add components to an existing Jinkō advanced output set."
    )
    parser.add_argument(
        "--sid", required=True, help="Advanced output set SID, for example sc-..."
    )
    parser.add_argument(
        "--add-constraint",
        action="append",
        dest="add_constraints",
        default=[],
        help="Shorthand 'id:expr[:filter]', e.g. 'adults:age >= 18'. Repeatable.",
    )
    parser.add_argument(
        "--add-scalar",
        action="append",
        dest="add_scalars",
        default=[],
        help="Shorthand 'id:formula[:unit]', e.g. 'auc:auc(Drug):mg/L*s'. Repeatable.",
    )
    parser.add_argument(
        "--add-objective",
        action="append",
        dest="add_objectives",
        default=[],
        help=(
            "Shorthand "
            "'id:target:narrow_low:narrow_high:wide_low:wide_high:weight'. "
            "'target' should be a formula, not a sibling scalar's id (a "
            "sibling-id target can pass standalone validation here yet fail "
            "trial.sanity() later — see jk-output-set's "
            "references/advanced-output-set.md pitfalls), "
            "e.g. 'obj_auc:auc(Drug):8:12:5:15:1.0'. Repeatable."
        ),
    )
    parser.add_argument(
        "--add-objective-json",
        action="append",
        dest="add_objectives_json",
        default=[],
        help="Path to a JSON file with a full objective dict (id, formula, weight, ...). Repeatable.",
    )
    parser.add_argument(
        "--show-diagnostics",
        action="store_true",
        help="Print diagnostics after applying edits.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually add the components."
    )
    args = parser.parse_args()

    try:
        constraints = [parse_constraint(entry) for entry in args.add_constraints]
        scalars = [parse_scalar(entry) for entry in args.add_scalars]
        objectives = [parse_objective(entry) for entry in args.add_objectives]
        for path_str in args.add_objectives_json:
            path = Path(path_str)
            if not path.exists():
                print(
                    f"--add-objective-json file does not exist: {path}", file=sys.stderr
                )
                return 1
            objectives.append(load_objective_json(path))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not constraints and not scalars and not objectives:
        print(
            "Nothing to add. Pass --add-constraint, --add-scalar, --add-objective, "
            "or --add-objective-json.",
            file=sys.stderr,
        )
        return 1

    if not args.apply:
        print(f"Would edit advanced output set {args.sid}:")
        for constraint in constraints:
            print(f"  add constraint {constraint['id']!r}: {constraint['constraint']}")
        for scalar in scalars:
            print(f"  add scalar {scalar['id']!r}: {scalar['formula']}")
        for objective in objectives:
            print(f"  add objective {objective['id']!r}")
        print("Run again with --apply to add these components.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError, ValidationError = sdk

    try:
        client = JinkoClient()
        scoring_design = client.get_advanced_output_set(args.sid)

        for constraint in constraints:
            scoring_design.components.add_constraint(
                constraint["id"],
                constraint=constraint["constraint"],
                filter=constraint["filter"],
            )
            print(f"Added constraint {constraint['id']!r}")

        for scalar in scalars:
            scoring_design.components.add_scalar(
                scalar["id"], formula=scalar["formula"], unit=scalar["unit"]
            )
            print(f"Added scalar {scalar['id']!r}")

        for objective in objectives:
            if "formula_target" in objective:
                scoring_design.components.add_objective(
                    objective["id"],
                    formula_target=objective["formula_target"],
                    narrow_range_low_bound=objective["narrow_range_low_bound"],
                    narrow_range_high_bound=objective["narrow_range_high_bound"],
                    wide_range_low_bound=objective["wide_range_low_bound"],
                    wide_range_high_bound=objective["wide_range_high_bound"],
                    weight=objective["weight"],
                )
            else:
                formula = objective["formula"]
                scoring_design.components.add_objective(
                    objective["id"],
                    formula_target=formula.get("target"),
                    narrow_range_low_bound=formula["range"]["narrowRangeLowBound"],
                    narrow_range_high_bound=formula["range"]["narrowRangeHighBound"],
                    wide_range_low_bound=formula["range"]["wideRangeLowBound"],
                    wide_range_high_bound=formula["range"]["wideRangeHighBound"],
                    weight=objective["weight"],
                    filter=objective.get("filter"),
                    description=objective.get("description"),
                    display_name=objective.get("display_name"),
                )
            print(f"Added objective {objective['id']!r}")

        diagnostics = scoring_design.diagnostics
        if args.show_diagnostics or diagnostics.has_errors():
            print(str(diagnostics))
            print(
                f"{len(diagnostics.errors())} error(s), "
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
