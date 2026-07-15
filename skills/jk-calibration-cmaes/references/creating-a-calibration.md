# Creating a Calibration

## `Calibration` body

| Field | Required | Notes |
| --- | --- | --- |
| `parameters` | yes | `CalibrationParameter[]` |
| `dataTableDesigns` | yes | `DataTableDesign[]` (may be empty array only if `scoringDesignId` supplies objectives) |
| `computationalModelId` | no | `{coreItemId, snapshotId}` |
| `protocolDesignId` | no | `{coreItemId, snapshotId}` |
| `scoringDesignId` | no | advanced output set ref |
| `measureDesignId` | no | simple output set ref |
| `coreVersion` | no | engine version pin — **no typed kwarg, use raw creation** |
| `calibrationOptions` | no (practically required) | `CalibrationOptions` |
| `calibrationOptionsOverride` | no | `CalibrationOptionsJson`, all-nullable — **no typed kwarg, use raw creation** |
| `solvingOptions` | no | `SolvingOptions` |
| `solvingOptionsOverride` | no | `SolvingOptions` — **no typed kwarg, use raw creation** |

## `CalibrationParameter`

| Field | Default | Notes |
| --- | --- | --- |
| `id` | — | required, sbml-id |
| `logTransform` | `false` | |
| `mean` | — | nullable |
| `std` | — | nullable |
| `minBound` | `-inf` | nullable |
| `maxBound` | `+inf` | nullable |

## `dataTableDesigns[]` (`DataTableDesign`)

| Field | Notes |
| --- | --- |
| `dataTableId` | `{coreItemId, snapshotId}` |
| `include` | bool |
| `options.label` | sbml-id, names the generated fitness function |
| `options.weight` | default 1, ≥0 |
| `options.logTransformWideBounds` | observable id list |
| `options.timeTolerance` | date/duration string |

## `CalibrationOptions`

| Field | Bounds | Default | Required in schema |
| --- | --- | --- | --- |
| `seed` | 0–4294967295 | — (required, no default) | yes |
| `thresholdWeightedScore` | any | — (required, no default) | yes |
| `populationSize` | 2–100 | — | no (functionally required) |
| `numberOfIterations` | 1–100000 | — | no (functionally required) |
| `stagnationAbsoluteTolerance` | ≥0 | 0.001 | no |
| `stagnationBurnInPeriod` | 1–100000 | 100 | no |
| `stagnationIterationWindowSize` | 1–100 | 25 | no |
| `stagnationRelativeTolerance` | ≥0 | 0.001 | no |

## `solving_*` kwargs

Flattened onto `create()`/`create_calibration()`: `solving_allow_varying_stoichiometry`, `solving_discontinuity_events`, `solving_evaluator`, `solving_extent_units`, `solving_inline_limit`, `solving_max_events`, `solving_mute_phenomena`, `solving_mute_variables`, `solving_ode_solver_absolute_tolerance`, `solving_ode_solver_initial_step`, `solving_ode_solver_maximum_step`, `solving_ode_solver_relative_tolerance`, `solving_output_compartments`, `solving_output_parameters`, `solving_output_rates`, `solving_output_variables`, `solving_scoring_mode`, `solving_solver`, `solving_solving_times`, `solving_unit_check`. Source of truth: `Model.create_calibration` docstring in the SDK.

## Creation patterns

**Typed, model-scoped:**
```python
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
    protocol=protocol,
    advanced_output_set=scoring_design,
    calib_seed=42,
    calib_threshold_weighted_score=0.0,
    calib_number_of_iterations=100,
    calib_population_size=12,
)
```

**Typed, client-scoped:**
```python
calibration = client.create_calibration(
    model=model,
    data_tables=[data_table],
    parameters=[...],
    advanced_output_set=scoring_design,
    calib_seed=42,
    calib_threshold_weighted_score=0.0,
)
```

**Raw fallback** (required for `calibrationOptionsOverride`, `solvingOptionsOverride`, `coreVersion`):
```python
payload = {
    "parameters": [
        {"id": "k_elim", "mean": -1.0, "std": 0.5, "minBound": -3.0, "maxBound": 1.0}
    ],
    "dataTableDesigns": [
        {
            "dataTableId": {
                "coreItemId": data_table.core_id,
                "snapshotId": data_table.snapshot_id,
            },
            "include": True,
            "options": {"weight": 1},
        }
    ],
    "computationalModelId": {
        "coreItemId": model.core_id,
        "snapshotId": model.snapshot_id,
    },
    "calibrationOptions": {
        "seed": 42,
        "thresholdWeightedScore": 0.0,
        "numberOfIterations": 100,
        "populationSize": 12,
    },
    "coreVersion": "...",
}
calibration = client.create_calibration_from_json(
    json_content=payload, folder=folder, name="sdk-calibration"
)
# equivalent lower-level entry point: client.calibrations.create_raw(payload)
```

## Cross-references

- Data table `validForFitnessFunction` check: `jk-data-table`.
- Advanced output set objectives/constraints: `jk-output-set`.
