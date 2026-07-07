---
name: jk-output-set
description: >-
  Create, inspect, validate, and incrementally edit Jinkō output sets via the
  jinko-sdk: simple output sets (measure designs) that list scalar measures
  derived from model outputs, and advanced output sets (scoring designs) that
  define constraints, scalars, and weighted objectives for scoring virtual
  populations. Validate scoring expressions and read diagnostics before
  attaching an output set elsewhere. Do not use this skill for attaching a
  simple or advanced output set to a trial and running it; use jk-trial for
  that. Do not use this skill for data-table creation or fitness-function
  metadata; use jk-data-table for that. Do not use this skill for calibration
  setup or CMA-ES options; use jk-task-cmaes for that.
compatibility: >-
  Check set-up with the `jk-sdk-setup` skill. Creating output sets requires
  write access to the Jinkō project; simple output sets also require an
  existing model. Advanced output sets can be created standalone. Objective
  preview rendering benefits from IPython and matplotlib but degrades to
  plain text without them.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Output Set SDK Workflows

Use this skill for output-set mechanics through the SDK: creating, validating, inspecting, and incrementally editing simple and advanced output sets.
Keep trial/calibration attachment in `jk-trial` (and, for CMA-ES calibrations, `jk-task-cmaes`), and data tables in `jk-data-table`.

## Core Concepts

Jinkō uses different names for the same objects in the UI, the API, and the SDK.

| UI wording          | API project-item type | SDK entry points                                              |
| -------------------- | ---------------------- | -------------------------------------------------------------- |
| Simple output set    | `MeasureDesign`         | `client.create_simple_output_set(...)`, `SimpleOutputSet`     |
| Advanced output set  | `ScoringDesign`         | `client.create_advanced_output_set(...)`, `AdvancedOutputSet` |

An advanced output set groups three component kinds: constraints (boolean per-patient eligibility expressions), scalars (numeric formulas derived from simulation output), and objectives (range-based scoring rules with a weight).
Scalars serialize under the raw JSON key `components.measures` — do not confuse with simple-output-set "measures".

## Discovering Output Ids

Never invent output ids.
Call `model.time_dependent_ids()` to discover the model's valid output ids before creating a simple output set, same as `jk-trial` does.
Advanced-output-set formulas reference output ids or other scalar ids by name.
If unsure whether a piece of formula syntax is still supported, validate it with `client.validate_scoring_formula(...)` rather than assuming old examples still apply.

## Simple Output Set Workflow

```python
model = client.get_model("cm-...")
output_set = client.create_simple_output_set(model, model.time_dependent_ids())
# Equivalently: model.create_simple_output_set([...])
```

Measures accept output-id strings (shorthand for `{"timeseriesId": id}`) or dicts for custom names, origins, and point-in-time/across-time functions.
Edit with `.content()`, `.measures`, `.replace_all_measures()`, `.add_measures()`, `.remove_measures()`, `.update_measure()`.
See `references/simple-output-set.md` for the full schema.

## Advanced Output Set Workflow

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

Add components incrementally with `scoring_design.components.add_constraint(...)`, `.add_scalar(...)`, `.add_objective(...)` — each call creates a new versioned snapshot.
See `references/advanced-output-set.md` for full schemas, the components service, and the raw JSON escape hatch.

## Validation & Diagnostics

Constraint and formula expressions are validated automatically inside `create()` and `components.add_*()`.
They always raise `ValidationError` on failure — `show_validation` only controls whether a report is printed, it does not suppress the raise.

```python
if scoring_design.diagnostics.errors():
    print(scoring_design.diagnostics.errors().explain())
```

`sd.diagnostics` is chainable: `.for_kind(...)`, `.with_severity(...)`, `.with_code(...)`, `.for_component(...)`, `.errors()`, `.warnings()`, `.has_errors()`, `.by_component()`, `.by_kind()`, `.by_severity()`, `.explain()`.
Use `sd.diagnostics_at(revision)` for a historical snapshot.

## Attaching to Trials/Calibrations

This skill only creates, inspects, and edits output sets — it does not attach them or run anything.
For trials, use `jk-trial`: `model.create_trial(simple_output_set=..., scoring=..., ...)`.
The lower-level `client.create_trial(...)` uses `advanced_output_set=` instead of `scoring=` for the same argument — both exist, pick the one matching your call site.
For calibrations, use `jk-task-cmaes`: `model.create_calibration(simple_output_set=..., scoring=..., ...)`.
A calibration needs at least one fitness-function source: a data table with `validForFitnessFunction: True` (see `jk-data-table`) and/or an advanced output set with objectives.

## Bundled Scripts

- `scripts/create_simple_output_set.py`: dry-run by default, creates a simple output set with `--apply`.
- `scripts/create_advanced_output_set.py`: dry-run by default, creates an advanced output set with `--apply`.
- `scripts/inspect_output_set.py`: inspects an existing simple or advanced output set.
- `scripts/edit_advanced_output_set.py`: adds constraints/scalars/objectives to an existing advanced output set.

```bash
python skills/jk-output-set/scripts/create_simple_output_set.py --model-sid cm-... --output-id Drug
python skills/jk-output-set/scripts/create_simple_output_set.py --model-sid cm-... --output-id Drug --folder 2026-07-07-output-sets --create-folder --apply
python skills/jk-output-set/scripts/create_advanced_output_set.py --constraint "adults:age >= 18" --scalar "auc:AUC_drug" --name "PK scoring"
python skills/jk-output-set/scripts/create_advanced_output_set.py --from-json skills/jk-output-set/assets/advanced_output_set_example.json --apply
python skills/jk-output-set/scripts/inspect_output_set.py --kind advanced --sid sc-... --diagnostics
python skills/jk-output-set/scripts/edit_advanced_output_set.py --sid sc-... --add-objective "obj_auc:AUC_target:8:12:5:15:1.0" --show-diagnostics --apply
```

## Reference Routing

- Read `references/simple-output-set.md` for measure dict shapes and editing methods.
- Read `references/advanced-output-set.md` for constraint/scalar/objective shapes, validation, diagnostics, and tags.
