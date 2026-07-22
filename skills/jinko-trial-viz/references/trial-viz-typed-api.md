# TrialVisualization Typed API

Prefer this API over raw requests. Every section is exposed as a subservice
on the `TrialVisualization` object, each with `get()`/`clear()` plus
section-specific setters that read-modify-write only that section.

## Create

```python
trial = client.get_trial("tr-...")
folder = client.get_folder_by_name("2026-06-15-analysis", exact_match_only=True)
viz = trial.create_empty_trial_visualization(folder=folder, name="My trial viz")
```

Or from an existing JSON export:

```python
viz = trial.create_trial_visualization_from_json("viz.json")
```

## Top-Level Options

```python
viz = viz.set_selected_arms(["control", "treated"])  # or None for default arm selection
viz = viz.clear_selected_arms()
viz = viz.set_equate_baseline(True)
viz = viz.set_time_unit("day")
```

## Time-Series

```python
viz.timeseries.set_selectors(["Drug", "TumorVolume"])
viz.timeseries.add_selectors(["TumorVolume"])
viz.timeseries.get()  # current section payload
```

## Scalars

```python
viz.scalars.set_selectors(["AUC", "Cmax"])
viz.scalars.add_selectors(["Cmax"])
```

## Scatter Plots

X-vs-Y compares two variables across one or more arms:

```python
viz.scatter_plots.add_x_vs_y_plot("AUC", "Cmax", arms=["control", "treated"])
```

X-vs-X compares one variable in a reference arm against the same variable in other arms:

```python
viz.scatter_plots.add_x_vs_x_plot(
    "Drug",
    reference_arm="control",
    compare_arms=["treated"],
)
```

Regression options:

```python
viz.scatter_plots.set_regression(show_line_equation=True, regression_type="linear")
```

For a plot shape not covered by `add_x_vs_x_plot`/`add_x_vs_y_plot`, read the current config with `viz.scatter_plots.get()`, edit it, and write it back with `viz.scatter_plots.set_config(...)`.

## Survival Analysis

```python
viz.survival_analysis.set_selectors(["time_to_progression"])
viz.survival_analysis.set_observation_window_from_start_until_end()
viz.survival_analysis.set_observation_window_from_start_until_time("PT30D")
viz.survival_analysis.set_confidence_interval(True)
```

## Contribution Analysis

```python
viz.contribution_analysis.set_selectors(["AUC"])
viz.contribution_analysis.set_quantile(0.5)
viz.contribution_analysis.set_input_baseline_only()
viz.contribution_analysis.set_all_baseline()
viz.contribution_analysis.set_custom_baseline(["WT"])
```

## Data Overlay

```python
table = client.get_data_table("dt-...")
viz.data_overlay.add_table(table, label="ObservedData", include=True)
viz.data_overlay.set_ranges_enabled(True)
```

`add_table` also accepts a raw `{"coreItemId": ..., "snapshotId": ...}` reference instead of a `DataTable` handle. `label`, when provided, may only contain letters, digits, `-`, `_`, or `:`.

## Filters And Groups

```python
viz.filters.add_numeric("Dose", operator="Gte", value=1.0, arm="identity")
viz.filters.add_categorical("route", levels=["iv"], arm="identity")
viz.groups.set_group_by_arm(True)
viz.groups.add_scalar_bin_count_grouping("AUC", reference_arm="identity", count=4)
```

## Sanity

```python
diagnostics = (
    viz.sanity
)  # or viz.sanity_at(revision, only=["timeseries", "scatterPlots"])
if diagnostics.has_errors():
    print(diagnostics.errors())
```

`diagnostics.for_field("timeseries", "scalars")` filters an already-fetched view client-side (use this when you don't want to re-request a specific `only` scope from the API).

## Retrieving Content

```python
content = viz.content()  # typed TrialVisualizationWithMetadata
payload = content.model_dump(mode="json", by_alias=True, exclude_none=True)
```
