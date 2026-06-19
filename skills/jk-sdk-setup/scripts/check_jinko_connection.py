#!/usr/bin/env python3
"""Fail-fast Jinkō SDK connection check.

This script validates that local environment variables are present, can build a
JinkoClient, and have enough project access to list models.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None

API_KEY_HELP_URL = "https://doc.jinko.ai/docs/api/"


def redact(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "<set>"
    return f"{value[:4]}...{value[-4:]}"


def load_local_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def missing_required_env() -> list[str]:
    return [
        name for name in ("JINKO_API_KEY", "JINKO_PROJECT_ID") if not os.getenv(name)
    ]


def print_redacted_config() -> None:
    print(f"JINKO_API_KEY={redact(os.getenv('JINKO_API_KEY'))}", flush=True)
    print(f"JINKO_PROJECT_ID={redact(os.getenv('JINKO_PROJECT_ID'))}", flush=True)


def load_jinko_sdk():
    try:
        from jinko import JinkoClient
        from jinko.exceptions import (
            AuthenticationError,
            AuthorizationError,
            ConfigurationError,
            JinkoError,
        )
    except ImportError as exc:
        print(
            "Cannot import jinko. Install the SDK in this Python environment: "
            "pip install jinko python-dotenv",
            file=sys.stderr,
        )
        return None

    return (
        JinkoClient,
        ConfigurationError,
        AuthenticationError,
        AuthorizationError,
        JinkoError,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Jinkō SDK authentication.")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print redacted configuration before checking the connection.",
    )
    args = parser.parse_args()

    load_local_env()

    if args.show_config:
        print_redacted_config()

    missing = missing_required_env()
    if missing:
        names = ", ".join(missing)
        if "JINKO_API_KEY" in missing:
            print(
                f"Missing required config: {names}. Create an API key: {API_KEY_HELP_URL}",
                file=sys.stderr,
            )
        else:
            print(f"Missing required config: {names}.", file=sys.stderr)
        return 2

    sdk = load_jinko_sdk()
    if sdk is None:
        return 1
    (
        JinkoClient,
        ConfigurationError,
        AuthenticationError,
        AuthorizationError,
        JinkoError,
    ) = sdk

    try:
        client = JinkoClient()
        client.auth_check()
    except ConfigurationError as exc:
        print(f"Missing or invalid config; check .env: {exc}", file=sys.stderr)
        return 2
    except AuthenticationError as exc:
        print(
            f"Auth refused; check JINKO_API_KEY. Create or rotate a key: {API_KEY_HELP_URL} ({exc})",
            file=sys.stderr,
        )
        return 3
    except AuthorizationError as exc:
        print(
            f"Auth refused; check JINKO_PROJECT_ID and project access: {exc}",
            file=sys.stderr,
        )
        return 4
    except JinkoError as exc:
        print(
            f"Jinkō SDK request failed; check project ID, network, and API access: {exc}",
            file=sys.stderr,
        )
        return 5

    print("jinkō connection OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
