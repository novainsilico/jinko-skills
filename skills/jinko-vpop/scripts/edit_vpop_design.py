#!/usr/bin/env python3
"""Replace marginal distributions in an existing Jinkō Vpop design.

Dry-run by default. Pass --apply to update the VpopDesign project item.

Uses the design's ``descriptors`` mutator service (``set_distribution`` for
existing descriptors, ``create`` for new ones) rather than replacing the raw
design payload, so each change is validated individually by the API.
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


def load_marginal_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Design JSON must be a list of marginal entries")
    for index, entry in enumerate(data):
        if (
            not isinstance(entry, dict)
            or "id" not in entry
            or "distribution" not in entry
        ):
            raise ValueError(f"Marginal entry {index} must contain id and distribution")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Edit marginal distributions in a Vpop design."
    )
    parser.add_argument(
        "--vpop-design-sid", required=True, help="VpopDesign SID, for example vd-..."
    )
    parser.add_argument(
        "--design",
        required=True,
        help="Replacement JSON list of {id, distribution} entries. Existing "
        "descriptors are updated in place; unseen ids are created.",
    )
    parser.add_argument("--version", default="update vpop design marginals")
    parser.add_argument(
        "--apply", action="store_true", help="Actually update the Vpop design."
    )
    args = parser.parse_args()

    try:
        entries = load_marginal_list(Path(args.design))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid design JSON: {exc}", file=sys.stderr)
        return 1

    print(
        f"Replacement marginal descriptors: {', '.join(entry['id'] for entry in entries)}"
    )
    if not args.apply:
        print(f"Would update Vpop design {args.vpop_design_sid}.")
        print("Run again with --apply to update the design.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError, NotFoundError = sdk

    try:
        client = JinkoClient()
        design = client.get_vpop_design(args.vpop_design_sid)

        diagnostics = design.diagnostics
        if diagnostics.has_errors():
            print("Design has pre-existing sanity errors:", file=sys.stderr)
            print(diagnostics.errors().explain(), file=sys.stderr)

        for entry in entries:
            try:
                descriptor = design.descriptors.get(entry["id"])
                descriptor.set_distribution(entry["distribution"], version=args.version)
                print(f"Updated descriptor {entry['id']!r}")
            except NotFoundError:
                design.descriptors.create(
                    entry["id"], entry["distribution"], version=args.version
                )
                print(f"Created descriptor {entry['id']!r}")

        print(f"Updated Vpop design {design.sid}")
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Vpop design update failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
