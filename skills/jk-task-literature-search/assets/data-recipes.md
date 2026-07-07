# Data Recipes

Per-group recipes for the **Data** intent group of `jk-task-literature-search`. Consumed by Step 1 (query construction) and Step 3 (priority + verification) of the parent `SKILL.md`. Reuse the Entity Table, the triangulation rule, and the single-pass search defined in the spine — only Data-specific patterns live here.

For the meaning of the PubMed primitives (`[mh]`, `[pt]`, `[ta]`, `[tiab]`, `[PDat]`, `[lang]`, `humans[mh]` / `animals[mh]`, etc.) used in the recipes below, see `pubmed-primitives.md`.

## Data Queries

### Required Data-context inputs (Step 0 must elicit or inherit these before queries are built)

Data papers are found by precise specification — generic "find me data on diabetes" produces an off-target shortlist no matter how good the methodology is. Before issuing any Data query, confirm the following.

**Hard requirements — stop and ask if any is missing**:

- **The variable(s) to inform.** The specific model parameter or model observable the data must anchor (e.g. `cG postprandial peak`, `HR mortality`, `NT-proBNP change-from-baseline`). Without this, the *Outcome / endpoint* facet has nothing to bind to.
- **Population × disease-state precision.** Not just the disease label — also the potential cohort descriptors that matter for the calibration target (severity descriptors, treatment-naive vs treatedk etc*, etc.).
- **Calibration mode** — single-reference-patient (means + SDs per arm are sufficient) vs population-distribution / Vpop matching (needs IPD, detailed within-arm distributions, or detailed subgroup tables).

**Where these inputs come from**:

- When invoked from `nova-workflow-calib-plan`, all four hard requirements come from the step plan — the variable(s) from the *Parameters to calibrate* table, the population from the RP / RPop definition, the calibration mode from the *Strategy* section, and the comparator structure from the step's scenarios.
- When invoked from `nova-workflow-project-scoping`, hard requirements come from the project plan's step entries (looser; ask the user to refine when the step is not yet fully scoped).
- When invoked ad-hoc, the skill must elicit them from the user's prompt or — if missing — stop and ask one focused clarifying question per Step 0 #1.

### Evidence-type guide

The granularity of evidence depends on what the user wants to inform. Confirm the type with the user when not obvious; otherwise choose by the rules below.

Match the evidence type to the modeling object:

- **Clinical trials / Registries** (different things — trials are interventional, registries are observational):
  - When the target is a virtual population, clinical outcome, biological outcome, or treatment effect.
- **Clinical studies** (observational, mechanistic, or cohort, not phase-X trials):
  - When the target is a biological outcome, biomarker dynamics, or mechanistic readouts in humans.
- **Animal studies**:
  - When in-human data are missing and translation from preclinical data is needed.
- **In vitro studies**:
  - When mechanism-level translation is needed (e.g. assay-derived rate constants, binding affinities, target engagement).

### Data-specific facet model (overrides the spine's content-facet triplet)

Data papers are found by **named-thing** angles (specific trials, drugs, authors, outcomes), not by the *content-conceptual* angles that work for Knowledge searches. For each variable in the Entity Table, **build at least 3 angled queries by picking 3 facets from the 5-facet list below**, prioritising the facets where the most concrete known information exists. This overrides the Topical / Mechanism / Adjacent-entity triplet defined in the spine for Knowledge-style searches.

1. **Trial / Study facet** — `<trial-acronym>[tiab]`, multiple acronyms joined with `OR` (e.g. `("PARADIGM-HF"[tiab] OR "DAPA-HF"[tiab] OR "EMPEROR-Reduced"[tiab])`). The strongest possible facet when landmark trials are known for the variable. **First choice when known.**
2. **Drug-name facet** — generic + brand + research code (e.g. `("sacubitril/valsartan"[tiab] OR "Entresto"[tiab] OR "LCZ696"[tiab])`). Catches the landmark trial publication plus its substudies / post-hoc analyses / pharmacology papers that may not name the trial acronym in the title.
3. **Author facet** — known canonical authors for the topic (e.g. `(Vilsbøll T[au] OR Nauck MA[au] OR Edholm T[au])`). Use when the variable has well-known principal investigators. Sourced from (in order of preference): the existing project plan's reference list, the user's expert input, or the top authors surfaced by an initial keyword angle (the *fine-tune* follow-up in Step 5 of the spine).
4. **Outcome / endpoint facet** — the population paired with the specific outcome the model needs to reproduce (e.g. `<DISEASE>[tiab] AND ("hazard ratio for mortality"[tiab] OR "HF hospitalization"[tiab] OR "NT-proBNP"[tiab])`). Catches sub-analyses that emphasize the endpoint and would not surface via a generic population query.
5. **Population × Intervention facet** — disease + intervention + severity / comorbidity / sampling-protocol descriptors (e.g. `("HFrEF"[tiab]) AND (<DRUG>) AND ("LVEF ≤ 35%"[tiab] OR "NYHA II-IV"[tiab])`). The closest analogue of the Knowledge *Topical* facet, scoped to the trial-data context. Use this when the variable has no known landmark trials or authors — it's the lowest-information fallback.

**PMID-seeded angle (mandatory whenever the caller passes known anchor PMIDs).** When the calling workflow (`nova-workflow-calib-plan`, `nova-workflow-project-scoping`) or the user provides a list of known anchor PMIDs from the project plan, prior calibration steps, or expert input, **add one extra angle** of the form `(<PMID1>[uid] OR <PMID2>[uid] OR …)`. This guarantees the foundational anchors enter the candidate pool regardless of keyword relevance or sort order. Treat this as the publication-side equivalent of the trial-scoping auto-invocation gate.

The lit-search script implements this via the **`--seed-pmids "<comma-separated PMIDs>"`** CLI flag — it issues an additional `esearch` with the PMIDs OR-joined and merges the resulting references into the candidate pool with `seeded_anchor: true` on each one. The manifest's `counts.seeded_anchors` reflects how many were successfully added. Calling workflows (e.g. `nova-workflow-calib-plan` Step 3) auto-extract PMID references from existing per-step plans and the project plan and pass them through this flag.

**Full-text verification (opt-in, for Tier-1 candidates).** When Tier-1 candidates have a PMCID, fetching the PMC full text dramatically improves verification quality — the *Results* and *Methods* sections carry the actual numeric values, table references, and protocol details that the abstract only summarises. The lit-search script implements this via the **`--fetch-pmc-fulltext`** CLI flag — for every reference with a `pmcid`, the script fetches the PMC XML, extracts the Results / Methods / Discussion sections (matching by `sec-type` attribute or `<title>` text), and attaches a `pmc_text_excerpt` field (truncated to ~5000 chars) to the reference. Downstream verification heuristics can then scan that field for endpoint values, week-X timepoints, dose-arm tables, and PK metrics that don't appear in titles or abstracts.

**Always-on enrichment**: abstracts via PubMed `efetch` (so verification heuristics can match against abstract text rather than title-only) and citation counts via NIH iCite (so older landmark trials with under-enriched Crossref counts — e.g. CIBIS-II, MERIT-HF, SOLVD — get accurate citation evidence for ranking). These are unconditional; no flag needed.

### Default Data recipe (broad — `[pt]` moved to post-hoc verification)

```text
... AND humans[mh] AND english[lang]
```

The default is intentionally minimal. **Publication type is no longer a query-time AND clause** — it became too exclusionary in practice. Specifically:

- Older landmark trials (CONSENSUS 1987, SOLVD 1991, MERIT-HF 1999, COPERNICUS 2001, RALES 1999) often carry legacy `[pt]` tags that don't match `Randomized Controlled Trial[pt]` or `Clinical Trial, Phase III[pt]` cleanly.
- Trial substudies, post-hoc analyses, longitudinal follow-ups, *Letters / Comments*, and pre-registered protocol papers — often the most calibration-useful sources — carry non-trial `[pt]` values and were being silently filtered out.
- Network meta-analyses and systematic reviews use `Meta-Analysis[pt]` / `Systematic Review[pt]`, not `Randomized Controlled Trial[pt]`.

Publication type is instead **checked post-hoc in Step 3 verification** — see *Verification heuristics* below. A candidate carrying a trial-relevant `[pt]` value gains a verification signal; a candidate missing it is not dropped, just unflagged.

Overrides on the default recipe for non-default evidence types:

- **animal studies** → drop `humans[mh]`, add `animals[mh]`.
- **in vitro studies** → drop `humans[mh]`, add `"in vitro techniques"[mh]`.
- **treatment PK calibration** → optionally add `"pharmacokinetics"[mh]` to narrow toward PK-specific tables when results are too broad.

A candidate Data paper still only counts if it likely **contains a table or a figure** with extractable values — including the in-trial outcome tables and timecourse figures of phase-X publications. The verification heuristics below confirm this.

## Data Priorities — With Verification Heuristics

Prefer candidates that:

- **Likely contain a table or a figure** with extractable values for the variables the user named — *including* the outcome tables and timecourse figures inside clinical-trial publications.
- Match the right evidence type for the user's modeling objective (phase-3 trial for clinical outcomes; phase-1 for treatment PK; observational study for natural history; animal / in vitro for mechanistic translation).
- Match the target population, disease state, dose range, route, regimen, and any required time horizon.

**Verification heuristics — Data** (apply to every candidate before assigning a priority tier):

Scan title + abstract + (PMC full text or supplementary index when available) for the following signals. The candidate is verified when one or more match the variables of interest:

- **Publication-type signal (post-hoc)** — `[pt] ∈ {Randomized Controlled Trial, Clinical Trial Phase I/II/III, Observational Study, Meta-Analysis, Systematic Review, Multicenter Study, Clinical Trial Protocol}`. Fires the *trial-class* verification flag. **Absence of this signal does not drop the candidate** — many landmark older trials, substudies, and post-hoc analyses carry non-trial `[pt]` values but are still calibration-grade evidence. This signal replaces the former query-time `[pt]` AND clause; it is informative, not exclusionary.
- Generic data presence: `Table 1`, `Figure 1`, `Supplementary Table`, `Supplementary Figure`, `Appendix`.
- Numeric quantities in abstract: units (`mg`, `ng/mL`, `µmol/L`, `%`, `hours`, `weeks`), means / SDs / 95 % CIs, `N = ...`, percent change values.
- **Clinical-trial data signals** (apply to phase-X publications and registries publications):
  - Endpoint terms (`primary endpoint`, `secondary endpoint`, `change from baseline`, `time to event`, `event rate`, `hazard ratio`, `odds ratio`, `response rate`, `HbA1c`, `weight loss`, etc.) reported with values.
  - Timepoint terms (`week 24`, `week 52`, `month 6`, `2 years`) reported with values.
  - Dose / arm structure described (`<DOSE> mg/kg`, `placebo`, `comparator`, `randomized to ...`).
  - Safety / AE tables (`treatment-emergent adverse events`, `serious adverse events`, `discontinuation rate`).
- PK / PD signals: `Cmax`, `AUC`, `Tmax`, `half-life`, `clearance`, `Vd`, `concentration-time`, `dose-response`.
- Biomarker dynamics: longitudinal series, mean change-from-baseline curves, response-distribution plots.

Each candidate carries `verification_passed` (boolean) and `verification_note` (one line, the matched signals). Candidates that fail verification are **downgraded one priority tier**, not dropped — the user may still want a paper-level full read.

Flag as lower priority when the paper is review-only on a Data search, animal-only for a human calibration question, or missing accessible data (no DOI, no PMC, no supplement, behind a paywall with no extractable abstract).

## Registry-only sibling: `jk-trial-data-scoping`

For Data searches that target human clinical, biological, or PK / PD evidence (clinical trial, clinical study, observational study, biomarker dynamics in humans, PK, PD, PK / PD), `jk-trial-data-scoping` is **auto-invoked alongside PubMed in the Step 2 single pass** — see the spine `SKILL.md`. The trial-scoping shortlist (NCTs with `evidence_type ∈ {clinical trial registry, clinical trial results, natural history registry, observational study registry}`) joins the unified Data inventory, and the **NCT-to-publication seeds** are constructed as additional `<NCT_ID>[si]` PubMed queries (with `[ti]` / sponsor / acronym fallbacks) that run in the same batch so the paper(s) reporting each high-priority trial enter the Data candidate pool alongside the keyword-discovered publications. NCTs and publications co-exist in the unified Data inventory and may be linked via the `nct_id` field of `assets/shortlist-schema.json` when the linkage is known.

Skip the auto-invocation when the Data scope is animal-only or in-vitro-only (CT.gov is not the right source for those); the gate is set in Step 0 of the spine and the user can override it either way. Both skills consume the same Entity Table and emit candidates against the same `assets/shortlist-schema.json`, so the two outputs union cleanly into one Data inventory for the downstream workflows. PubMed (this skill) is the path for published evidence; ClinicalTrials.gov (trial-scoping) is the path for what's registered, ongoing, or only partially posted as results — they complement, they do not overlap.
