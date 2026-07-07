"""Standalone PubMed and Crossref literature search pipeline entrypoint."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from common import (
        display_path,
        get_json,
        load_env_file,
        normalize_doi,
        require_ncbi_params,
        require_requests,
        write_json,
    )
    from publication_download import download_publications
except ImportError:  # pragma: no cover
    from .common import (
        display_path,
        get_json,
        load_env_file,
        normalize_doi,
        require_ncbi_params,
        require_requests,
        write_json,
    )
    from .publication_download import download_publications

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
ICITE_URL = "https://icite.od.nih.gov/api/pubs"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _extract_pubmed_doi(summary: dict[str, Any]) -> str:
    article_ids = summary.get("articleids", [])
    if isinstance(article_ids, list):
        for item in article_ids:
            if isinstance(item, dict) and str(item.get("idtype", "")).lower() == "doi":
                return normalize_doi(str(item.get("value", "")))
    return ""


def _extract_pubmed_pmcid(summary: dict[str, Any]) -> str:
    article_ids = summary.get("articleids", [])
    if isinstance(article_ids, list):
        for item in article_ids:
            if isinstance(item, dict) and str(item.get("idtype", "")).lower() == "pmc":
                return str(item.get("value", "")).upper()
    return ""


def _crossref_doi_map(crossref_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    message = crossref_payload.get("message", {})
    items = message.get("items", []) if isinstance(message, dict) else []
    doi_map: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return doi_map
    for item in items:
        if not isinstance(item, dict):
            continue
        doi = normalize_doi(str(item.get("DOI", "")))
        if doi:
            doi_map[doi] = item
    return doi_map


def _clean_title(value: str) -> str:
    value = value.strip()
    return re.sub(r"\s+", " ", value) if value else ""


def _date_from_crossref(item: dict[str, Any]) -> str:
    issued = item.get("issued", {}) if isinstance(item, dict) else {}
    date_parts = issued.get("date-parts", []) if isinstance(issued, dict) else []
    if not isinstance(date_parts, list) or not date_parts:
        return ""
    first = date_parts[0]
    if not isinstance(first, list) or not first:
        return ""
    year = int(first[0])
    month = int(first[1]) if len(first) > 1 else 1
    day = int(first[2]) if len(first) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _date_from_pubmed(summary: dict[str, Any]) -> str:
    for key in ("epubdate", "pubdate"):
        raw = str(summary.get(key, "")).strip()
        if not raw:
            continue
        year_match = re.search(r"\b(19|20)\d{2}\b", raw)
        if not year_match:
            continue
        year = int(year_match.group(0))
        month = 1
        day = 1
        lowered = raw.lower()
        for token, month_value in MONTHS.items():
            if re.search(rf"\b{token}[a-z]*\b", lowered):
                month = month_value
                break
        day_match = re.search(r"\b([0-2]?\d|3[0-1])\b", raw)
        if day_match:
            day = int(day_match.group(1))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def _author_full_name(author: dict[str, Any]) -> str:
    given = str(author.get("given", "")).strip()
    family = str(author.get("family", "")).strip()
    if given and family:
        return f"{given} {family}"
    return family or given


def _ama_author_name(author: dict[str, Any]) -> str:
    family = str(author.get("family", "")).strip()
    given = str(author.get("given", "")).strip()
    initials = "".join(part[0] for part in re.findall(r"[A-Za-z]+", given) if part)
    if family and initials:
        return f"{family} {initials}"
    return family or given


def _ama_citation(reference: dict[str, Any], crossref_item: dict[str, Any]) -> str:
    crossref_authors = (
        crossref_item.get("author", []) if isinstance(crossref_item, dict) else []
    )
    author_names: list[str] = []
    if isinstance(crossref_authors, list):
        author_names = [
            _ama_author_name(a) for a in crossref_authors if isinstance(a, dict)
        ]
        author_names = [name for name in author_names if name]
    if len(author_names) > 6:
        author_block = ", ".join(author_names[:3]) + ", et al"
    else:
        author_block = ", ".join(author_names)
    title = str(reference.get("title", "")).strip().rstrip(".")
    journal = str(reference.get("journal_abbreviation", "")).strip().rstrip(".") or str(
        reference.get("journal_title", "")
    ).strip().rstrip(".")
    published_date = str(reference.get("published_date", "")).strip()
    year = published_date[:4] if len(published_date) >= 4 else ""
    volume = str(reference.get("volume", "")).strip()
    issue = str(reference.get("issue", "")).strip()
    pages = str(reference.get("pages", "")).strip()
    vol_issue = ""
    if volume and issue:
        vol_issue = f"{volume}({issue})"
    elif volume:
        vol_issue = volume
    details = ""
    if year and vol_issue and pages:
        details = f"{year};{vol_issue}:{pages}"
    elif year and vol_issue:
        details = f"{year};{vol_issue}"
    elif year:
        details = year
    doi = str(reference.get("doi", "")).strip()
    pmid = str(reference.get("pmid", "")).strip()
    author_block = author_block.rstrip(".")
    segments = [
        segment for segment in [author_block, title, journal, details] if segment
    ]
    citation = ". ".join(segments).strip()
    if citation and not citation.endswith("."):
        citation += "."
    if doi:
        citation += f" doi:{doi}."
    if pmid:
        citation += f" PMID:{pmid}."
    return citation.strip()


def _reference_from_match(
    *,
    pmid: str,
    summary: dict[str, Any],
    crossref_item: dict[str, Any],
    doi: str,
) -> dict[str, Any]:
    pubmed_authors = summary.get("authors", []) if isinstance(summary, dict) else []
    crossref_authors = (
        crossref_item.get("author", []) if isinstance(crossref_item, dict) else []
    )
    author_records: list[dict[str, str]] = []
    if isinstance(pubmed_authors, list):
        for idx, pubmed_author in enumerate(pubmed_authors):
            if not isinstance(pubmed_author, dict):
                continue
            pubmed_name = str(pubmed_author.get("name", "")).strip()
            crossref_full = ""
            if isinstance(crossref_authors, list) and idx < len(crossref_authors):
                crossref_author = crossref_authors[idx]
                if isinstance(crossref_author, dict):
                    crossref_full = _author_full_name(crossref_author)
            author_records.append({"pubmed": pubmed_name, "crossref": crossref_full})

    crossref_title_raw = (
        crossref_item.get("title", []) if isinstance(crossref_item, dict) else []
    )
    crossref_title = ""
    if isinstance(crossref_title_raw, list) and crossref_title_raw:
        crossref_title = str(crossref_title_raw[0]).strip()
    pubmed_title = str(summary.get("title", "")).strip()
    title = crossref_title or _clean_title(pubmed_title)

    crossref_journal_raw = (
        crossref_item.get("container-title", [])
        if isinstance(crossref_item, dict)
        else []
    )
    crossref_journal = ""
    if isinstance(crossref_journal_raw, list) and crossref_journal_raw:
        crossref_journal = str(crossref_journal_raw[0]).strip()
    pubmed_full_journal = str(summary.get("fulljournalname", "")).strip()
    journal_title = crossref_journal or _clean_title(pubmed_full_journal)

    published_date = _date_from_crossref(crossref_item) or _date_from_pubmed(summary)
    volume = (
        str(crossref_item.get("volume", "")).strip()
        or str(summary.get("volume", "")).strip()
    )
    issue = (
        str(crossref_item.get("issue", "")).strip()
        or str(summary.get("issue", "")).strip()
    )
    pages = (
        str(crossref_item.get("page", "")).strip()
        or str(summary.get("pages", "")).strip()
    )
    cited_by = int(crossref_item.get("is-referenced-by-count", 0) or 0)

    reference = {
        "pmid": pmid,
        "doi": doi,
        "pmcid": _extract_pubmed_pmcid(summary) or None,
        "authors": author_records,
        "title": title,
        "journal_title": journal_title,
        "journal_abbreviation": str(summary.get("source", "")).strip(),
        "published_date": published_date,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "type": str(crossref_item.get("type", "")).strip(),
        "publisher": str(crossref_item.get("publisher", "")).strip(),
        "is_referenced_by_count": cited_by,
    }
    reference["ama_citation"] = _ama_citation(reference, crossref_item)
    return reference


def _tokenize_for_ranking(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]+", text)}


def _apply_reference_ranking(
    references: list[dict[str, Any]],
    *,
    query: str,
    objective_keywords: str,
    compartment_keywords: str,
) -> list[dict[str, Any]]:
    objective_tokens = _tokenize_for_ranking(objective_keywords)
    compartment_tokens = _tokenize_for_ranking(compartment_keywords)
    query_tokens = _tokenize_for_ranking(query)
    target_tokens = objective_tokens | compartment_tokens | query_tokens

    if not target_tokens:
        return references

    for reference in references:
        text = " ".join([
            str(reference.get("title", "")),
            str(reference.get("journal_title", "")),
            str(reference.get("ama_citation", "")),
        ])
        tokens = _tokenize_for_ranking(text)
        title_tokens = _tokenize_for_ranking(str(reference.get("title", "")))
        matched = sorted(target_tokens.intersection(tokens))
        title_matched = target_tokens.intersection(title_tokens)
        overlap_score = len(matched)
        title_boost = len(title_matched) * 2
        citation_count = int(reference.get("is_referenced_by_count", 0) or 0)
        citation_boost = min(citation_count, 100) / 25.0
        id_boost = 0.5 if reference.get("pmcid") else 0.0
        score = overlap_score + title_boost + citation_boost + id_boost
        reference["ranking_score"] = round(score, 3)
        reference["ranking_terms_matched"] = matched
        reference["ranking_version"] = "v1"

    return sorted(
        references,
        key=lambda item: float(item.get("ranking_score", 0.0)),
        reverse=True,
    )


def _source_link(reference: dict[str, Any]) -> str:
    doi = str(reference.get("doi", "")).strip()
    if doi:
        return f"https://doi.org/{doi}"
    pmcid = str(reference.get("pmcid", "")).strip()
    if pmcid:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    pmid = str(reference.get("pmid", "")).strip()
    if pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return ""


def _to_year(reference: dict[str, Any]) -> str:
    published = str(reference.get("published_date", "")).strip()
    if len(published) >= 4 and published[:4].isdigit():
        return published[:4]
    return ""


def _relative_link(base_dir: Path, path_value: str) -> str:
    normalized = path_value.strip()
    if not normalized:
        return ""
    path = Path(normalized)
    absolute = path if path.is_absolute() else (Path.cwd() / path).resolve()
    try:
        return str(absolute.relative_to(base_dir.resolve()))
    except ValueError:
        return display_path(absolute)


def _write_readme_summary(
    *,
    output_dir: Path,
    selected_references: list[dict[str, Any]],
    downloads_manifest_path: Path | None,
) -> None:
    download_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if downloads_manifest_path is not None and downloads_manifest_path.exists():
        raw_manifest = json.loads(downloads_manifest_path.read_text(encoding="utf-8"))
        records = (
            raw_manifest.get("downloads", []) if isinstance(raw_manifest, dict) else []
        )
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict):
                    continue
                doi = str(record.get("doi", "")).strip().lower()
                pmid = str(record.get("pmid", "")).strip()
                download_by_key[(doi, pmid)] = record

    header = [
        "# Literature Search",
        "",
        "## Download Summary",
        "",
        "| Year | Article | Title | Ranking | Citations | Journal | PDF | "
        "Source | Supplements | PMCID |",
        "|---|---|---|---:|---:|---|---|---|---|---|",
    ]

    rows: list[str] = []
    for reference in selected_references:
        doi = str(reference.get("doi", "")).strip()
        pmid = str(reference.get("pmid", "")).strip()
        key = (doi.lower(), pmid)
        download = download_by_key.get(key, {})

        article_id = pmid or doi or ""
        title = str(reference.get("title", "")).strip().replace("|", "\\|")
        ranking = str(reference.get("ranking_score", "")).strip()
        citations = str(int(reference.get("is_referenced_by_count", 0) or 0))
        journal = str(reference.get("journal_title", "")).strip().replace("|", "\\|")

        pdf_value = ""
        main_pdf_raw = download.get("downloaded_main_file", "")
        main_pdf = str(main_pdf_raw).strip() if main_pdf_raw is not None else ""
        if main_pdf and main_pdf.lower() != "none":
            rel = _relative_link(output_dir, main_pdf)
            pdf_value = f"[{Path(rel).name}]({rel})"

        source_url = _source_link(reference)
        source_value = f"[link]({source_url})" if source_url else ""

        supp_paths = (
            download.get("supplementary_files", [])
            if isinstance(download, dict)
            else []
        )
        supplements: list[str] = []
        if isinstance(supp_paths, list):
            for supp in supp_paths:
                if not isinstance(supp, str) or not supp:
                    continue
                rel = _relative_link(output_dir, supp)
                supplements.append(f"[{Path(rel).name}]({rel})")
        supplements_value = ", ".join(supplements)

        pmcid = str(reference.get("pmcid", "") or "")
        rows.append(
            "| "
            + " | ".join([
                _to_year(reference),
                article_id.replace("|", "\\|"),
                title,
                ranking,
                citations,
                journal,
                pdf_value,
                source_value,
                supplements_value,
                pmcid,
            ])
            + " |"
        )

    (output_dir / "README.md").write_text(
        "\n".join(header + rows + [""]), encoding="utf-8"
    )


def _print_reference_candidates(references: list[dict[str, Any]]) -> None:
    print("Candidate publications:")
    for index, reference in enumerate(references, start=1):
        title = str(reference.get("title", "")).strip() or "Untitled"
        pmid = str(reference.get("pmid", "")).strip() or "N/A"
        doi = str(reference.get("doi", "")).strip() or "N/A"
        print(f"  [{index}] PMID {pmid} | DOI {doi} | {title}")


def _select_references_human_in_loop(
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not references:
        return []
    _print_reference_candidates(references)
    prompt = "Select publications to keep (all, none, or comma-separated indices like 1,3,5): "
    while True:
        answer = input(prompt).strip().lower()
        if answer == "all":
            return references
        if answer in {"none", ""}:
            return []
        tokens = [token.strip() for token in answer.split(",") if token.strip()]
        if not tokens:
            print("Invalid selection. Enter all, none, or valid indices.")
            continue
        indices: list[int] = []
        valid = True
        for token in tokens:
            if not token.isdigit():
                valid = False
                break
            value = int(token)
            if value < 1 or value > len(references):
                valid = False
                break
            if value not in indices:
                indices.append(value)
        if not valid:
            print("Invalid selection. Enter all, none, or valid indices.")
            continue
        return [references[index - 1] for index in indices]


def _fetch_abstracts_via_efetch(
    pmids: list[str],
    base_params: dict[str, str],
    output_dir: Path,
) -> dict[str, str]:
    """Fetch abstract text for each PMID via PubMed efetch. Returns {pmid: abstract}.

    Structured abstracts (with Label attributes) are concatenated with their labels.
    Best-effort: errors return an empty dict rather than crashing the pipeline.
    """
    if not pmids:
        return {}
    requests = require_requests()
    time.sleep(0.34)  # PubMed rate limit: 3 req/s without API key
    try:
        response = requests.get(
            EFETCH_URL,
            params={
                **base_params,
                "db": "pubmed",
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "xml",
            },
            timeout=60,
        )
        response.raise_for_status()
        xml_text = response.text
    except Exception:
        return {}
    (output_dir / "efetch_abstracts.xml").write_text(xml_text, encoding="utf-8")
    abstracts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return abstracts
    for article in root.iter("PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()
        parts: list[str] = []
        for abs_text in article.findall(".//Abstract/AbstractText"):
            label = abs_text.get("Label", "").strip()
            text = "".join(abs_text.itertext()).strip()
            if not text:
                continue
            parts.append(f"{label}: {text}" if label else text)
        if parts:
            abstracts[pmid] = "\n".join(parts)
    return abstracts


def _fetch_icite_citations(pmids: list[str]) -> dict[str, int]:
    """Fetch citation counts via NIH iCite. Returns {pmid: citation_count}.

    iCite is more reliable than Crossref for PubMed papers, especially older trials.
    Best-effort: errors return what was collected so far rather than crashing.
    """
    if not pmids:
        return {}
    requests = require_requests()
    counts: dict[str, int] = {}
    chunk_size = 500  # iCite accepts up to ~1000 PMIDs per call; 500 is safer
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        try:
            response = requests.get(
                ICITE_URL,
                params={"pmids": ",".join(chunk)},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        data = payload.get("data", [])
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            pmid = str(item.get("pmid", "")).strip()
            count = item.get("citation_count")
            if pmid and isinstance(count, int):
                counts[pmid] = count
    return counts


def _fetch_pmc_text_excerpt(pmcid: str, base_params: dict[str, str]) -> str:
    """Fetch PMC full-text XML and extract Results + Methods sections (truncated).

    Returns up to ~5000 chars of section text, prefixed with section titles.
    Best-effort: errors return empty string.
    """
    if not pmcid:
        return ""
    pmcid_num = pmcid.replace("PMC", "").strip()
    if not pmcid_num:
        return ""
    requests = require_requests()
    time.sleep(0.34)
    try:
        response = requests.get(
            EFETCH_URL,
            params={
                **base_params,
                "db": "pmc",
                "id": pmcid_num,
                "retmode": "xml",
            },
            timeout=60,
        )
        response.raise_for_status()
        xml_text = response.text
    except Exception:
        return ""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    parts: list[str] = []
    keywords = ("result", "method", "discussion", "finding", "outcome")
    for sec in root.iter("sec"):
        # Match by sec-type attribute (common) OR by <title> text (more common in practice).
        sec_type = (sec.get("sec-type", "") or "").lower()
        title_el = sec.find("title")
        title_text = ""
        if title_el is not None:
            title_text = "".join(title_el.itertext()).strip()
        haystack = (sec_type + " " + title_text).lower()
        if not any(k in haystack for k in keywords):
            continue
        text = " ".join(sec.itertext()).strip()
        if text:
            label = title_text or sec_type or "section"
            parts.append(f"[{label}]\n{text[:3000]}")
    return "\n\n".join(parts)[:5000]


def _enrich_references(
    references: list[dict[str, Any]],
    abstracts_by_pmid: dict[str, str],
    icite_by_pmid: dict[str, int],
) -> None:
    """In-place: add `abstract`, `icite_citation_count`; update `is_referenced_by_count`."""
    for ref in references:
        pmid = str(ref.get("pmid", "")).strip()
        if not pmid:
            continue
        if pmid in abstracts_by_pmid:
            ref["abstract"] = abstracts_by_pmid[pmid]
        if pmid in icite_by_pmid:
            icite_count = int(icite_by_pmid[pmid])
            ref["icite_citation_count"] = icite_count
            crossref_count = int(ref.get("is_referenced_by_count") or 0)
            ref["is_referenced_by_count"] = max(crossref_count, icite_count)


def _enrich_references_with_pmc_text(
    references: list[dict[str, Any]],
    base_params: dict[str, str],
) -> int:
    """For each ref with a `pmcid`, fetch PMC text and attach `pmc_text_excerpt`.

    Returns the number of references successfully enriched.
    """
    enriched = 0
    for ref in references:
        pmcid = str(ref.get("pmcid", "")).strip()
        if not pmcid:
            continue
        excerpt = _fetch_pmc_text_excerpt(pmcid, base_params)
        if excerpt:
            ref["pmc_text_excerpt"] = excerpt
            enriched += 1
    return enriched


def run_literature_search(
    *,
    query: str,
    output_dir: Path,
    retmax: int = 50,
    enable_prompt_selection: bool = True,
    enable_publication_download: bool = False,
    enable_ranking: bool = False,
    objective_keywords: str = "",
    compartment_keywords: str = "",
    seed_pmids: list[str] | None = None,
    fetch_pmc_fulltext: bool = False,
    sort: str = "relevance",
) -> dict[str, Any]:
    """Run the standalone literature search pipeline and persist artifacts."""
    load_env_file(Path(".env"))
    output_dir_abs = output_dir.resolve()
    output_dir_abs.mkdir(parents=True, exist_ok=True)

    base_params = require_ncbi_params()
    safe_retmax = max(1, min(retmax, 200))
    allowed_sorts = {"relevance", "pub_date", "Author", "JournalName"}
    safe_sort = sort if sort in allowed_sorts else "relevance"
    esearch_payload = get_json(
        ESEARCH_URL,
        {
            **base_params,
            "db": "pubmed",
            "retmode": "json",
            "retmax": safe_retmax,
            "sort": safe_sort,
            "term": query,
        },
    )
    write_json(output_dir_abs / "esearch.json", esearch_payload)

    id_list = esearch_payload.get("esearchresult", {}).get("idlist", [])
    pmids = (
        [str(item) for item in id_list if str(item).strip()]
        if isinstance(id_list, list)
        else []
    )

    # Seed-PMID extra esearch (calibration-context recovery for known anchors)
    seed_pmid_set: set[str] = set()
    if seed_pmids:
        seed_clean = [str(p).strip() for p in seed_pmids if str(p).strip()]
        if seed_clean:
            seed_query = " OR ".join(f"{p}[uid]" for p in seed_clean)
            seed_payload = get_json(
                ESEARCH_URL,
                {
                    **base_params,
                    "db": "pubmed",
                    "retmode": "json",
                    "retmax": max(len(seed_clean), 1),
                    "term": seed_query,
                },
            )
            write_json(output_dir_abs / "esearch_seed.json", seed_payload)
            seed_ids = seed_payload.get("esearchresult", {}).get("idlist", []) or []
            for sid in seed_ids:
                sid_str = str(sid).strip()
                if sid_str:
                    seed_pmid_set.add(sid_str)
                    if sid_str not in pmids:
                        pmids.append(sid_str)

    esummary_payload: dict[str, Any] = {"result": {"uids": []}}
    if pmids:
        esummary_payload = get_json(
            ESUMMARY_URL,
            {
                **base_params,
                "db": "pubmed",
                "retmode": "json",
                "id": ",".join(pmids),
            },
        )
    write_json(output_dir_abs / "esummary.json", esummary_payload)

    result_block = (
        esummary_payload.get("result", {}) if isinstance(esummary_payload, dict) else {}
    )
    uids = result_block.get("uids", []) if isinstance(result_block, dict) else []
    summary_by_doi: dict[str, tuple[str, dict[str, Any]]] = {}
    if isinstance(uids, list):
        for uid in uids:
            summary = result_block.get(str(uid), {})
            if not isinstance(summary, dict):
                continue
            doi = _extract_pubmed_doi(summary)
            if doi and doi not in summary_by_doi:
                summary_by_doi[doi] = (str(uid), summary)

    crossref_payload: dict[str, Any] = {"message": {"items": []}}
    if summary_by_doi:
        doi_filter = ",".join([f"doi:{doi}" for doi in summary_by_doi])
        crossref_payload = get_json(
            CROSSREF_WORKS_URL,
            {
                "filter": doi_filter,
                "rows": len(summary_by_doi),
            },
        )
    write_json(output_dir_abs / "crossref.json", crossref_payload)

    crossref_by_doi = _crossref_doi_map(crossref_payload)
    references: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()
    for doi, (pmid, summary) in summary_by_doi.items():
        crossref_item = crossref_by_doi.get(doi)
        if not crossref_item:
            continue
        references.append(
            _reference_from_match(
                pmid=pmid,
                summary=summary,
                crossref_item=crossref_item,
                doi=doi,
            )
        )
        seen_pmids.add(pmid)

    if isinstance(uids, list):
        for uid in uids:
            pmid = str(uid).strip()
            if not pmid or pmid in seen_pmids:
                continue
            summary = result_block.get(pmid, {})
            if not isinstance(summary, dict):
                continue
            doi = _extract_pubmed_doi(summary)
            crossref_item = crossref_by_doi.get(doi, {}) if doi else {}
            references.append(
                _reference_from_match(
                    pmid=pmid,
                    summary=summary,
                    crossref_item=crossref_item,
                    doi=doi,
                )
            )
            seen_pmids.add(pmid)

    # Enrich: abstracts via efetch + citation counts via iCite (always on)
    abstracts_by_pmid = _fetch_abstracts_via_efetch(pmids, base_params, output_dir_abs)
    icite_by_pmid = _fetch_icite_citations(pmids)
    _enrich_references(references, abstracts_by_pmid, icite_by_pmid)

    # Optional: PMC full-text excerpt for refs with PMCID
    pmc_enriched_count = 0
    if fetch_pmc_fulltext:
        pmc_enriched_count = _enrich_references_with_pmc_text(references, base_params)

    # Flag seeded refs in their query_provenance so downstream ranking can see them
    if seed_pmid_set:
        for ref in references:
            if str(ref.get("pmid", "")).strip() in seed_pmid_set:
                ref["seeded_anchor"] = True

    references.sort(key=lambda ref: int(ref.get("pmid", "0") or 0), reverse=True)
    if enable_ranking:
        references = _apply_reference_ranking(
            references,
            query=query,
            objective_keywords=objective_keywords,
            compartment_keywords=compartment_keywords,
        )

    selected_references = (
        _select_references_human_in_loop(references)
        if enable_prompt_selection
        else references
    )

    write_json(output_dir_abs / "references.json", references)
    write_json(output_dir_abs / "selected_references.json", selected_references)
    write_json(output_dir_abs / "summary_table.json", references)
    (output_dir_abs / "references_ama.txt").write_text(
        "\n".join(
            item.get("ama_citation", "")
            for item in references
            if item.get("ama_citation")
        )
        + ("\n" if references else ""),
        encoding="utf-8",
    )

    download_summary: dict[str, Any] | None = None
    download_manifest_path: Path | None = None
    if enable_publication_download and selected_references:
        download_output_dir = output_dir_abs / "downloads"
        download_summary = download_publications(
            selected_references_path=output_dir_abs / "selected_references.json",
            output_dir=download_output_dir,
        )
        download_manifest_path = download_output_dir / "downloads_manifest.json"

    artifacts = {
        "esearch.json": display_path(output_dir_abs / "esearch.json"),
        "esummary.json": display_path(output_dir_abs / "esummary.json"),
        "crossref.json": display_path(output_dir_abs / "crossref.json"),
        "references.json": display_path(output_dir_abs / "references.json"),
        "references_ama.txt": display_path(output_dir_abs / "references_ama.txt"),
        "selected_references.json": display_path(
            output_dir_abs / "selected_references.json"
        ),
        "summary_table.json": display_path(output_dir_abs / "summary_table.json"),
        "README.md": display_path(output_dir_abs / "README.md"),
    }
    if (output_dir_abs / "efetch_abstracts.xml").exists():
        artifacts["efetch_abstracts.xml"] = display_path(
            output_dir_abs / "efetch_abstracts.xml"
        )
    if seed_pmid_set and (output_dir_abs / "esearch_seed.json").exists():
        artifacts["esearch_seed.json"] = display_path(
            output_dir_abs / "esearch_seed.json"
        )
    if download_manifest_path is not None:
        artifacts["downloads_manifest.json"] = display_path(download_manifest_path)
    manifest = {
        "stage": "jk-task-literature-search-standalone",
        "query": query,
        "retmax": safe_retmax,
        "sort": safe_sort,
        "selection_mode": "prompt" if enable_prompt_selection else "non_interactive",
        "status": "completed",
        "counts": {
            "pmids": len(pmids),
            "doi_candidates": len(summary_by_doi),
            "crossref_matches": len(references),
            "abstracts_fetched": len(abstracts_by_pmid),
            "icite_enriched": len(icite_by_pmid),
            "pmc_fulltext_enriched": pmc_enriched_count,
            "seeded_anchors": len(seed_pmid_set),
            "selected": len(selected_references),
            "downloaded": (
                int(download_summary.get("downloaded_count", 0))
                if download_summary is not None
                else 0
            ),
        },
        "artifacts": artifacts,
    }
    manifest_path = output_dir_abs / "manifest.json"
    write_json(manifest_path, manifest)
    _write_readme_summary(
        output_dir=output_dir_abs,
        selected_references=selected_references,
        downloads_manifest_path=download_manifest_path,
    )

    return {
        "status": "completed",
        "manifest": display_path(manifest_path),
        "query": query,
        "retmax": safe_retmax,
        "pmids": len(pmids),
        "doi_candidates": len(summary_by_doi),
        "crossref_matches": len(references),
        "selected": len(selected_references),
        "download": download_summary,
        "artifacts": artifacts,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PubMed plus Crossref literature search."
    )
    parser.add_argument("--query", type=str, required=True, help="PubMed query term.")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Artifact destination."
    )
    parser.add_argument(
        "--retmax",
        type=int,
        default=50,
        help=(
            "PubMed max result count per query. "
            "Default 50, hard cap 200 (raised from the previous hard cap of 50). "
            "Above the cap the script silently downcaps; 200 is the sweet spot "
            "where PubMed relevance signal is still meaningful."
        ),
    )
    parser.add_argument(
        "--sort",
        type=str,
        default="relevance",
        choices=["relevance", "pub_date", "Author", "JournalName"],
        help=(
            "PubMed esearch sort order. `relevance` (default) favours recent + "
            "highly cited contemporary work; `pub_date` returns most-recent first "
            "and is the right choice when recovering foundational older papers "
            "(combine with a date range in the query). `Author` / `JournalName` "
            "are niche."
        ),
    )
    parser.add_argument(
        "--no-prompt-selection",
        action="store_true",
        help="Disable interactive candidate selection prompt.",
    )
    parser.add_argument(
        "--enable-publication-download",
        action="store_true",
        help="Download selected publications immediately after selection.",
    )
    parser.add_argument(
        "--enable-ranking",
        action="store_true",
        help="Enable score-based ranking using query/objective/compartment overlaps.",
    )
    parser.add_argument(
        "--objective-keywords",
        type=str,
        default="",
        help="Optional objective keywords for ranking.",
    )
    parser.add_argument(
        "--compartment-keywords",
        type=str,
        default="",
        help="Optional compartment keywords for ranking.",
    )
    parser.add_argument(
        "--seed-pmids",
        type=str,
        default="",
        help=(
            "Comma-separated PMIDs to guarantee in the candidate pool "
            "(calibration-context anchor recovery). Each PMID is added via an "
            "extra esearch using <PMID>[uid] OR clauses."
        ),
    )
    parser.add_argument(
        "--fetch-pmc-fulltext",
        action="store_true",
        help=(
            "For each reference with a PMCID, fetch PMC full-text Results+Methods "
            "section excerpts (truncated to ~5000 chars) and attach as "
            "`pmc_text_excerpt`."
        ),
    )
    return parser


def main() -> None:
    """Run literature search from CLI."""
    args = _build_parser().parse_args()
    seed_pmids_list: list[str] | None = None
    if args.seed_pmids:
        seed_pmids_list = [p.strip() for p in args.seed_pmids.split(",") if p.strip()]
    summary = run_literature_search(
        query=args.query,
        output_dir=args.output_dir,
        retmax=args.retmax,
        enable_prompt_selection=not args.no_prompt_selection,
        enable_publication_download=args.enable_publication_download,
        enable_ranking=args.enable_ranking,
        objective_keywords=args.objective_keywords,
        compartment_keywords=args.compartment_keywords,
        seed_pmids=seed_pmids_list,
        fetch_pmc_fulltext=args.fetch_pmc_fulltext,
        sort=args.sort,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
