# Creating and Editing a Subsampling Design

## Discover descriptors on the source Trial

Subsampling refers to Trial descriptors, including their arms.
Discover those objects from the concrete completed Trial:

```python
trial = client.get_trial("tr-...")
for descriptor in trial.descriptors.scalars.list():
    print(descriptor.id, descriptor.arm, descriptor.unit)
for descriptor in trial.descriptors.categoricals.list():
    print(descriptor.id, descriptor.arm, descriptor.levels)
```

Use a descriptor object whenever possible.
It carries the arm into builder methods and avoids hand-written payload mistakes.

## Creation

`Trial.create_subsampling_design` accepts builders and raw dict escape hatches:

```python
age = trial.descriptors.scalars.get("age", arm="treated")
marker = trial.descriptors.scalars.get("marker", arm="treated")
sex = trial.descriptors.categoricals.get("sex", arm="treated")

design = trial.create_subsampling_design(
    numeric_filters=[age.gte(18)],
    categorical_filters=[sex.in_levels(["female"])],
    marginals=[marker.normal(mean=12.0, standard_deviation=2.5, weight=1.0)],
    observables=[marker],
    name="example-subsampling",
)
```

The typed creation arguments are `numeric_filters`, `categorical_filters`, `marginals`, `categoricals`, `correlations`, `survivals`, `summary_statistics`, and `observables`.
Use raw dicts only when the typed builder cannot express an API field.

## Target families

| Need | Builder/service |
| --- | --- |
| Numeric inclusion/exclusion | `ScalarTrialDescriptor.eq/neq/lt/lte/gt/gte`; `design.numeric_filters` |
| Categorical inclusion | `CategoricalTrialDescriptor.in_levels`; `design.categorical_filters` |
| Scalar distribution | `scalar.uniform/normal/normal_truncated/log_normal/weibull/mixture`; `design.marginals` |
| Categorical distribution | `categorical.categorical(...)`; `design.categoricals` |
| Scalar relationship | `scalar.correlate_with(...)`; `design.correlations` |
| Survival curve | `scalar.survival(...)`; `design.survivals` |
| Target moments/ranges | `scalar.summary_statistic(...)`; `design.summary_statistics` |
| Scalar retained for review | `ObservableBuilder` or a descriptor/id; `design.observables` |

Validate the concrete design with `design.diagnostics` before running a subsampling.

## Safe edits and reuse

Typed services return persisted handles.
Use them for small changes:

```python
marginal = design.marginals.find("marker", arm="treated")[0]
marginal.set_distribution_normal(mean=13.0, standard_deviation=2.0)
design.numeric_filters.create_gte("age", value=21, arm="treated")
```

Each edit creates a new design revision.
Use `design.edit(...)` only when replacing a complete component slice; it is an advanced API.
To point a design at a new Trial, call `design.set_trial(other_trial)` only when every referenced descriptor/arm pair is compatible, then re-read diagnostics.
A design that has already generated a Vpop may need to be duplicated rather than repointed by the platform.
