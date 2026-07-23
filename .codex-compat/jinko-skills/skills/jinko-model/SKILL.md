---
name: jinko-model
description: >-
  Build or edit a Jinkō computational model (QSP/PK-PD) via the jinko-sdk: parameters, categorical parameters, compartments, species, ODEs, reactions, dosing events, algebraic or assignment rules, baseline checks, and solving options. Use this skill whenever the user wants to create a model from scratch, create an empty model, edit an existing model, add or modify components, configure unit checking, define model-level dosing events, validate diagnostics, or debug model sanity or simple_solve errors. Prefer editing existing models over recreating them. Do not use this skill for running trials; use jinko-trial for trial execution.
compatibility: >-
  Check set-up with the `jinko-sdk-setup` skill. Model creation/editing requires write access to the Jinkō project.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Model SDK Workflows

Use this skill for technical model construction and editing through the SDK. Keep the scope on SDK mechanics and model validity, not biological plausibility.

> **PREREQUISITE:** Before using this skill, make sure the Jinkō connection is
> initialized as described in `../jinko-sdk-setup/SKILL.md`. If that skill is not
> found, check the available skills for `jinko-sdk-setup`, or tell the user
> to install it from `novainsilico/jinko-skills` before proceeding.

## Core Rules

- Prefer editing an existing model over recreating a model from scratch.
- Start a new model only when the user explicitly needs one, using `client.create_empty_model()`.
- Favor high-level component methods; do not build raw model payloads unless the typed SDK surface cannot express the requested edit.
- Favor `model.components.batch(version=...)` for component changes so related edits are committed as one model version.
- Treat a complete model as one with no error-level diagnostics and a successful `simple_solve()` for relevant outputs.
- For event-driven behavior, also check the returned series for the intended pre-/post-event change; a successful solve only proves that the solver ran.
- Report diagnostics or solve errors clearly and ask whether the user wants them fixed.

## Project Folder Hygiene

- Prefer creating models inside a dedicated Jinkō folder instead of the project root. At the start of a workflow, ask for or propose a folder name, for example `YYYY-MM-DD-<experiment-name>`.
- Reuse an existing exact-match folder when possible: `client.get_folder_by_name(name, exact_match_only=True)`.
- If the folder does not exist, create it only after user confirmation or when a script is run with `--apply`.
- Resolve one folder object or folder id, then pass `folder=folder` to SDK creation calls that support it.

## Default Workflow

1. Load credentials and construct `JinkoClient()`.
2. If the user has a model SID, retrieve it with `client.get_model("<model-sid>")`.
3. If the user needs a new model, create an empty model, then add components in a batch.
4. Set solving options intentionally, especially `unitCheck`.
5. Stage component changes with `model.components.batch(version="...")`.
6. Re-fetch the model after edits if you need fresh diagnostics or solving behavior.
7. Check diagnostics with `model.diagnostics.errors()`.
8. Check solvability with `model.simple_solve(timeseries_ids=[...])`, using `model.time_dependent_ids()` as the default candidate outputs when the user has not specified ids.
9. If the default `simple_solve` candidates exceed 10 ids, preselect the first 10 returned by `model.time_dependent_ids()` and ask the user to confirm or adjust the selection before solving.

## Example Scripts

Use scripts rather than embedding long Python snippets in chat.

- `scripts/create_minimal_model.py`: creates a small model from an empty model when run with `--apply`.
- `scripts/edit_existing_model_batch.py`: applies a batch edit template to an existing model when run with `--apply`.
- `scripts/validate_model_readiness.py`: checks diagnostics and `simple_solve()` for an existing model.

Examples:

```bash
python skills/jinko-model/scripts/create_minimal_model.py --name sdk-minimal-model
python skills/jinko-model/scripts/create_minimal_model.py --name sdk-minimal-model --apply
python skills/jinko-model/scripts/create_minimal_model.py --name sdk-minimal-model --folder 2026-06-15-pk-study --create-folder --apply
python skills/jinko-model/scripts/edit_existing_model_batch.py --model-sid cm-... --apply
python skills/jinko-model/scripts/validate_model_readiness.py --model-sid cm-...
python skills/jinko-model/scripts/validate_model_readiness.py --model-sid cm-... --timeseries-id Drug
python skills/jinko-model/scripts/validate_model_readiness.py --model-sid cm-... --timeseries-id meal_rate --expect-series-change meal_rate
```

## Formula Syntax

- Piecewise formulas use ternary syntax: `condition ? value_if_true : value_if_false`.
- Categorical switches use case syntax: `case ID of { value1 -> expr1; value2 -> expr2; _ -> fallback }`.
- Event `time_trigger_*` expressions need time dimension, for example `0 * u(h)` or `1 * u(day)`.
- Recurrent events (for regular doses) use `time_trigger_first_time` plus `time_trigger_every`, and optionally `time_trigger_count` or `time_trigger_until`.
- ODE right-hand sides are rates. Under unit checking, multiply by an inverse-time unit when the expression is otherwise dimensionless.

## Units Policy

- Read `references/unit_docs.md` before advising on non-trivial units or conversion behavior.
- Use `references/units_static_info.json` as the default allowed-unit registry before introducing non-trivial units or aliases.
- Refresh unit registry data from `/core/v2/static/units/static_info` only if the local registry is stale or insufficient.
- Set `unitCheck` intentionally and tell the user which mode was selected.
- Prefer `UnitCheckAndConvertAllSpeciesToExtentUnits` for new SDK-created models unless the user has a reason to choose another mode.
- Do not add an unverified "positive exponents only" rule for unit strings. Use the documented unit syntax and validate non-trivial units with diagnostics and a representative solve.

Available unit-check modes:

- `NoUnitCheck`
- `UnitCheckWithNoUnitConversion`
- `UnitCheckAndConvertAllSpeciesToExtentUnits`
- `UnitCheckAndConvertOnlyReactantsAndProductsToExtentUnits`

## Solving times policy

- Jinko solving time options must stay within a 10..1000 time points.
- Number of points is `(tMax - tMin) / tStep + 1`.
- If `TOO_MANY_TIMEPOINTS` occurs, increase step size.
- First-pass heuristic:
  - compute `tStep_sec = (tMax_sec - tMin_sec) / 100`,
  - convert to canonical ISO8601/Jinko duration using `duration_from_secs` from `scripts/iso8601.py`
  - round down to first non-null unit using `round_duration_down_to_full_unit`

## Reference Routing

- Read `references/model-components.md` for component batching, event safety, algebraic rules, and method names.
- Read `references/model-validation.md` for diagnostics and `simple_solve()` readiness checks.
- Read `references/unit_docs.md` for unit semantics.
