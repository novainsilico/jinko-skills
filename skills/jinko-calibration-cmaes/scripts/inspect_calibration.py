#!/usr/bin/env python3
"""Inspect an existing Jinkō calibration: performance, results summary,
objective weights, sorted patients.

Prints raw JSON to stdout; --output-dir additionally writes one JSON file per
requested payload. All payloads are unparsed API responses (see
references/results-and-inspection.md).
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
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def emit(name: str, payload: Any, output_dir: Path | None) -> None:
    print(f"--- {name} (raw, unparsed) ---")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Jinkō calibration.")
    parser.add_argument("--calibration-sid", required=True)
    parser.add_argument("--performance", action="store_true")
    parser.add_argument("--results-summary", action="store_true")
    parser.add_argument("--objective-weights", action="store_true")
    parser.add_argument("--sorted-patients", metavar="SORT_BY")
    parser.add_argument(
        "--output-dir", help="Optional directory to also write JSON files."
    )
    args = parser.parse_args()

    if not any([
        args.performance,
        args.results_summary,
        args.objective_weights,
        args.sorted_patients,
    ]):
        print(
            "Pass at least one of --performance, --results-summary, "
            "--objective-weights, --sorted-patients",
            file=sys.stderr,
        )
        return 1

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        client = JinkoClient()
        calibration = client.get_calibration(args.calibration_sid)

        if args.performance:
            emit("performance", calibration.performance(), output_dir)
        if args.results_summary:
            emit("results_summary", calibration.results_summary(), output_dir)
        if args.objective_weights:
            emit("objective_weights", calibration.objective_weights(), output_dir)
        if args.sorted_patients:
            payload = calibration.results.sorted_patients(sort_by=args.sorted_patients)
            emit("sorted_patients", payload, output_dir)
        return 0
    except (ValueError, RuntimeError, JinkoError) as exc:
        print(f"Calibration inspection failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep diagnostics concise
        print(f"Calibration inspection failed unexpectedly: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
