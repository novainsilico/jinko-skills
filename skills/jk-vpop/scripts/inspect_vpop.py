#!/usr/bin/env python3
"""Inspect a Jinkō Vpop project item."""

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


def print_json(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Jinkō Vpop.")
    parser.add_argument(
        "--vpop-sid", required=True, help="Vpop SID, for example vp-..."
    )
    parser.add_argument("--content", action="store_true", help="Print Vpop content.")
    parser.add_argument(
        "--describe", action="store_true", help="Print Vpop describe payload."
    )
    parser.add_argument(
        "--statistics", action="store_true", help="Print Vpop statistics."
    )
    parser.add_argument(
        "--correlations",
        action="store_true",
        help="Include correlations in statistics.",
    )
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        vpop = client.get_vpop(args.vpop_sid)
        if not (args.content or args.describe or args.statistics):
            print(f"Vpop {vpop.sid}")
            if getattr(vpop, "url", None):
                print(vpop.url)
            return 0
        if args.content:
            print_json(vpop.content())
        if args.describe:
            print_json(vpop.describe())
        if args.statistics:
            print_json(vpop.statistics(correlations=args.correlations))
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
