#!/usr/bin/env python3
"""Replace scenario arms on an existing Jinkō protocol design.

Dry-run by default. Pass --apply to update the ProtocolDesign project item.

Uses the design's ``arms`` mutator service (``set_control``/``set_active``/
``set_weight``/``set_override`` for existing arms, ``create`` for new ones)
rather than replacing the raw design payload, so each change is validated
individually by the API.
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
        from jinko.exceptions import JinkoError, NotFoundError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError, NotFoundError


def load_arms(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("arms JSON must be a non-empty list")
    for index, arm in enumerate(data):
        if not isinstance(arm, dict):
            raise ValueError(f"arm {index} must be an object")
        if "armName" not in arm or "armOverrides" not in arm:
            raise ValueError(f"arm {index} must contain armName and armOverrides")
    return data


def print_arm_summary(arms: list[dict[str, Any]]) -> None:
    for arm in arms:
        overrides = ", ".join(
            f"{override['key']}={override['formula']}"
            for override in arm.get("armOverrides", [])
        )
        print(
            f"- {arm['armName']} control={arm.get('armControl')} overrides=[{overrides}]"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or update arms in an existing protocol design."
    )
    parser.add_argument(
        "--protocol-design-sid",
        required=True,
        help="ProtocolDesign SID, for example pd-...",
    )
    parser.add_argument(
        "--arms", required=True, help="JSON file containing scenario arm list."
    )
    parser.add_argument("--version", default="update protocol arms")
    parser.add_argument(
        "--apply", action="store_true", help="Actually update the protocol design."
    )
    args = parser.parse_args()

    try:
        arms = load_arms(Path(args.arms))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid arms JSON: {exc}", file=sys.stderr)
        return 1

    print(f"Arms to apply: {len(arms)}")
    print_arm_summary(arms)

    if not args.apply:
        print(f"Would update protocol design {args.protocol_design_sid}.")
        print("Run again with --apply to update the protocol design.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError, NotFoundError = sdk

    try:
        client = JinkoClient()
        protocol = client.get_protocol_design(args.protocol_design_sid)

        for arm in arms:
            overrides = {
                override["key"]: override["formula"]
                for override in arm.get("armOverrides", [])
            }
            try:
                handle = protocol.arms.get(arm["armName"])
                handle.set_control(arm.get("armControl"), version=args.version)
                handle.set_active(arm.get("armIsActive"), version=args.version)
                handle.set_weight(arm.get("armWeight"), version=args.version)
                for key, formula in overrides.items():
                    handle.set_override(key, formula, version=args.version)
                print(f"Updated arm {arm['armName']!r}")
            except NotFoundError:
                protocol.arms.create(
                    arm["armName"],
                    control=arm.get("armControl"),
                    overrides=overrides,
                    weight=arm.get("armWeight"),
                    active=arm.get("armIsActive"),
                    version=args.version,
                )
                print(f"Created arm {arm['armName']!r}")

        print(f"Updated protocol design {protocol.sid}")
        return 0
    except JinkoError as exc:
        print(f"Protocol design update failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
