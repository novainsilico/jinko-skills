# Trial Plot Data

Calculated plot data (distributions, quantile bands, survival curves,
contribution analysis, per-patient scatter values) comes straight from the
trial through `trial.results`. You do not need a TrialVisualization: creating
one only to read data clutters the project. Every call is read-only and returns
a typed `jinko.openapi_types` model. Use these calls when the aggregate is
what you need. Download the full tables with `timeseries()` / `scalars()` only
when you need raw per-patient series.

`JinkoClient` is the only import: filters and groups are built from the
descriptor handles and the results service themselves.

## Selectors

Aggregate methods take the outputs to compute as their first argument:

- descriptor handles from `trial.descriptors` (`d.scalars.get(id, arm=...)`). A handle scoped to one arm queries only that arm.
- raw output ids. Cross-arm outputs query `crossArms`, and per-arm outputs query `arms=` (every trial arm by default).
- a raw `{output_id: [arm, ...]}` mapping, sent unchanged.

`scalars_per_population` takes output ids (every arm plus `crossArms` is
queried) or the raw mapping.

## Filters And Groups

Both are built from descriptor handles. The filter builders are the same ones
that configure subsampling designs and TrialVisualizations.

```python
d = trial.descriptors
age = d.scalars.get("age", arm="identity")
sex = d.categoricals.get("sex", arm="identity")
auc = d.scalars.get("Tumor.Drug.auc", arm="treated")

filters = [age.gte(18), sex.in_levels(["female"])]
group_by = [
    trial.results.group_by_arm(),  # UI "group by arm"
    auc.group_by_quantiles(4),
    sex.group_by_levels(),
]
```

Scalar handles also offer `group_by_values()` (distinct values),
`group_by_bins(count)`, `group_by_bin_width(offset=, width=)` and
`group_by_breaks([...])`.

- Every grouping accepts `reference_arm=`. Without it, a handle scoped to one arm uses that arm, otherwise `crossArms`.
- Tagged filters read from a TrialVisualization (`viz.filters.list()`) and its groups (`viz.groups.get()`) are accepted as-is, so a saved plot's scoping can be reused.
- Restrict per-patient calls to specific patients with `patients=[...]`. Aggregate routes have no such argument.
- Omitting `group_by` means no grouping. Pass `trial.results.group_by_arm()` to split by arm like the UI default.

## Calls

```python
r = trial.results
common = dict(filters=filters, group_by=group_by, equate_baselines=False)

r.aggregate_scalars([auc], **common)  # ScalResSummary
r.aggregate_timeseries(
    ["Tumor.volume"],
    quantiles=[0.05, 0.25, 0.5, 0.75, 0.95],
    variance=False,
    **common,
)  # VpopSummary
r.tornado_sensitivity(
    [auc], quantile=0.5, input_descriptors=None, **common
)  # TornadoSensitivitySummary
r.survival_analysis(
    ["time_to_progression"], observation_window="FromStartUntilEnd", **common
)  # SurvivalAnalysisResponse
r.scalars_per_population(
    [auc.id, "Blood.Drug.cmax"], **common
)  # ScalarResultPopulation
r.patients_matching_filters([age.gte(18)], patients=["p1"])  # list[str]
```

- `tornado_sensitivity(input_descriptors=)` accepts `None` or `"InputBaselineOnly"`, `"AllBaseline"`, or a list of input descriptor ids.
- `survival_analysis(observation_window=)` accepts `"FromStartUntilEnd"` or `{"FromStartUntilTime": ...}`.
- `filter_tokens=` / `group_tokens=` are deprecated aliases of `filters=` / `group_by=`.
- Query errors (empty selectors, invalid group parameters) are raised before any request is sent.
