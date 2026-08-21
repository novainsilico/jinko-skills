"""Search ClinicalTrials.gov v2 and persist raw and normalized trial records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from common import display_path, write_json
except ImportError:  # pragma: no cover
    from .common import display_path, write_json


VALID_STATUSES = {
    "ACTIVE_NOT_RECRUITING",
    "COMPLETED",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
    "RECRUITING",
    "SUSPENDED",
    "TERMINATED",
    "UNKNOWN",
    "WITHDRAWN",
}
VALID_PHASES = {"EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"}


def _list(module: Any, key: str) -> list[Any]:
    value = module.get(key, []) if isinstance(module, dict) else []
    return value if isinstance(value, list) else []


def _names(items: list[Any]) -> list[str]:
    return [
        str(item["name"])
        for item in items
        if isinstance(item, dict) and item.get("name")
    ]


def _arm_labels(items: list[Any]) -> list[str]:
    return [
        str(item["label"])
        for item in items
        if isinstance(item, dict) and item.get("label")
    ]


def _outcomes(items: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "measure": str(item.get("measure") or ""),
            "time_frame": str(item.get("timeFrame") or ""),
            "description": str(item.get("description") or ""),
        }
        for item in items
        if isinstance(item, dict) and item.get("measure")
    ]


def _to_trial_record(study: dict[str, Any], query: str) -> dict[str, Any]:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    conditions = protocol.get("conditionsModule", {})
    design = protocol.get("designModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    sponsors = protocol.get("sponsorCollaboratorsModule", {})
    locations = protocol.get("contactsLocationsModule", {})
    results = study.get("resultsSection", {})

    nct_id = str(identification.get("nctId") or "")
    has_results = bool(study.get("hasResults")) or bool(results)
    primary_outcomes = _outcomes(_list(outcomes, "primaryOutcomes"))
    result_modules = sorted(results) if isinstance(results, dict) else []
    enrollment = design.get("enrollmentInfo", {})
    lead_sponsor = sponsors.get("leadSponsor", {})
    countries = sorted({
        str(location.get("country"))
        for location in _list(locations, "locations")
        if isinstance(location, dict) and location.get("country")
    })

    signals = []
    if has_results:
        signals.append("posted results")
    if primary_outcomes:
        signals.append("primary outcomes")
    if enrollment.get("count") is not None:
        signals.append("enrollment")
    if eligibility.get("eligibilityCriteria"):
        signals.append("eligibility")
    if _list(arms, "interventions"):
        signals.append("interventions")
    if result_modules:
        signals.extend(f"results:{name}" for name in result_modules)

    study_type = str(design.get("studyType") or "")
    if has_results:
        evidence_type = "clinical trial results"
    elif study_type == "OBSERVATIONAL":
        evidence_type = "observational study registry"
    else:
        evidence_type = "clinical trial registry"

    return {
        "nct_id": nct_id,
        "title": str(
            identification.get("officialTitle")
            or identification.get("briefTitle")
            or ""
        ),
        "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        "intent_group": "Data",
        "evidence_type": evidence_type,
        "phase": [str(value) for value in _list(design, "phases")],
        "overall_status": str(status.get("overallStatus") or ""),
        "has_results": has_results,
        "study_type": study_type,
        "conditions": [str(value) for value in _list(conditions, "conditions")],
        "interventions": _names(_list(arms, "interventions")),
        "arms": _arm_labels(_list(arms, "armGroups")),
        "primary_outcomes": primary_outcomes,
        "secondary_outcomes": _outcomes(_list(outcomes, "secondaryOutcomes")),
        "enrollment": enrollment.get("count"),
        "enrollment_type": str(enrollment.get("type") or ""),
        "sex": str(eligibility.get("sex") or ""),
        "minimum_age": str(eligibility.get("minimumAge") or ""),
        "maximum_age": str(eligibility.get("maximumAge") or ""),
        "eligibility_criteria": str(eligibility.get("eligibilityCriteria") or ""),
        "lead_sponsor": str(lead_sponsor.get("name") or ""),
        "countries": countries,
        "brief_summary": str(description.get("briefSummary") or ""),
        "result_modules": result_modules,
        "record_signals": signals,
        "record_completeness": len(signals),
        "query_provenance": [{"angle": query}],
        "access": {
            "has_results": has_results,
            "overall_status": str(status.get("overallStatus") or ""),
        },
    }


def find_clinical_trials(
    *,
    query: str,
    output_path: Path,
    max_results: int = 25,
    statuses: list[str] | None = None,
    phases: list[str] | None = None,
    require_results: bool = False,
) -> dict[str, Any]:
    """Query ClinicalTrials.gov and persist raw and normalized trial candidates."""
    safe_max_results = max(1, min(max_results, 1000))
    fetch_size = (
        min(safe_max_results * 5, 1000)
        if phases or require_results
        else safe_max_results
    )
    params: dict[str, Any] = {
        "query.term": query,
        "pageSize": fetch_size,
        "format": "json",
        "countTotal": "true",
    }
    if statuses:
        params["filter.overallStatus"] = ",".join(statuses)

    source_url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(
        params, doseq=True
    )
    request = Request(source_url, headers={"User-Agent": "jinko-skills/1"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS host
        payload = json.load(response)
        source_url = response.url
    studies = payload.get("studies", []) if isinstance(payload, dict) else []
    if phases:
        requested_phases = set(phases)
        studies = [
            study
            for study in studies
            if isinstance(study, dict)
            and requested_phases.intersection(
                _list(
                    study.get("protocolSection", {}).get("designModule", {}),
                    "phases",
                )
            )
        ]
    if require_results:
        studies = [
            study
            for study in studies
            if isinstance(study, dict)
            and (study.get("hasResults") or study.get("resultsSection"))
        ]
    normalized = [
        _to_trial_record(study, query) for study in studies if isinstance(study, dict)
    ][:safe_max_results]

    output_abs = output_path.resolve()
    raw_path = output_abs.with_suffix(".raw.json")
    table_path = output_abs.with_suffix(".table.json")
    write_json(raw_path, payload)
    write_json(table_path, normalized)
    output_payload = {
        "stage": "clinical-trials-discovery",
        "query": query,
        "filters": {
            "statuses": statuses or [],
            "phases": phases or [],
            "require_results": require_results,
        },
        "max_results": safe_max_results,
        "total_count": payload.get("totalCount") if isinstance(payload, dict) else None,
        "record_count": len(normalized),
        "records": normalized,
        "source_url": source_url,
        "artifacts": {
            "raw": display_path(raw_path),
            "table": display_path(table_path),
        },
    }
    write_json(output_abs, output_payload)
    return {
        "status": "completed",
        "record_count": len(normalized),
        "output": display_path(output_abs),
        "raw_output": display_path(raw_path),
        "table_output": display_path(table_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--status", action="append", choices=sorted(VALID_STATUSES))
    parser.add_argument("--phase", action="append", choices=sorted(VALID_PHASES))
    parser.add_argument("--require-results", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    summary = find_clinical_trials(
        query=args.query,
        output_path=args.output,
        max_results=args.max_results,
        statuses=args.status,
        phases=args.phase,
        require_results=args.require_results,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
