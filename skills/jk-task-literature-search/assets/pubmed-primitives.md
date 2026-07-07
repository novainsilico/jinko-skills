# PubMed Query Primitives

Field-tag cheatsheet for queries built by `jk-task-literature-search`. Used by Step 1 of the parent `SKILL.md` and by every per-group recipe (`knowledge-recipes.md`, `data-recipes.md`, `models-recipes.md`). Bare keyword queries are a last resort — every angled query should use at least one tag from this table.

## Field tags

| primitive | use |
|---|---|
| `term[mh]` | MeSH heading **with explosion** — matches the term and all narrower MeSH descendants (e.g. `"Cardiovascular Diseases"[mh]` also matches "Atherosclerosis", "Coronary Disease", etc.). Default choice for an entity that has a clean MeSH home. |
| `term[mh:noexp]` | MeSH heading **without explosion** — matches the exact heading only, no descendants. Use when the broader hierarchy would pull in off-target literature (e.g. `"Diabetes Mellitus, Type 2"[mh:noexp]` to keep T1D-related papers out). |
| `term[mh:major]` | MeSH heading restricted to articles where the term is a **major topic** of the paper. Use to favour papers *about* the entity over papers that merely mention it. |
| `term[tiab]` | Text-word match in **title or abstract**. Use when MeSH coverage is incomplete (new term, broad concept, brand name) or to complement an `[mh]` query for triangulation. |
| `term[ti]` | Text-word match in **title only** — tighter than `[tiab]`. Use for exact-title fallbacks (e.g. trial acronyms, model names). |
| `Type[pt]` | **Publication type**. Common values: `Review[pt]`, `Randomized Controlled Trial[pt]`, `Clinical Trial, Phase III[pt]`, `Clinical Trial, Phase II[pt]`, `Clinical Trial, Phase I[pt]`, `Meta-Analysis[pt]`, `Practice Guideline[pt]`, `Observational Study[pt]`. Combine with `OR` inside parentheses when multiple types apply. |
| `Lastname FN[au]` | **Author** tag. Use in the *fine-tune* follow-up of Step 5 after the first search pass surfaces top authors. Initial format is `LastName FN` (first initial only). |
| `Journal Title[ta]` | **Journal abbreviation** tag. Use for high-impact venues — examples: `Nat Rev Drug Discov[ta]`, `Lancet[ta]`, `N Engl J Med[ta]`, `Annu Rev *[ta]` (the trailing `*` matches the *Annual Review of …* family). |
| `("YYYY"[PDat] : "YYYY"[PDat])` | **Date range** filter. Use `"3000"` as the upper bound to mean "up to now" (e.g. `("2015"[PDat] : "3000"[PDat])`). Default to recent (≥ last 10 years) for Knowledge reviews; loosen for landmark / historical evidence. |
| `english[lang]` | **Language** filter. On by default for human-scale Knowledge / Data; drop when the user explicitly wants non-English literature. |
| `humans[mh]` | Restrict to **human** studies. On by default for human-scale Knowledge / Data; drop for basic-biology pathway searches or animal / in-vitro Data branches. |
| `NOT (animals[mh] NOT humans[mh])` | Exclude **animal-only** studies while keeping mixed translational papers that mention humans. Default for Models searches (animal models are a different category — route them to Data → animal studies); also useful for human Knowledge searches that keep mixed-species reviews. |

## Combining clauses

- Combine clauses with `AND`, `OR`, `NOT`, and parentheses.
- **Inside an entity clause**, always join the synonym set from the Entity Table with `OR`: `("ASCVD"[tiab] OR "atherosclerotic cardiovascular disease"[mh] OR "atherosclerosis"[mh])`.
- **Between clauses**, use `AND` to compose (entity AND publication-type AND date AND species). See the *Triangulation* section of `SKILL.md` Step 1 for how separate angled queries are then merged and intersection-ranked.
- `NOT` interacts with MeSH hierarchies. `NOT animals[mh]` would remove every paper indexed under any animal MeSH descendant — typically too aggressive. The construct `NOT (animals[mh] NOT humans[mh])` is the safer "exclude animal-only" idiom: it removes only papers where animals are tagged but humans are not.

## When to prefer one primitive over another

- **`[mh]` first, `[tiab]` as a complementary angle.** MeSH indexing is curated but lags new papers by weeks to months. Pair an `[mh]` angle with a `[tiab]` angle to cover both indexed and unindexed populations.
- **`[mh:noexp]` when the hierarchy is broader than the question.** Default `[mh]` explodes; use `:noexp` to keep a narrow entity narrow.
- **`[mh:major]` for surveys, not for completeness.** Major-topic restriction filters out incidental mentions — good for an orientation Knowledge query, bad for a Data search where every mention may carry a usable table.
- **`[pt]` is a hard filter — use it deliberately.** A wrong publication type filter (e.g. `Review[pt]` on a Data search) silently drops relevant trial publications.
- **`[au]` and `[ta]` only after Step 2.** These are best as Step 5 *fine-tune* follow-ups, after the first pass has surfaced the top authors and journals in the field.
