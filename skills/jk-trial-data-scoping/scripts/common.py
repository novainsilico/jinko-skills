"""Minimal helpers for the ClinicalTrials.gov scoping skill."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any


def require_requests() -> Any:
    """Import requests only when network operations are actually used."""
    try:
        return import_module("requests")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "The jk-trial-data-scoping scripts need the 'requests' package for "
            "network calls. Run them through the repository Nix environment or "
            "install requests in the active Python environment."
        ) from exc


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON artifact with stable indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def display_path(path: Path) -> str:
    """Return a path relative to cwd when possible, otherwise absolute."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(resolved)
