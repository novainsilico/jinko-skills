# Model Validation

A complete technical model uses `UnitCheckAndConvertAllSpeciesToExtentUnits` by default, or another checked mode explicitly authorized by a human. It gives every directly declared numeric component value a unit, has no error-level diagnostics, and can solve with `simple_solve()` for representative `output` IDs. A formula-derived parameter may omit its declared unit when its expression determines it.

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

Use `scripts/validate_model_readiness.py` for a reusable check. Pass every mandatory tag as `--require-tag`; without at least one such option, the script reports only that diagnostics and solve checks passed and does not claim full readiness:

```bash
python skills/jinko-model/scripts/validate_model_readiness.py --model-sid cm-... --timeseries-id Drug --require-tag Drug=output
```

After an explicit human decision authorizes another checked mode, pass
`--allow-nondefault-unit-check` while validating that model.

If diagnostics or solve errors appear, report them to the user and ask whether they want the model fixed.
