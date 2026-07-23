#!/usr/bin/env python3
"""Create a Jinkō protocol design from arm overrides.

Dry-run by default. Pass --apply to create the ProtocolDesign project item.
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


DEFAULT_ARM_NAMES = ["iv_low_dose", "po_mid_dose", "iv_high_dose"]


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


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_arms(
    *,
    dose_key: str,
    route_key: str,
    doses: list[str],
    routes: list[str],
    arm_names: list[str],
    control_arm: str,
) -> list[dict[str, Any]]:
    if not (len(doses) == len(routes) == len(arm_names)):
        raise ValueError("doses, routes, and arm names must have the same length")
    if control_arm not in arm_names:
        raise ValueError("control arm must be one of the arm names")
    arms = []
    for name, dose, route in zip(arm_names, doses, routes):
        arms.append({
            "armControl": None if name == control_arm else control_arm,
            "armIsActive": True,
            "armName": name,
            "armOverrides": [
                {"key": dose_key, "formula": dose},
                {"key": route_key, "formula": route},
            ],
            "armWeight": 1,
        })
    return arms


def override_keys(arms: list[dict[str, Any]]) -> set[str]:
    return {
        override["key"]
        for arm in arms
        for override in arm.get("armOverrides", [])
        if isinstance(override, dict) and "key" in override
    }


def validate_model_override_keys(model: Any, keys: set[str]) -> None:
    component_ids = {component.id for component in model.components.list()}
    missing = sorted(keys.difference(component_ids))
    if missing:
        raise ValueError(
            "Override keys are not present as model components: " + ", ".join(missing)
        )


def print_arm_summary(arms: list[dict[str, Any]]) -> None:
    for arm in arms:
        overrides = ", ".join(
            f"{override['key']}={override['formula']}"
            for override in arm.get("armOverrides", [])
        )
        print(
            f"- {arm['armName']} control={arm.get('armControl')} overrides=[{overrides}]"
        )


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
    parser = argparse.ArgumentParser(description="Create a Jinkō protocol design.")
    parser.add_argument(
        "--model-sid", help="Optional model SID to link and validate override keys."
    )
    parser.add_argument("--name", default="sdk-three-arm-protocol")
    parser.add_argument(
        "--description", default="Three-arm protocol design created with the SDK."
    )
    parser.add_argument("--dose-key", default="Dose")
    parser.add_argument("--route-key", default="route")
    parser.add_argument("--doses", default="1.0,2.0,3.0")
    parser.add_argument("--routes", default="iv,po,iv")
    parser.add_argument("--arm-names", default=",".join(DEFAULT_ARM_NAMES))
    parser.add_argument("--control-arm", default="iv_low_dose")
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new protocol design.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually create the protocol design."
    )
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    try:
        arms = build_arms(
            dose_key=args.dose_key,
            route_key=args.route_key,
            doses=split_csv(args.doses),
            routes=split_csv(args.routes),
            arm_names=split_csv(args.arm_names),
            control_arm=args.control_arm,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Protocol arms: {len(arms)}")
    print_arm_summary(arms)
    if args.model_sid:
        print(f"Model link: {args.model_sid}")
    else:
        print("Model link: none")

    if not args.apply:
        print(f"Would create protocol design named {args.name!r}.")
        if args.folder:
            action = "Would create or reuse" if args.create_folder else "Would reuse"
            print(f"{action} folder: {args.folder}")
        print("Run again with --apply to create the protocol design.")
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
        if model is not None:
            validate_model_override_keys(model, override_keys(arms))
        protocol = client.create_protocol_design(
            arms,
            model=model,
            folder=folder,
            name=args.name,
            description=args.description,
        )
        print(f"Created protocol design {protocol.sid}")
        if folder is not None:
            print(f"Folder: {folder.path}")
        if getattr(protocol, "url", None):
            print(protocol.url)
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Protocol design creation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
