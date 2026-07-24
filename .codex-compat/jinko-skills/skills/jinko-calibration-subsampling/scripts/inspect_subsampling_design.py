#!/usr/bin/env python3
"""Inspect a Jinkō subsampling design without mutating it."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - environment dependent
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


def jsonable(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    return dump(mode="json") if callable(dump) else value


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Jinkō subsampling design.")
    parser.add_argument("--subsampling-design-sid", required=True)
    parser.add_argument("--content", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--source-trial", action="store_true")
    parser.add_argument("--generated-vpops", action="store_true")
    args = parser.parse_args()
    if not any((
        args.content,
        args.diagnostics,
        args.source_trial,
        args.generated_vpops,
    )):
        print("Pass at least one inspection option.", file=sys.stderr)
        return 1

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk
    try:
        design = JinkoClient().get_subsampling_design(args.subsampling_design_sid)
        if args.content:
            print(json.dumps(design.content(), indent=2, sort_keys=True))
        if args.diagnostics:
            print(design.diagnostics.explain())
        if args.source_trial:
            trial = design.source_trial
            print(f"{trial.sid}\t{trial.name}\t{trial.url}")
        if args.generated_vpops:
            for entry in design.generated_vpops.list_with_details():
                print(
                    json.dumps(
                        {
                            "vpop_sid": entry.vpop.sid,
                            "vpop_url": entry.vpop.url,
                            "design_revision": entry.revision,
                            "options": jsonable(entry.options),
                            "subsampling_fitness": jsonable(entry.subsampling_fitness),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
        return 0
    except (ValueError, RuntimeError, JinkoError) as exc:
        print(f"Subsampling-design inspection failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(
            f"Subsampling-design inspection failed unexpectedly: {exc}", file=sys.stderr
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
