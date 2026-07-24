# Scalar Discovery and Candidate Law Estimates

## Discover Output Scalars

Use the source Trial's typed descriptor catalog to identify an output scalar and its arm. The catalog is derived from the Trial results summary and is the authoritative SDK surface for descriptor IDs, display names, units, labels, and available arms.

```python
for scalar in trial.descriptors.scalars.list():
    print(scalar.id, scalar.display_name, scalar.arm, scalar.unit, scalar.labels)

uninfected_tumor_end = trial.descriptors.scalars.get("Tu.tend", arm="HighDose")
```

Do not infer an ID or arm from a display label. A descriptor identifies the output to target; it does not contain one value per patient.

## Retrieve Per-Patient Values

When values are needed for a user-specified analysis, retrieve the scalar output separately:

```python
download = trial.results.scalars({"Tu.tend": ["HighDose"]})
dataframe = download.to_dataframe()
```

Do not choose a scientific target distribution from these values within this skill.

## Obtain Candidate Law Estimates

For a persisted subsampling design, request platform-fitted candidate laws and compatible target forms for a discovered scalar:

```python
estimate = design.estimate_distributions("Tu.tend", arm="HighDose")

print(estimate.lawEstimates)
print(estimate.priorMarginal)
```

This is read-only. The estimate is evaluated against the design's source-Trial snapshot and filters, so it requires an existing design. `lawEstimates` and `priorMarginal` inform a user- or expert-specified target; they are neither automatic target selection nor an acceptance criterion. Validate the resulting design through `design.diagnostics` before generation.
