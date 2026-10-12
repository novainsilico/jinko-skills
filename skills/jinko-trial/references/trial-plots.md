# Trial Plots

Draw trial results with the Jinkō plot style, so your figures match the Trial
Visualizations of the Jinkō web app. Get the data with the calls in
`trial-plot-data.md`, flatten it with `to_dataframe()`, and draw it with
matplotlib.

This needs matplotlib and pandas in the active Python environment. These
dependencies are provided by the SDK's `plot` extra; use the project's existing
dependency management to add any that are missing.
This style is the default, not a hard rule. Use another style when the user
asks for one, or when the figures must match an existing report or template.

```python
import matplotlib.pyplot as plt
from jinko.plotting import (
    BAND_ALPHA,
    BAR_ALPHA,
    LINE_ALPHA,
    NEUTRAL,
    PALETTE,
    TORNADO_ALPHA,
    ZERO_LINE,
    axis_label,
    jinko_style,
)
```

`jinko_style()` is a context manager. Draw inside `with jinko_style():`. Call
`use_jinko_style()` instead to set the style for the whole session.

## Rules for every plot

- One color per group: `PALETTE[i % len(PALETTE)]`. Use `PALETTE[0]` when nothing is grouped. Group by arm with `trial.results.group_by_arm()` to color by arm.
- Label axes with `axis_label(name, unit)`: it gives "Name (unit)", or the name alone when there is no unit. Read the unit from the `unit` and `time_unit` columns.
- When the name appears in titles or captions, write "Jinkō" with the macron.
- Save figures for documents as PNG (`fig.savefig("name.png")`). Upload them with `jinko-document`.
- Give each figure in a document a caption with the data source: a link to the trial, and the quantiles or statistics shown. Readers then find the source data in Jinkō.
- Look at the saved PNG before you use it. Check labels, legend, and units.
- Every frame has an `output_id` column and holds every output you requested. Filter to one output with `frame[frame["output_id"] == "..."]` before you draw.

## Time series

Median as a solid line. Narrow band (25th to 75th percentile) with dashed bounds
and a fill. Wide band (5th to 95th percentile) with dotted bounds and no fill.

```python
frame = trial.results.aggregate_timeseries(
    ["Tumor.volume"],
    quantiles=[0.05, 0.25, 0.5, 0.75, 0.95],
    group_by=[trial.results.group_by_arm()],
).to_dataframe()

with jinko_style():
    fig, ax = plt.subplots()
    for i, (group, d) in enumerate(frame.groupby("group", sort=False)):
        color = PALETTE[i % len(PALETTE)]
        ax.plot(d["time"], d["q0.5"], color=color, alpha=LINE_ALPHA, label=group)
        ax.fill_between(
            d["time"],
            d["q0.25"],
            d["q0.75"],
            color=color,
            alpha=BAND_ALPHA,
            linewidth=0,
        )
        for q in ("q0.25", "q0.75"):
            ax.plot(d["time"], d[q], color=color, alpha=LINE_ALPHA, linestyle="--")
        for q in ("q0.05", "q0.95"):
            ax.plot(d["time"], d[q], color=color, alpha=LINE_ALPHA, linestyle=":")
    ax.set(
        xlabel=axis_label("Time", frame["time_unit"].iat[0]),
        ylabel=axis_label("Tumor volume", frame["unit"].iat[0]),
    )
    ax.legend()
    fig.savefig("tumor-volume.png")
```

- Request `variance=True` for mean and standard deviation. The frame then has `mean` and `std_dev` columns. Draw mean ± 1 SD as the narrow band and mean ± 2 SD as the wide band.
- Use `ax.set_yscale("log")` for a log axis.
- Draw observed data over the bands with `ax.errorbar(x, y, yerr=..., fmt="_", capsize=3, color=color)`. Use the arm color. Use `NEUTRAL` when the plot is grouped by something other than the arm.

## Scalar distributions

Histogram bars at half opacity, one color per group. Add the group size to the
legend.

```python
frame = trial.results.aggregate_scalars(
    ["Tumor.auc"], group_by=[trial.results.group_by_arm()]
).to_dataframe()

with jinko_style():
    fig, ax = plt.subplots()
    for i, (group, d) in enumerate(frame.groupby("group", sort=False)):
        ax.bar(
            d["bin_low"],
            d["bin_count"],
            width=d["bin_high"] - d["bin_low"],
            align="edge",
            color=PALETTE[i % len(PALETTE)],
            alpha=BAR_ALPHA,
            label=f"{group} (n={d['count'].iat[0]})",
        )
    ax.set(xlabel=axis_label("AUC", frame["unit"].iat[0]), ylabel="Patients")
    ax.legend()
    fig.savefig("auc-histogram.png")
```

- Discrete scalars have `bin_low == bin_high`. Draw them with `ax.bar(d["bin_low"], d["bin_count"], color=..., alpha=BAR_ALPHA)`.
- Categorical outputs: `to_dataframe(kind="categorical")` gives `category` and `bin_count`.
- For box plots or per-patient values, use `scalars_per_population` (see Scatter) and `ax.boxplot(...)` with the group colors at `BAR_ALPHA`.

## Contribution analysis (tornado)

Bars show the change of the output relative to its median. Overlay the low and
high bars. Put the strongest input on top.

```python
frame = trial.results.tornado_sensitivity(["Tumor.auc"], quantile=0.5).to_dataframe()
d = frame[frame["group"] == frame["group"].iat[0]].copy()
d["low"] = d["low_sensitivity"] / d["median_value"].abs()
d["high"] = d["high_sensitivity"] / d["median_value"].abs()
d = d.loc[
    (d["low_sensitivity"].abs() + d["high_sensitivity"].abs())
    .sort_values(ascending=False)
    .index
]
labels = d["input_descriptor"]

with jinko_style():
    fig, ax = plt.subplots()
    ax.barh(labels, d["low"], color=PALETTE[0], alpha=TORNADO_ALPHA, label="low")
    ax.barh(labels, d["high"], color=PALETTE[1], alpha=TORNADO_ALPHA, label="high")
    ax.invert_yaxis()
    ax.axvline(0, color=ZERO_LINE, linewidth=1)
    ax.set(xlabel="Change relative to the median")
    ax.legend(loc="lower right")
    fig.savefig("contribution-analysis.png")
```

Draw one figure per group when you group the query.

## Survival analysis

Step curves with dashed confidence bounds, filled between them. Draw no censor
marks.

```python
frame = trial.results.survival_analysis(
    ["time_to_progression"], group_by=[trial.results.group_by_arm()]
).to_dataframe()

with jinko_style():
    fig, ax = plt.subplots()
    for i, (group, d) in enumerate(frame.groupby("group", sort=False)):
        color = PALETTE[i % len(PALETTE)]
        ax.step(
            d["time"],
            d["cumulativeSurvivalRates"],
            where="post",
            color=color,
            alpha=LINE_ALPHA,
            label=group,
        )
        low, high = (
            d["lowerBoundConfidenceIntervals"],
            d["upperBoundConfidenceIntervals"],
        )
        ax.fill_between(
            d["time"],
            low,
            high,
            step="post",
            color=color,
            alpha=BAND_ALPHA,
            linewidth=0,
        )
        for bound in (low, high):
            ax.step(
                d["time"],
                bound,
                where="post",
                color=color,
                alpha=LINE_ALPHA,
                linestyle="--",
            )
    ax.set(
        xlabel=axis_label("Time", frame["time_unit"].iat[0]),
        ylabel="Survival probability",
    )
    ax.legend()
    fig.savefig("survival.png")
```

- The curves are named as the API names them. Read `frame.columns` first. The cumulative hazard is `cumulativeHazardRates`. The confidence bounds are missing when the API returns none, so guard for that.
- Log-rank tests between groups: `survival_analysis(...).log_rank_dataframe()`.

## Scatter

Per-patient values, one point per patient. Color by arm.

```python
frame = trial.results.scalars_per_population(
    ["Tumor.auc", "Blood.Drug.cmax"], group_by=[trial.results.group_by_arm()]
).to_dataframe(wide=True)

with jinko_style():
    fig, ax = plt.subplots()
    for i, (arm, d) in enumerate(frame.groupby("arm", sort=False)):
        ax.scatter(
            d["Blood.Drug.cmax"],
            d["Tumor.auc"],
            s=20,
            color=PALETTE[i % len(PALETTE)],
            label=arm,
        )
    ax.set(xlabel="Cmax", ylabel="AUC")
    ax.legend()
    fig.savefig("auc-vs-cmax.png")
```

- The route returns no patient ids. `patient_index` is the position of the patient inside its group and arm.
- Cross-arm outputs sit under the arm `crossArms`. Scatter two outputs only when both belong to the same arm.
- The long frame (`to_dataframe()` without `wide=True`) has `output_id` and `value` columns. Use it for box plots and group-wise statistics.
