"""Helpers for downloading open-access PDFs from the PMC S3 bucket."""

from __future__ import annotations

import re
from importlib import import_module
from typing import Any
from xml.etree import ElementTree

PMC_BUCKET_URL = "https://pmc-oa-opendata.s3.us-east-1.amazonaws.com"
PMCID_REGEX = re.compile(r"^PMC\d+$")
_COMMON_PREFIX_TAG = "{http://s3.amazonaws.com/doc/2006-03-01/}CommonPrefixes"
_PREFIX_TAG = "{http://s3.amazonaws.com/doc/2006-03-01/}Prefix"


def require_requests() -> Any:
    """Import requests only when PMC network operations are used."""
    try:
        return import_module("requests")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "The jk-task-literature-search scripts need the 'requests' package for "
            "network calls. Run them through the repository Nix environment or "
            "install requests in the active Python environment."
        ) from exc


def is_valid_pmcid(value: str) -> bool:
    """Return whether a value matches canonical PMC ID format."""
    return bool(PMCID_REGEX.match(value.strip()))


def list_pmc_revisions(pmcid: str, *, timeout: int = 60) -> list[int]:
    """List available numeric revisions for a PMCID in the PMC S3 bucket."""
    requests = require_requests()
    if not is_valid_pmcid(pmcid):
        raise ValueError(f"Invalid PMC ID format: {pmcid}")

    response = requests.get(
        PMC_BUCKET_URL,
        params={"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"},
        timeout=timeout,
    )
    response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    revisions: list[int] = []
    revision_pattern = re.compile(rf"^{re.escape(pmcid)}\.(\d+)/$")

    for common_prefix in root.findall(_COMMON_PREFIX_TAG):
        prefix_value = common_prefix.findtext(_PREFIX_TAG, default="")
        match = revision_pattern.match(prefix_value)
        if match:
            revisions.append(int(match.group(1)))

    return sorted(set(revisions), reverse=True)


def build_pdf_key(pmcid: str, revision: int) -> str:
    """Build the canonical key for a PMC revision PDF."""
    pmc_version_id = f"{pmcid}.{revision}"
    return f"{pmc_version_id}/{pmc_version_id}.pdf"


def build_pdf_url(pmcid: str, revision: int) -> str:
    """Build the full S3 URL for a PMC revision PDF."""
    return f"{PMC_BUCKET_URL}/{build_pdf_key(pmcid, revision)}"
