#!/usr/bin/env python3
"""Apply built-in Jinkō input, source, and output tags to model components.

Dry-run by default. Pass --apply to commit component assignments in one batch.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


ALLOWED_TAGS = {
    "i::vpop",
    "i::protocol",
    "s::knowledge",
    "s::arbitrary",
    "s::to-calibrate",
    "output",
}
SCOPED_PREFIXES = ("i::", "s::")
EDIT_METHODS = {
    "Parameter": "edit_parameter",
    "CategoricalParameter": "edit_categorical_parameter",
    "Compartment": "edit_compartment",
    "Species": "edit_species",
    "Reaction": "edit_reaction",
    "Event": "edit_event",
    "Ode": "edit_ode",
    "BaselineCheck": "edit_baseline_check",
    "AlgebraicRule": "edit_algebraic_rule",
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


def parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Invalid tag assignment {value!r}; expected COMPONENT=TAG")
    component_id, tag_id = value.split("=", 1)
    if not component_id or tag_id not in ALLOWED_TAGS:
        allowed = ", ".join(sorted(ALLOWED_TAGS))
        raise ValueError(
            f"Invalid tag assignment {value!r}; allowed tags are: {allowed}"
        )
    return component_id, tag_id


def validate_assignments(assignments: list[tuple[str, str]]) -> None:
    scoped_tags: dict[tuple[str, str], str] = {}
    for component_id, tag_id in assignments:
        prefix = next(
            (prefix for prefix in SCOPED_PREFIXES if tag_id.startswith(prefix)), None
        )
        if prefix is None:
            continue
        key = (component_id, prefix)
        previous = scoped_tags.get(key)
        if previous is not None and previous != tag_id:
            raise ValueError(
                f"Conflicting {prefix[:-2]} tags for {component_id}: "
                f"{previous}, {tag_id}"
            )
        scoped_tags[key] = tag_id


def print_plan(model_sid: str, assignments: list[tuple[str, str]]) -> None:
    print(f"Would tag model: {model_sid}")
    for component_id, tag_id in assignments:
        print(f"Would set {component_id}: {tag_id}")
    print("Run again with --apply to commit the component tags.")


def apply_tags(model: Any, assignments: list[tuple[str, str]], version: str) -> None:
    components = {component.id: component for component in model.components.list()}
    assignments_by_component: dict[str, list[str]] = defaultdict(list)
    for component_id, tag_id in assignments:
        component = components.get(component_id)
        if component is None:
            raise ValueError(f"Component not found: {component_id}")
        if component.kind not in EDIT_METHODS:
            raise ValueError(
                f"Tagging is not supported for {component.kind}: {component_id}"
            )
        assignments_by_component[component_id].append(tag_id)

    known_tags = {tag.id for tag in model.tags}
    missing_tags = sorted({tag_id for _, tag_id in assignments} - known_tags)
    if missing_tags:
        raise ValueError(
            "Expected built-in platform tags were not found: " + ", ".join(missing_tags)
        )

    with model.components.batch(version=version) as batch:
        for component_id, desired_tags in assignments_by_component.items():
            component = components[component_id]
            draft = getattr(batch, EDIT_METHODS[component.kind])(component)
            current_tags = [tag.id for tag in component.tags]
            for tag_id in desired_tags:
                prefix = next(
                    (prefix for prefix in SCOPED_PREFIXES if tag_id.startswith(prefix)),
                    None,
                )
                if prefix is not None:
                    for current_tag in current_tags:
                        if current_tag.startswith(prefix) and current_tag != tag_id:
                            draft.remove_tag(current_tag)
                draft.add_tag(tag_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply standard tags to Jinkō model components."
    )
    parser.add_argument(
        "--model-sid", required=True, help="Computational model SID, for example cm-..."
    )
    parser.add_argument(
        "--tag",
        action="append",
        required=True,
        help="Tag assignment as COMPONENT=TAG. May be repeated.",
    )
    parser.add_argument("--version-name", default="apply model component tags")
    parser.add_argument("--apply", action="store_true", help="Actually edit the model.")
    args = parser.parse_args()

    try:
        assignments = [parse_assignment(value) for value in args.tag]
        validate_assignments(assignments)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.apply:
        print_plan(args.model_sid, assignments)
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk
    try:
        model = JinkoClient().get_model(args.model_sid)
        apply_tags(model, assignments, args.version_name)
        print(f"Tagged model {args.model_sid}")
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
