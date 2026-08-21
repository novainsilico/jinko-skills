---
name: jinko-model
description: >-
  Build or edit a Jinkō computational model (QSP/PK-PD) via the jinko-sdk: parameters, categorical parameters, compartments, species, ODEs, reactions, dosing events, algebraic rules, baseline checks, solving options, units, and component tags. Use this skill whenever the user wants to create a model from scratch, create an empty model, edit an existing model, add or modify components, apply input/source/output tags, configure unit checking, define model-level dosing events, validate diagnostics, or debug model sanity or simple_solve errors. Prefer editing existing models over recreating them. Do not use this skill for running trials; use jinko-trial for trial execution.
compatibility: >-
  Check set-up with the `jinko-sdk-setup` skill. Model creation/editing requires write access to the Jinkō project.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Model SDK Workflows

Use this skill for technical model construction and editing through the SDK. Keep the scope on SDK mechanics and model validity, not biological plausibility. Initialize the connection with `jinko-sdk-setup` first.

## Required Workflow

1. Prefer editing the supplied model. Create one only when needed, in a dedicated folder, with `client.create_empty_model()`.
2. Retrieve the model, inspect its components, tags, units, solving options, and diagnostics before proposing edits. Inspect the unit-checking mode with `model.get_unit_check()`.
3. Set the unit-checking mode with `model.set_unit_check("UnitCheckAndConvertAllSpeciesToExtentUnits")`. Do not select another mode unless a human explicitly directs it after the consequences are explained.
4. Give every directly declared numeric value a unit: numeric parameter formulas, compartment volumes, and species initial conditions. A parameter whose value is derived from an expression may omit its declared unit when the expression determines it. Validate non-trivial units against `references/units_static_info.json` and diagnostics.
5. Attach the built-in platform tags before considering the model complete:
   - `i::vpop` for inputs that vary across virtual patients.
   - `i::protocol` for inputs that vary across protocol arms or scenarios.
   - One evidence-backed source tag for each applicable value-bearing input: `s::knowledge`, `s::arbitrary`, or `s::to-calibrate`. Leave an uncertain input untagged and report it for review. Never assign `s::calibrated` during construction; it records an accepted calibration result.
   - `output` for important time-series outputs to plot or calibrate against.
6. Use high-level SDK methods and `model.components.batch(version="...")` for related component changes. The platform tags above already exist; do not recreate them. Create declarations only for other, custom tags.
7. Re-fetch the model, require no error diagnostics, and run `simple_solve()` for representative `output` components. For events, verify the expected pre-/post-event change.

Use `scripts/create_minimal_model.py`, `scripts/tag_model_components.py`, and `scripts/validate_model_readiness.py` rather than long ad-hoc snippets. Scripts are dry-run by default and mutate only with `--apply`.

For solver time-grid calculations, use `scripts/iso8601.py`.

## Reference Routing

- Read `references/model-components.md` for component batching, tags, events, formulas, and algebraic rules.
- Read `references/unit_docs.md` for unit semantics and conversion behavior.
- Read `references/model-validation.md` for diagnostics and readiness checks.
