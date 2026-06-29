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

Example event pattern:

```python
batch.create_event(
    id="dose_start",
    updates={"Drug": "Dose * bioavailability"},
    time_trigger_first_time="0 * u(h)",
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
)
```

## Formula Syntax

- Piecewise: `condition ? value_if_true : value_if_false`
- Categorical switch: `case route of { iv -> 1; po -> 0.5; _ -> 1 }`

## Algebraic Rules

Algebraic rules are residual equations, interpreted as `0 = equation`. Add one rule for each unknown algebraic variable in the implicit system.

Avoid adding algebraic-rule examples blindly to a model because the wrong equation count can create sanity errors.
