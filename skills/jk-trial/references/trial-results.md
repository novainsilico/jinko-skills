# Trial Results

Use completed trials for result downloads.

## Find Completed Trials

```python
client = JinkoClient()
for trial in client.list_trials(limit=20):
    status = trial.status()
    if isinstance(status, dict) and status.get("status") == "completed":
        print(trial.name, trial.sid, trial.url)
        break
```

## Summary

```python
summary = trial.results.summary()
arms = summary["arms"]
scalar_ids = [item["id"] for item in summary.get("scalars", [])]
```

## TimeSeries

```python
requested_ids = ["Drug"]
available_ids = {
    item["id"] for item in trial.output_ids() if isinstance(item, dict) and "id" in item
}
timeseries_selector = {
    timeseries_id: arms
    for timeseries_id in requested_ids
    if timeseries_id in available_ids
}
download = trial.results.timeseries(timeseries_selector)
timeseries_df = download.to_dataframe()
```

## Scalars

```python
scalar_df = trial.results.scalars(scalar_ids).to_dataframe()
```

`to_dataframe()` requires pandas and handles CSV or zipped CSV payloads. If pandas is not available, use `download.bytes` and write the raw payload; result payloads can be plain CSV or zipped CSV.
