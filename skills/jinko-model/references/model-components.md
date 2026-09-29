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

Recurrent event pattern (here for weekly treatment). The dose amount, the first
dose time, the dose interval, and the number of doses are parameters tagged
`i::protocol`, so a protocol design can vary the regimen without a model edit:

```python
with model.components.batch(version="dosing") as batch:
    batch.create_parameter(
        id="dose_amount", formula="10", unit="mg", tags=["i::protocol"]
    )
    batch.create_parameter(
        id="dose_start", formula="7", unit="day", tags=["i::protocol"]
    )
    batch.create_parameter(
        id="dose_interval", formula="7", unit="day", tags=["i::protocol"]
    )
    batch.create_parameter(id="dose_number", formula="6", tags=["i::protocol"])
    batch.create_event(
        id="weekly_dose",
        updates={"Drug": "Drug + dose_amount"},
        time_trigger_first_time="dose_start",
        time_trigger_every="dose_interval",
        time_trigger_count="dose_number",
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

- Write the dosing schedule as model parameters tagged `i::protocol`: the dose amount, the first dose time, the dose interval, and the number of doses. Do not write them as literals in the event. A protocol design overrides parameters, so a literal schedule cannot be compared across arms and forces a model edit for each new regimen. A trigger field accepts a parameter name as well as a number.
- An event may update a parameter, compartment, or species. A parameter targeted by an event must be created or edited with `constant=False`; a constant parameter cannot be altered by an event.
- Express a numeric time trigger with an explicit time dimension, for example `7 * u(h)` and `24 * u(h)`. Do not rely on a bare number being interpreted in the intended time unit. A parameter used in a trigger carries its own declared unit.
- Set `record=True` when users need to inspect the discontinuity in `simple_solve` or trial output. This records the state immediately before and after the event.
- After adding or changing an event, request the affected component in `simple_solve`, inspect its values around the trigger, and report whether the expected update occurred.

## Component Tags and Links

The platform already provides `i::vpop`, `i::protocol`, `s::knowledge`,
`s::arbitrary`, `s::to-calibrate`, `s::calibrated`, and `output`; attach them by
id and do not recreate them. Use `i::vpop` for patient-varying inputs,
`i::protocol` for arm/scenario inputs, one justified `s::*` source tag for
applicable value-bearing inputs, and `output` for important time-series
outputs. Do not assign `s::calibrated` until an accepted calibration produced
the value.

For other, custom tags, use `model.create_tag(...)`. The returned handle can
update custom metadata with `tag.set_description(...)` or `tag.set_color(...)`.

Every component returned by `model.components.get_*`, `list_*`, `create_*`, or
`batch.edit_*` supports tags and traceability links. Create helpers also accept
`tags=[...]` and `links=[...]` when the metadata is already known.

Link a value-bearing input to the evidence it came from, in this order of
preference: the Extract that holds the value, the Reference that holds the
Extract, then another project item such as a Document. Use an external DOI or
URL only when the project holds no such item. Never build a link from a
hard-coded hostname. `ProjectItem.url` and `Highlight.url` follow the configured
`JINKO_URL`, so they stay correct on an on-premises deployment.

```python
parameter = model.components.get_parameter("k_clearance")

parameter.add_tag("i::vpop")

# Preferred: the Extract that carries the value. The SDK stores its Jinkō URL.
extract = client.get_extract("as-EXAMPLE")
parameter.add_link(extract)

# A Reference, Document, or any other project item can be passed directly.
parameter.add_link(client.get_reference("so-EXAMPLE"))

# A highlight inside an Extract is addressed by its own URL.
parameter.add_link(extract.highlights[0].url)
```

Use `component.tags` and `component.links` to inspect the current metadata;
`has_tag(...)` and `has_link(...)` check for a specific entry. The mutations
`remove_tag`, `set_tags`, `remove_link`, `set_links`, and `clear_links` are
also available. Immediate component-handle mutations create a model edit;
when several related component changes belong in one version, call the same
methods on the object returned by `batch.edit_*` or `batch.create_*` inside a
`model.components.batch(version=...)` block.

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
