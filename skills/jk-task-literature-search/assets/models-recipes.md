# Models Recipes

Per-group recipes for the **Models** intent group of `jk-task-literature-search`. Consumed by Step 1 (query construction) and Step 3 (priority + verification) of the parent `SKILL.md`. Reuse the Entity Table, the triangulation rule, and the single-pass search defined in the spine — only Models-specific patterns live here.

For the meaning of the PubMed primitives (`[mh]`, `[tiab]`, `[lang]`, `NOT (animals[mh] NOT humans[mh])`, etc.) used in the recipes below, see `pubmed-primitives.md`.

## Model Queries

Search for **reference mathematical / computational models** that could be reimplemented or used as a source of structure, equations, or reference values.

The model granularity should come from the user or context (PK / PBPK / Pop-PK; QSP / mechanistic / statistical mechanistic). If unspecified, propose searching across several granularities and let the user choose.

**Default Model recipe**:

```text
... AND ("mathematical model"[tiab] OR "computational model"[tiab] OR "mechanistic model"[tiab] OR "QSP"[tiab] OR "PBPK"[tiab] OR "ODE"[tiab])
```

**Model-search exclusions** — applied at the Step 3 verification stage (post-search), since the default recipe above is intentionally permissive at query time. Filter the following classes out of the final shortlist:

- **Animal models** — experimental disease analogues (mouse model of obesity, rat model of MI, etc.) — *not* mathematical models. Route them to Data → animal studies (see `data-recipes.md`).
- **Disease risk models / risk scores** — purely statistical equations that compute a risk score from patient features (e.g. Seattle Heart Failure Model, Framingham Risk Score). Filter them out unless the user explicitly asks for risk scores.
- **Pure ML / deep-learning predictive models** — title-or-abstract keywords `machine learning`, `deep learning`, `neural network`, `random forest`, `XGBoost`, `gradient boosting`. These are statistical pattern-matchers, not mechanistic models.

**Co-presence rescue (important)**: the ML exclusion is **conditional** — do NOT filter a paper out when its title also carries a mechanistic / dynamical-systems keyword: `QSP`, `quantitative systems pharmacology`, `mechanistic`, `PBPK`, `PK/PD`, `ODE`, `compartmental`, `mass balance`, `state variable`. QSP-and-ML hybrid papers (mechanistic core augmented with ML for inference or stratification) are *exactly* what a Models search wants to surface — they shouldn't be dropped on a literal `\bmachine learning\b` match. Same logic for "animal" co-presence with humans (`humans[mh]` already handles this at query time) and for "risk score" co-presence with `mechanistic` (rare but possible). When in doubt, keep the paper and let the user inspect.

Typical keyword patterns (each becomes one angled query):

- For a **disease or pathophysiological phenomenon**:
  - `<DISEASE>[tiab] AND ("mathematical model"[tiab] OR "computational model"[tiab])` + default recipe
  - `<DISEASE>[tiab] AND "mechanistic model"[tiab]`
  - `<DISEASE>[tiab] AND ("QSP"[tiab] OR "quantitative systems pharmacology"[tiab])`
- For a **treatment**:
  - `<TREATMENT>[tiab] AND ("PK model"[tiab] OR "pharmacokinetic model"[tiab])`
  - `<TREATMENT>[tiab] AND ("PBPK"[tiab] OR "physiologically based pharmacokinetic"[tiab])`
  - `<TREATMENT>[tiab] AND ("Pop-PK"[tiab] OR "population pharmacokinetic"[tiab])`

## Model Priorities — With Verification Heuristics

Prefer candidates that:

- Describe an actual **mathematical or computational model** — equations, ODE / PDE systems, agent-based logic, QSP structure, compartmental PK / PBPK / Pop-PK structure.
- Match the requested granularity (PK / PBPK / Pop-PK / QSP / mechanistic).
- Report **parameter values, equations, or model code / supplementary appendices** that would support reimplementation or reuse.
- Are validated against external data when possible.

**Verification heuristics — Models** (apply to every candidate before assigning a priority tier):

Scan title + abstract + (PMC full text or supplementary index when available) for:

- Equation / structure signals: `equation`, `ODE`, `PDE`, `compartment`, `state variable`, `system of equations`, `mass balance`.
- Parameter / value signals: `parameter table`, `parameter estimate`, `prior distribution`, `posterior distribution`, `sensitivity analysis`.
- Reusable-artifact signals: `Supporting Information`, `Supplementary`, `BioModels`, `SBML`, `code available`, `Zenodo`, `GitHub`, `https://github.com`, `DOI:10.5281/zenodo`.
- Validation signals: `validated against`, `external validation`, `held-out`, `independent dataset`.

Each candidate carries `verification_passed` and `verification_note`. Failed verification → downgrade one tier.

**Filter-out check** (do this before assigning a tier). Apply the *Model-search exclusions* list above. For each exclusion pattern that matches the title:

1. Check **co-presence rescue keywords** in the same title: `QSP`, `quantitative systems pharmacology`, `mechanistic`, `PBPK`, `PK/PD`, `ODE`, `compartmental`, `mass balance`, `state variable`.
2. If **any rescue keyword is present** → do **not** filter; keep the candidate and add a `verification_note` flag like `hybrid (ML + mechanistic)` or `hybrid (risk score + mechanistic)`.
3. Only **no rescue keyword** → filter out and exclude from the shortlist entirely; record the reason in `manifest.json` under a dedicated `filtered_out` list so the user can audit what was dropped.

Animal-only papers that survive Step 1 (e.g. when `humans[mh]` is dropped) follow the same rule but are routed to Data → animal studies rather than dropped silently — record the routing.
