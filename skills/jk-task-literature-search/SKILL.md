---
name: jk-task-literature-search
description: >-
  Find and shortlist citation-grounded biomedical publication candidates for any of three search intents: Knowledge (understanding a disease, pathway, treatment, population, or clinical paradigm), Data (clinical trials, clinical studies, animal or in vitro experiments that could inform parameters, virtual populations, protocols, calibration, or validation), and Models (reference mathematical, computational, or QSP / PK / PBPK / Pop-PK models that could be reimplemented or used for reference values and equations). Use this skill whenever the user needs a targeted PubMed publication search strategy, DOI / PMID citation normalization, AMA citation output, publication download triage, or evidence-discovery shortlist before extraction or modeling. Do not use it for ClinicalTrials.gov registry / result scoping, OCR, quantitative endpoint extraction, calibration execution, model building, or full systematic reviews.
compatibility: Check set-up with the `jk-sdk-setup` skill. Requires USER_EMAIL for NCBI identity in .env file; optional NCBI_API_KEY for higher NCBI rate limits.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Literature Search

## Purpose

Discover and shortlist public biomedical publications that could support modeling and analysis work. The output is a search-derived publication inventory — not extracted data, not a knowledge synthesis, not a calibration plan.

Every search is organized around one or more of three intent groups: **Knowledge** (understanding a disease, pathway, mechanism, treatment, population, or clinical paradigm), **Data** (clinical-trial, observational, animal, or in-vitro publications that could inform parameters, virtual populations, calibration, or validation), and **Models** (reference mathematical / computational / mechanistic / QSP / PK / PBPK / Pop-PK models).

## Scope

- In scope: clarify the search intent and frame, build an Entity Table with synonyms / acronyms / alternative names, build triangulated angled PubMed queries per intent group with explicit PubMed primitives, run them in a single search pass, normalize DOI and citation fields, merge Crossref metadata, format AMA citations, verify Data and Model candidates with concrete heuristics, rank and shortlist candidates with a structured schema, surface follow-up suggestions (citation-graph expansion, continued search, fine-tuning seeds), and optionally attempt open publication download for later reading.
- Out of scope: ClinicalTrials.gov registry / result scoping (use `jk-trial-data-scoping`), OCR (use `jk-mistral-ocr`), quantitative endpoint extraction, curve digitization, data-table creation from already extracted values (use `jk-task-extract-data-table` then `jk-data-table`), knowledge synthesis into a phenomenon map (use `nova-workflow-knowledge-investigation`), Jinkō upload, model build (use `jk-model`), calibration execution, trial execution (use `jk-trial`), and full systematic-review protocol management.

## General Guidelines

Operating principles that do not have a dedicated workflow step of their own (the workflow steps themselves enforce primitives, the single-pass search, cross-intent consistency, and verification — they are not restated here):

- **Build the Entity Table first** (Step 0). Every batch draws synonyms, related entities, and exclusions from it; do not re-derive them ad-hoc.
- **Triangulate by at least 3 angled queries per entity per intent group** (one per facet: topical / mechanism / adjacent-entity), not one omnibus query. Convergence across facets is the strongest "this is canonical" signal.
- **Small purposeful batches** beat one broad query — separate by intent group and by evidence type so candidates remain inspectable.
- **Keep redundant Knowledge candidates** — overlap across reviews is a feature, not a duplicate.

## Workflow

### Step 0 — Clarify The Search Frame And Build The Entity Table

Before searching, settle the frame. Inherit as much as possible from existing context before asking the user.

1. **Identify and clarify the search request.** The search request is *what to search for* and *at what depth* — the subject of investigation (disease, pathway, treatment, population, paradigm, or model class), its **scope** (target population, intervention, comparator, time horizon, evidence types), and the required **granularity** (a broad orientation vs. a fine-grained expert scan; expected number of candidates per intent group). The request comes from one of two sources:
   - **Context** — read the active workflow (`nova-workflow-*`), conversation history, project notes, prior shortlists, and any document the user has attached (protocol, scoping note, model plan, slide deck). Extract subject, scope, and granularity from that material first.
   - **User prompt** — when context is silent on a dimension (or no context is available), take the missing piece from the user's current prompt.

   If the request is still unclear after both sources — subject named but scope or granularity ambiguous, two plausible interpretations would produce very different shortlists, or the user's prompt is too generic ("find me papers on diabetes") — **stop and ask the user one focused clarifying question** before continuing. Do not guess scope or granularity from a vague prompt; that is the most common cause of an off-target shortlist downstream. Conversely, do not stall on *optional* inputs (e.g. preferred journals, exact date window) — state a default assumption and move on.

   **For Data-intent searches**, additionally confirm the three Data-specific hard requirements listed in `assets/data-recipes.md` (*Required Data-context inputs*) — the **variable(s) to inform**, the **population × disease-state precision**, and the **calibration mode** (single-reference-patient vs population/Vpop) — before issuing queries. When called from `nova-workflow-calib-plan`, these come from the step plan; when called ad-hoc, the skill must elicit them.
2. **Determine the intent group(s).** Decide whether the search is for **Knowledge**, **Data**, **Models**, or a combination. A single user request can span multiple groups — run them as separate query batches and keep the shortlists labeled by group.
3. **Build the Entity Table.** This is the first artifact of the skill. It is shared by every query batch and every group. One row per entity, with the columns:

   | column | meaning |
   |---|---|
   | `canonical_name` | the entity name used in the final shortlist and downstream documents |
   | `synonyms` | acronyms, full names, brand / generic, MeSH preferred terms, common spelling variants |
   | `mesh_term` | the verified PubMed MeSH heading when one exists, otherwise empty |
   | `related_entities` | adjacent / upstream / downstream concepts that may need paired-keyword passes (e.g. ASCVD → cholesterol, plaque, LDL; obesity → adipose tissue, energy balance) |
   | `intent_groups` | which of Knowledge / Data / Models the entity is searched against |
   | `exclusions` | terms to filter out for this entity (e.g. for IL-2: "in vivo gene therapy" if off-target; for `<DISEASE> model`: animal models, risk scores) |

   For each row, enumerate **all** synonyms / acronyms / alternative names up front. Examples: `("ASCVD" OR "atherosclerotic cardiovascular disease" OR "atherosclerosis" OR "coronary artery disease")`, `("Ozempic" OR "semaglutide" OR "Wegovy" OR "Rybelsus")`. When an entity has many plausible aliases, confirm the synonym list with the user.

   Propose `related_entities` expansions to the user when they are not obvious from the prompt (e.g. ASCVD → propose adding `cholesterol`, `plaque`, `LDL`). Adjacent entities drive paired-keyword passes in Step 1 (`role of X in Y`, `impact of X on Y`, `X Y`).

4. **Trial-scoping auto-invocation gate (Data branch).** Default behavior: when the Data evidence type targets human clinical, biological, or PK / PD data (clinical trial, clinical study, observational study, biomarker dynamics in humans, PK, PD, PK / PD), Step 2 will invoke `jk-trial-data-scoping` in parallel with PubMed in the single search pass; the resulting NCTs join the Data inventory and seed `<NCT_ID>[si]` PubMed queries in the same batch. Skip the auto-invocation when the Data scope is animal-only or in-vitro-only. The user can override the gate either way (`--skip-trial-scoping` to disable, `--force-trial-scoping` to invoke even on a non-default scope). State the gate decision in the frame.
5. **Validate the Entity Table with the user — mandatory checkpoint before any query is issued.** Surface the draft Entity Table in full (every row with canonical name, synonyms, MeSH term, related entities, intent groups, exclusions) and the trial-scoping gate decision. Ask the user to confirm, refine, or extend. Common edits to invite explicitly:
   - **Add a missing synonym** — acronym, brand name, alternative spelling, MeSH preferred term not yet enumerated.
   - **Add a related entity** for paired-keyword expansion (e.g. ASCVD → also `cholesterol`, `plaque`, `LDL`).
   - **Tighten an exclusion** — narrow off-target terms, e.g. for `<DISEASE> model` also exclude `Markov decision process`; for `IL-2` also exclude `in vivo gene therapy` when off-scope.
   - **Drop an off-scope entity** that the inheritance picked up but does not belong in this frame.
   - **Adjust the intent groups** for an entity that is in scope for Knowledge but not Data (or vice versa).

   Wait for the user's response. Apply their edits, then proceed. Do not skip this checkpoint — it is the cheapest opportunity to catch a wrong canonical name, a missing synonym, or an off-scope expansion before the query batch runs.
6. **Write down the frame** (subject, intent groups, validated Entity Table, exclusions, trial-scoping gate decision) and state assumptions before proposing queries. The validated Entity Table is included verbatim in the final `manifest.json` so downstream skills consuming this skill's output (`nova-workflow-knowledge-investigation`, `nova-workflow-calib-plan`, `nova-workflow-project-scoping`) inherit it without re-derivation.

### Step 1 — Build Triangulated Queries Per Intent Group

Construct one query batch per intent group, then split further by evidence type or sub-entity. Build queries using PubMed field tags and the angled-query (triangulation) pattern.

#### PubMed Query Primitives

Use PubMed field tags deliberately. The cheatsheet lives in `assets/pubmed-primitives.md`. Load it before building queries. Bare keyword queries are a last resort.

Always include the synonym set from the Entity Table joined with `OR` inside the entity clause.

#### Triangulation — Angled Queries Per Entity

For each entity in scope of an intent group, build **at least 3 angled queries** (one per facet, with additional Adjacent-entity angles when the Entity Table lists several `related_entities`) that approach the same entity from different content angles. Run them in parallel. Merge the resulting candidate sets and rank each candidate by the number of angles it appears in (intersection-weighted ranking). The three facets:

- *Topical facet* — MeSH heading on the entity itself (`<ENTITY>[mh]` OR (`<ENTITY>[ti]`)).
- *Mechanism facet* — entity in `[tiab]` combined with mechanism terms (`<ENTITY>[tiab] AND (pathophysiology[tiab] OR "mechanism of action"[tiab] OR mechanisms[tiab])`).
- *Adjacent-entity facet* — `<ENTITY> AND <RELATED_ENTITY>` from the Entity Table; one angle per related entity that matters.

Quality / venue / publication-type priors are not separate facets; they live in the per-group default recipe (e.g. Knowledge's `Review[pt] AND humans[mh]`, Data's phase-X clause) and are applied uniformly across the three facet angles.

A candidate that appears in all three facets is much stronger than one that appears in only one — that is the intersection-weighted ranking signal.

#### Per-Group Query Recipes

The per-group query patterns and default-primitive recipes live in dedicated asset files so this spine stays scannable. **Load the file that matches each intent group in scope** before issuing queries.

- **Knowledge** → `assets/knowledge-recipes.md`. 
- **Data** → `assets/data-recipes.md`. 
- **Models** → `assets/models-recipes.md`. 

### Step 2 — Run The Search In A Single Pass

Use the bundled scripts when the environment has network access and `USER_EMAIL` is set. If live search is not available, give the user concrete PubMed queries and ask for PMIDs, DOIs, abstracts, search exports, or papers to continue from.

**One search pass.** The skill runs the angled queries built in Step 1 once. There is no automatic iteration; any further exploration is decided by the user in Step 5.

For each intent group in scope:

- Run the PubMed angled queries built in Step 1 in parallel (default `retmax = 50` per angle, overridable).
- Merge per-group candidate sets, dedup by PMID / DOI, and score each candidate by the number of angles in which it appears (intersection-weighted ranking).
- Prefer DOI-seeded or title-exact searches when broad keyword queries retrieve off-target literature.

**Data branch — when the Step 0 gate triggered the trial-scoping auto-invocation, run `jk-trial-data-scoping` in parallel with the PubMed batch in this same pass.** Its NCTs join the Data inventory, and the `<NCT_ID>[si]` PubMed queries derived from each high-priority NCT run in the same batch and surface the publications behind those trials. See `assets/data-recipes.md` (*Registry-only sibling*) for the NCT ↔ publication mechanics.

### Step 3 — Verify And Prioritize Candidate Studies

Apply the generic priorities first, then the group-specific priorities and verification heuristics. When the request spans multiple groups, prioritize within each group separately.

**Generic priorities (all groups).** Prefer candidates that:

- Match the search frame and intent group from Step 0.
- Match the target entity (disease, population, treatment, pathway) and any required scope (disease stage, dose range, route, regimen, species).
- Are peer-reviewed publications or credible public datasets.
- Have a DOI, PMID, PMCID, or supplementary-material identifier that makes follow-up retrieval practical.
- Appeared in multiple angled queries (high triangulation score from Step 2).

#### Per-Group Priorities And Verification Heuristics

The per-group priority rules and verification heuristics live in the same recipe files used by Step 1. **Load the file that matches each intent group in scope** before assigning priority tiers.

- **Knowledge** → `assets/knowledge-recipes.md` (section *Knowledge Priorities*). 
- **Data** → `assets/data-recipes.md` (section *Data Priorities — With Verification Heuristics*). 
- **Models** → `assets/models-recipes.md` (section *Model Priorities — With Verification Heuristics*).

### Step 4 — Present A Structured Shortlist

Return a concise Markdown shortlist, **rendered from a structured JSON object**, grouped by intent (Knowledge / Data / Models). Ask the user which sources to inspect next.

The structured per-candidate object is defined by **`assets/shortlist-schema.json`** (JSON Schema, draft-07). One row of `summary_table.json` per candidate, with extras carried in `references.json`.

**Emit two layers of shortlist files** so the user can see both the cross-angle synthesis and what each angle uniquely surfaced:

1. **Merged shortlist** — `shortlist.json` (or one per intent group when multiple groups ran: `shortlist_knowledge.json`, `shortlist_data.json`, `shortlist_models.json`). Built from the union of all angled-query results, deduped by PMID / DOI, ranked using all four verification signals (triangulation across angles, title pattern, high-impact venue, citation evidence). This is the cross-angle synthesis.
2. **Per-angle shortlists** — `shortlist_<angle_label>.json` per angled query (e.g. `shortlist_topical.json`, `shortlist_mechanism.json`, `shortlist_adj_<entity>.json`). Each contains only the candidates that surfaced via that angle, ranked using the same verification heuristics **minus the triangulation signal** (which doesn't apply within a single angle). This lets the user inspect what each angle uniquely contributed and which sub-topic the candidates belong to. Same `assets/shortlist-schema.json` shape.

The Markdown shortlist is generated from these files: one section per intent group with the merged top-N candidates, followed by a **per-angle subsection** listing the top 3–5 candidates from each angled query (so the user can see the angle-by-angle thematic breakdown). Use intent-group labels and angle labels consistent with the Entity Table and the per-angle output directories — the disease / treatment / population names must be the `canonical_name` values from Step 0 (cross-intent consistency); the angle labels must match the directory names from Step 2 (so the user can trace each candidate back to its source query).

Do not overclaim numeric data availability from titles or abstracts alone. Say "likely contains" or "needs full-text check" when the artifact has not been inspected. Do not imply this skill digitizes figures, extracts quantitative endpoints, or chooses calibration parameters.

### Step 5 — Suggest Next-Step Directions

After the shortlist has been presented, ask the user how they want to continue the search and in which direction to explore. Propose three follow-up actions; the user picks one, several, or none. Each follow-up is a *user-decided next call*, not an automatic next pass.

1. **Citation-graph expansion** — propose `jk-connected-paper` (placeholder skill) on one or two strong seed papers from the shortlist to surface adjacent literature. Especially valuable for **Data** searches, where one well-targeted seed paper often leads to several adjacent studies with the same outcome measurements.
2. **Continue the search** — propose re-running this skill with a wider `retmax`, with broader synonyms, or with additional entities from the Entity Table's `related_entities` column that have not yet been queried. Useful when the shortlist looks thin or when the user wants to widen coverage of the same frame.
3. **Fine-tune with identified seeds** — from the merged result set, tabulate the top 3–5 **authors** (by occurrence, with first / last-author boost), the top 3–5 **journals** (by occurrence and by impact for the intent group: high-impact reviews for Knowledge, trial-publishing journals for Data, modeling-publishing journals for Models), and any new keywords / sub-entities / named cohorts / regimens / model types that surfaced. Propose them as targeted next-pass queries (`Lastname FN[au]`, `Journal Title[ta]`, refined entity terms). For the Data branch, also list any sponsors / mechanism-class members that appeared in the trial-scoping shortlist as additional fine-tuning seeds.

Record the user's choice (and any declined options) in `manifest.json`. If the user picks a follow-up, it becomes the input frame for the next invocation of this skill (or `jk-connected-paper` in the first case).

## Bundled Assets

- `assets/knowledge-recipes.md` — query patterns, default-primitive recipe, priorities, and lower-priority flags for the **Knowledge** intent group. Load when running a Knowledge batch.
- `assets/data-recipes.md` — query patterns by evidence type (clinical trial / clinical study / animal / in vitro), default-primitive recipes with phase-X overrides, and the full Data verification-heuristic checklist (including clinical-trial-data signals). Load when running a Data batch.
- `assets/models-recipes.md` — query patterns by model granularity (PK / PBPK / Pop-PK / QSP / mechanistic), default-primitive recipe with the `NOT` clauses, and Model verification heuristics (equations / parameters / BioModels / SBML / code DOIs). Load when running a Models batch.
- `assets/pubmed-primitives.md` — PubMed field-tag cheatsheet (MeSH explosion control, publication type, date, language, species, author, journal, NOT idioms) used by every recipe and by Step 1.
- `assets/shortlist-schema.json` — JSON Schema (draft-07) for the structured shortlist candidate object. The contract for `references.json` / `summary_table.json` and for every downstream skill that consumes this skill's output.
- `assets/.env.example` — environment template, see *Environment* below.

The spine of this `SKILL.md` (Step 0, the triangulation rule, Step 2 single-pass search, Step 4 shortlist schema, Step 5 next-step follow-ups) is shared by all three groups; the per-group query patterns, the per-group verification heuristics, and the PubMed primitives cheatsheet live in the asset files.

## Scripts

- `scripts/literature_search.py`: PubMed search, PubMed summaries, Crossref merge, ranking, selection, AMA output, and optional download. Run it once per angled query and merge the resulting `references.json` files; or once with a compound `term=` clause covering several angles at the cost of losing per-angle provenance.
- `scripts/publication_download.py`: Downloads selected article PDFs when a PMC or DOI landing page PDF can be resolved.
- `scripts/supplementary_triage.py`: Downloads supplementary files listed in download manifests or selected references.
- `scripts/common.py`: Shared `.env`, path, JSON, retry, and filename helpers.
- `scripts/pmc_open_access.py`: PMC open-access S3 revision helpers.

## Environment

See `assets/.env.example` file.

## HITL Checkpoints

Pause for user confirmation at these decision points:

1. **Mandatory** — at the end of Step 0, surface the draft Entity Table in full and ask the user to confirm, refine, or extend it (add synonyms / related entities / exclusions, drop off-scope rows, flag ambiguous acronyms, override the trial-scoping gate) before any query is issued. Apply edits, then move on.
2. In Step 5, after the structured shortlist has been presented, surface the three next-step follow-ups (`jk-connected-paper` expansion / continue / fine-tune with identified seeds) and ask which direction the user wants to explore next, if any.
3. After candidate references are prepared, ask which publications to keep or download.
4. After downloads are ready, ask whether supplementary triage should be run.

## CLI Usage

Basic PubMed + Crossref search:

```bash
python skills/jk-task-literature-search/scripts/literature_search.py \
  --query "semaglutide obesity exposure-response pharmacodynamics" \
  --output-dir literature_search
```

One angled query (Knowledge default recipe):

```bash
python skills/jk-task-literature-search/scripts/literature_search.py \
  --query '("atherosclerotic cardiovascular disease"[mh] OR "ASCVD"[tiab] OR "atherosclerosis"[mh]) AND (Review[pt] OR Practice Guideline[pt]) AND humans[mh] AND english[lang] AND ("2015"[PDat] : "3000"[PDat])' \
  --output-dir literature_search/ascvd_review
```

For ranking (`--enable-ranking`, `--objective-keywords`, `--compartment-keywords`), non-interactive selection (`--no-prompt-selection`), publication download (`--enable-publication-download` or `publication_download.py`), and supplementary triage (`supplementary_triage.py`), run `python skills/jk-task-literature-search/scripts/<script>.py --help`.

## Expected Artifacts

**Per angled-query directory** (one directory per angle):

- **Raw search outputs**: `esearch.json`, `esummary.json`, `crossref.json`, `references_ama.txt`, `selected_references.json`, `README.md`.
- **`references.json`** and **`summary_table.json`** — candidates conforming to `assets/shortlist-schema.json`.
- **`shortlist_<angle_label>.json`** — within-angle ranked shortlist applying the verification heuristics (title pattern, high-impact venue, citation evidence) minus the cross-angle triangulation signal. Same shape as the merged shortlist; lets the user inspect what each angle uniquely surfaced and which sub-topic the candidates belong to.

**At the search root** (alongside the per-angle directories):

- **Merged shortlist** — `shortlist.json` (or `shortlist_knowledge.json` / `shortlist_data.json` / `shortlist_models.json` when more than one intent group ran). Cross-angle, intersection-weighted, full four-signal ranking.
- **`manifest.json`** — Entity Table, the list of angles run (with their directory labels), trial-scoping invocation decision (Data branch), NCT-to-publication seeds derived from trial-scoping (Data branch), the verification-heuristic thresholds in force, and the follow-up suggestions surfaced to the user with their accept / decline status.

Optional **publication download** output: `downloads_manifest.json` and `files/<reference-slug>/main.pdf` when downloadable. Optional **supplementary triage** output: `supplementary_manifest.json` and per-publisher supplementary files.

## Validation Checklist

Auditable post-conditions on the deliverable (not a restatement of methodology):

- `USER_EMAIL` set in `.env` before PubMed calls.
- `manifest.json` contains the Entity Table, the angled-query list run in the single pass, the trial-scoping invocation decision (Data branch), and the follow-up suggestions surfaced to the user (with accept / decline status).
- Every candidate in `references.json` / `summary_table.json` conforms to `assets/shortlist-schema.json` (intent_group, evidence_type, entities from the Entity Table, verification_passed/note, priority + rationale, query_provenance).
- Two layers of shortlist files are produced: a **per-angle** `shortlist_<angle_label>.json` inside each angle directory, and a **merged** `shortlist.json` (or per-intent-group when several ran) at the search root. The per-angle shortlists apply the verification heuristics minus the triangulation signal; the merged shortlist applies all four signals.
- Data and Model candidates carry a populated `verification_note`; failed verifications are downgraded one tier, not dropped.
- Canonical names (disease / treatment / population) are consistent across Knowledge / Data / Models shortlists when more than one group ran.
- Only openly downloadable PDFs were downloaded.
- The final answer distinguishes discovered candidates from extracted, calibration-ready data, and labels each candidate by intent group.

## Referenced Skills

- `jk-connected-paper` — *placeholder*: citation-graph expansion of a seed paper into adjacent literature. To be confirmed / implemented.
- `jk-trial-data-scoping` — the registry-only sibling: auto-invoked alongside PubMed in the Step 2 single pass when the Data branch targets human clinical / biological / PK / PD evidence; its NCTs join the Data inventory and seed `<NCT_ID>[si]` PubMed queries that run in the same batch to find publications behind each high-priority trial.
- `jk-sdk-setup` — SDK credentials and environment setup.
