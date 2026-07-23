# Model Components

Use high-level component methods on `model.components`. Prefer batching for edits that belong to the same model version.

## Batch Pattern

```python
with model.components.batch(version="retune") as batch:
    batch.edit_parameter("k_clearance").set_formula("CL2 / V")
    batch.create_parameter(id="k_new", formula="0.8", unit="1/h")
```

The batch reads the current component snapshot once, stages all changes locally, and commits one model edit on normal context-manager exit.

## Supported High-Level Creates

- `create_parameter(id=..., formula=..., unit=...)`
- `create_categorical_parameter(id=..., level=..., available_levels=[...])`
- `create_compartment(id=..., volume=..., unit=...)`
- `create_species(id=..., compartment=..., initial_condition=..., unit=...)`
- `create_ode(id=..., left_side=..., right_side=...)`
- `create_event(id=..., updates=..., time_trigger_first_time=...)`
- `create_event(id=..., updates=..., time_trigger_first_time=..., time_trigger_every=..., time_trigger_count=...)`
- `create_baseline_check(id=..., condition=...)`
- `create_algebraic_rule(id=..., equation=...)`
- Reaction helpers such as `create_general_reaction()` and `create_mass_action_reaction()`

## Dosing Events

Dosing belongs in model events. Protocols can later override model parameters used by these events.

Events can update parameters as well as species. The target parameter must be
mutable (`constant=False`); setting it constant prevents assignment by an event.
Use an explicit time unit in every time trigger. Set `record=True` when the
discontinuity must be visible in solver or trial results.

Example event pattern:

```python
batch.create_event(
    id="dose_start",
    updates={"Drug": "Dose * bioavailability"},
    time_trigger_first_time="0 * u(h)",
    record=True,
)
```

Recurrent event pattern (here for weekly treatment):

```python
batch.create_event(
    id="weekly_dose",
    updates={"Drug": "Drug + Dose"},
    time_trigger_first_time="7 * u(day)",
    time_trigger_every="7 * u(day)",
    time_trigger_count=6,
    record=True,
)
```

Parameter-update pattern:

```python
batch.create_parameter(id="meal_rate", formula=0, unit="mol/h", constant=False)
batch.create_event(
    id="breakfast",
    updates={"meal_rate": "1 * u(mol/h)"},
    time_trigger_first_time="7 * u(h)",
    record=True,
)
```

After committing, solve for `meal_rate` and verify that the returned series
contains the expected value before and after the trigger.

## Event Safety

- An event may update a parameter, compartment, or species. A parameter targeted by an event must be created or edited with `constant=False`; a constant parameter cannot be altered by an event.
- Express time triggers with an explicit time dimension, for example `7 * u(h)` and `24 * u(h)`. Do not rely on a bare number being interpreted in the intended time unit.
- Set `record=True` when users need to inspect the discontinuity in `simple_solve` or trial output. This records the state immediately before and after the event.
- After adding or changing an event, request the affected component in `simple_solve`, inspect its values around the trigger, and report whether the expected update occurred.

## Model Tags

Model tags are writable through `model.create_tag("pk", description=..., color=...)`.
Use the returned handle to update metadata with `tag.set_description(...)` or
`tag.set_color(...)`; pass the tag or its id when assigning it to components.

## Formula Syntax

- Piecewise: `condition ? value_if_true : value_if_false`
- Categorical switch: `case route of { iv -> 1; po -> 0.5; _ -> 1 }`

## Algebraic Rules

Algebraic rules are residual equations, interpreted as `0 = equation`. Add one rule for each unknown algebraic variable in the implicit system.

Avoid adding algebraic-rule examples blindly to a model because the wrong equation count can create sanity errors.

Use `create_algebraic_rule()` or `edit_algebraic_rule()` for implicit constraints and cyclic dependencies. Convert explicit implicit definitions into residual form:

- `x1 = f1(x1, x2)` becomes `f1(x1, x2) - x1`.
- `x2 = f2(x1, x2)` becomes `f2(x1, x2) - x2`.

If diagnostics report `TOO_FEW_ALGEBRAIC_RULES`, `TOO_MANY_ALGEBRAIC_RULES`, or `MISSING_UNKNOWN`, check that the number of algebraic equations matches the number of unknown algebraic variables.
