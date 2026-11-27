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
from jinko import SimpleSolveError

try:
    result = model.simple_solve(timeseries_ids=["Drug"])
except SimpleSolveError as failure:
    print(failure.output.error)  # the server message
    raise
```

A failed solve raises `SimpleSolveError`. To read the error without an exception, pass `raise_on_error=False` and check `result.error`.

An override is a MathJS formula with units in `u(...)`, such as `{"k_el": "19.0 * u(1/day)"}`, or a level name for a categorical parameter. A plain number, such as `"19.0"`, is read in the unit of the component. Do not pass a component's `definition`: it is a display string, such as `"19.0 1 / day"`, and the solve fails on it.

Use `python -m jinko.cli.validate_model_readiness` for a reusable check. Pass every mandatory tag as `--require-tag`; without at least one such option, the script reports only that diagnostics and solve checks passed and does not claim full readiness:

```bash
python -m jinko.cli.validate_model_readiness --model-sid cm-... --timeseries-id Drug --require-tag Drug=output
```

After an explicit human decision authorizes another checked mode, pass
`--allow-nondefault-unit-check` while validating that model.

If diagnostics or solve errors appear, report them to the user and ask whether they want the model fixed.
