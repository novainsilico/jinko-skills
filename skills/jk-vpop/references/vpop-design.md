# Vpop Design From Marginal Distributions

Use vpop designs when the user wants to generate a vpop from descriptor marginal distributions.

## Marginal List Format

The skill scripts use this list format:

```json
[
  {"id": "Dose", "distribution": {"tag": "Uniform", "lowBound": 0.8, "highBound": 1.2}},
  {"id": "k_elim", "distribution": {"tag": "NormalTruncated", "mean": 0.1, "stdev": 0.02, "lowBound": 0.01, "highBound": 0.3}}
]
```

The script converts the list to the mapping expected by:

```python
folder = client.get_folder_by_name("2026-06-15-vpop-study", exact_match_only=True)
design = client.create_vpop_design_from_design(
    model=model,
    marginal_distributions={
        "Dose": {"tag": "Uniform", "lowBound": 0.8, "highBound": 1.2},
        "k_elim": {
            "tag": "NormalTruncated",
            "mean": 0.1,
            "stdev": 0.02,
            "lowBound": 0.01,
            "highBound": 0.3,
        },
    },
    folder=folder,
)
```

`create_vpop_design_from_design()` also accepts `correlations` (a `{(x, y): coefficient}` mapping) and `marginal_categoricals`. For a raw JSON payload instead of the structured design, use `client.create_vpop_design_from_json()`.

## Distribution Shapes

Read `assets/distrib.json` before adding or changing distribution payloads.

## Checking Design Sanity

Before generating, check the design for validation errors:

```python
diagnostics = design.diagnostics  # or design.diagnostics_at(revision)
if diagnostics.has_errors():
    print(diagnostics.errors().explain())
```

## Editing an Existing Design

Edit descriptors and correlations through the design's mutator services rather than replacing the whole payload:

```python
design = client.get_vpop_design("vd-...")
design.descriptors.get("k_elim").set_distribution({
    "tag": "NormalTruncated",
    "mean": 0.1,
    "stdev": 0.02,
    "lowBound": 0.01,
    "highBound": 0.3,
})
design.descriptors.create("Dose", {"tag": "Uniform", "lowBound": 0.8, "highBound": 1.2})
design.correlations.create(
    "Dose", "k_elim", 0.3
)  # or .set(...) to update an existing pair
```

`design.get_model()`, `design.set_model(model)`, and `design.clear_model()` link or unlink the design's computational model. `design.generated_vpops` lists vpops previously generated from this design.

## Generation

After creating (or editing) a design, generate a Vpop with:

```python
vpop = design.generate_vpop(
    size=10,
    seed=42,
    variance_reduction=False,
    folder=folder,
)
```

Generated Vpops are not edited directly. Update the Vpop design and regenerate.
