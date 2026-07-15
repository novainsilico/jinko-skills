# Running and Polling

## Sanity

```python
report = calibration.get_sanity()
report["model"]["sanity"][
    "errors"
]  # raw dict, one key per input: model, protocol, outputSet, scorings, dataTables, parameters, options, solvingTimes
```

Raw dict (same caveat as `references/results-and-inspection.md`). Wraps `GET .../snapshots/{snapshotId}/sanity`.

## Run / stop

```python
calibration.run()  # POST .../run, no body, no return value
calibration.stop()  # POST .../stop
```

## Status

```python
calibration.status()  # -> {"status": ..., "stoppingReason": ...}, wraps status_with_metadata
```

`JobStatus`: `completed` | `running` | `not_launched` | `stopped` | `error`.

`StoppingReason` variants (factual — see `jk-task-cmaes` for interpretation/diagnosis):

| Variant | Payload |
| --- | --- |
| `MaxNumberOfIterations` | `numIterations` |
| `WeightedScoreReachedThreshold` | `optimizationWeightedScore` |
| `WeightedScoreStagnates` | `lowestValue`, `highestValue` |
| `SigmaTooSmall` | `sigma` |
| `NonPositiveEigenValue` | `smallestEigenValue` |
| `IllConditionedCovarianceMatrix` | `conditionNumber` |
| `NotProgressing` | — |

## Poll to completion

```python
final_status = calibration.wait_until_completed(timeout=3600, poll_interval=5.0)
```

Polls until `status` is `completed`/`stopped`/`error` (or `isRunning` flips false); raises `TimeoutError` past `timeout`.
