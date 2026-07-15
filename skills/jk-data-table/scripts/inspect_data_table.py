#!/usr/bin/env python3
"""Inspect and validate a Jinkō data table."""

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


def valid_for_fitness_from_content(content: Any) -> bool | None:
    if isinstance(content, dict):
        public = (content.get("metadata") or {}).get("public") or {}
        return public.get("validForFitnessFunction")

    metadata = getattr(content, "metadata", None)
    public = getattr(metadata, "public", None)
    return getattr(public, "validForFitnessFunction", None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Jinkō data table.")
    parser.add_argument(
        "--data-table-sid", required=True, help="DataTable SID, for example dt-..."
    )
    parser.add_argument(
        "--content", action="store_true", help="Print structured content."
    )
    parser.add_argument("--summary", action="store_true", help="Print backend summary.")
    parser.add_argument(
        "--validate", action="store_true", help="Run backend validation."
    )
    parser.add_argument(
        "--fitness", action="store_true", help="Print validForFitnessFunction metadata."
    )
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        table = client.get_data_table(args.data_table_sid)
        content = None

        if not (args.content or args.summary or args.validate or args.fitness):
            print(f"DataTable {table.sid}")
            if getattr(table, "url", None):
                print(table.url)
            return 0

        if args.content or args.fitness:
            content = table.content()
        if args.content:
            print(json.dumps(to_jsonable(content), indent=2, sort_keys=True))
        if args.summary:
            print(json.dumps(to_jsonable(table.summary()), indent=2, sort_keys=True))
        if args.validate:
            print(json.dumps(to_jsonable(table.validate()), indent=2, sort_keys=True))
        if args.fitness:
            valid = valid_for_fitness_from_content(content)
            if valid is None:
                print("validForFitnessFunction: <not reported>")
            else:
                print(f"validForFitnessFunction: {valid}")
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
