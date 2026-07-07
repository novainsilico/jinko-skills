"""Publication download utilities for selected standalone literature references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    from common import (
        display_path,
        looks_like_pdf,
        require_requests,
        safe_reference_slug,
        write_json,
    )
    from pmc_open_access import build_pdf_url, list_pmc_revisions
except ImportError:  # pragma: no cover
    from .common import (
        display_path,
        looks_like_pdf,
        require_requests,
        safe_reference_slug,
        write_json,
    )
    from .pmc_open_access import build_pdf_url, list_pmc_revisions

DOWNLOADABLE_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt")


def resolve_doi_to_pmc_url(doi: str) -> str:
    """Use OpenAlex to find a PubMed Central landing page for a DOI."""
    requests = require_requests()
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    locations = payload.get("locations", []) if isinstance(payload, dict) else []
    for location in locations:
        if not isinstance(location, dict):
            continue
        source = location.get("source") or {}
        source_name = source.get("display_name", "") if isinstance(source, dict) else ""
        landing = str(location.get("landing_page_url") or "")
        if "PubMed Central" in source_name or "pmc" in landing.lower():
            if "europepmc.org" in landing:
                article_id = landing.rstrip("/").split("/")[-1]
                return f"https://pmc.ncbi.nlm.nih.gov/articles/{article_id}/"
            if "pmc.ncbi.nlm.nih.gov" in landing and not landing.endswith("/"):
                return f"{landing}/"
            return landing
    raise RuntimeError(f"No PubMed Central landing URL found for DOI {doi}")


def extract_pmc_asset_urls(pmc_url: str) -> dict[str, Any]:
    """Parse a PMC article page for main PDF and supplementary file URLs."""
    requests = require_requests()
    response = requests.get(pmc_url, timeout=60)
    response.raise_for_status()
    html = response.text

    pdf_meta = re.search(r'<meta\s+name="citation_pdf_url"\s+content="([^"]+)"', html)
    if not pdf_meta:
        raise RuntimeError(f"No citation_pdf_url found at {pmc_url}")
    main_pdf_url = pdf_meta.group(1)

    hrefs = re.findall(r'href="([^"]+)"', html)
    supplementary_urls: list[str] = []
    for href in hrefs:
        full = urljoin(pmc_url, href)
        low = full.lower()
        if full == main_pdf_url:
            continue
        if "/bin/" in low or low.endswith(DOWNLOADABLE_SUFFIXES):
            supplementary_urls.append(full)

    deduped: list[str] = []
    for link in supplementary_urls:
        if link not in deduped:
            deduped.append(link)

    return {
        "pmc_url": pmc_url,
        "main_pdf_url": main_pdf_url,
        "supplementary_urls": deduped,
    }


def _extract_pdf_link_from_html(landing_url: str, html: str) -> str:
    meta_match = re.search(r'<meta\s+name="citation_pdf_url"\s+content="([^"]+)"', html)
    if meta_match:
        return str(meta_match.group(1)).strip()
    href_match = re.search(r'href="([^"]+\.pdf(?:\?[^"]*)?)"', html, re.IGNORECASE)
    if href_match:
        return urljoin(landing_url, str(href_match.group(1)).strip())
    return ""


def _download_pdf_with_validation(url: str, destination: Path) -> Path:
    requests = require_requests()
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    if not looks_like_pdf(response.content):
        raise RuntimeError(f"Downloaded content is not a valid PDF from {url}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return destination


def _safe_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "supplement"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name.split("?", 1)[0])


def _download_pmc_assets_with_validation(
    *, pmc_url: str, item_output_dir: Path
) -> dict[str, Any]:
    assets = extract_pmc_asset_urls(pmc_url)
    main_pdf = _download_pdf_with_validation(
        assets["main_pdf_url"], item_output_dir / "main.pdf"
    )
    rejected_files: list[dict[str, str]] = []
    supplementary_files: list[str] = []
    for supp_url in assets.get("supplementary_urls", []):
        if not isinstance(supp_url, str):
            continue
        lower_url = supp_url.lower()
        if not lower_url.endswith(".pdf") and ".pdf?" not in lower_url:
            continue
        target_path = item_output_dir / _safe_name_from_url(supp_url)
        try:
            _download_pdf_with_validation(supp_url, target_path)
            supplementary_files.append(display_path(target_path))
        except Exception as exc:  # noqa: BLE001
            if target_path.exists():
                target_path.unlink()
            rejected_files.append({
                "url": supp_url,
                "path": display_path(target_path),
                "reason": str(exc),
            })

    return {
        "main_pdf": main_pdf,
        "supplementary_files": supplementary_files,
        "supplementary_urls": [
            url for url in assets.get("supplementary_urls", []) if isinstance(url, str)
        ],
        "rejected_files": rejected_files,
    }


def _cleanup_stale_pdf_files(item_output_dir: Path) -> None:
    if not item_output_dir.exists():
        return
    for path in item_output_dir.glob("*.pdf"):
        if path.name != "main.pdf":
            path.unlink()


def _download_from_pmc_s3(
    *,
    pmcid: str,
    item_output_dir: Path,
    doi: str,
    pmid: str,
) -> dict[str, Any]:
    revisions = list_pmc_revisions(pmcid)
    if not revisions:
        raise RuntimeError(f"No revision found for {pmcid}")

    attempts: list[dict[str, Any]] = []
    for revision in revisions:
        pdf_url = build_pdf_url(pmcid, revision)
        try:
            main_pdf = _download_pdf_with_validation(
                pdf_url, item_output_dir / "main.pdf"
            )
            pmc_version_id = f"{pmcid}.{revision}"
            return {
                "status": "downloaded",
                "strategy": "pmc_s3",
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "pmc_version_id": pmc_version_id,
                "landing_url": pdf_url,
                "downloaded_main_file": display_path(main_pdf),
                "local_file": str(main_pdf.resolve()),
                "supplementary_files": [],
                "supplementary_urls": [],
                "pmc_attempts": attempts,
                "rejected_files": [],
            }
        except Exception as exc:  # noqa: BLE001
            attempts.append({"revision": revision, "url": pdf_url, "error": str(exc)})

    raise RuntimeError(f"No downloadable PDF revision found for {pmcid}: {attempts}")


def _download_via_doi_landing(
    reference: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    doi = str(reference.get("doi", "")).strip()
    if not doi:
        return {
            "status": "error",
            "strategy": "doi_landing",
            "error": "missing_doi",
            "downloaded_main_file": None,
            "supplementary_files": [],
            "supplementary_urls": [],
            "rejected_files": [],
        }
    try:
        requests = require_requests()
        landing_response = requests.get(f"https://doi.org/{doi}", timeout=120)
        landing_response.raise_for_status()
        landing_url = str(landing_response.url)
        pdf_url = _extract_pdf_link_from_html(landing_url, landing_response.text)
        if not pdf_url:
            return {
                "status": "error",
                "strategy": "doi_landing",
                "error": "no_pdf_link_found",
                "landing_url": landing_url,
                "downloaded_main_file": None,
                "supplementary_files": [],
                "supplementary_urls": [],
                "rejected_files": [],
            }

        slug = safe_reference_slug(reference, 0)
        main_path = output_dir / slug / "main.pdf"
        _download_pdf_with_validation(pdf_url, main_path)
        return {
            "status": "downloaded",
            "strategy": "doi_landing",
            "landing_url": landing_url,
            "downloaded_main_file": display_path(main_path),
            "local_file": str(main_path.resolve()),
            "supplementary_files": [],
            "supplementary_urls": [],
            "rejected_files": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "strategy": "doi_landing",
            "error": str(exc),
            "downloaded_main_file": None,
            "supplementary_files": [],
            "supplementary_urls": [],
            "rejected_files": [],
        }


def _download_single_reference(
    reference: dict[str, Any],
    output_dir: Path,
    index: int,
) -> dict[str, Any]:
    slug = safe_reference_slug(reference, index)
    item_output_dir = output_dir / slug
    _cleanup_stale_pdf_files(item_output_dir)

    pmcid_raw = reference.get("pmcid")
    doi_raw = reference.get("doi")
    pmcid = str(pmcid_raw).strip() if pmcid_raw else ""
    doi = str(doi_raw).strip() if doi_raw else ""
    pmc_error = ""

    pmc_url = ""
    if pmcid:
        try:
            return _download_from_pmc_s3(
                pmcid=pmcid,
                item_output_dir=item_output_dir,
                doi=doi,
                pmid=str(reference.get("pmid", "")).strip(),
            )
        except Exception as exc:  # noqa: BLE001
            pmc_error = f"pmc_s3_failed: {exc}"
        pmc_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    elif doi:
        try:
            pmc_url = resolve_doi_to_pmc_url(doi)
        except Exception:  # noqa: BLE001
            pmc_url = ""

    if pmc_url:
        try:
            downloaded = _download_pmc_assets_with_validation(
                pmc_url=pmc_url,
                item_output_dir=item_output_dir,
            )
            main_pdf = downloaded.get("main_pdf")
            return {
                "status": "downloaded",
                "strategy": "pmc",
                "doi": doi,
                "pmid": str(reference.get("pmid", "")).strip(),
                "pmcid": pmcid or None,
                "landing_url": pmc_url,
                "downloaded_main_file": (
                    display_path(main_pdf) if isinstance(main_pdf, Path) else None
                ),
                "local_file": str(main_pdf.resolve())
                if isinstance(main_pdf, Path)
                else "",
                "supplementary_files": downloaded.get("supplementary_files", []),
                "supplementary_urls": downloaded.get("supplementary_urls", []),
                "rejected_files": downloaded.get("rejected_files", []),
            }
        except Exception as exc:  # noqa: BLE001
            if pmc_error:
                pmc_error = f"{pmc_error}; pmc_html_failed: {exc}"
            else:
                pmc_error = f"pmc_html_failed: {exc}"
    else:
        pmc_error = pmc_error or "no_pmc_resolution"

    doi_result = _download_via_doi_landing(reference, output_dir)
    return {
        "doi": doi,
        "pmid": str(reference.get("pmid", "")).strip(),
        "pmcid": pmcid or None,
        "pmc_error": pmc_error,
        **doi_result,
    }


def download_publications(
    *,
    selected_references_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Download publications from selected references and persist a manifest."""
    output_dir_abs = output_dir.resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)

    selected_payload: Any = []
    if selected_references_path.exists():
        selected_payload = json.loads(
            selected_references_path.read_text(encoding="utf-8")
        )

    references = selected_payload if isinstance(selected_payload, list) else []
    downloads: list[dict[str, Any]] = []
    for index, reference in enumerate(references, start=1):
        if isinstance(reference, dict):
            downloads.append(
                _download_single_reference(reference, output_dir_abs / "files", index)
            )

    downloaded_ok = sum(1 for item in downloads if item.get("status") == "downloaded")

    manifest_path = output_dir_abs / "downloads_manifest.json"
    manifest = {
        "stage": "publication-download",
        "selected_references_path": display_path(selected_references_path),
        "selected_count": len(references),
        "downloaded_count": downloaded_ok,
        "status": "completed",
        "downloads": downloads,
        "artifacts": {
            "downloads_manifest": display_path(manifest_path),
            "downloaded_files": display_path(output_dir_abs / "files"),
        },
    }
    write_json(manifest_path, manifest)
    return {
        "status": "completed",
        "manifest": display_path(manifest_path),
        "selected_count": len(references),
        "downloaded_count": downloaded_ok,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run publication download workflow.")
    parser.add_argument(
        "--selected-references",
        type=Path,
        required=True,
        help="Path to selected references JSON.",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Destination directory."
    )
    return parser


def main() -> None:
    """Run publication download workflow from CLI."""
    args = _build_parser().parse_args()
    summary = download_publications(
        selected_references_path=args.selected_references,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
