# Results and Inspection

All accessors below return unparsed dicts (raw API payloads) — no pydantic model backs them today. Compare to `Trial.results` (`jinko-trial`), which has typed `TabularDownload`-returning `.timeseries()`/`.scalars()`; no equivalent exists here.

## Aggregate calls

```python
calibration.performance()  # {"status", "startTime", "endTime", "armCount", "patientCount", "totalPatientCount", "iterationCount", "timeserieCount", "defaultTimepointCount", "clockTimeSeconds", "totalCpuTimeSeconds", "sizeProxy"}
calibration.results_summary()  # {"arms": [...], "scalars": [...], "scalarsCrossArm": [...], "timeseries": {...}}
calibration.objective_weights()  # {objective_id: weight, ...}
```

## Monitoring progress safely

For a CMA-ES run, `iterationCount` is useful context but is **not** the most
reliable measure of solver work. Use the completed-population equivalent:

```
completed_population_equivalents = totalPatientCount / populationSize
```

Read `populationSize` from the calibration content and `totalPatientCount` from
`performance()`. This quantity may be fractional while a population is still
being solved. Report it together with status and elapsed clock time; do not
claim convergence from it alone.

Prefer lightweight `status()` checks at the agreed cadence. Fetch
`performance()` only for a requested progress report, a meaningful status
change, or terminal inspection. The report that monitoring itself slows or
stalls a calibration is not yet established: if it is suspected, reproduce it
with the same snapshot/seed under two documented cadences (status-only versus
status plus performance) before attributing causality.

## `calibration.results.*` (`CalibrationResults`)

| Method | Kwargs | Notes |
| --- | --- | --- |
| `.errors(...)` | `iteration`, `scalar_id`, `arm_id=None` | per-patient errors for one iteration/scalar |
| `.sorted_patients(...)` | `sort_by` | bare scalar id; returns patient ids, best first, without values |
| `.augment_data_tables(...)` | `patient_id`, `iteration` | |
| `.timeseries_per_patient(...)` | `patient_id`, `select`, `iteration` | `select` is a list of series ids |
| `.scalars_per_patient(...)` | `patient_number`, `scalars`, `arms`, `iteration` | |

```python
calibration.results.sorted_patients(sort_by="optimizationWeightedScore")
calibration.results.errors(iteration=5, scalar_id="auc")
```

### Sorting

`sorted_patients` returns `{"iteration", "patientNumber", "scenarioArm"}`
entries in descending order of the scalar, best first, and no values. On a
completed 150-iteration run it returned 1200 of the 20880 simulated patients.
`sort_by` takes a bare scalar id: the API has no sort-direction argument yet.
It rejects `"optimizationWeightedScore desc"` and returns an empty list for
`"optimizationWeightedScore:desc"` or `":asc"`.

Sort after the download for any other order, or when the values are needed:

```python
ranked = calibration.results.sorted_patients(sort_by="optimizationWeightedScore")
scores = []
for patient in ranked[:50]:
    raw = calibration.results.scalars_per_patient(
        patient_number=patient["patientNumber"],
        scalars=["optimizationWeightedScore"],
        arms=["crossArms"],
        iteration=int(patient["iteration"]),
    )
    value = next(
        r["value"]
        for o in raw["outputs"]
        for r in o["res"]
        if r["id"] == "optimizationWeightedScore"
    )
    scores.append((value, patient))
scores.sort(key=lambda item: item[0])  # ascending: worst first
```

## Not exposed

`result_iteration_summary` exists at the service layer (`CalibrationsService.result_iteration_summary`) but is intentionally not on `Calibration`/`CalibrationResults` — its `select` id contract is unstable. Do not use it in normal workflows.
