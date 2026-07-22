#!/usr/bin/env python3
"""Apply a safe batch-edit template to an existing Jinkō model.

Dry-run by default. Pass --apply to mutate the model.
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


def parse_update(values: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid update {value!r}; expected COMPONENT=FORMULA")
        key, formula = value.split("=", 1)
        updates[key] = formula
    return updates


def print_plan(args: argparse.Namespace, updates: dict[str, Any]) -> None:
    print(f"Would edit model: {args.model_sid}")
    print(f"Would set solving unitCheck: {args.unit_check}")
    print(f"Would edit parameter {args.parameter_id}: {args.parameter_formula}")
    print(
        f"Would create parameter {args.new_parameter_id}: {args.new_parameter_formula} [{args.new_parameter_unit}]"
    )
    print(f"Would edit event {args.event_id} updates: {updates}")
    print(
        f"Would edit reaction {args.reaction_id} general kinetics rate: {args.reaction_rate}"
    )
    if args.algebraic_rule_id:
        print(
            f"Would create algebraic residual {args.algebraic_rule_id}: {args.algebraic_equation}"
        )
    print("Run again with --apply to commit the batch edit.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch edit an existing Jinkō model.")
    parser.add_argument(
        "--model-sid", required=True, help="Computational model SID, for example cm-..."
    )
    parser.add_argument("--apply", action="store_true", help="Actually edit the model.")
    parser.add_argument("--version-name", default="sdk batch model edits")
    parser.add_argument(
        "--unit-check", default="UnitCheckAndConvertAllSpeciesToExtentUnits"
    )
    parser.add_argument("--parameter-id", default="k_clearance")
    parser.add_argument("--parameter-formula", default="CL2 / V")
    parser.add_argument("--new-parameter-id", default="k_new")
    parser.add_argument("--new-parameter-formula", default="0.8")
    parser.add_argument("--new-parameter-unit", default="1/h")
    parser.add_argument("--event-id", default="dose_start")
    parser.add_argument(
        "--event-update",
        action="append",
        default=["Dose=120"],
        help="Event update as COMPONENT=FORMULA. May be repeated.",
    )
    parser.add_argument("--reaction-id", default="binding")
    parser.add_argument(
        "--reaction-rate", default="kon * Drug * Target - koff * Complex"
    )
    parser.add_argument("--algebraic-rule-id", default=None)
    parser.add_argument(
        "--algebraic-equation",
        default="f1(x1, x2) - x1",
        help="Residual equation interpreted as 0 = equation.",
    )
    args = parser.parse_args()

    try:
        updates = parse_update(args.event_update)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.apply:
        print_plan(args, updates)
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        model = client.get_model(args.model_sid)
        model = model.edit_solving_options(
            {"unitCheck": args.unit_check},
            version=f"{args.version_name}: solving options",
        )

        with model.components.batch(version=args.version_name) as batch:
            batch.edit_parameter(args.parameter_id).set_formula(args.parameter_formula)
            batch.create_parameter(
                id=args.new_parameter_id,
                formula=args.new_parameter_formula,
                unit=args.new_parameter_unit,
            )
            batch.edit_event(args.event_id).set_updates(updates)
            batch.edit_reaction(args.reaction_id).set_general_kinetics(
                reactants={"Drug": 1, "Target": 1},
                products={"Complex": 1},
                rate=args.reaction_rate,
            )
            if args.algebraic_rule_id:
                batch.create_algebraic_rule(
                    id=args.algebraic_rule_id,
                    equation=args.algebraic_equation,
                )

        refreshed = client.get_model(args.model_sid)
        diagnostics = refreshed.diagnostics.errors()
        if diagnostics:
            print(
                "Batch committed, but model diagnostics contain errors:",
                file=sys.stderr,
            )
            for entry in diagnostics:
                diagnostic = entry.diagnostic
                print(
                    f"- {entry.component.id}: {diagnostic.code} ({diagnostic.severity}) {diagnostic.message}",
                    file=sys.stderr,
                )
            return 3

        print(f"Edited model {args.model_sid}")
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
