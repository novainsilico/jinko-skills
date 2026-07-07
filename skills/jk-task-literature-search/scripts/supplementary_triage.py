"""Generic supplementary-material triage for standalone literature search outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from common import display_path, require_requests, safe_filename, write_json
except ImportError:  # pragma: no cover
    from .common import display_path, require_requests, safe_filename, write_json


def _select_publisher_adapter(reference: dict[str, Any]) -> str:
    doi = str(reference.get("doi", "")).lower()
    landing_url = str(reference.get("landing_url", "")).lower()
    if reference.get("pmcid"):
        return "pmc"
    if doi.startswith("10.1016/") or "sciencedirect.com" in landing_url:
        return "elsevier"
    if doi.startswith("10.1007/") or "springer" in landing_url:
        return "springer"
    if doi.startswith("10.1002/") or "wiley.com" in landing_url:
        return "wiley"
    if doi.startswith("10.1038/") or "nature.com" in landing_url:
        return "nature"
    return "generic"


def _safe_filename_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or f"supplement_{index}"
    if "." not in name:
        name = f"{name}.bin"
    return safe_filename(name, fallback=f"supplement_{index}.bin")


def _download_supplementary(
    *,
    reference: dict[str, Any],
    output_dir: Path,
    publisher: str,
) -> dict[str, Any]:
    output_abs = output_dir.resolve()
    output_abs.mkdir(parents=True, exist_ok=True)

    urls = reference.get("supplementary_urls", [])
    downloadable_urls = [
        str(url) for url in urls if isinstance(url, str) and url.strip()
    ]
    downloaded_files: list[str] = []
    skipped_links: list[str] = []
    errors: list[str] = []
    requests = require_requests()

    for index, url in enumerate(downloadable_urls, start=1):
        filename = _safe_filename_from_url(url, index)
        destination = output_abs / filename
        try:
            response = requests.get(url, timeout=120)
            if not response.ok:
                skipped_links.append(url)
                errors.append(f"{url}: http_{response.status_code}")
                continue
            destination.write_bytes(response.content)
            downloaded_files.append(display_path(destination))
        except Exception as exc:  # noqa: BLE001
            skipped_links.append(url)
            errors.append(f"{url}: {exc}")

    return {
        "status": "completed",
        "publisher": publisher,
        "doi": reference.get("doi"),
        "downloaded_files": downloaded_files,
        "skipped_links": skipped_links,
        "errors": errors,
        "output_dir": display_path(output_abs),
    }


def _load_references(input_manifest_path: Path) -> list[dict[str, Any]]:
    references_payload: Any = []
    if input_manifest_path.exists():
        references_payload = json.loads(input_manifest_path.read_text(encoding="utf-8"))

    if isinstance(references_payload, list):
        return [item for item in references_payload if isinstance(item, dict)]
    if isinstance(references_payload, dict):
        downloads = references_payload.get("downloads", [])
        if isinstance(downloads, list):
            return [item for item in downloads if isinstance(item, dict)]
    return []


def triage_supplementary_materials(
    *,
    input_manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Download supplementary URLs using generic publisher-grouped routing."""
    output_dir_abs = output_dir.resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    references = _load_references(input_manifest_path)

    items: list[dict[str, Any]] = []
    for reference in references:
        adapter_name = _select_publisher_adapter(reference)
        result = _download_supplementary(
            reference=reference,
            output_dir=output_dir_abs / adapter_name,
            publisher=adapter_name,
        )
        items.append({"adapter": adapter_name, "result": result})

    downloaded_count = sum(
        len(item.get("result", {}).get("downloaded_files", []))
        for item in items
        if isinstance(item, dict)
    )

    summary_path = output_dir_abs / "supplementary_manifest.json"
    summary = {
        "stage": "supplementary-triage",
        "status": "completed",
        "input_manifest_path": display_path(input_manifest_path),
        "input_count": len(references),
        "processed_count": len(items),
        "downloaded_count": downloaded_count,
        "items": items,
    }
    write_json(summary_path, summary)
    return {
        "status": "completed",
        "processed_count": len(items),
        "downloaded_count": downloaded_count,
        "manifest": display_path(summary_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run supplementary triage workflow.")
    parser.add_argument(
        "--selected-references",
        type=Path,
        required=False,
        help="Path to selected references JSON.",
    )
    parser.add_argument(
        "--downloads-manifest",
        type=Path,
        required=False,
        help="Path to downloads_manifest.json from publication download stage.",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Destination directory."
    )
    return parser


def main() -> None:
    """Run supplementary triage workflow from CLI."""
    args = _build_parser().parse_args()
    input_manifest = args.downloads_manifest or args.selected_references
    if input_manifest is None:
        raise ValueError("Provide --downloads-manifest or --selected-references")
    summary = triage_supplementary_materials(
        input_manifest_path=input_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
