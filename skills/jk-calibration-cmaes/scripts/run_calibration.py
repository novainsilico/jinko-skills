#!/usr/bin/env python3
"""Run and poll an existing Jinkō calibration.

Dry-run by default (prints current status). Pass --apply to launch and poll.
"""

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
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and poll a Jinkō calibration.")
    parser.add_argument("--calibration-sid", required=True)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--apply", action="store_true", help="Launch the calibration.")
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        calibration = client.get_calibration(args.calibration_sid)
        print(f"Calibration: {calibration.sid}")
        print(json.dumps(calibration.status(), indent=2, sort_keys=True))

        if not args.apply:
            print("Not launched. Pass --apply to run.")
            return 0

        calibration.run()
        final_status = calibration.wait_until_completed(
            timeout=args.timeout, poll_interval=args.poll_interval
        )
        print("Final status:")
        print(json.dumps(final_status, indent=2, sort_keys=True))
        if isinstance(final_status, dict) and final_status.get("status") != "completed":
            print("Calibration did not complete successfully.", file=sys.stderr)
            return 3
        return 0
    except (ValueError, RuntimeError, TimeoutError, JinkoError) as exc:
        print(f"Calibration run failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep diagnostics concise
        print(f"Calibration run failed unexpectedly: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
