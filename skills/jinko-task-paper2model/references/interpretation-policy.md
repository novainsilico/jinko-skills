# Interpretation policy

Reproduce the model supported by the evidence. A publication can contain errors,
incomplete definitions, or conflicting representations. Preserve its original
statements and document the defense for each implementation choice.

## Decision rules

| Kind | Required defense | Action |
| --- | --- | --- |
| `equivalent_translation` | Reversible conversion or equivalent expression, with a passed check | Apply automatically |
| `platform_adaptation` | Source and destination semantics, with a passed subsystem check | Apply automatically |
| `source_correction` | Precise source statements, a derivation, and passed verification | Apply automatically |
| `assumption` | Missing evidence, chosen value or convention, impact, and recorded approval | Apply within the approved scope |
| `unresolved_conflict` | Competing statements, alternatives, and affected outputs | Preserve the conflict; block a target-driving path without a defensible executable choice |

Use the smallest sufficient change. A successful solve alone does not establish
scientific correctness. A failed solve alone does not establish a paper error.
Check extraction and platform semantics before changing the science.

An equation correction and a missing parameter value are separate decisions.
For example, a source-supported dimensional correction can still leave an
unknown coefficient. Approval to use that coefficient does not make it a
published value. Test sensitivity when the assumption affects the claim, or
record that its impact has not been measured.

Accept alternative units, state representations, and interpretations when their
defense is documented. Use conversion checks, initial derivatives, event jumps,
or trajectories to test equivalence. Component names and counts alone are not
an equivalence test. Unit substitutions that discard a physical dimension need
an explicit limitation; they are not exact conversions.

## Ledger contract

Use `interpretations` in `reproduction-spec.json` as the authoritative ledger.
A separate `interpretation-ledger.json` is an export of these records, not a
second editable set of decisions. Each record contains:

- `id`, `status`, and `supersedes`: stable identity and decision history.
- `kind`, `decision`, `alternatives`, and `evidence`: the choice and its defense.
  Include why each rejected alternative failed in `evidence`.
- `source_statements`: source IDs, precise locators, and original statements.
- `affected_components` and `implementation_change`: what changed, including
  original and replacement values, expressions, or units.
- `verification`: named checks with status and evidence or result locations.
- `affected_targets`: all declared outputs affected by the choice.
- `informed_by_targets`: targets consulted to choose the interpretation.
- `target_informed`: whether the local `informed_by_targets` list is nonempty.
- `approved_by`: the recorded approver for an assumption; otherwise nullable.

Targets link back through `decision_ids`. Keep these links for historical
decisions too. Record structural changes even when no quantitative target exists.
Use decision IDs in repair and unresolved-conflict summaries. Link each
assumption summary through `decision_id`; derive its text from that decision.
Repair summaries contain active correction or translation IDs.
Unresolved-conflict summaries contain every active unresolved decision ID. Each
assumption summary copies the decision's statement, evidence, approver, and
implementation change into `statement`, `basis`, `approved_by`, and `impact`.

`active` means the current choice or current unresolved conflict. `proposed`
means not applied. `rejected` means considered and rejected. When replacing a
choice, mark it `superseded`, add a successor, and explain the new evidence.
Keep results tied to their specification and model revision. A report must not
present superseded checks or choices as the current model's state.

## Comparison rounds and independence

Freeze the choices, metrics, tolerances, transformations, and event-side
semantics before each comparison round. Retain the failed round if you revise a
choice. A figure used to choose a reporting scale remains target-informed after
review or approval. Report both raw and transformed values.

Dependency tracking is target-specific. If target A selected a choice, mark A
non-independent. A held-out target B can remain independent even when that choice
affects B. The validator retains selection dependencies from superseded choices;
changing a decision ID cannot restore independence.

When required publication targets include a target used to select the current
implementation, the executable model's outcome is `partially_reproduced`, even
if all numerical comparisons pass. `reproduced` with lower confidence does not
satisfy this rule. Apply it to inherited selection evidence too. Report each
held-out result on its own merits. Do not remove failed or selection targets from the agreed scope to obtain
a stronger verdict. An unresolved issue outside the declared scope must be
documented as a limitation.

## Two assessments

Every target has a `basis`: `publication` or `curated_implementation`.
`assessment.outcome` and `confidence` describe publication reproduction only.
`assessment.curated_implementation` contains `status`, `rationale`, and
`reference_artifact`. Status is `passed`, `failed`, `incomplete`, or
`not_assessed`. A scored comparison requires a hashed reference artifact.
An active assumption affecting publication targets prevents high confidence.
Record an unresolved decision outside the target scope in a limitation that
names its ID.

Freeze the curated model revision or export, interpretation set, units,
protocol, initial conditions, solver settings, output mapping, and tolerances
in that artifact. A curated trajectory is a regression reference for those
choices. It is not independent proof that the publication has been reproduced.

For benchmark design, keep three layers separate:

1. Verified source facts, with source locators and extraction provenance.
2. Reviewed interpretations, acceptable alternatives, and unresolved questions.
3. Numerical regression references tied to a fixed implementation.

Keep curator decisions and outputs hidden from a blind reconstruction agent.
Expose them only to the evaluator after the reconstruction is frozen. Score
source reasoning, execution, publication agreement, and curated agreement
separately. Credit a justified blocked or unresolved result. Distinguish a
curator-reviewed statement from a primary source checked in the current run.

Do not infer approvals, passed checks, or independence from historical prose.
Leave unsupported decisions proposed and measurements unavailable until
evidence is recovered.
