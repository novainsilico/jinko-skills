# Advanced output set (scoring design)

Load this reference when the user asks how to create, validate, inspect, or edit an advanced output set — the UI wording for what the API calls a `ScoringDesign`.
An advanced output set defines how a virtual population is scored, via three component kinds: constraints, scalars, and objectives.

## Component dict schemas

**Constraint** — boolean expression a patient must satisfy to be included:

- `id` *(required)*: unique identifier, e.g. `"adults"`.
- `constraint` *(required)*: boolean expression, e.g. `"age >= 18"`.
- `filter`: optional condition restricting which time points or arms it applies to. Do not use ISO durations such as `"time > PT47H"` or unqualified scientific thresholds such as `"time > 900"`; use a named, unit-bearing model helper parameter instead (for example `"time > analysisStartTime"`).
- `description`, `display_name`, `is_active`: optional metadata.

**Scalar** — numeric formula derived from simulation output.
Serializes under the raw JSON key `components.measures`; unrelated to simple-output-set "measures".

- `id` *(required)*: unique identifier, e.g. `"auc"`.
- `formula` *(required)*: numeric expression, e.g. `"auc(Drug)"`.
- `unit`: optional unit string accepted on scalars, e.g. `"mg/L*h"`. It declares the scalar's expected unit; it is distinct from the unsupported `u(...)` expression syntax. Set it from the verified model/time context rather than guessing an AUC/integral time factor.
- `description`, `display_name`, `is_active`: optional metadata.

See `formula-language.md` for the actual formula/condition grammar (functions, time indexing, arm references) — the `constraint`/`formula` examples below are shapes, not a syntax reference.

**Objective** — range-based scoring rule applied to a scalar or expression:

- `id` *(required)*: unique identifier.
- `formula` *(required)*: dict with `"target"` (expression, or `None` to score bounds directly) and `"range"` (`narrowRangeLowBound`, `narrowRangeHighBound`, `wideRangeLowBound`, `wideRangeHighBound`).
- `weight` *(required)*: positive float, this objective's relative contribution to the overall score.
- `filter`, `description`, `display_name`, `is_active`: optional.

## Creation

```python
scoring_design = client.create_advanced_output_set(
    constraints=[{"id": "adults", "constraint": "age >= 18"}],
    scalars=[{"id": "auc", "formula": "auc(Drug)", "unit": "mg/L*h"}],
    objectives=[
        {
            "id": "obj_auc",
            "formula": {
                "target": "auc",
                "range": {
                    "narrowRangeLowBound": 8.0,
                    "narrowRangeHighBound": 12.0,
                    "wideRangeLowBound": 5.0,
                    "wideRangeHighBound": 15.0,
                },
            },
            "weight": 1.0,
        }
    ],
    name="PK scoring",
)
```

Raw JSON escape hatch: `client.create_advanced_output_set_from_json(json_content=..., json_file_path=..., name=..., folder=..., description=..., version=...)`.

## Validation contract

`client.validate_scoring_condition(expr)` and `client.validate_scoring_formula(expr)` run automatically inside `create()` and `components.add_*()`.
They always raise `ValidationError` on failure, regardless of `show_validation` — that argument only controls whether a report is printed (defaults to `True` in Jupyter, `False` elsewhere).
Validate directly first when unsure whether an expression is currently supported; do not assume syntax from older examples still works.

**This is standalone validation only.** `validate_scoring_formula`/`validate_scoring_condition` and `scoring_design.diagnostics` check formula syntax and that referenced ids resolve to *something* — they have no notion of a concrete trial's simple output set, protocol, or model. An advanced output set that passes every check in this skill can still fail Jinkō's trial-context sanity check once attached to a trial. Do not conclude "this advanced output set is compatible with trial X" from these checks; use `trial.sanity()` in `jinko-trial` for that.

### Range bound constraints

`narrowRangeLowBound` must be strictly greater than `wideRangeLowBound` (and by symmetry, `narrowRangeHighBound` strictly less than `wideRangeHighBound`) — the narrow range must sit strictly inside the wide range, touching bounds is rejected. `scoring_design.diagnostics.has_errors()` catches this (`"narrowRangeLowBound must be greater than wideRangeLowBound"`), but it is easy to hit by accident when both bounds are meant to be "no lower limit" (e.g. `0.0` for both) — use a small epsilon offset (e.g. `wideRangeLowBound=0.0, narrowRangeLowBound=0.001`) instead of equal bounds.

### Common pitfalls

- **Formula syntax drift**: the expression grammar accepted by `validate_scoring_formula`/`validate_scoring_condition` has changed across Jinkō versions. Re-validate old example formulas rather than assuming they still parse — a syntax change here raises `ValidationError` immediately, which is easy to fix; it is the *silent* trial-context failures below that this skill cannot catch.
- **Derived measures referencing ids outside this output set**: a scalar or objective formula can reference another component's `id` defined in *this* advanced output set. Standalone validation only checks that the referenced `id` exists among this output set's own components — it cannot know whether an id is meant to resolve against the trial's model outputs or simple output set, since those aren't visible until the advanced output set is attached to a concrete trial. If a formula is meant to reference a model output or a simple-output-set measure, confirm that binding with `trial.sanity()` after attaching, not with standalone validation.
- **Objective `target` referencing a sibling scalar's `id` can fail `trial.sanity()` even though it's the pattern shown in this file's own creation example** (`target: "auc"` for a scalar `id: "auc"`). Observed on a live trial: `client.create_advanced_output_set(scalars=[{"id": "tumor_burden_auc", "formula": "auc(T)", ...}], objectives=[{"id": "obj_x", "formula": {"target": "tumor_burden_auc", ...}}])` passes `scoring_design.diagnostics` cleanly, but attaching to a trial and calling `trial.sanity()` reports `ADVANCED_OUTPUTS_ERRORS` for the objective only (the scalar itself resolves fine), with the same "not a model descriptor" diagnostic you'd get from a genuine typo. The fix that resolved it: put the scalar's own formula directly in the objective's `target` (`"target": "auc(T)"`) instead of referencing the scalar `id`. Treat any `target` that is a bare sibling-scalar id as suspect — verify with `trial.sanity()` after attaching, and if it fails, try inlining the formula before assuming something else is wrong.
- **Reserved/shorthand names**: picking a component `id` that collides with a model output id or another reserved name can pass standalone validation (the expression still parses) yet resolve to the wrong quantity once bound to a trial. When in doubt, use `trial.sanity()` to confirm the intended binding.

## Incremental editing

Each `add_*` call creates a new versioned snapshot:

```python
scoring_design.components.add_constraint("adults", constraint="age >= 18")
scoring_design.components.add_scalar("auc", formula="auc(Drug)", unit="mg/L*h")
scoring_design.components.add_objective(
    "obj_auc",
    formula_target="auc",
    narrow_range_low_bound=8.0,
    narrow_range_high_bound=12.0,
    wide_range_low_bound=5.0,
    wide_range_high_bound=15.0,
    weight=1.0,
)
```

All `add_*` methods accept `filter`, `description`, `display_name`, `is_active`, `tags`, `links`, `version`, `show_validation`.
For edits not covered by these helpers, use `scoring_design.edit(payload, ...)` as a raw last resort.

## Listing and reading components

- `scoring_design.components.list()`: all components (constraints, scalars, objectives, in that order).
- `.list_constraints()`, `.list_scalars()`, `.list_objectives()`: filtered by kind.
- `.get(component_id)`: retrieve by user-defined id.
- `.get_by_immutable_id(immutable_id)`: retrieve by platform-assigned immutable id (stable across renames/versions).
- `.get_constraint(id)`, `.get_scalar(id)`, `.get_objective(id)`: typed retrieval.

## Diagnostics

```python
if scoring_design.diagnostics.errors():
    print(scoring_design.diagnostics.errors().explain())
```

`scoring_design.diagnostics` fetches fresh each access and is chainable:

- `.for_kind("Constraint"|"Scalar"|"Objective")`
- `.with_severity(...)`, `.with_code(code)`, `.for_component(component_or_id)`
- `.errors()`, `.warnings()`, `.has_errors()`
- `.by_component()`, `.by_kind()`, `.by_severity()`
- `.explain()`: diagnostics alongside each component's definition

Use `scoring_design.diagnostics_at(revision)` for a historical snapshot.
Check `.has_errors()` before attaching an advanced output set to a trial or calibration.

## Other capabilities

- `scoring_design.summary()`: backend summary of the current snapshot.
- `scoring_design.show_objective_preview(objective_id)`: Jupyter-only formula/curve preview, falls back to plain text without IPython/matplotlib.
- Tags: `scoring_design.tags`, `.get_tag(id)`, `.create_tag(id, description=, color=)`, `.delete_tag(tag, force=False)`.
  Attach via `tags=` on `add_constraint`/`add_scalar`/`add_objective`; filter with `components.list(tags_all=..., tags_any=...)`.

## Discovery

- `client.list_advanced_output_sets(...)`, `client.iter_advanced_output_sets(...)`
- `client.get_advanced_output_set(sid)`
