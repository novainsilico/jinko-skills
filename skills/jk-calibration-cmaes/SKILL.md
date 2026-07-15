---
name: jk-calibration-cmaes
description: >-
  Create, run, poll, and inspect results for Jinkō CMA-ES calibrations via
  the jinko-sdk: attach data tables and/or an advanced output set as
  fitness-function sources, set CMA-ES options and parameter priors, launch
  and monitor the run, and read performance/results payloads. Use whenever
  the user needs the SDK mechanics of building or driving a Calibration
  object. Do not use this skill for calibration business rules (defaults,
  diagnostics, deliverable rules) — use jk-task-cmaes. Do not use this
  skill for advanced output set / scoring design authoring — use
  jk-output-set. Do not use this skill for data-table creation or
  validForFitnessFunction checks — use jk-data-table. Do not use this
  skill for model or protocol authoring — use jk-model / jk-protocol. Do
  not use this skill for calibration-plan orchestration or iteration
  workflow — use nova-workflow-calib-plan / nova-workflow-calibration-process.
compatibility: >-
  Check set-up with jk-sdk-setup. Creating/running calibrations requires
  write and run permissions.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō CMA-ES Calibration SDK Workflows

| UI wording  | API project-item type | SDK entry points |
| ----------- | ---------------------- | ----------------- |
| Calibration | `Calibration`           | `client.create_calibration(...)`, `model.create_calibration(...)`, `Calibration` domain object |

The calibration manager API is CMA-ES only — no type/method discriminator exists. "Subsampling" is an unrelated VPop-generator feature, not a calibration type.
This skill is pure SDK mechanics: no defaults, no diagnostics, no when-to-calibrate guidance. Use `jk-task-cmaes` for that.

## Minimum Calibration

- `parameters`: priors to calibrate (required, ≥1).
- At least one fitness-function source (required): `dataTableDesigns` (data table must report `metadata.public.validForFitnessFunction: True`, see `jk-data-table`) and/or an advanced output set with objectives (see `jk-output-set`). This skill creates neither input.
- `CalibrationOptions`: `seed` + `thresholdWeightedScore` (schema-required), `populationSize` + `numberOfIterations` (functionally required).

## Create

```python
model = client.get_model("cm-...")
data_table = client.get_data_table("dt-...")
calibration = model.create_calibration(
    data_tables=[data_table],
    parameters=[
        {
            "id": "k_elim",
            "mean": -1.0,
            "std": 0.5,
            "log_transform": True,
            "min_bound": -3.0,
            "max_bound": 1.0,
        }
    ],
    calib_seed=42,
    calib_threshold_weighted_score=0.0,
    calib_number_of_iterations=100,
    calib_population_size=12,
)
```

Equivalent client-level call: `client.create_calibration(model=model, ...)`.
`calibrationOptionsOverride`, `solvingOptionsOverride`, `coreVersion` have no typed kwarg — use `client.create_calibration_from_json(json_content=payload)` / `client.calibrations.create_raw(payload)`.
See `references/creating-a-calibration.md` for full field tables.

## Run & Poll

```python
calibration.run()
final_status = calibration.wait_until_completed(timeout=3600)
```

See `references/running-and-polling.md` for `.get_sanity()`, `.status_with_metadata()`, `StoppingReason` values.

## Results

```python
calibration.performance()  # raw dict
calibration.results_summary()  # raw dict
calibration.objective_weights()  # raw dict, {objective_id: weight}
calibration.results.sorted_patients(sort_by="weightedScore desc")  # raw, low-level
```

All results accessors return unparsed dicts today. See `references/results-and-inspection.md`.

## Project Folder Hygiene

Same as `jk-trial`/`jk-data-table`: propose a `YYYY-MM-DD-<experiment>` folder, reuse an exact-name match via `client.get_folder_by_name(name, exact_match_only=True)`, create only on confirmation or `--create-folder --apply`.

## Bundled Scripts

- `scripts/create_cmaes_calibration.py`: dry-run by default, creates a calibration with `--apply`.
- `scripts/run_calibration.py`: runs and polls an existing calibration with `--apply`.
- `scripts/inspect_calibration.py`: prints/writes raw performance/results_summary/objective_weights/sorted_patients JSON.

```bash
python skills/jk-calibration-cmaes/scripts/create_cmaes_calibration.py --model-sid cm-... --data-table-sid dt-... --parameter "k_elim:-1.0:0.5:-3.0:1.0:log" --seed 42 --threshold-weighted-score 0.0 --iterations 100 --population-size 12
python skills/jk-calibration-cmaes/scripts/create_cmaes_calibration.py --model-sid cm-... --data-table-sid dt-... --parameter "k_elim:-1.0:0.5:-3.0:1.0" --seed 42 --threshold-weighted-score 0.0 --iterations 100 --population-size 12 --folder 2026-07-07-calib --create-folder --apply
python skills/jk-calibration-cmaes/scripts/run_calibration.py --calibration-sid ca-... --apply --timeout 3600
python skills/jk-calibration-cmaes/scripts/inspect_calibration.py --calibration-sid ca-... --performance --results-summary --objective-weights --output-dir calib-results
```

## Reference Routing

- `references/creating-a-calibration.md`: full field tables, three creation patterns.
- `references/running-and-polling.md`: run/stop/status/sanity, `JobStatus`, `StoppingReason`.
- `references/results-and-inspection.md`: performance/results_summary/objective_weights/results.* field tables and caveats.
