#!/usr/bin/env python3
"""Validate and apply source/calibration-step labels to Jinkō model inputs.

The JSON plan is validated in dry-run mode. Pass --apply to validate it against
the model, create missing CalibIter tags, and commit component tags in one batch.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


ALLOWED_SOURCES = {"knowledge", "arbitrary", "to-calibrate"}
ELIGIBLE_KINDS = {"Parameter", "CategoricalParameter", "Species"}
EDIT_METHODS = {
    "Parameter": "edit_parameter",
    "CategoricalParameter": "edit_categorical_parameter",
    "Species": "edit_species",
}


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


def load_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read labeling plan {path}: {exc}") from exc
    if not isinstance(plan, dict):
        raise ValueError("Labeling plan must be a JSON object")
    return validate_plan(plan)


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    steps = plan.get("in_scope_steps")
    assignments = plan.get("assignments")
    if not isinstance(steps, list) or not steps:
        raise ValueError("in_scope_steps must be a non-empty array")
    if not all(isinstance(step, str) and step.strip() for step in steps):
        raise ValueError("Every in_scope_steps entry must be a non-empty string")
    if len(steps) != len(set(steps)):
        raise ValueError("in_scope_steps contains duplicates")
    if not isinstance(assignments, list):
        raise ValueError("assignments must be an array")

    normalized = []
    seen_components = set()
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            raise ValueError(f"assignments[{index}] must be an object")
        component_id = assignment.get("component_id")
        source = assignment.get("source")
        step = assignment.get("calibration_step")
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError(
                f"assignments[{index}].component_id must be a non-empty string"
            )
        if component_id in seen_components:
            raise ValueError(f"Duplicate assignment for component {component_id!r}")
        seen_components.add(component_id)
        if source not in ALLOWED_SOURCES:
            allowed = ", ".join(sorted(ALLOWED_SOURCES))
            raise ValueError(
                f"Assignment for {component_id!r} has source {source!r}; "
                f"allowed values are {allowed}"
            )
        if source == "to-calibrate":
            if step not in steps:
                raise ValueError(
                    f"Assignment for {component_id!r} requires a calibration_step "
                    "from in_scope_steps"
                )
        elif step is not None:
            raise ValueError(
                f"Assignment for {component_id!r} may only set calibration_step "
                "with source 'to-calibrate'"
            )
        normalized.append({
            "component_id": component_id,
            "source": source,
            "calibration_step": step,
        })

    return {"in_scope_steps": steps, "assignments": normalized}


def scoped_tags(component: Any, prefix: str) -> list[str]:
    return [tag.id for tag in component.tags if tag.id.startswith(prefix)]


def validate_model_assignments(
    components: dict[str, Any], assignments: list[dict[str, Any]], *, relabel: bool
) -> None:
    for assignment in assignments:
        component_id = assignment["component_id"]
        component = components.get(component_id)
        if component is None:
            raise ValueError(f"Component not found: {component_id}")
        if component.kind not in ELIGIBLE_KINDS:
            raise ValueError(
                f"Component {component_id!r} has ineligible kind {component.kind}"
            )

        desired_source = f"s::{assignment['source']}"
        desired_step = assignment["calibration_step"]
        desired_calib = f"CalibIter::{desired_step}" if desired_step else None
        current_sources = scoped_tags(component, "s::")
        current_steps = scoped_tags(component, "CalibIter::")
        if len(current_sources) > 1 or len(current_steps) > 1:
            raise ValueError(f"Component {component_id!r} has conflicting scoped tags")
        if relabel:
            continue
        if current_sources and current_sources != [desired_source]:
            raise ValueError(
                f"Component {component_id!r} already has {current_sources[0]}; "
                "pass --relabel to replace it"
            )
        if current_steps and current_steps != [desired_calib]:
            raise ValueError(
                f"Component {component_id!r} already has {current_steps[0]}; "
                "pass --relabel to replace it"
            )


def apply_assignments(
    model: Any,
    components: dict[str, Any],
    assignments: list[dict[str, Any]],
    *,
    relabel: bool,
    version: str,
) -> list[str]:
    if not assignments:
        return []

    known_tags = {tag.id for tag in model.tags}
    required_steps = sorted({
        f"CalibIter::{assignment['calibration_step']}"
        for assignment in assignments
        if assignment["calibration_step"] is not None
    })
    created_tags = []
    for tag_id in required_steps:
        if tag_id not in known_tags:
            model.create_tag(
                tag_id,
                description=f"Calibration step {tag_id.removeprefix('CalibIter::')}",
                version=version,
            )
            created_tags.append(tag_id)

    with model.components.batch(version=version) as batch:
        for assignment in assignments:
            component = components[assignment["component_id"]]
            draft = getattr(batch, EDIT_METHODS[component.kind])(component)
            desired = {f"s::{assignment['source']}"}
            if assignment["calibration_step"] is not None:
                desired.add(f"CalibIter::{assignment['calibration_step']}")
            for tag in component.tags:
                if (
                    relabel
                    and tag.id.startswith(("s::", "CalibIter::"))
                    and tag.id not in desired
                ):
                    draft.remove_tag(tag)
            for tag_id in sorted(desired):
                if not component.has_tag(tag_id):
                    draft.add_tag(tag_id)
    return created_tags


def report(plan: dict[str, Any], *, applied: bool, created_tags: list[str]) -> None:
    assignments = plan["assignments"]
    payload = {
        "applied": applied,
        "assignment_count": len(assignments),
        "source_counts": dict(Counter(row["source"] for row in assignments)),
        "step_counts": dict(
            Counter(
                row["calibration_step"]
                for row in assignments
                if row["calibration_step"] is not None
            )
        ),
        "created_tags": created_tags,
        "assignments": assignments,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply source and calibration-step labels to Jinkō model inputs."
    )
    parser.add_argument("--model-sid", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--version-name", default="define parameters to calibrate")
    parser.add_argument(
        "--relabel", action="store_true", help="Replace conflicting scoped labels."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    try:
        plan = load_plan(args.plan)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.apply:
        report(plan, applied=False, created_tags=[])
        print("Run again with --apply to edit the model.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk
    try:
        model = JinkoClient().get_model(args.model_sid)
        components = {component.id: component for component in model.components.list()}
        validate_model_assignments(
            components, plan["assignments"], relabel=args.relabel
        )
        created_tags = apply_assignments(
            model,
            components,
            plan["assignments"],
            relabel=args.relabel,
            version=args.version_name,
        )
        report(plan, applied=True, created_tags=created_tags)
        print(f"Updated model {model.sid}: {model.url}")
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Labeling failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep diagnostics concise
        print(f"Labeling failed unexpectedly: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
