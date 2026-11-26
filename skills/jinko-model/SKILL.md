---
name: jinko-model
description: >-
  Build or edit a Jinkō computational model (QSP/PK-PD) via the jinko-sdk: parameters, categorical parameters, compartments, species, ODEs, reactions, dosing events, algebraic rules, baseline checks, solving options, units, and component tags. Use this skill whenever the user wants to create a model from scratch, create an empty model, import a model from an SBML, SimBiology XLSX, or Monolix file or a Monolix project, edit an existing model, add or modify components, apply input/source/output tags, configure unit checking, define model-level dosing events, combine two models and resolve their conflicts, validate diagnostics, or debug model sanity or simple_solve errors. Prefer editing existing models over recreating them. Do not use this skill for running trials; use jinko-trial for trial execution.
compatibility: >-
  Check set-up with the `jinko-sdk-setup` skill. Model creation/editing requires write access to the Jinkō project.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.22,<2.0"
license: MIT
---

# Jinkō Model SDK Workflows

Use this skill for technical model construction and editing through the SDK. Keep the scope on SDK mechanics and model validity, not biological plausibility. Initialize the connection with `jinko-sdk-setup` first.

> **PREREQUISITE:** This skill needs an initialized `jinko-sdk` connection and
> an SDK satisfying its `metadata.requires_sdk` range. Run the `jinko-sdk-setup`
> skill (`../jinko-sdk-setup/SKILL.md`) and proceed only once its check passes.
> Use `JINKO_API_KEY` when it is set. Only without a key, call
> `get_session_code` again before this skill's own SDK process, because a
> session code can be exchanged only once. If that skill is not found, install
> it from `novainsilico/jinko-skills`.

## Required Workflow

1. If a model was already supplied, prefer editing it over creating a new one. Create one only when needed, in a dedicated folder, with `client.create_empty_model()`.
   To import an SBML, SimBiology XLSX, or Monolix structural model file, use `client.create_model_from_file()`. To import a Monolix project (`.mlxtran`), use `client.import_monolix_project()`: it also creates a simple output set and a trial. To replace the content of an existing model from such a file, use `model.replace_from_file()`: it creates a new version and drops the component tags. An import may rename components, change units, or leave inputs without values: review the result like any other model with the steps below.
2. Retrieve the model, inspect its components, tags, units, solving options, and diagnostics before proposing edits. Inspect the unit-checking mode with `model.get_unit_check()`.
3. Set the unit-checking mode with `model.set_unit_check("UnitCheckAndConvertAllSpeciesToExtentUnits")`. Do not select another mode unless a human explicitly directs it after the consequences are explained.
4. Give every directly declared numeric value a unit: numeric parameter formulas, compartment volumes, and species initial conditions. Give a literal inside a formula its unit with `u(...)`, for example `13.2 * u(L/h) * scale`. A derived parameter may omit its declared unit only when it is not an output: declare the unit of every `output` parameter, including `dimensionless`, or results report the raw number in a composite unit. Validate non-trivial units against `references/units_static_info.json` and diagnostics. Read `references/unit-pitfalls.md` before building a model with non-substance states (volumes, cell counts, dimensionless) or literal physiological values.
5. Attach the built-in platform tags before considering the model complete:
   - `i::vpop` for inputs that vary across virtual patients.
   - `i::protocol` for inputs that vary across protocol arms or scenarios, including the dose amount, first dose time, dose interval, and number of doses of a dosing event.
   - One evidence-backed source tag for each applicable value-bearing input: `s::knowledge`, `s::arbitrary`, or `s::to-calibrate`. Leave an uncertain input untagged and report it for review. Never assign `s::calibrated` during construction; it records an accepted calibration result.
   - `output` for important time-series outputs to plot or calibrate against.

   Three of these decide whether the model is usable downstream, so check them
   across the whole model, not only per component. At least one component must
   carry `output`, or nothing can be plotted, measured, or calibrated against:
   treat its absence as an error. No component carrying `i::protocol` means the
   model cannot be given protocol arms, and none carrying `i::vpop` means it
   cannot vary across virtual patients: report each as a warning, correct only
   for a model meant to be single-arm and deterministic.
   `python -m jinko.cli.validate_model_readiness --model-sid cm-...` runs these
   three checks by default.
6. Attach a traceability link to every value-bearing input tagged `s::knowledge`. Prefer, in this order: the Extract that holds the value, the Reference that holds the Extract, then any other project item that produced the value. Use an external DOI or URL only when the project holds no such item, and report every external link for review. Use the `jinko-reference` skill to upload a missing source PDF as a Reference and to create its Extracts before you link. Put them in the folder that the project's folder convention gives for References.
7. Optionally attach scientific scoped tags for model navigation and visualization:
   - `granularity::*` for biological or spatial scale; tag color `#0cd95e`.
   - `phenomenon::*` for the represented physical or biological process; tag color `#f87171`.
   - `module::*` for an implemented mechanism or submodel; tag color `#66c09c`.
   - `readout::*` for observation level; tag color `#da1d1d`.

   Use confirmed component definitions and source evidence. Preserve existing
   tags; leave unsupported classifications unassigned. These custom tags are
   not readiness requirements. Read [scientific scoped tags](references/scientific-scoped-tags.md)
   for selection rules and the QSP, PBPK, and PK/PD example catalog.
   Pass the family color to `model.create_tag(..., color=...)`; use
   `tag.set_color(...)` when aligning an existing declaration. Tag-family colors
   are separate from graph component-type colors.
8. Use high-level SDK methods and `model.components.batch(version="...")` for related component changes. When the model is generated from code or a specification, keep a declarative target and apply it with `scripts/sync_model_to_target.py`: it diffs the target against the latest model version and commits only real changes. The platform tags above already exist; do not recreate them. Create declarations only for other, custom tags.
9. Re-fetch the model, require no error diagnostics, and run `simple_solve()` for representative `output` components. For events, verify the expected pre-/post-event change.

To read a method signature, call `help()` on the object the client returns, for example `help(type(model))` or `help(model.simple_solve)`. The SDK has no `jinko.model` module.

Use `scripts/create_minimal_model.py`, `scripts/sync_model_to_target.py`, and the SDK's `python -m jinko.cli.tag_model_components` and `python -m jinko.cli.validate_model_readiness`, rather than long ad-hoc snippets. Scripts are dry-run by default and mutate only with `--apply`.

For transparent ISO 8601 duration conversions, use `from jinko.iso8601 import Duration`, for example `Duration.parse("P1M").to_timedelta()`. Solving times accept `timedelta` or ISO strings: `model.set_solving_times(t_max=timedelta(days=28), t_step="P1D", additional_periods=[{"t_max": "P7D", "t_step": timedelta(hours=1)}])`.

## Reference Routing

- Read `references/model-components.md` for component batching, tags, events, formulas, and algebraic rules. Its "Keep piecewise outputs continuous" section applies to every `?:` formula on an output, such as a log with a floor.
- Read `references/unit_docs.md` for unit semantics and conversion behavior.
- Read `references/unit-pitfalls.md` for errors that pass creation and fail in diagnostics or results, with fixes.
- Use `scripts/sync_model_to_target.py --model-sid cm-... --target target.json` to plan (dry run) and then `--apply --base-snapshot <id>` to sync an existing model to a JSON target. Its docstring gives the target format.
- Read `references/model-validation.md` for diagnostics and readiness checks.
- Read `references/model-combination.md` before `combine_with`, and to read or resolve `model.conflicts`.
- Read `references/scientific-scoped-tags.md` when selecting optional scale, phenomenon, module, or readout tags. It includes a broad, extensible catalog of QSP, PBPK, and PK/PD examples.

## Slow solves and solver failures

For a timeout, non-finite result, or simple_solve taking at least 15 seconds,
use `jinko-task-debug-solving-errors`. The threshold is a triage signal; client
wall time includes overhead. Start with `python -m jinko.cli.debug_solving
--model-sid cm-... --out <new-directory>` to retain a pinned diagnostic bundle.
The command does not rerun the model unless `--run-simple-solve` is supplied.
Keep available `__jinko*` outputs for performance diagnosis, separate from
scientific comparisons. Do not change solver settings automatically.
