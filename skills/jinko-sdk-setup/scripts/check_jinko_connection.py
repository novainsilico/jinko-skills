#!/usr/bin/env python3
"""Fail-fast Jinkō SDK installation, configuration, and connection check."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from importlib import metadata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None

API_KEY_HELP_URL = "https://doc.jinko.ai/docs/agentic/sdk-and-skills"
PYPI_JSON_URL = "https://pypi.org/pypi/jinko-sdk/json"
SDK_INSTALL_COMMAND = "python -m pip install --upgrade jinko-sdk"
REQUIRED_ENV = ("JINKO_API_KEY", "JINKO_PROJECT_ID")
ALTERNATE_ENV = ("JINKO_BASE_URL", "JINKO_URL")
SDK_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SDK_REQUIREMENT_RE = re.compile(r"^>=(\d+)\.(\d+),<(\d+)\.0$")
REQUIRES_SDK_LINE_RE = re.compile(r'^  requires_sdk:\s*["\']([^"\']+)["\']\s*$')


def redact(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "<set>"
    return f"{value[:4]}...{value[-4:]}"


def load_local_env() -> bool:
    if load_dotenv is not None:
        load_dotenv()
        return True
    return False


def missing_required_env() -> list[str]:
    return [name for name in REQUIRED_ENV if not os.getenv(name)]


def print_redacted_config() -> None:
    for name in (*REQUIRED_ENV, *ALTERNATE_ENV):
        print(f"{name}={redact(os.getenv(name))}", flush=True)


def installed_sdk_version() -> str | None:
    try:
        return metadata.version("jinko-sdk")
    except metadata.PackageNotFoundError:
        return None


def latest_sdk_version() -> str:
    request = Request(
        PYPI_JSON_URL,
        headers={"Accept": "application/json", "User-Agent": "jinko-sdk-setup-check"},
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed HTTPS host
            payload = json.load(response)
        return payload["info"]["version"]
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(str(exc)) from exc


def parse_sdk_version(version: str) -> tuple[int, int, int] | None:
    match = SDK_VERSION_RE.fullmatch(version)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def canonical_sdk_requirement(version: str) -> str | None:
    parsed = parse_sdk_version(version)
    if parsed is None:
        return None
    major, minor, _ = parsed
    return f">={major}.{minor},<{major + 1}.0"


def check_sdk_installation() -> str | None:
    installed = installed_sdk_version()
    if installed is None:
        print(
            "The jinko-sdk package is not installed in this Python environment. "
            f"Install it with: {SDK_INSTALL_COMMAND}. Do not install the unrelated "
            "package named 'jinko'.",
            file=sys.stderr,
        )
        return None

    if parse_sdk_version(installed) is None:
        print(
            f"The installed jinko-sdk version '{installed}' is not a supported "
            "X.Y.Z release. Install a published release with: "
            f"{SDK_INSTALL_COMMAND}",
            file=sys.stderr,
        )
        return None

    try:
        latest = latest_sdk_version()
    except RuntimeError as exc:
        print(
            "WARNING: Could not check the latest jinko-sdk release on PyPI. "
            "Check network, "
            f"proxy, and TLS access to {PYPI_JSON_URL}, then rerun this script. ({exc})",
            file=sys.stderr,
        )
        return installed

    if installed != latest:
        print(
            f"WARNING: jinko-sdk {installed} is installed, but PyPI reports {latest} as the "
            f"latest release. Upgrade with: {SDK_INSTALL_COMMAND}",
            file=sys.stderr,
        )

    return installed


def read_sdk_requirement(skill_file: Path) -> str | None:
    in_frontmatter = False
    for line in skill_file.read_text(encoding="utf-8").splitlines():
        if line == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if in_frontmatter and (match := REQUIRES_SDK_LINE_RE.fullmatch(line)):
            return match.group(1)
    return None


def requirement_contains(requirement: str, version: str) -> bool | None:
    requirement_match = SDK_REQUIREMENT_RE.fullmatch(requirement)
    parsed_version = parse_sdk_version(version)
    if requirement_match is None or parsed_version is None:
        return None

    lower_major, lower_minor, upper_major = (
        int(part) for part in requirement_match.groups()
    )
    lower = (lower_major, lower_minor, 0)
    upper = (upper_major, 0, 0)
    return lower <= parsed_version < upper


def check_neighbor_skill_requirements(installed: str, skills_dir: Path) -> bool:
    expected = canonical_sdk_requirement(installed)
    if expected is None:
        return False

    compatible = True
    for skill_file in sorted(skills_dir.glob("jinko-*/SKILL.md")):
        requirement = read_sdk_requirement(skill_file)
        if requirement is None:
            continue

        contains = requirement_contains(requirement, installed)
        if contains is None:
            print(
                f"{skill_file.parent.name} has unsupported requires_sdk "
                f"'{requirement}'. Expected the canonical form '{expected}'.",
                file=sys.stderr,
            )
            compatible = False
        elif not contains:
            print(
                f"Installed jinko-sdk {installed} does not satisfy "
                f"{skill_file.parent.name} requires_sdk '{requirement}'. Update the "
                "SDK and Jinkō skills together before using SDK workflows.",
                file=sys.stderr,
            )
            compatible = False
        elif requirement != expected:
            print(
                f"WARNING: {skill_file.parent.name} declares requires_sdk "
                f"'{requirement}', while jinko-sdk {installed} corresponds to "
                f"'{expected}'. The installed version is compatible, but updating "
                "the Jinkō skills bundle is recommended.",
                file=sys.stderr,
            )

    return compatible


def print_missing_config_help(missing: list[str], dotenv_loaded: bool) -> None:
    print(f"Missing required config: {', '.join(missing)}.", file=sys.stderr)

    env_file = Path.cwd() / ".env"
    if env_file.is_file() and not dotenv_loaded:
        print(
            "A .env file exists but python-dotenv is not installed, so this script "
            "cannot load it. Run: python -m pip install python-dotenv",
            file=sys.stderr,
        )
    elif not env_file.is_file():
        template = Path(__file__).resolve().parent.parent / "assets" / ".env.example"
        print(
            f"Create .env from {template} or export the variables in your shell. "
            "Keep API keys out of chat and version control.",
            file=sys.stderr,
        )

    if "JINKO_API_KEY" in missing:
        print(f"Create an API key at {API_KEY_HELP_URL}", file=sys.stderr)

    if (Path.cwd() / ".envrc").is_file():
        print(
            "This directory uses direnv. Ensure .envrc loads .env, then run "
            "'direnv allow' and rerun this script.",
            file=sys.stderr,
        )


def check_environment(dotenv_loaded: bool) -> bool:
    missing = missing_required_env()
    if missing:
        print_missing_config_help(missing, dotenv_loaded)
        return False

    configured_alternates = [name for name in ALTERNATE_ENV if os.getenv(name)]
    if len(configured_alternates) == 1:
        missing_alternate = next(name for name in ALTERNATE_ENV if not os.getenv(name))
        print(
            "Alternate environments require both JINKO_BASE_URL (API endpoint) and "
            f"JINKO_URL (application URL). Set {missing_alternate} so generated links "
            "do not point to the public application.",
            file=sys.stderr,
        )
        return False

    return True


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
            "jinko-sdk is installed but its 'jinko' module cannot be imported. "
            f"Repair this Python environment with: {SDK_INSTALL_COMMAND} ({exc})",
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

    if sys.version_info < (3, 11):
        print(
            f"Python 3.11+ is required; this interpreter is {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 1

    installed = check_sdk_installation()
    if installed is None:
        return 1

    skills_dir = Path(__file__).resolve().parents[2]
    if not check_neighbor_skill_requirements(installed, skills_dir):
        return 1

    dotenv_loaded = load_local_env()

    if args.show_config:
        print_redacted_config()

    if not check_environment(dotenv_loaded):
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
        client.search(
            limit=1,
            show_table=False,
            show_table_hint=False,
        )
    except ConfigurationError as exc:
        print(
            "The SDK rejected the configuration. Check that JINKO_API_KEY and "
            f"JINKO_PROJECT_ID are copied exactly in .env or the shell. ({exc})",
            file=sys.stderr,
        )
        return 2
    except AuthenticationError as exc:
        print(
            "Authentication failed. JINKO_API_KEY may be expired, malformed, or "
            f"copied incorrectly. Create or rotate it at {API_KEY_HELP_URL} ({exc})",
            file=sys.stderr,
        )
        return 3
    except AuthorizationError as exc:
        print(
            "Authorization failed. The API key is valid but does not have access to "
            f"JINKO_PROJECT_ID={redact(os.getenv('JINKO_PROJECT_ID'))}. Check the "
            f"project ID and ask a project administrator to grant access. ({exc})",
            file=sys.stderr,
        )
        return 4
    except JinkoError as exc:
        print(
            "The Jinkō request failed. Verify that JINKO_PROJECT_ID is copied exactly "
            "and that the network can reach JINKO_BASE_URL (or the public Jinkō API), "
            f"then rerun this script. ({exc})",
            file=sys.stderr,
        )
        return 5

    print("jinkō connection and project read access OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
