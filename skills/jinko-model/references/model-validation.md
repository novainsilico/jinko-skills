# Model Validation

A complete technical model has no error-level diagnostics and can solve with `simple_solve()` for representative output IDs.

## Diagnostics

```python
diagnostics = model.diagnostics.errors()
if diagnostics:
    for entry in diagnostics:
        diagnostic = entry.diagnostic
        print(
            entry.component.id, diagnostic.code, diagnostic.severity, diagnostic.message
        )
```

## Simple Solve

```python
result = model.simple_solve(timeseries_ids=["Drug"])
if result.error:
    raise RuntimeError(result.error)
```

Use `scripts/validate_model_readiness.py` for a reusable check:

```bash
python skills/jinko-model/scripts/validate_model_readiness.py --model-sid cm-... --timeseries-id Drug
```

If diagnostics or solve errors appear, report them to the user and ask whether they want the model fixed.
