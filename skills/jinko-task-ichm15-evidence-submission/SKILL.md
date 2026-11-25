---
name: jinko-task-ichm15-evidence-submission
description: >-
  From model outcomes and the ICH M15 planning-stage record (Question of
  Interest, Context of Use, the four rated Key Assessment Elements, Technical
  Criteria, and Appropriateness of Proposed MIDD, usually from a MAP), get
  recommendations and documentation for the ICH M15 evidence submission stage:
  model evaluation (verification, validation, and applicability assessment),
  Evaluation of Model(s) and Model Outcomes, Outcome of MIDD Evidence
  Assessment, and a Model Analysis Report (MAR), then upload it to Jinkō. Do
  not use it before model outcomes exist; use jinko-task-ichm15-planning for
  the planning stage.
compatibility: >-
  Requires the jinko-task-ichm15-planning skill (shared terms, MAP template,
  and leak check script). Jinkō upload requires jinko-document,
  jinko-sdk-setup, and project write access.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.21,<2.0"
license: MIT
---

# ICH M15 MIDD evidence submission

Use this skill to evaluate model outcomes against a prior ICH M15 plan and to
write the Model Analysis Report (MAR). The `§` numbers refer to sections of the
ICH M15 guideline (<https://ich.org/page/multidisciplinary-guidelines#15>).

> **PREREQUISITE:** This skill uses files of the `jinko-task-ichm15-planning`
> skill: `references/terms.md` (shared terms), `references/map.md` (MAP
> template), and `scripts/check_no_skill_leak.py`. Locate that skill
> directory before you start. If it is not installed, install it from
> `novainsilico/jinko-skills`.

> **PREREQUISITE:** The Jinkō upload step needs an initialized `jinko-sdk`
> connection that satisfies `metadata.requires_sdk`. Run the `jinko-sdk-setup`
> skill and continue only when its check passes.

## Inputs

Two inputs are necessary:

1. The planning-stage record: Question of Interest, Context of Use, the four
   rated Key Assessment Elements, Technical Criteria, Appropriateness of
   Proposed MIDD, and the "Deviations From Plan" log. The user gives a MAP (a
   Jinkō document or text) or states the record directly.
2. The model evaluation evidence: verification results, validation and
   applicability results, and the pass, concern, or fail outcome of each
   Technical Criterion.

If one input is missing, ask one question about the gap that changes the
assessment most. Do not run an intake interview. If the user asks for a
best-effort draft without questions, continue. Put each assumed planning-stage
element in an "Assumptions" block at the top of the output.

Do not change the planning-stage ratings. Carry them into the MAR unchanged.

## Assessment content

Write the assessment into the MAR sections given in parentheses. Use only the
rules below that the template does not already show.

- **Verification** (§3; MAR 4.4, 5.3): code, equations, and calculations are
  correct, documented, reproducible, and available for review. Make the depth
  of verification match the Model Risk rating from the MAP, and cite that
  rating.
- **Validation and applicability assessment** (§3; MAR 4, 5): cover data,
  model structure and assumptions, performance and robustness, external
  validation, and simulation.
  - Prioritize the performance metrics that answer the Question of Interest.
  - Address method-specific issues, for example selection bias for
    model-based meta-analysis, knowledge gaps for mechanistic models, and
    overfitting for AI/ML models.
  - If there is no external validation, state whether it is necessary for
    this Question of Interest, Context of Use, and Model Risk. Do not omit the
    gap.
- **Evaluation of Model(s) and Model Outcomes** (§2.2.3; MAR 5.3, 8):
  summarize how the model outcomes meet each Technical Criterion. Put the
  detailed evidence in MAR 5.3.
- **Outcome of MIDD Evidence Assessment** (§2.2.4; MAR 7, 8): give the
  multidisciplinary conclusion on whether the model outcomes are MIDD
  evidence, and how they answer the Question of Interest.

The last two elements are narrative. Write `Not rated` in the Rating column
and keep the MAR section 8 footnote in every table that shows them.

## Safeguards

- Never invent a model evaluation result (verification outcome, metric, or
  Technical Criterion outcome), also in a best-effort draft. Write
  `[data needed]` in its table cell. Do not use a placeholder as a fact in the
  Discussion or Conclusions.
- Carry every logged deviation into MAR 5.4 with its justification and
  impact, and discuss it in MAR 6.
- Write only the content above and the Assumptions block. Do not add an
  introduction, a conclusion, or next steps outside the MAR.
- Do not show skill names, file paths, or workflow structure in a deliverable.
  Write each deliverable to a file and run
  `python <planning-skill-dir>/scripts/check_no_skill_leak.py <file...>`. Fix
  each reported line and run it again until it exits 0.

## Workflow

1. Get the two inputs (see "Inputs").
2. Write the MAR from `references/mar.md`. Remove the `(e.g. ...)` hints.
3. Run the leak check on the MAR file.
4. Ask the user for the target Jinkō project and folder. Then load the
   `jinko-document` skill and create (or update) the MAR as a Jinkō document.
   Skip this step only if the user declines.
5. If a Jinkō MAP document exists, link the two documents in both directions:
   the MAR "Related Model Analysis Plan" field links to the MAP, and the MAP
   Appendices link to the MAR. Use Jinkō document links, not local Markdown
   paths.

At the end of the MAR, cite the ICH M15 guideline:
<https://ich.org/page/multidisciplinary-guidelines#15>.
