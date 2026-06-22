---
name: jk-trial-data-scoping
description: >-
  Scope public ClinicalTrials.gov registry and results records for pharmacometrics and clinical evidence planning. Use this skill whenever the user needs ClinicalTrials.gov query framing, NCT candidate discovery, trial status/phase/result availability screening, endpoint and population inventory, control-arm or comparator trial scoping, or a registry-derived trial evidence shortlist. Do not use it for PubMed publication discovery, Jinko trial execution, protocol authoring, OCR, quantitative endpoint extraction, calibration execution, model building, or full systematic reviews.
compatibility: Check set-up with the `jk-sdk-setup` skill. Uses the public ClinicalTrials.gov v2 API and does not require credentials.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Trial Data Scoping

## Purpose

Use this skill to discover and shortlist public ClinicalTrials.gov registry and results records that could inform pharmacometrics work. The output is a trial-candidate inventory and data-availability screen, not extracted endpoint data and not a Jinko trial execution plan.

The skill is intentionally atomic: it helps answer "which registered trials should we inspect next, and what registry/result data might be available?" It does not execute Jinko trials, author protocols, fit models, extract numeric endpoint tables, or replace full clinical evidence review.

## Scope

- In scope: clarify the trial evidence need, build ClinicalTrials.gov queries, run ClinicalTrials.gov v2 study search, normalize NCT IDs and registry links, screen status/phase/results availability, summarize intervention and population fit from registry records, prepare endpoint/result-availability notes, and rank trial candidates for follow-up.
- Out of scope: PubMed publication discovery (use `jk-literature-search`), Jinko trial execution or simulation work (use `jk-trial`), protocol authoring (use `jk-protocol`), OCR (use `jk-mistral-ocr`), quantitative endpoint extraction, curve digitization, data-table creation from already extracted values (use `jk-data-table`), model build (use `jk-model`), calibration execution, and full systematic-review protocol management.

## Workflow

### Step 0 - Clarify The Trial Evidence Need

Before searching, clarify enough trial context to avoid broad, unusable results. Ask or confirm only what is missing:

1. Intervention, comparator, mechanism class, or treatment regimen of interest.
2. Condition, indication, population, subgroup, or disease stage.
3. Pharmacometric or evidence-planning purpose: endpoint scoping, comparator/control-arm evidence, trial enrichment, dose/regimen context, population extrapolation, safety signal scoping, or market-access support.
4. Trial attributes needed: phase, recruitment status, completion status, posted results, arms/interventions, outcome measures, eligibility criteria, enrollment size, or study design.
5. Whether the user wants only a search strategy or wants scripts run to produce local artifacts.

If the user gives a document, protocol, slide deck, or project summary, extract the trial scoping frame from it first and state assumptions before proposing queries.

### Step 1 - Build ClinicalTrials.gov Queries

Construct small, purposeful query batches instead of one broad query. Separate searches by comparator, mechanism class, population, or trial purpose when needed.

ClinicalTrials.gov strategy:

- Query term: combine intervention, condition, population, comparator, endpoint, or mechanism class terms.
- Prefer specific intervention and condition terms first; broaden to mechanism class or standard-of-care terms only when the first pass is too sparse.
- Prioritize `Completed`, `Active, not recruiting`, or `Terminated` studies with posted results when the user needs endpoint values or control-arm outcomes.
- Include earlier phase or not-yet-posted studies when the user needs development landscape, dose/regimen context, or safety-signal scoping.

### Step 2 - Run Search Or Prepare Commands

Use the bundled script when the environment has network access. If live search is not available, give the user concrete ClinicalTrials.gov queries and ask for NCT IDs, registry exports, or trial summaries to continue from.

Keep the shortlist manageable; this skill is for candidate scoping, not exhaustive review.

### Step 3 - Prioritize Trial Candidates

Prefer candidates that:

- Match the condition, population, intervention, comparator, and trial purpose from Step 0.
- Have posted ClinicalTrials.gov results when the user needs endpoint or control-arm outcome availability.
- Report relevant outcome measures, arms/interventions, eligibility criteria, enrollment, phase, status, and study design fields.
- Use a regimen, route, dose range, population, endpoint, or comparator likely to support later extraction or modeling context.

Flag candidates as lower priority when they are off-population, wrong line of therapy, not interventional when intervention evidence is required, missing posted results for an endpoint scoping request, or too early/terminated to support the stated evidence need.

### Step 4 - Present A Trial Inventory

Return a concise Markdown shortlist and ask the user which trials to inspect next. Include:

- NCT ID and ClinicalTrials.gov link.
- Official title.
- Phase, status, and results availability.
- Condition and target population.
- Intervention, comparator, arms, or regimen when available.
- Outcome or endpoint categories expected from the registry.
- Relevance to the pharmacometric or evidence-planning purpose.
- Priority: high, medium, or low, with one-sentence rationale.
- Follow-up notes: whether to inspect posted results, eligibility, outcome measures, publications, or sponsor materials next.

Do not overclaim numeric data availability from registry metadata alone. Say "posted results may contain" or "needs registry/results inspection" when the result tables have not been inspected.

When the user asks for adjacent work, keep handoffs precise: `jk-literature-search` can find peer-reviewed publications linked to the trial question; `jk-trial` supports Jinko trial execution; `jk-protocol` supports protocol work. Do not imply this skill extracts quantitative endpoint values, builds models, or executes trials.

## Scripts

- `scripts/clinical_trials.py`: ClinicalTrials.gov v2 study search and normalized table output.
- `scripts/common.py`: Minimal path, JSON, and optional dependency helpers duplicated for standalone packaging.

## Environment

See `assets/.env.example` file.

## HITL Checkpoints

Pause for user confirmation at these decision points:

1. After the trial scoping frame is clarified, confirm the query strategy when the scope is ambiguous or broad.
2. After candidate trials are prepared, ask which NCT records to inspect next.
3. Before expanding from intervention-specific queries to broader mechanism-class or comparator-landscape queries.
4. Before handing off to publication discovery, Jinko trial execution, protocol authoring, or extraction workflows.

## CLI Usage

Run ClinicalTrials.gov discovery:

```bash
python skills/jk-trial-data-scoping/scripts/clinical_trials.py \
  --query "pembrolizumab melanoma exposure response" \
  --max-results 5 \
  --output trial_data_scoping/clinical_trials.json
```

Run a control-arm scoping query:

```bash
python skills/jk-trial-data-scoping/scripts/clinical_trials.py \
  --query "rare disease natural history placebo completed has results" \
  --max-results 10 \
  --output trial_data_scoping/control_arm_trials.json
```

## Expected Artifacts

The output path produces:

- `clinical_trials.json`
- A sibling `*.table.json` normalized table file.

## Validation Checklist

- The trial scoping frame names condition, intervention/comparator, population, and purpose before ranking trials.
- ClinicalTrials.gov is treated as a registry/results source, not as peer-reviewed publication discovery.
- Candidate prioritization distinguishes registry metadata from inspected posted results.
- The final answer distinguishes scoped trial candidates from extracted, analysis-ready endpoint data.
- Handoffs to `jk-literature-search`, `jk-trial`, `jk-protocol`, `jk-data-table`, and `jk-model` are precise and non-overlapping.
