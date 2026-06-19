#!/usr/bin/env python3
"""Inspect a Jinkō protocol design."""

from __future__ import annotations

import argparse
import json
import sys

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


def print_summary(content) -> None:
    arms = content.scenarioArms or []
    print(f"Protocol arms: {len(arms)}")
    for arm in arms:
        overrides = ", ".join(
            f"{override.key.root if hasattr(override.key, 'root') else override.key}="
            f"{override.formula.root if hasattr(override.formula, 'root') else override.formula}"
            for override in arm.armOverrides
        )
        control = (
            arm.armControl.root if hasattr(arm.armControl, "root") else arm.armControl
        )
        print(f"- {arm.armName.root} control={control} overrides=[{overrides}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a protocol design.")
    parser.add_argument(
        "--protocol-design-sid",
        required=True,
        help="ProtocolDesign SID, for example pd-...",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print concise arm summary."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print full protocol content as JSON."
    )
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        protocol = client.get_protocol_design(args.protocol_design_sid)
        content = protocol.content()
        if args.json:
            print(
                json.dumps(
                    content.model_dump(mode="json", exclude_none=True),
                    indent=2,
                    sort_keys=True,
                )
            )
        if args.summary or not args.json:
            print_summary(content)
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
