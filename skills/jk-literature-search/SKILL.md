---
name: jk-literature-search
description: >-
  Find and shortlist citation-grounded biomedical publication candidates for pharmacometrics work, including PK, PK/PD, PBPK, QSP, exposure-response, translational, and calibration-planning questions. Use this skill whenever the user needs a targeted PubMed publication search strategy, DOI/PMID citation normalization, AMA citation output, publication download triage, or evidence-discovery shortlist before extraction or modeling. Do not use it for ClinicalTrials.gov registry/result scoping, OCR, quantitative endpoint extraction, calibration execution, model building, or full systematic reviews.
compatibility: Check set-up with the `jk-sdk-setup` skill. Requires USER_EMAIL for NCBI identity in .env file; optional NCBI_API_KEY for higher NCBI rate limits.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Literature Search

## Purpose

Use this skill to discover and shortlist public biomedical publications that could inform pharmacometrics work. The output is a search-ready or search-derived publication inventory, not extracted data and not a calibration plan.

The skill is intentionally atomic: it helps answer "which sources should we inspect next?" It does not decide parameter values, extract numeric time courses, fit models, or build a full evidence package.

## Scope

- In scope: clarify the pharmacometrics evidence need, build targeted PubMed queries, run PubMed search and summaries, normalize DOI and citation fields, merge Crossref metadata, format AMA citations, rank publication candidates, prepare a selection shortlist, and optionally attempt open publication download for later reading.
- Out of scope: ClinicalTrials.gov registry/result scoping (use `jk-trial-data-scoping`), OCR (use `jk-mistral-ocr`), quantitative endpoint extraction, curve digitization, data-table creation from already extracted values (use `jk-data-table`), Jinko upload, model build (use `jk-model`), calibration execution, trial execution (use `jk-trial`), and full systematic-review protocol management.

## Workflow

### Step 0 - Clarify The Evidence Need

Before searching, clarify enough modeling context to avoid broad, unusable results. Ask or confirm only what is missing:

1. Drug, intervention, biomarker, or biological pathway of interest.
2. Indication, population, or experimental system.
3. Pharmacometric purpose: PK, PK/PD, PBPK, QSP, exposure-response, dose selection, virtual population construction, translation, or model qualification.
4. Evidence type needed: concentration-time profiles, dosing regimens, response biomarkers, baseline physiology, disease-state descriptors, clinical endpoints, safety readouts, or comparator treatment data.
5. Target population and dose range when they matter for inclusion.
6. Whether the user wants only a search strategy or wants scripts run to produce local artifacts.

If the user gives a document, protocol, slide deck, or project summary, extract the search frame from it first and state the assumptions before proposing queries.

### Step 1 - Build Targeted Queries

Construct small, purposeful query batches instead of one broad query. Separate searches by evidence type when needed.

PubMed pattern:

```text
("drug or pathway"[MeSH Terms] OR "drug or pathway"[tiab] OR "synonym"[tiab])
AND ("indication or population"[MeSH Terms] OR "indication or population"[tiab])
AND ("pharmacokinetics"[tiab] OR "pharmacodynamics"[tiab] OR "biomarker"[tiab] OR "dose-response"[tiab])
```

Adapt the third clause to the evidence need:

- PK: `pharmacokinetics`, `AUC`, `Cmax`, `clearance`, `half-life`, `concentration-time`.
- PK/PD or QSP dynamics: `pharmacodynamics`, `biomarker`, `time course`, `dose-response`, `mechanism`.
- Baseline or virtual population: `baseline`, `cell count`, `physiology`, `disease activity`, `healthy volunteers`, disease subgroup terms.
- Comparator publication evidence: intervention names, synonyms, mechanism class, phase, and target disease terms.
- Translational evidence: `in vitro`, `ex vivo`, animal species, `human`, `translation`, and assay-specific terms.

### Step 2 - Run Search Or Prepare Commands

Use the bundled scripts when the environment has network access and `USER_EMAIL` is set. If live search is not available, give the user concrete PubMed queries and ask for PMIDs, DOIs, abstracts, search exports, or papers to continue from.

Prefer DOI-seeded or title-exact searches when the initial query retrieves off-target literature. Keep the shortlist manageable; this skill is for candidate discovery, not exhaustive review.

### Step 3 - Prioritize Candidate Studies

Prefer candidates that:

- Match the pharmacometric purpose and evidence type from Step 0.
- Report time-course, dose-response, concentration, biomarker, baseline, or endpoint data likely to support later extraction.
- Match the target population, disease state, dose range, route, and regimen.
- Are peer-reviewed publications or credible public datasets.
- Have DOI, PMID, PMCID, or supplementary material identifiers that make follow-up retrieval practical.

Flag candidates as lower priority when they are review-only, mechanistically relevant but non-quantitative, animal-only for a human calibration question, or missing accessible data.

### Step 4 - Present A Shortlist

Return a concise Markdown shortlist and ask the user which sources to inspect next. Include:

- Citation or title.
- Year and source.
- Study type or data source.
- Population or system.
- Intervention, dose, comparator, or pathway.
- Evidence type expected.
- Relevance to the pharmacometric purpose.
- Access notes: DOI, PMID, PMCID, supplement availability when known.
- Priority: high, medium, or low, with one-sentence rationale.

Do not overclaim numeric data availability from titles or abstracts alone. Say "likely contains" or "needs full-text check" when the artifact has not been inspected.

When the user asks for downstream work, keep handoffs precise: `jk-trial-data-scoping` can scope ClinicalTrials.gov registry/results candidates; `jk-mistral-ocr` can help convert PDFs into OCR artifacts; `jk-data-table` can package already extracted observations; `jk-model` can support model-building mechanics. Do not imply this skill or `jk-data-table` digitizes figures, extracts quantitative endpoints, or chooses calibration parameters.

## Scripts

- `scripts/literature_search.py`: PubMed search, PubMed summaries, Crossref merge, ranking, selection, AMA output, and optional download.
- `scripts/publication_download.py`: Downloads selected article PDFs when a PMC or DOI landing page PDF can be resolved.
- `scripts/supplementary_triage.py`: Downloads supplementary files listed in download manifests or selected references.
- `scripts/common.py`: Shared `.env`, path, JSON, retry, and filename helpers.
- `scripts/pmc_open_access.py`: PMC open-access S3 revision helpers.

## Environment

See `assets/.env.example` file


## HITL Checkpoints

Pause for user confirmation at these decision points:

1. After the search frame is clarified, confirm the query strategy when the scope is ambiguous or broad.
2. After candidate references are prepared, ask which publications to keep or download.
3. After downloads are ready, ask whether supplementary triage should be run.

## CLI Usage

Run a PubMed plus Crossref search:

```bash
python skills/jk-literature-search/scripts/literature_search.py \
  --query "semaglutide obesity exposure-response pharmacodynamics" \
  --output-dir literature_search
```

Run non-interactively and keep all candidates:

```bash
python skills/jk-literature-search/scripts/literature_search.py \
  --query "vancomycin population pharmacokinetics renal impairment" \
  --output-dir literature_search \
  --no-prompt-selection
```

Enable simple relevance ranking:

```bash
python skills/jk-literature-search/scripts/literature_search.py \
  --query "low dose IL-2 regulatory T cells systemic lupus erythematosus pharmacodynamics" \
  --output-dir literature_search \
  --enable-ranking \
  --objective-keywords "regulatory T cells IL-2 SLE pharmacodynamics dose-response" \
  --compartment-keywords "blood PBMC CD4 CD8 NK Th17"
```

Download selected publications:

```bash
python skills/jk-literature-search/scripts/publication_download.py \
  --selected-references literature_search/selected_references.json \
  --output-dir literature_downloads
```

Run supplementary triage:

```bash
python skills/jk-literature-search/scripts/supplementary_triage.py \
  --downloads-manifest literature_downloads/downloads_manifest.json \
  --output-dir literature_supplementary
```

Run all available non-Jinko steps from the main script:

```bash
python skills/jk-literature-search/scripts/literature_search.py \
  --query "rifampicin efavirenz drug-drug interaction PBPK clinical pharmacology" \
  --output-dir literature_search \
  --enable-publication-download
```

## Expected Artifacts

The search output directory contains:

- `esearch.json`
- `esummary.json`
- `crossref.json`
- `references.json`
- `references_ama.txt`
- `selected_references.json`
- `summary_table.json`
- `manifest.json`
- `README.md`

Optional publication download output contains:

- `downloads_manifest.json`
- `files/<reference-slug>/main.pdf` when a PDF is downloadable.

Optional supplementary triage output contains:

- `supplementary_manifest.json`
- downloaded supplementary files grouped by inferred publisher.

## Validation Checklist

- `USER_EMAIL` is set or documented in `.env` before PubMed calls.
- The search frame names a pharmacometric purpose and evidence type before selecting studies.
- Candidate selection happens before publication download.
- Prefer DOI-seeded or title-exact query passes when broad keyword queries retrieve off-target literature.
- Only openly downloadable PDFs or landing-page-discovered PDFs are downloaded.
- The final answer distinguishes discovered candidates from extracted, calibration-ready data.
