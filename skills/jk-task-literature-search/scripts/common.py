"""Shared helpers for the standalone literature search skill."""

from __future__ import annotations

import json
import os
import re
import time
from importlib import import_module
from pathlib import Path
from typing import Any


def load_env_file(path: Path = Path(".env")) -> None:
    """Load simple KEY=value pairs from a dotenv file without overriding env vars."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def require_ncbi_params() -> dict[str, str]:
    """Return NCBI identity parameters from the environment."""
    email = os.environ.get("USER_EMAIL", "").strip()
    if not email:
        raise ValueError("Missing USER_EMAIL environment variable")
    params = {"email": email}
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    return params


def require_requests() -> Any:
    """Import requests only when network operations are actually used."""
    try:
        return import_module("requests")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "The jk-task-literature-search scripts need the 'requests' package for "
            "network calls. Run them through the repository Nix environment or "
            "install requests in the active Python environment."
        ) from exc


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    """Fetch a JSON object with simple retries for transient HTTP failures."""
    requests = require_requests()
    last_error: Exception | None = None
    for attempt in range(1, 6):
        response = requests.get(url, params=params, timeout=timeout)
        status_code = int(getattr(response, "status_code", 200) or 200)
        if status_code in {429, 500, 502, 503, 504}:
            retry_after = str(response.headers.get("Retry-After", "")).strip()
            try:
                delay = (
                    float(retry_after) if retry_after else min(2 ** (attempt - 1), 16)
                )
            except ValueError:
                delay = min(2 ** (attempt - 1), 16)
            last_error = requests.HTTPError(
                f"Transient HTTP status {status_code} from {url}", response=response
            )
            if attempt < 5:
                time.sleep(delay)
                continue
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected JSON payload from {url}: {type(payload)}")
        return payload
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unexpected failure while fetching JSON from {url}")


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


def safe_filename(value: str, *, fallback: str = "downloaded_file") -> str:
    """Return a filesystem-safe filename or slug."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    return cleaned or fallback


def safe_reference_slug(reference: dict[str, Any], index: int) -> str:
    """Return a stable directory slug for one literature reference."""
    doi = str(reference.get("doi", "")).strip().lower()
    if doi:
        return safe_filename(doi.replace("/", "_"), fallback=f"reference_{index}")
    pmid = str(reference.get("pmid", "")).strip()
    if pmid:
        return f"pmid_{safe_filename(pmid, fallback=str(index))}"
    return f"reference_{index}"


def normalize_doi(raw: str | None) -> str:
    """Normalize DOI text for matching across PubMed and Crossref."""
    if not raw:
        return ""
    doi = raw.strip().lower()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:")
    return doi.rstrip(".,;) ")


def looks_like_pdf(content: bytes) -> bool:
    """Return whether bytes look like a real PDF payload."""
    trimmed = content.lstrip()
    return trimmed.startswith(b"%PDF-") and b"obj" in trimmed[:4096]
