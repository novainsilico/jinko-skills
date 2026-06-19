#!/usr/bin/env python3
"""Replace marginal distributions in an existing Jinkō Vpop design.

Dry-run by default. Pass --apply to update the VpopDesign project item.
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
        from jinko.exceptions import JinkoError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


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


def replace_marginals(
    payload: dict[str, Any], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    updated = json.loads(json.dumps(payload))
    if updated.get("tag") != "VpopGeneratorFromDesign":
        raise ValueError(
            "Only VpopGeneratorFromDesign payloads are supported by this script"
        )
    contents = updated.setdefault("contents", {})
    contents["marginalDistributions"] = [
        {"id": entry["id"], "distribution": entry["distribution"]} for entry in entries
    ]
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Edit marginal distributions in a Vpop design."
    )
    parser.add_argument(
        "--vpop-generator-sid", required=True, help="VpopDesign SID, for example vd-..."
    )
    parser.add_argument(
        "--design",
        required=True,
        help="Replacement JSON list of {id, distribution} entries.",
    )
    parser.add_argument("--version-name", default="update vpop design marginals")
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
        print(f"Would update Vpop design {args.vpop_generator_sid}.")
        print("Run again with --apply to update the design.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        generator = client.get_vpop_generator(args.vpop_generator_sid)
        payload = replace_marginals(generator.content(), entries)
        updated_item = generator.update_raw(payload, version_name=args.version_name)
        print(f"Updated Vpop design {updated_item.sid}")
        return 0
    except (ValueError, JinkoError) as exc:
        print(f"Vpop design update failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
