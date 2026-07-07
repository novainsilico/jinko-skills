# Advanced output set (scoring design)

Load this reference when the user asks how to create, validate, inspect, or edit an advanced output set — the UI wording for what the API calls a `ScoringDesign`.
An advanced output set defines how a virtual population is scored, via three component kinds: constraints, scalars, and objectives.

## Component dict schemas

**Constraint** — boolean expression a patient must satisfy to be included:

- `id` *(required)*: unique identifier, e.g. `"adults"`.
- `constraint` *(required)*: boolean expression, e.g. `"age >= 18"`.
- `filter`: optional expression restricting which time points or arms it applies to.
- `description`, `display_name`, `is_active`: optional metadata.

**Scalar** — numeric formula derived from simulation output.
Serializes under the raw JSON key `components.measures`; unrelated to simple-output-set "measures".

- `id` *(required)*: unique identifier, e.g. `"auc"`.
- `formula` *(required)*: numeric expression, e.g. `"AUC_drug"`.
- `unit`: optional unit string, e.g. `"mg/L*h"`.
- `description`, `display_name`, `is_active`: optional metadata.

**Objective** — range-based scoring rule applied to a scalar or expression:

- `id` *(required)*: unique identifier.
- `formula` *(required)*: dict with `"target"` (expression, or `None` to score bounds directly) and `"range"` (`narrowRangeLowBound`, `narrowRangeHighBound`, `wideRangeLowBound`, `wideRangeHighBound`).
- `weight` *(required)*: positive float, this objective's relative contribution to the overall score.
- `filter`, `description`, `display_name`, `is_active`: optional.

## Creation

```python
scoring_design = client.create_advanced_output_set(
    constraints=[{"id": "adults", "constraint": "age >= 18"}],
    scalars=[{"id": "auc", "formula": "AUC_drug", "unit": "mg/L*h"}],
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

## Incremental editing

Each `add_*` call creates a new versioned snapshot:

```python
scoring_design.components.add_constraint("adults", constraint="age >= 18")
scoring_design.components.add_scalar("auc", formula="AUC_drug", unit="mg/L*h")
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
