# Knowledge Recipes

Per-group recipes for the **Knowledge** intent group of `jk-task-literature-search`. Consumed by Step 1 (query construction) and Step 3 (priority + verification) of the parent `SKILL.md`. Reuse the Entity Table, the triangulation rule, and the single-pass search defined in the spine — only Knowledge-specific patterns live here.

For the meaning of the PubMed primitives (`[mh]`, `[mh:noexp]`, `[mh:major]`, `[pt]`, `[ta]`, `[tiab]`, `[PDat]`, `[lang]`, `NOT (animals[mh] NOT humans[mh])`, etc.) used in the recipes below, see `pubmed-primitives.md`.

## Knowledge Queries

Prioritize **reviews** of the subject, and within reviews prefer **high-impact venues** when they exist (e.g. *Nature Reviews* series, *Nature Primers*, *Lancet Seminars*, *NEJM Reviews*, *Annual Review* series). Prefer broad overviews to many granular papers, unless the user has asked for expert-level detail. Do not deduplicate by topic — keep redundant high-quality reviews.

**Default Knowledge recipe** (applied to every Knowledge angled query unless overridden):

```text
... AND Review[pt]
AND humans[mh]
```

Override the date filter when the user wants landmark / historical reviews; override the `humans[mh]` filter for a Knowledge search on a basic-biology pathway.

Typical keyword patterns (each becomes one angled query):

- For a **disease**:
  - `<DISEASE>[mh]` + default recipe
  - `<DISEASE>[tiab] AND (pathophysiology[tiab] OR physiopathology[tiab] OR mechanisms[tiab])`
  - `<DISEASE>[mh:major] AND ("Nat Rev *"[ta] OR "Lancet"[ta] OR "N Engl J Med"[ta] OR "Annu Rev *"[ta])`
- For a **biological pathway, phenomenon, or mechanism**:
  - `<PATHWAY>[mh] OR <PATHWAY>[tiab]` + default recipe
  - `<PATHWAY>[tiab] AND (physiology[tiab] OR pathology[tiab] OR physiopathology[tiab])`
  - `"role of <PATHWAY> in <CONTEXT>"[tiab]`
- For a **treatment**:
  - `<TREATMENT>[mh]` + default recipe
  - `<TREATMENT>[tiab] AND ADME[tiab]`
  - `<TREATMENT>[tiab] AND ("mechanism of action"[tiab] OR pharmacology[tiab])`
- For a **population**:
  - `<POPULATION>[tiab] AND ("risk factors"[tiab] OR epidemiology[mh] OR characteristics[tiab])`
- For a **clinical paradigm**:
  - `<PARADIGM>[tiab] AND ("clinical guidelines"[tiab] OR consensus[tiab] OR "standard of care"[tiab])` with `Practice Guideline[pt]` boost

Combine paired entities when relevant: `<DISEASE> <BIOMARKER>`, `role of <BIOMARKER> in <DISEASE>`, `impact of <TREATMENT> on <OUTCOME>`. The pairs come from the `related_entities` column of the Entity Table.

## Knowledge Priorities

Prefer candidates that:

- Are **reviews** of the subject, especially in high-impact venues (*Nature Reviews*, *Nature Primers*, *Lancet Seminars*, *NEJM Reviews*, *Annual Reviews*).
- Provide a **big picture** of the subject rather than a granular slice, unless the user has asked for expert depth.
- Cover physiopathology, mechanism, ADME, mechanism of action, risk factors, or clinical guidelines depending on the entity type.
- **Match a Knowledge title pattern** — title-level wording is a strong relevance signal even without inspecting the full text. Auto-promote candidates whose titles contain:
   - *Pathophysiology of* / *Physiopathology of* / *Pathology of* `<ENTITY>`
   - *Pathogenesis of* `<ENTITY>` / *Mechanisms of* `<ENTITY>` / *Mechanism of action of* `<ENTITY>`
   - *Role of* `<X>` *in* `<ENTITY>` / *Impact of* `<X>` *on* `<ENTITY>` / *`<ENTITY>` and `<Y>`: …*
   - *A review of* `<ENTITY>` / *State of the art in* `<ENTITY>` / *`<ENTITY>`: a review* / *`<ENTITY>` (Primer / Seminar)*
   - *Clinical guidelines for* `<ENTITY>` / *Consensus statement on* `<ENTITY>`
- **Carry strong citation evidence** — for Knowledge, citation count is itself a canonicity signal. A foundational paper from 10–20 years ago that only intersects one of the angled queries (because the field's vocabulary has shifted) is still canonical. Use **citation density** to normalize for age:
   - `citation_density = is_referenced_by_count / max(1, current_year - publication_year)`
   - **High-citation signal**: `citation_density ≥ 50` (foundational level) **or** `is_referenced_by_count ≥ 1000` (landmark level regardless of age).
- Are retained even when they appear redundant with another Knowledge candidate.

Flag as lower priority when the paper is mechanism-only with no broader context, non-peer-reviewed, or animal-only when a human-scale Knowledge claim is needed.

**Knowledge verification heuristic — four signals, "any two" rule.** A candidate is **high-priority** when at least two of the four signals fire:

1. **Triangulation** — surfaces in ≥ 2 angled queries from Step 1.
2. **Title pattern** — title matches one of the patterns listed above.
3. **High-impact venue** — venue is in the curated list (*Nat Rev \**, *Nature*, *Lancet*, *N Engl J Med*, *Annu Rev \**, *Cell*, etc.).
4. **Strong citation evidence** — `citation_density ≥ 50` or `is_referenced_by_count ≥ 1000`.

Exactly one signal → **medium-priority**. Zero signals → **low-priority**.

Populate `verification_passed` (true when ≥ 2 signals fired) and `verification_note` with the matched signals (e.g. `"triangulation 3/5; title='pathogenesis'; citations 142/year"`).
