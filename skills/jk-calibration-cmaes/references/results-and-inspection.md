# Results and Inspection

All accessors below return unparsed dicts (raw API payloads) — no pydantic model backs them today. Compare to `Trial.results` (`jk-trial`), which has typed `TabularDownload`-returning `.timeseries()`/`.scalars()`; no equivalent exists here.

## Aggregate calls

```python
calibration.performance()  # {"status", "startTime", "endTime", "armCount", "patientCount", "totalPatientCount", "iterationCount", "timeserieCount", "defaultTimepointCount", "clockTimeSeconds", "totalCpuTimeSeconds", "sizeProxy"}
calibration.results_summary()  # {"arms": [...], "scalars": [...], "scalarsCrossArm": [...], "timeseries": {...}}
calibration.objective_weights()  # {objective_id: weight, ...}
```

## `calibration.results.*` (`CalibrationResults`)

| Method | Kwargs | Notes |
| --- | --- | --- |
| `.errors(...)` | `iteration`, `scalar_id`, `arm_id=None` | per-patient errors for one iteration/scalar |
| `.sorted_patients(...)` | `sort_by` | `sort_by` forwarded as-is to the API |
| `.augment_data_tables(...)` | `patient_id`, `iteration` | |
| `.timeseries_per_patient(...)` | `patient_id`, `select`, `iteration` | `select` is a list of series ids |
| `.scalars_per_patient(...)` | `patient_number`, `scalars`, `arms`, `iteration` | |

```python
calibration.results.sorted_patients(sort_by="weightedScore desc")
calibration.results.errors(iteration=5, scalar_id="auc")
```

## Not exposed

`result_iteration_summary` exists at the service layer (`CalibrationsService.result_iteration_summary`) but is intentionally not on `Calibration`/`CalibrationResults` — its `select` id contract is unstable. Do not use it in normal workflows.
