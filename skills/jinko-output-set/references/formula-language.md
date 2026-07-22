# Advanced-output-set formula language

Load this reference before writing any advanced-output-set constraint, scalar, or objective formula.
`client.validate_scoring_formula`/`validate_scoring_condition` only check that a string parses; they do not teach the grammar, and its error messages are easy to misread (see Pitfalls below). This reference is the grammar itself, condensed from `docs/platform/core-features-modeling/10-using-formulas/index.mdx`.

## What formulas reference

Advanced-output-set formulas resolve against the **trial's model descriptors** (species, parameters, compartments, reactions, ODE rates) — the same ids returned by `model.time_dependent_ids()` and `model.components`.

They do **not** resolve against simple-output-set measure names (e.g. a measure you named `T_auc` in a simple output set). Passing a simple-output-set measure name into an advanced-output-set formula parses fine standalone (it's just an unrecognized identifier syntactically) but fails `trial.sanity()` with `ADVANCED_OUTPUTS_ERRORS` once attached to a trial — the diagnostic looks identical to a plain typo: `"<name> is a timeseries. A numerical value is expected instead. You should use a time reduction function."` plus `"The following IDs do not match any model species, parameter, compartment, reaction or ODE rate: <name>"`. If you see both of those for a name you expected to resolve, check whether that name is a simple-output-set measure rather than a raw model descriptor id.

## Core syntax

- Function calls: `f(...)`. All function names are **lowercase** (`auc`, `avg`, `gmax`, not `AUC`/`Avg`/`GMax`). Wrong case does not raise a "wrong case" error — it raises a generic `Could not parse <Name> as a valid function name`, which reads like the function doesn't exist at all.
- Operators, in precedence order (highest to lowest): `(...)`/`f(...)` > `!` (factorial) > `^` > unary `-` > `*`, `/` > `+`, `-` > `cond ? valIfTrue : valIfFalse`.
- Unit literals such as `u(unit)` are **not accepted in advanced-output-set formulas**. Do not try to make a hard-coded number unit-safe with `u(...)`.
- Random draws: `rnorm(seed, index, mean, stdev)`, `runif(seed, index, min, max)` — not SBML-exportable.
- Categorical casing: `case ID of { value1 -> a; value2 -> b; _ -> c }`.

### Conditions (constraints, objective filters, `ifThenElse`)

Precedence, highest to lowest: `(...)` > `not` > `xor` > `==`, `!=`, `<`, `>`, `<=`, `>=`, `in` > `and` > `or`.
Categorical membership: `origin in {APAC, EU}`.

### Component filters

The optional `filter` field on a constraint or objective is a **condition**, not
an ISO-8601 duration field. A bare number is interpreted in the unit of the
quantity it is compared with; for example, `time > 900` means “900 in the
current unit of `time`”, not necessarily 900 seconds. Since advanced-output
formulas cannot use `u(...)`, do **not** hard-code scientific thresholds in a
filter.

Instead, after user confirmation, add a clearly named, unit-bearing helper
parameter to the model, then use that id in the formula. For example, define
`analysisStartTime` in the model with the desired value and time unit, then use:

```
time > analysisStartTime
```

Do **not** write `time > PT47H`: `PT47H` is data-table/simple-output-set
duration syntax, not formula syntax. Use `jinko-model` to create or update the
helper parameter; do not silently change the model merely to author an output
set. Validate the resulting condition with
`client.validate_scoring_condition(...)` before creating or editing the
component.

## Advanced-output-set-specific syntax

Time indexing accepts numeric coordinates, not ISO-8601 durations such as
`PT4H`. Do not label a bare coordinate as seconds unless the model/time context
has been verified; use a unit-bearing model helper parameter for a scientifically
meaningful threshold.

### Time indexing

- `descriptorID[t]` — value at a single time point, e.g. `T[10]`.
- `descriptorID[a,b]` — slice the time series between `t=a` and `t=b`, e.g. `T[0,50]`.

### Time reduction functions (time series → scalar)

A formula that is meant to be a scalar (any bare scalar, any objective target) must end up reduced to a single number — wrap the raw descriptor in one of these, don't reference it bare:

| Function | Meaning |
| --- | --- |
| `gmax(x)` | global maximum |
| `gmin(x)` | global minimum |
| `avg(x)` | average value |
| `int(x)` | integral over time |
| `auc(x)` | area under the curve |
| `lastTime(x)` | last available time |
| `firstTime(x)` | first available time |
| `lastValue(x)` | last available value (use this for "final value", not `x[TEnd]` — there is no `TEnd`/`TStart` keyword here, only numeric offsets or `firstValue`/`lastValue`) |
| `firstValue(x)` | first available value |
| `timeOfMax(x)` | time at which the maximum occurs |
| `timeOfMin(x)` | time at which the minimum occurs |

Combine with slicing: `gmax(X[0,100])` is the max of `X` between the numeric coordinates 0 and 100 in the model's time context.

### Other time-series functions

- `ddt(x)` — time derivative at each point, e.g. `ddt(X[0,100])`.
- `localMinima(x)` / `localMaxima(x)` — list of (time, value) extrema, e.g. `localMaxima(Z)`, `localMinima(Y@ArmB[0,50])`.
- `ifThenElse(condition, ifTrue, ifFalse)` — e.g. `ifThenElse(X@ArmA[10] > 5, Y@ArmA[20], Y@ArmA[30])`.

### Arm references

- `descriptorID@armID` — value in a specific arm, e.g. `X@ArmA[10]`.
- `descriptorID` without `@armID` — computed across all arms, each contributing equally.
- You cannot mix namespaced (`x@arm`) and non-namespaced (`x`) descriptors in the same formula.

`@` here means **arm selection**, not "value at time" — there is no `x@TEnd` time syntax. (It happens to parse if `TEnd`/`TStart` looks like a valid identifier, because the parser reads it as an arm named `TEnd`; it silently resolves to nothing meaningful rather than raising a clear error.)

### Objective example

```
X@ArmA[10] / X@ArmA[20]
```
scored against a range, e.g. "stays within `[0.8, 1.2]`" — maps directly onto this SDK's objective `range` bounds.

## Delay differential equations

`delay(y, delta)` evaluates `y` at `time - delta`. For `time - delta < tmin`, it returns `y`'s initial condition. `delta` must never evaluate negative (runtime error). Not usable in advanced-output-set formulas — this is a base-formula (model definition) construct.

## Pitfalls when using `validate_scoring_formula`/`validate_scoring_condition`

- **It is a syntax check only.** It has no notion of a concrete trial's model, so `auc(NotARealDescriptor)` parses fine standalone and only fails at `trial.sanity()` — see `jinko-trial`.
- **Case sensitivity reads as "function doesn't exist."** `Max(a, b)` → `Could not parse Max as a valid function name`; `max(a, b)` → parses correctly (and is a plain 2-argument elementwise max, not a time reduction — do not use it as a substitute for `gmax`).
- **Underscore-joined identifiers always parse**, whether or not they mean anything. `AUC_T`, `T_end`, `Foo_Bar` are all syntactically valid *identifiers* to the parser (subscript notation), not function applications — do not assume `AUC_<id>` invokes an AUC function; use `auc(<id>)` instead.
- **`x@TEnd`/`x@TStart` parses but is wrong.** `@` is the arm-selector operator, not a time-at-end operator. Use `lastValue(x)`/`firstValue(x)`, or `x[<numeric time coordinate>]` only when its unit context is verified.
- **Hard-coded time thresholds are unit-ambiguous.** `time > 900` has no unit annotation, and `u(...)` is not accepted in advanced outputs. `time > PT47H` is also wrong because ISO durations are not formula syntax. Prefer `time > analysisStartTime`, where `analysisStartTime` is a clearly named, unit-bearing model parameter.
- **AUC/integral units need verification.** The scalar `unit=` field is accepted and should be used when the expected dimension is known. It does not make `u(...)` valid inside a formula. Set `unit=` only after verifying the model/time context and trial sanity diagnostics; do not assume its time factor is seconds.
- **An objective's `target` referencing a sibling scalar's `id` can fail `trial.sanity()`** even standing on the exact pattern this skill's own examples show. See `references/advanced-output-set.md`'s "Common pitfalls" for the confirmed repro and the workaround (inline the formula in `target` instead of the scalar id).
