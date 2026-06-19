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
folder = client.folders.get_by_name("2026-06-15-vpop-study", exact_match_only=True)
client.create_vpop_generator_from_design(
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

## Distribution Shapes

Read `assets/distrib.json` before adding or changing distribution payloads.

## Generation

After creating a design, generate a Vpop with:

```python
vpop = vpop_generator.generate_vpop_by_design(
    size=10,
    seed=42,
    variance_reduction=False,
    folder=folder,
)
```

Generated Vpops are not edited directly. Update the Vpop design and regenerate.
