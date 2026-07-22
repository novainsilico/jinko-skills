# Simple output set (measure design)

Load this reference when the user asks how to create, inspect, or edit a simple output set — the UI wording for what the API calls a `MeasureDesign`.

## Measure dict schema

Each entry in `measures` is a bare output-id string (shorthand for `{"timeseriesId": <id>}`) or a dict with these keys:

- `timeseriesId` *(required)*: the model output id to measure.
  Discover valid ids with `model.time_dependent_ids()` — do not invent ids.
- `name`: custom measure name.
- `origin`: one of `"OnEachArm"`, `"DifferenceVsControl"`, or `"RatioVsControl"`.
- `function`: how the scalar is computed from the output timeseries.

`function` supports two forms.

Point-in-time:

- `{"PointAtTime": "TStart"}` — first simulated time.
- `{"PointAtTime": "TEnd"}` — last simulated time.
- `{"PointAtTime": {"At": "PT4H"}}` — specific time, as an ISO 8601 duration.

Across-time (requires both `CrossTimeMeasure` and `ObservationWindow`):

- `{"AcrossTime": {"CrossTimeMeasure": "Min", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "Max", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "TimeOfMax", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "TimeOfMin", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "Avg", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "Auc", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "MaxSlope", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "MinSlope", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "Amplitude", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "EndMinusStart", "ObservationWindow": "FromStartUntilEnd"}}`
- `{"AcrossTime": {"CrossTimeMeasure": "HalfLife", "ObservationWindow": "FromStartUntilEnd"}}`

`ObservationWindow` shapes:

- `"FromStartUntilEnd"`
- `{"FromTimeUntilEnd": "PT2H"}`
- `{"FromStartUntilTime": "PT8H"}`
- `{"FromTimeUntilTime": {"TStart": "PT2H", "TEnd": "PT8H"}}`

You can mix shorthand strings and dicts in the same list.
Only the fields you provide are sent; unspecified options keep platform defaults.

## Creation

```python
model = client.get_model("cm-...")

output_set = client.create_simple_output_set(
    model,
    [
        "Drug",
        {
            "timeseriesId": "Drug",
            "name": "Drug_end",
            "function": {"PointAtTime": "TEnd"},
        },
        {
            "timeseriesId": "Drug",
            "function": {
                "AcrossTime": {
                    "CrossTimeMeasure": "Auc",
                    "ObservationWindow": "FromStartUntilEnd",
                }
            },
            "name": "Drug_auc",
        },
    ],
    name="PK outputs",
    folder=folder,
)
```

Equivalently, use `model.create_simple_output_set(measures, ...)`.

Raw JSON escape hatch: `client.create_simple_output_set_from_json(json_content=..., json_file_path=..., name=..., folder=..., description=..., version=...)`.

## Inspecting and editing

- `output_set.content()`: full structured definition (source model reference, measures, metadata).
- `output_set.measures`: just the measures list.
- `output_set.replace_all_measures(measures)`: discard existing measures, write exactly the given entries.
- `output_set.add_measures(measures)`: append one or more measures.
- `output_set.remove_measures(names=..., immutable_ids=..., timeseries_ids=...)`: remove all matching any selector; at least one selector family required.
- `output_set.update_measure(selector, by="name"|"immutable_id", new_timeseries_id=..., new_name=..., new_origin=..., new_function=..., new_immutable_id=...)`: update one measure.
  Omitted `new_*` args leave that field unchanged; `None` explicitly clears it.

There is no `.summary()` method on a simple output set — use `.content()` for structured detail.

## Discovery

- `client.list_simple_output_sets(...)`, `client.iter_simple_output_sets(...)`
- `client.get_simple_output_set(sid)`
