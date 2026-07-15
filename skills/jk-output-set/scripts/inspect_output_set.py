#!/usr/bin/env python3
"""Inspect a Jinkō simple or advanced output set."""

from __future__ import annotations

import argparse
import json
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


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Jinkō output set.")
    parser.add_argument(
        "--kind",
        required=True,
        choices=["simple", "advanced"],
        help="Whether the sid refers to a simple or advanced output set.",
    )
    parser.add_argument(
        "--sid", required=True, help="Output set SID, for example ms-... or sc-..."
    )
    parser.add_argument(
        "--content", action="store_true", help="Print structured content."
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print backend summary (advanced output sets only).",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print component diagnostics (advanced output sets only).",
    )
    parser.add_argument(
        "--tags", action="store_true", help="Print tags (advanced output sets only)."
    )
    args = parser.parse_args()

    if args.kind == "simple" and (args.summary or args.diagnostics or args.tags):
        print(
            "--summary, --diagnostics, and --tags are only available for "
            "--kind advanced; simple output sets have no equivalent.",
            file=sys.stderr,
        )
        return 1

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        if args.kind == "simple":
            output_set = client.get_simple_output_set(args.sid)
        else:
            output_set = client.get_advanced_output_set(args.sid)

        if not (args.content or args.summary or args.diagnostics or args.tags):
            print(f"Output set {output_set.sid}")
            if getattr(output_set, "url", None):
                print(output_set.url)
            return 0

        if args.content:
            print(
                json.dumps(to_jsonable(output_set.content()), indent=2, sort_keys=True)
            )
        if args.summary:
            print(
                json.dumps(to_jsonable(output_set.summary()), indent=2, sort_keys=True)
            )
        if args.diagnostics:
            diagnostics = output_set.diagnostics
            print(str(diagnostics))
            print(
                f"{len(diagnostics.errors())} error(s), "
                f"{len(diagnostics.warnings())} warning(s)"
            )
        if args.tags:
            for tag in output_set.tags:
                print(tag.id)
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
