# Unit pitfalls under unit checking

These pitfalls pass `create_*` calls and fail later, either as a diagnostic or
as a silently wrong number in results. They assume the default mode
`UnitCheckAndConvertAllSpeciesToExtentUnits` with extent unit `mol`. Read
`unit_docs.md` for the semantics.

## Checks

| # | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| 1 | `UNIT_CHECKING_ERROR Could not convert Species from mL to mol` (or `dimensionless`, `count`), or `Missing a molar mass to convert Species from mg to mol` | In this mode every species converts to the extent unit. A species in volume, count, or dimensionless units has no conversion to `mol`. A species in mass units converts only with a molar mass. | For a mass, set the species `molar_mass` to a parameter in `g/mol` (see the weekly dose example in `model-components.md`). For the other units, store the state as an amount with a constant carrier parameter, for example `vol_carrier = 1 mL/nmol`, `P` in `nmol`, initial condition `V0 / vol_carrier`, and `P * vol_carrier` wherever a volume is needed. Do not change the unit mode to avoid the error unless a human approves it. |
| 2 | A derived output shows numbers off by powers of ten, or a unit such as `mL mol / mm**3 / nanomol` in `simple_solve` | A formula parameter with no declared unit keeps the composite unit of its expression. Results report the raw number in that composite unit, with no simplification. | Declare the unit of every output parameter, including `dimensionless`. Build outputs from other declared-unit parameters, for example `SLD_pct = 100 * (V_rel ^ (1/3) - 1)` with `V_rel` declared `dimensionless`. Read `SolvedSeries.unit` for each output and compare it with the intended unit. |
| 3 | `Attempted to add/subtract/compare ... non-matching dimensions` on a sum of flows or volumes | A bare numeric literal is dimensionless. `13.2 * scale` is not `L/h`, even when `13.2` is in L/h in the source. | Attach the unit to the literal: `13.2 * u(L/h) * scale`. |
| 4 | Results scaled by 1e3, 1e6, or 1e9 compared with a hand calculation | A formula carries a hand-written conversion factor, for example `dose_mgkg * BW * 1e6 / MW`, and Jinkō also converts. | Declare correct units on the inputs and write the formula without factors: `dose_mgkg * BW / MW` with `mg/kg`, `kg`, and `g/mol` gives `mol`. |
| 5 | An ODE right side has the wrong numeric scale | In this mode a species inside a formula is in extent units (`mol`), not in its declared unit. | Write right sides as amount fluxes (`mol/time`) and divide by a volume parameter to form a concentration. Do not assume `nM` values inside formulas. |
| 6 | A rate constant read from a paper behaves 24 or 3600 times too fast or too slow | A source prints a value with an inconsistent time unit, or Jinkō solves in seconds and a literal had no time unit. | Give every rate parameter an explicit time unit. Check one known decay over a physical interval with `simple_solve`. Record any unit reinterpretation of a source value as an assumption. |

## Protocol and trial notes

- A protocol override with a dimension uses `u()`: `"6.4 * u(mg/kg)"`. A protocol can override a derived parameter; the override replaces its formula.
- Trial and `simple_solve` times are in seconds. `simple_solve` returns no time vector: the series follows the model solving times, plus duplicated pre- and post-event points for events with `record=True`.

## Verification pattern

1. Run `model.diagnostics.errors()` and resolve every `UNIT_CHECKING_ERROR`.
2. Run `simple_solve` for each output and read `SolvedSeries.unit`.
3. Compare at least one output with an independent calculation (a hand value or a local simulation) at two or more time points. A dimensionally valid model can still be wrong by a constant factor (pitfalls 2, 4, and 5).
