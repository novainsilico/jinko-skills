---
name: jk-trial-data-scoping
description: >-
  Scope public ClinicalTrials.gov registry and results records for biomedical modeling and clinical evidence planning. Use this skill whenever the user needs ClinicalTrials.gov query framing, NCT candidate discovery, trial status / phase / result-availability screening, endpoint and population inventory, control-arm or comparator trial scoping, or a registry-derived trial evidence shortlist. This skill complements `jk-task-literature-search` (the primary path for published evidence) by surfacing ongoing-trial intelligence, eligibility criteria, sites, recruitment status, and pre-publication endpoints that publications do not yet carry. Do not use it for PubMed publication discovery, Jinko trial execution, protocol authoring, OCR, quantitative endpoint extraction, calibration execution, model building, or full systematic reviews.
compatibility: Check set-up with the `jk-sdk-setup` skill. Uses the public ClinicalTrials.gov v2 API and does not require credentials.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Trial Data Scoping

## Purpose

Use this skill to discover and shortlist public ClinicalTrials.gov registry and results records that could inform biomedical modeling work. The output is a trial-candidate inventory and data-availability screen, not extracted endpoint data and not a Jinko trial execution plan.

This skill is the **registry-only sibling** of `jk-task-literature-search`. Both share the Entity Table format and the structured shortlist schema (`assets/shortlist-schema.json`), so workflow callers (`nova-workflow-calib-plan`, `nova-workflow-project-scoping`) can union their outputs into a single Data inventory.

**Two invocation modes:**

- **Orchestrated from `jk-task-literature-search` Step 2** (default for human clinical / biological / PK / PD Data searches). Lit-search invokes this skill in parallel with its single PubMed pass, passes its Entity Table, and uses the resulting NCTs to seed `<NCT_ID>[si]` PubMed queries that run in the same batch to find the publications behind each high-priority trial. In this mode, drop the *find-associated-publications* follow-up from this skill's Step 5 — the orchestration already chains it.
- **Standalone** (this skill called directly). The Step 4 *Suggested next user action* line stands: surface the follow-up to find publications via `jk-task-literature-search` as a separate user-driven step. Do not auto-chain.

## Scope

- In scope: clarify the trial evidence need, reuse or build an Entity Table, build triangulated ClinicalTrials.gov v2 queries per facet, run a single search pass, normalize NCT IDs and registry links, screen status / phase / results availability, summarize intervention and population fit from registry records, apply verification heuristics for registry / results signals, rank trial candidates, emit a structured shortlist conforming to `assets/shortlist-schema.json`, and propose follow-up actions to the user.
- Out of scope: PubMed publication discovery (use `jk-task-literature-search`), Jinko trial execution or simulation work (use `jk-trial`), protocol authoring (use `jk-protocol`), OCR (use `jk-mistral-ocr`), quantitative endpoint extraction, curve digitization, data-table creation from already extracted values (use `jk-data-table`), model build (use `jk-model`), calibration execution, and full systematic-review protocol management.

## General Guidelines

These guidelines apply throughout the workflow. The methodology spine is intentionally aligned with `jk-task-literature-search` so the two skills cooperate cleanly.

- **Reuse the Entity Table when one already exists.** When invoked from a workflow that already ran `jk-task-literature-search` (or that built an Entity Table for any other reason), inherit the canonical names, synonyms, MeSH terms, related entities, and exclusions from that table. Do not re-derive them. Otherwise, build a minimal Entity Table at Step 0 with the same six-column shape.
- **Triangulate by facet.** For each entity in scope, build 3–4 angled CT.gov queries that approach the same trial-evidence need from different facets (intervention / condition / mechanism class / comparator-landscape) and any status / phase filters the user has named. Run them in parallel and rank candidates by how many facets surface them.
- **Cross-intent consistency.** All trial-scoping candidates carry `intent_group = Data` in the structured shortlist, with `evidence_type` in `{clinical trial registry, clinical trial results, natural history registry, observational study registry}`. Canonical names of disease / treatment / population in the shortlist come from the same Entity Table used by lit-search.
- **Distinguish registry metadata from posted results.** A registered trial is not the same as a trial with usable data. The verification heuristics in Step 3 flag which candidates likely carry analysis-ready endpoint values.
- **Never overclaim from registry metadata alone.** Use "posted results may contain" or "needs registry / results inspection" until the artifact has been inspected.

## Workflow

### Step 0 — Clarify The Trial Evidence Need And The Entity Table

Inherit as much as possible from existing context before asking the user.

1. **Identify and clarify the trial-scoping request.** The request is *what trials to search for* and *at what depth* — the intervention / condition / mechanism class and the trial-scoping purpose, the **scope** (target population, comparator, phase, time horizon), and the required **granularity** (registry-only vs. results-bearing, ongoing vs. completed, completeness threshold, expected number of NCTs). The request comes from one of two sources:
   - **Context** — read the active workflow (`nova-workflow-*`), conversation history, project notes, and any document the user has attached. If `jk-task-literature-search` has already run, **inherit its Entity Table verbatim** — do not rebuild it. Extract intervention / condition / purpose, scope, and granularity from the available material.
   - **User prompt** — when context is silent on a dimension (or no context is available), take the missing piece from the user's current prompt.

   If the request is still unclear after both sources — intervention or condition named but purpose / phase / status requirements ambiguous, or the user's prompt is too generic — **stop and ask the user one focused clarifying question** before continuing. Do not guess scope or granularity; that is the most common cause of an off-target shortlist downstream. Conversely, do not stall on *optional* inputs (e.g. preferred sponsors, exact enrollment threshold) — state a default assumption and move on.
2. **Clarify the trial evidence need.** Ask or confirm only what is missing:
   - Intervention, comparator, mechanism class, or treatment regimen of interest.
   - Condition, indication, population, subgroup, or disease stage.
   - Trial-scoping purpose: endpoint scoping, comparator / control-arm evidence, trial enrichment, dose / regimen context, population extrapolation, safety signal scoping, market-access support, or ongoing-trial / pre-publication intelligence.
   - Trial attributes needed: phase, recruitment status, completion status, posted results, arms / interventions, outcome measures, eligibility criteria, enrollment size, study design.
   - Whether the user wants only a search strategy or wants scripts run to produce local artifacts.
3. **Build a minimal Entity Table when none was inherited.** Same six columns as `jk-task-literature-search`: `canonical_name`, `synonyms`, `mesh_term`, `related_entities`, `intent_groups` (always `Data` for trial-scoping), `exclusions`. The Entity Table is included in the manifest so downstream workflows can union this skill's shortlist with the lit-search shortlist by canonical name.
4. **Validate the Entity Table and the default status filter with the user — mandatory checkpoint before any query is issued.** Surface two things:

   (a) **The Entity Table in full** (every row with canonical name, synonyms, MeSH term, related entities, intent groups, exclusions), whether it was inherited from `jk-task-literature-search` or built fresh in step 3.

   (b) **The default trial status filter**: `Recruiting | Active, not recruiting | Completed` (i.e. active or completed trials). This default excludes `Terminated`, `Withdrawn`, `Suspended`, `Not yet recruiting`, and `Unknown status`. Ask the user explicitly whether the default is OK, or whether to extend it — for example, include `Terminated` for safety-signal scoping or for trials that stopped early but still have published results; include `Not yet recruiting` for development-landscape intelligence.

   Ask the user to confirm both, refine, or extend. Common edits to invite explicitly:
   - **Add a missing synonym** — acronym, brand name, alternative spelling, MeSH preferred term not yet enumerated.
   - **Add a related entity** for paired-keyword expansion (e.g. ASCVD → also `cholesterol`, `plaque`, `LDL`).
   - **Tighten an exclusion** — narrow off-target terms (e.g. for `<DISEASE> model` also exclude `Markov decision process`).
   - **Drop an off-scope entity** that the inheritance picked up but does not belong in this frame.
   - **Override the default trial status filter** — add `Terminated` / `Withdrawn` / `Suspended` / `Not yet recruiting` / `Unknown status`, or narrow further (e.g. `Completed` only).

   When the Entity Table was inherited from lit-search, edits made here should be reported back to that frame (orchestrated mode) so the two skills stay consistent. Wait for the user's response, apply their edits, then proceed.
5. **Write down the frame** (purpose, validated Entity Table, exclusions, validated trial status filter, trial attributes needed) before proposing queries.

### Step 1 — Build Triangulated ClinicalTrials.gov Queries

Construct small, purposeful query batches instead of one broad query. For each entity in scope, build **3–4 angled queries** that approach the trial-evidence need from different facets:

- *Intervention facet* — query on the canonical intervention name plus its synonyms (`semaglutide OR Ozempic OR Wegovy OR Rybelsus`).
- *Condition facet* — query on the canonical condition / indication plus synonyms.
- *Mechanism-class facet* — query on the mechanism class to surface comparators and competitors (`GLP-1 receptor agonist`).
- *Comparator-landscape facet* — query on the comparator or standard-of-care to find control-arm trials.

Strategy:

- Prefer specific intervention and condition terms first; broaden to mechanism class or standard-of-care terms only when the first pass is too sparse.
- Apply the **validated trial status filter from Step 0 step 4** (default: `Recruiting | Active, not recruiting | Completed`) to every angled query in the batch. If the user extended the filter at validation (e.g. added `Terminated` for safety scoping), apply the extended filter; if the user narrowed it (e.g. `Completed` only), narrow accordingly. When the user wants endpoint / control-arm data, layer a posted-results filter (`hasResults=true`) on top.
- Combine paired entities from the Entity Table's `related_entities` column when relevant (e.g. `<TREATMENT> AND <COMORBIDITY>` for subgroup landscape).

### Step 2 — Run The Search

Use the bundled script when the environment has network access. If live search is not available, give the user concrete ClinicalTrials.gov queries and ask for NCT IDs, registry exports, or trial summaries to continue from.

**One search pass.** The skill runs the angled queries built in Step 1 once. There is no automatic iteration; any further exploration is decided by the user in Step 5.

- For each entity, run the angled CT.gov queries from Step 1 in parallel (default `max-results = 25` per facet, overridable). Every query carries the **validated trial status filter** from Step 0 step 4 (default: `Recruiting | Active, not recruiting | Completed`).
- If the user has named an additional phase / posted-results requirement, layer those filters as **additional angled queries within the same batch** (not as a separate later pass). Examples: `Phase 3`, `Completed has_results`.
- Merge candidate sets, dedup by NCT ID, score by number of facets each candidate appears in.

Keep the shortlist manageable; this skill is for candidate scoping, not exhaustive review.

### Step 3 — Verify And Prioritize Trial Candidates

Apply the generic priorities first, then the verification heuristics.

**Generic priorities.** Prefer candidates that:

- Match the condition, population, intervention, comparator, and trial purpose from Step 0.
- Match the target population, disease stage, dose range, route, regimen, and time horizon.
- Have posted ClinicalTrials.gov results when the user needs endpoint or control-arm outcome availability.
- Report relevant outcome measures, arms / interventions, eligibility criteria, enrollment, phase, status, and study design fields.
- Appeared in multiple angled queries (high triangulation score from Step 2).

**Verification heuristics — Registry / Results** (apply to every candidate before assigning a priority tier):

Scan the v2 study record for the following signals. The candidate is verified when one or more match the variables of interest:

- Posted-results signals: `hasResults=true`, outcome-measures table populated, primary-outcome value present, AE / safety section populated, baseline-characteristics table populated.
- Recruitment / status signals: `overallStatus` in `Completed | Active, not recruiting | Terminated` for completed-evidence requests; `Recruiting | Not yet recruiting` for ongoing-trial intelligence requests.
- Population signals: enrollment N reported, eligibility criteria specific (inclusion / exclusion lists present), sex / age range specified.
- Design signals: phase declared, arms / interventions listed, randomization stated, masking described, sponsor identified.
- Endpoint signals: primary outcome measure with timeframe; secondary outcomes listed; outcome-measure descriptions specific enough to map to a model observable.

Each candidate carries `verification_passed` (boolean) and `verification_note` (one line, the matched signals — e.g. `hasResults=true; primary outcome table present; N=4733; Completed 2018`). Candidates that fail verification are **downgraded one priority tier**, not dropped — the user may still want the registry entry for population / design context even without posted results.

Flag as lower priority when the candidate is off-population, wrong line of therapy, not interventional when intervention evidence is required, missing posted results for an endpoint-scoping request, or too early / terminated to support the stated evidence need.

### Step 4 — Present A Structured Shortlist

Return a concise Markdown shortlist, **rendered from a structured JSON object**, grouped by trial purpose (e.g. *Completed with results*, *Ongoing*, *Terminated*, *Comparator landscape*). Ask the user which trials to inspect next.

The structured per-candidate object is defined by **`assets/shortlist-schema.json`** (JSON Schema, draft-07) — the same shape used by `jk-task-literature-search`. Trial-scoping candidates always carry `intent_group = Data`; populate `nct_id` as the primary identifier, `verification_passed` / `verification_note` from Step 3, and `query_provenance.angle` with the CT.gov v2 query string.

**Emit two layers of shortlist files** (mirrors `jk-task-literature-search`):

1. **Merged shortlist** — `shortlist.json` at the search root. Built from the union of all facet results, deduped by NCT ID, ranked using triangulation across facets + the registry / results verification heuristics from Step 3.
2. **Per-facet shortlists** — `shortlist_<facet_label>.json` per facet directory (intervention / condition / mechanism-class / comparator-landscape, plus any status-filter sub-batches). Each contains only the NCTs that surfaced via that facet, ranked using the verification heuristics minus the triangulation signal. This lets the user see what each facet uniquely contributed.

The Markdown shortlist is rendered from these files: one section per trial purpose (*Completed with results*, *Ongoing*, *Terminated*, *Comparator landscape*) using the merged ranking, followed by a **per-facet subsection** listing the top 3–5 candidates from each facet directory so the user can trace each NCT back to the facet that surfaced it. Each candidate bullet shows NCT ID and link, title, phase / status / results availability, population, intervention / comparator, expected outcomes, priority + rationale, and follow-up notes.

Do not overclaim numeric data availability from registry metadata alone. Say "posted results may contain" or "needs registry / results inspection" when the result tables have not been inspected.

Other handoffs, kept precise:

- `jk-task-literature-search` — finds peer-reviewed publications linked to the trial question (registry-only path here; published-evidence path there).
- `jk-trial` — Jinko trial execution.
- `jk-protocol` — protocol authoring.
- `jk-task-extract-data-table`, `jk-data-table` — quantitative extraction once a publication is identified.

Do not imply this skill extracts quantitative endpoint values, builds models, or executes trials.

### Step 5 — Suggest Next-Step Directions

After the shortlist has been presented, ask the user how they want to continue the search and in which direction to explore. Propose three follow-up actions; the user picks one, several, or none. Each follow-up is a *user-decided next call*, not an automatic next pass.

1. **Find associated publications** — for each high-priority NCT the user wants to use for quantitative evidence, propose calling `jk-task-literature-search` to locate the publication(s) reporting that trial. The published paper carries the actual quantitative endpoint tables and timecourse figures that the registry results section often only partially mirrors, and lit-search applies its own verification heuristics. (This stands in for the citation-graph follow-up that `jk-connected-paper` offers on the lit-search side — registries have no PubMed citation graph of their own.) In **orchestrated mode** (this skill called from `jk-task-literature-search` Step 2), drop this follow-up — the orchestration already chains.
2. **Continue the search** — propose re-running this skill with broader queries (mechanism-class or standard-of-care terms) or with additional entities from the Entity Table's `related_entities` column that have not yet been queried. Useful when the shortlist looks thin or when the user wants to widen coverage of the same frame.
3. **Fine-tune with identified seeds** — from the merged result set, tabulate the top 3–5 **sponsors**, the top 3–5 **trial sites / countries**, and any new mechanism-class members / comparator regimens / phase descriptors that surfaced. Propose them as targeted next-pass queries.

Record the user's choice (and any declined options) in the per-run manifest. If the user picks a follow-up, it becomes the input frame for the next invocation of this skill (or of `jk-task-literature-search` in the first case).

## Scripts

- `scripts/clinical_trials.py`: ClinicalTrials.gov v2 study search and normalized table output.
- `scripts/common.py`: Minimal path, JSON, and optional dependency helpers duplicated for standalone packaging.

## Bundled Assets

- `assets/shortlist-schema.json` — JSON Schema (draft-07) for the structured shortlist candidate object. **Shared with `jk-task-literature-search` — keep in sync.** Workflow callers can union the two skills' shortlists into a single Data inventory.
- `assets/.env.example` — environment template, see *Environment* below.

## Environment

See `assets/.env.example` file.

## HITL Checkpoints

Pause for user confirmation at these decision points:

1. **Mandatory** — at the end of Step 0, surface the Entity Table in full (inherited from lit-search or built fresh) and ask the user to confirm, refine, or extend it (add synonyms / related entities / exclusions, drop off-scope rows, flag ambiguous acronyms) before any query is issued. Apply edits, then move on.
2. In Step 5, after the structured shortlist has been presented, surface the three next-step follow-ups (find publications via `jk-task-literature-search` / continue / fine-tune with identified seeds) and ask which direction the user wants to explore next, if any.
3. After candidate trials are prepared, ask which NCT records to inspect next.

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

Run one angled query (intervention facet, status-filtered for posted results):

```bash
python skills/jk-trial-data-scoping/scripts/clinical_trials.py \
  --query "semaglutide cardiovascular outcomes Completed has_results" \
  --max-results 25 \
  --output trial_data_scoping/semaglutide_cv_completed.json
```

## Expected Artifacts

**Per facet directory** (one per angled query: intervention / condition / mechanism-class / comparator-landscape, plus any status-filter sub-batches):

- `clinical_trials.json` — raw v2 study records.
- A sibling `*.table.json` — normalized table whose rows conform to `assets/shortlist-schema.json` (`intent_group = Data`, `nct_id` populated, `evidence_type` set per record, `verification_passed` / `verification_note` populated from Step 3 heuristics, `query_provenance` carrying the CT.gov v2 query string).
- `shortlist_<facet_label>.json` — within-facet ranked shortlist using the Step 3 verification heuristics minus the triangulation signal.

**At the search root**:

- `shortlist.json` — merged shortlist (cross-facet, triangulation + verification heuristics).
- A manifest with the Entity Table, the validated trial status filter, the list of facets run (with their directory labels), and the follow-up suggestions surfaced to the user with their accept / decline status.

## Validation Checklist

- The trial-scoping frame names condition, intervention / comparator, population, and purpose before ranking trials.
- An **Entity Table** is inherited from `jk-task-literature-search` when one exists, or built fresh with the same six-column shape. Cross-intent consistency (same canonical names) holds across the two skills.
- Each entity has **3–4 angled CT.gov queries** (intervention / condition / mechanism class / comparator-landscape) plus any phase / posted-results filter queries the user named, all run in the single pass.
- Every query carries the **validated trial status filter** from Step 0 step 4 (default `Recruiting | Active, not recruiting | Completed`, with the user's override recorded in the manifest if they extended or narrowed it).
- Verification heuristics are applied to each candidate; `verification_passed` and `verification_note` are populated; failed verifications are downgraded one priority tier rather than dropped.
- ClinicalTrials.gov is treated as a registry / results source, not as peer-reviewed publication discovery.
- The final shortlist conforms to `assets/shortlist-schema.json` so workflow callers can union it with the lit-search shortlist.
- Two layers of shortlist files are produced: a **per-facet** `shortlist_<facet_label>.json` inside each facet directory, and a **merged** `shortlist.json` at the search root. The per-facet shortlists apply the verification heuristics minus the triangulation signal; the merged shortlist applies all signals.
- Step 5 surfaces the three follow-up suggestions (find publications / continue / fine-tune) after the shortlist is presented, with chosen / declined status recorded in the manifest. In orchestrated mode (called from `jk-task-literature-search` Step 2), the find-publications follow-up is dropped because the orchestration already chains.
- The final answer distinguishes scoped trial candidates from extracted, analysis-ready endpoint data.
- Handoffs to `jk-task-literature-search`, `jk-trial`, `jk-protocol`, `jk-data-table`, and `jk-model` are precise and non-overlapping.
