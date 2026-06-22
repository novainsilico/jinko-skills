"""ClinicalTrials.gov lookup for standalone trial data scoping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from common import display_path, require_requests, write_json
except ImportError:  # pragma: no cover
    from .common import display_path, require_requests, write_json


def _to_trial_record(study: dict[str, Any]) -> dict[str, str]:
    proto = study.get("protocolSection", {}) if isinstance(study, dict) else {}
    ident = proto.get("identificationModule", {}) if isinstance(proto, dict) else {}
    design = proto.get("designModule", {}) if isinstance(proto, dict) else {}
    status_mod = proto.get("statusModule", {}) if isinstance(proto, dict) else {}
    desc_mod = proto.get("descriptionModule", {}) if isinstance(proto, dict) else {}
    cond_mod = proto.get("conditionsModule", {}) if isinstance(proto, dict) else {}
    arms_mod = (
        proto.get("armsInterventionsModule", {}) if isinstance(proto, dict) else {}
    )
    outcomes_mod = proto.get("outcomesModule", {}) if isinstance(proto, dict) else {}

    nct_id = str(ident.get("nctId", "")).strip()
    phases = design.get("phases", []) if isinstance(design, dict) else []
    phase_text = (
        ", ".join(str(item) for item in phases)
        if isinstance(phases, list) and phases
        else "N/A"
    )
    conditions = cond_mod.get("conditions", []) if isinstance(cond_mod, dict) else []
    condition_text = (
        "; ".join(str(item) for item in conditions)
        if isinstance(conditions, list) and conditions
        else "N/A"
    )
    interventions = (
        arms_mod.get("interventions", []) if isinstance(arms_mod, dict) else []
    )
    intervention_names = []
    if isinstance(interventions, list):
        for item in interventions:
            if isinstance(item, dict) and item.get("name"):
                intervention_names.append(str(item["name"]))
    primary_outcomes = (
        outcomes_mod.get("primaryOutcomes", [])
        if isinstance(outcomes_mod, dict)
        else []
    )
    outcome_names = []
    if isinstance(primary_outcomes, list):
        for item in primary_outcomes:
            if isinstance(item, dict) and item.get("measure"):
                outcome_names.append(str(item["measure"]))
    summary_raw = str(desc_mod.get("briefSummary", "N/A"))
    summary = summary_raw[:150] + ("..." if len(summary_raw) > 150 else "")
    has_results_flag = bool(study.get("hasResults", False)) or "resultsSection" in study

    return {
        "Study Title": str(ident.get("officialTitle", "N/A")),
        "NCT ID": nct_id or "N/A",
        "Study URL": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "N/A",
        "Phase": phase_text,
        "Status": str(status_mod.get("overallStatus", "N/A")),
        "Results?": "Yes" if has_results_flag else "No",
        "Conditions": condition_text,
        "Interventions": "; ".join(intervention_names) if intervention_names else "N/A",
        "Primary Outcomes": "; ".join(outcome_names) if outcome_names else "N/A",
        "Trial Summary": summary,
    }


def find_clinical_trials(
    *,
    query: str,
    output_path: Path,
    max_results: int = 5,
) -> dict[str, Any]:
    """Query ClinicalTrials.gov and persist normalized trial candidates."""
    requests = require_requests()
    safe_max_results = max(1, max_results)
    encoded_query = quote_plus(query)
    ct_url = (
        "https://clinicaltrials.gov/api/v2/studies"
        f"?query.term={encoded_query}&pageSize={safe_max_results}"
    )
    response = requests.get(ct_url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    studies = payload.get("studies", []) if isinstance(payload, dict) else []
    normalized = [
        _to_trial_record(study) for study in studies if isinstance(study, dict)
    ]

    output_abs = output_path.resolve()
    output_payload = {
        "stage": "clinical-trials-discovery",
        "query": query,
        "max_results": safe_max_results,
        "status": "completed",
        "record_count": len(normalized),
        "records": normalized,
        "source_url": ct_url,
    }
    write_json(output_abs, output_payload)

    table_path = output_abs.with_suffix(".table.json")
    write_json(table_path, normalized)
    return {
        "status": "completed",
        "query": query,
        "max_results": safe_max_results,
        "record_count": len(normalized),
        "output": display_path(output_abs),
        "table_output": display_path(table_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ClinicalTrials.gov lookup.")
    parser.add_argument(
        "--query", type=str, required=True, help="ClinicalTrials.gov query term."
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path.")
    parser.add_argument(
        "--max-results", type=int, default=5, help="Max trial candidates."
    )
    return parser


def main() -> None:
    """Run ClinicalTrials.gov lookup from CLI."""
    args = _build_parser().parse_args()
    summary = find_clinical_trials(
        query=args.query,
        output_path=args.output,
        max_results=args.max_results,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
