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

### Log-transformed priors

`logTransform` changes **only the prior distribution coordinates**:

| Field | `logTransform: false` | `logTransform: true` |
| --- | --- | --- |
| `mean` | normal-prior mu for `x` | normal-prior mu for `log10(x)` |
| `std` | normal-prior sigma for `x` | normal-prior sigma for `log10(x)` |
| `minBound`, `maxBound` | bounds for `x` | still bounds for `x` (not log coordinates) |

Therefore, for a log-transformed positive parameter with a desired
base-10-log centre `m`, send `mean=m`, not `10**m`; the corresponding original
scale centre is `10**m`. Do not use natural-log (`ln`) values: the platform
uses `log10`. Avoid calling `mean` the arithmetic mean on the original scale;
it is the normal-distribution mu in the coordinate stated above.

If prior bounds are supplied in log10 coordinates, convert each bound back to
physical coordinates before creation. For example, a prior with log10 bounds
`[-3, 1]` must be sent as `min_bound=10**-3` and `max_bound=10**1`, not as
`min_bound=-3` and `max_bound=1`. Before launch, verify that `10**mean` lies
between the physical bounds and that calibration sanity has no
`MIN_BOUND_GREATER_THAN_MEAN_LOG` or `MAX_BOUND_LOWER_THAN_MEAN_LOG` warning.

## `dataTableDesigns[]` (`DataTableDesign`)

| Field | Notes |
| --- | --- |
| `dataTableId` | `{coreItemId, snapshotId}` |
| `include` | bool |
| `options.label` | sbml-id, names the generated fitness function |
| `options.weight` | default 1, ≥0 |
| `options.logTransformWideBounds` | observable id list |
| `options.timeTolerance` | date/duration string |

`logTransformWideBounds` is the API field behind the UI's **Scale bounds**
option. For a fitness data table, populate it with every distinct `obsId` in
the table by default. In typed SDK calls, use the Pythonic key
`log_transform_wide_bounds`:

```python
observed_ids = sorted({row["obsId"] for row in data_table.export()})
data_table_design = {
    "data_table": data_table,
    "include": True,
    "options": {
        "weight": 1.0,
        "log_transform_wide_bounds": observed_ids,
    },
}
```

After creation, read `calibration.content()["dataTableDesigns"]` and verify the
stored `options.logTransformWideBounds` contains the complete set. Omit an
observable only when the user explicitly requests linear bound scaling for it.

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
    parameters=[
        {
            "id": "k_elim",
            "mean": -1.0,
            "std": 0.5,
            "log_transform": True,
            "min_bound": 0.001,
            "max_bound": 10.0,
        }
    ],
    data_tables=[data_table_design],
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
    data_tables=[data_table_design],
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
        {
            "id": "k_elim",
            "mean": -1.0,
            "std": 0.5,
            "logTransform": True,
            "minBound": 0.001,
            "maxBound": 10.0,
        }
    ],
    "dataTableDesigns": [
        {
            "dataTableId": {
                "coreItemId": data_table.core_id,
                "snapshotId": data_table.snapshot_id,
            },
            "include": True,
            "options": {"weight": 1, "logTransformWideBounds": ["Drug", "Metabolite"]},
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
```

## Cross-references

- Data table `validForFitnessFunction` check: `jinko-data-table`.
- Advanced output set objectives/constraints: `jinko-output-set`.
