# What each NONMEM construct becomes

## Model structure

| NONMEM | Jinkō | Notes |
| --- | --- | --- |
| `$SUBROUTINES ADVAN{n} TRANS{m}` | explicit ODEs | The library is written out; Jinkō has no PREDPP |
| `$MODEL` + `$DES` | explicit ODEs | `DADT(i)` becomes the right-hand side directly |
| `A(n)` | a mutable parameter carrying an ODE | Not a species — see below |
| `S{n}` | `scale{Compartment}` | The observed prediction is `A(n) / S{n}` |
| `F{n}` | `bioavailability{Compartment}` | Multiplies the dose in the event |
| `ALAG{n}` | `lagTime{Compartment}` | Shifts the dosing event's first trigger |
| `R{n}` / `D{n}` | `infusionRate{Compartment}` | A rate term in the ODE, switched by a pair of events |
| `$MODEL COMP=(X,DEFOBS,DEFDOSE)` | which compartment is observed and dosed | Both default to compartment 1, *not* to declaration order |

PREDPP also accepts a **letter** where a compartment number would go: `SC` is
the central compartment's scale and `S0`/`SO` the output compartment's. `SC=V`
means exactly what `S2=V` means under `ADVAN2`. Reading it as an ordinary `$PK`
variable leaves the prediction an unscaled amount — a silent factor of one
whole volume, and the sort of error that looks plausible on a plot.

A `$DES` model often bypasses `F` and writes its own prediction:
`conc = A(2)/v`. That expression is the more direct statement of which
compartment is observed and how it is scaled, so it wins over `$MODEL`'s
`DEFOBS` when the two disagree, and the disagreement is reported.

`RATE` is emitted as a real zero-order input, not a bolus at its start time. A
positive `RATE` *is* the rate, `-1` says `R{n}` holds it, `-2` says `D{n}` holds
the duration. Each dose adds its own rate at the start and removes exactly that
rate at the end, so overlapping infusions accumulate the way NONMEM's do. A
`RATE` that neither `R{n}` nor `D{n}` resolves is a reported gap, never a
quiet bolus.

## Abbreviated code

NM-TRAN accepts Fortran's double-precision intrinsics alongside the generic
names: `DEXP`, `DLOG`, `DSQRT`, `DABS`, `DMAX1` and the rest. The `D` chose the
double variant in FORTRAN 77 and means nothing to a converter, so they resolve
to the plain forms. Refusing them as unknown functions rejected models that are
entirely ordinary, MU-referenced control streams among them.

A record can carry a parenthesised option on a line of its own:
`$ERROR (OBSERVATION ONLY)` restricts the block to observation records. That
says *when* the block runs, not what it computes, so the option is dropped and
the statements read as written. A parenthesised line that is *not* a known
option is still a syntax error -- dropping every one of them would hide real
mistakes.

Abbreviated code this converter cannot read is an itemised error naming the
record and line, not an exception. `MPAST`, an `ETA()` subscripted by a
variable via `$ABBR REPLACE`, a `CALL` to user Fortran, NM-TRAN's `include`
directive: each is refused, and the rest of the model is still reported. A
traceback says nothing about the ninety per cent that read perfectly.

A control stream or data set carrying bytes that are not UTF-8 is read anyway.
Numbers are ASCII, so nothing that matters is lost; a `uU/mL` column header
written in Latin-1 is not worth failing a conversion over.

## Reserved data items

| NONMEM | Jinkō | Notes |
| --- | --- | --- |
| `TIME`, `$DES`'s `T` | `time` | Simulation time, which a formula can reference |
| `AMT` | the dose parameter | See the approximation below |
| `DV`, `EVID`, `MDV`, `CMT`, `RATE`, `II`, `ADDL`, `SS` | nothing | Record-level facts a simulated model has no equivalent for |

`DOSE = AMT` — bare, or in the guarded `IF(AMT.GT.0) DOSE = AMT` form NONMEM
actually uses — points at the model's dose parameter. This was the largest
single refusal class in a 627-stream sweep. **It is an approximation and the
report says so:** one dose parameter cannot represent a subject whose doses
differ in amount, and such a model reads only the first.

`IF(AMT.GT.0) TDOS = TIME` is refused. It remembers the time of the most recent
dose and holds it between doses, which is state a formula cannot carry. The
refusal is deliberate rather than a gap: `TIME` *is* simulation time, so
substituting it would make `TAD = T - TDOS` identically zero and silently
delete the absorption term built on it. A plausible wrong answer is worse than
a refusal.

Not every `$PK` line is model. `IF(AMT.GT.0) BTIME=TIME` and `TAD=TIME-BTIME`
exist to be tabulated, and emitting them would put a reference to the data item
`AMT` into a Jinkō model, where no such thing exists — the platform then
rejects the whole model over a variable that was never part of it. Anything the
kinetics cannot reach is dropped and listed. Anything the kinetics *can* reach
that reads a record-level data item is a blocking error instead, because there
is nothing to convert it to.

Amounts are **parameters, not species**. A Jinkō species requires a
compartment, that compartment requires a volume, and conversion to
`extentUnits` wants a molar mass. NONMEM supplies none of the three: `A(1)` is
a depot with no volume, the output compartment is a sink, and no control stream
contains a molar mass. Any value put there would be invented. Jinkō allows an
ODE's left side to be a parameter, so amounts become parameters with a mass
unit and volumes stay ordinary parameters used inside rate expressions —
exactly NONMEM's own structure.

Under `TRANS4` a control stream may still assign `K`, `K23` and `K32`. NONMEM
ignores those and derives the rates from `CL`/`V2`/`Q`/`V3`, so the converter
does too and flags the assignments as dead. Taking them at face value would
silently change the model.

## Parameters and random effects

| NONMEM | Jinkō | Notes |
| --- | --- | --- |
| `THETA(n)` | `pop{Name}` parameter | Named from the `;` label when there is one |
| `ETA(n)` | `eta{N}` parameter, tagged `i::vpop` | Sampled by the vpop |
| `EPS(n)`/`ERR(n)` | `eps{N}` parameter, tagged `i::vpop` | One draw per patient — see `residual-error.md` |
| `$OMEGA` | normal marginals + pairwise correlations | Exact; see below |
| `$SIGMA` | `sigma{Role}` parameters | Carried so the error model is not lost |
| covariates | parameters tagged `i::vpop` | Default to the observed median |
| `$PRIOR`, `$NONPARAMETRIC` | nothing | Estimation-time only; the estimates convert as given |

A THETA's unit is solved from the dimensional balance of the formula that uses
it, not guessed from its position. The two shapes NONMEM uses for a covariate
effect look identical positionally and mean different things:

```
TVV = THETA(2) * WGT          THETA(2) is a volume
TVV = TVV * (1 + THETA(3))    THETA(3) is a fraction
```

A log-parameterised model has no unit to solve for at all — `KA =
EXP(THETA(1) + ETA(1))` is dimensionless arithmetic that NONMEM understands as
a rate because the modeller knows THETA(1) is a log rate. Jinkō checks
dimensions and rejects it, so the emitted formula carries an explicit unit
literal: `(exp(popKa + etaOne)) * u(1/h)`. The number is unchanged; the
dimension is stated.

The target `$OMEGA` distribution converts exactly in the default ETA mode. NONMEM states
`ETA ~ MVN(0, Ω)`; a Jinkō design with normal marginals and pairwise Pearson
coefficients `Ω_ij / sqrt(Ω_ii · Ω_jj)` *is* that multivariate normal. Jinkō
ignores declared correlations unless `optimize_correlation` is on, which the
scripts set whenever there are any. A generated finite population only samples
that target, so its realised covariance has sampling error.

In `--vpop-mode parameters` the marginals go on the derived parameters instead,
which needs the closed-form correlation of two jointly lognormal variables:

```
r_ij = (exp(Ω_ij) − 1) / sqrt((exp(Ω_ii) − 1)(exp(Ω_jj) − 1))
```

That transform is not cosmetic — an ETA-scale correlation of 0.500 becomes a
natural-scale Pearson of 0.484. It is exact only for a model without covariate
effects, since one marginal on `clearance` must otherwise absorb variation that
belongs to the covariates.

## Abbreviated code

`$PK` is imperative and reassigns symbols; a Jinkō model is declarative. The
converter folds one into the other: reassignment becomes versioning, a branch
becomes a conditional, and intermediate versions are inlined so each NONMEM
symbol yields exactly one Jinkō parameter.

```
KA = TVKA*EXP(ETA(9))
IF (MEAL.EQ.1) KA = TVKA*EXP(ETA(10))
```

becomes one parameter:

```
absorptionRate = mealStatus == 1 ? typicalAbsorptionRate * exp(etaTen)
                                 : typicalAbsorptionRate * exp(etaNine)
```

The kinetics are then right for both groups, but the *population* is not: a
vpop descriptor is a single marginal and cannot switch between two ETAs. The
report says so when it happens.

## Dosing

Dosing mechanics live in the model as events, and the protocol only overrides
their values — Jinkō's own separation. So the data set's dosing records become
one parameterised event plus `dose`, `doseInterval` and `doseCount` parameters
tagged `i::protocol`, and the protocol design carries one arm per distinct
schedule with arm weights set to the subject counts.

`II`/`ADDL` map to `time_trigger_every` and `time_trigger_count`. `ALAG{n}`
shifts `time_trigger_first_time`, and because trigger times accept formulas a
per-patient lag time works with no special-casing.

The event reads both parameters whether or not the data set repeats. Wiring
them only when the data set happened to repeat left both components unread,
which the platform reports as `UNUSED_COMPONENT`, and silently discarded any
arm override of either.

**The trigger's count is recurrences, not occurrences.** The event fires
`count + 1` times — the platform's own `numberOfOccurrences` reads
`EquallySpacedCount _ count -> count + 1` — while the UI labels the field
"Number of occurences", which is what makes this easy to get wrong. `doseCount`
is the number of *doses*, which is what `ADDL + 1`, the protocol arms and the
equivalence check all mean by it, so the trigger is emitted as
`doseCount - 1`. Passing `doseCount` straight through gave one dose too many:
an interval of 5 with a count of 3 dosed at 0, 5, 10 *and* 15.

An interval of zero hides that off-by-one, which is why it survived a first
round of checking: coincident occurrences collapse, so the single-dose default
doses once either way.

Each arm therefore pins all three values, an interval of zero included. The
model's defaults come from the first dosing record in the data set, which
belongs to whichever arm sorts first, so an arm overriding only the amount
would otherwise inherit that arm's repeat. Doses that are not evenly spaced are
not an interval and a count: that arm gives a single dose and the report names
what was lost, since repeating on an interval of zero would put every
occurrence at the first dose time and lose all but one of them.

`SS` has no Jinkō equivalent and is a hard error naming the records.

## Naming

Jinkō naming conventions reject almost every name NONMEM produces. `V2`, `K23`,
`S2` and `A(1)` all fall foul of the same three rules: no ordinal suffix as the
only differentiator, no unexpanded single letters, no compartment markers. Case
is fixed by category — parameters and events `lowerCamelCase`, states and ODEs
`PascalCase`, the model `UpperCamelCase` — and a concentration must be a derived
name rather than a state name.

A vocabulary table covers the standard PK and covariate terms, and the ADVAN
decides whether `V2` is the central or the peripheral volume. Anything outside
the table is derived from the modeller's own `;` label, and reported when there
is no usable one.

Override any of it with `--rename NONMEM=jinkoId`. The report prints the whole
table so it can be audited against the control stream.
