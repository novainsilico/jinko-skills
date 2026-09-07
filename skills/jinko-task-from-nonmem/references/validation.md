# Checking a conversion

A conversion that runs is not a conversion that is right. Three checks, each
answering a different question.

## 1. Read the report

The cheapest and most important. It lists:

- every inferred unit and the basis for it;
- every renamed symbol and why;
- every construct refused, with the record and line;
- every stated approximation.

Most conversion errors are visible here. A time unit of `h` against a data set
recorded in days, or a concentration read as `mg/L` when the assay reported
`ng/mL`, will not raise an error anywhere downstream — Jinkō converts units and
solves in seconds, so a wrong unit changes the kinetics quietly.

## 2. Did it read the control stream correctly?

```bash
python skills/jinko-task-from-nonmem/scripts/compare_against_reference.py run1.mod \
  --ext run1.ext --check parse
```

Compares the converter's reading against `nonmem2rx`, an independent NONMEM
parser. Agreement across THETA, OMEGA and the compartment structure means two
separately written parsers read the same model, which is strong evidence the
reading is right. Disagreement means one is wrong and names where.

Needs R with `nonmem2rx`; reports unavailable when absent. A command whose only
requested check is unavailable exits nonzero.

## 3. Does the Jinkō model reproduce what was read?

```bash
python skills/jinko-task-from-nonmem/scripts/compare_against_reference.py run1.mod \
  --ext run1.ext --check solve --model-sid cm-1234-5678 --time-unit h
```

`--reference` picks what Jinkō is compared against. The three are not
interchangeable, and which one ran changes what an agreement means.

| `--reference` | Solves | Agreement covers | Needs |
| --- | --- | --- | --- |
| `scipy` (default) | this converter's own IR, with scipy | the platform only | nothing |
| `rxode2` | nonmem2rx's independent translation, with rxode2 | reading, emitting and platform | R |
| `nonmem` | nothing -- reads PRED/IPRED from a `$TABLE` the run already wrote | everything, against the reference implementation | the output file |

`scipy` **isolates the platform**. It integrates the equations this converter
emitted, so a disagreement means Jinkō did not reproduce them -- and an
agreement says nothing about whether the reading was right. That is why the
parse check exists alongside it.

`rxode2` is the stronger claim and the blunter instrument. An independent
parser's translation, solved by an independent integrator: agreement covers the
reading, the emitting and the platform at once, and a disagreement does not say
which of the three is at fault. Run `scipy` to localise it.

Final THETA estimates and infusion duration are passed to both solves. The
`rxode2` path currently refuses models needing covariate overrides because its
generated event table cannot yet guarantee the same covariate inputs; use the
original run's `$TABLE` as the independent numerical reference for those models.

On `xgxr021` the two references agree with each other to **5.6e-11** and Jinkō
agrees with both to **4.8e-06** -- so the residual is the platform's solver
tolerance, not anybody's reading.

`nonmem` needs no licence, only the output file: point `--nonmem-table` at a
`$TABLE` and it compares against NONMEM's own PRED or IPRED for one subject,
interpolating the solved series onto the table's observation times.
`--subject` picks which subject, because a table holds every subject's rows in
sequence and reading TIME straight through gives a sawtooth nothing can match.
This is the only check that closes the loop against the reference
implementation, and it is the one to run when the numbers matter.

Solves the same equations locally and compares point-wise against Jinkō, with
Cmax and AUC reported alongside. Point-wise agreement is the gate because a
structural error can leave exposure intact: a sign slip on a peripheral
transfer changes the shape while barely moving AUC.

This check says nothing about whether the reading was right — it integrates the
same equations the converter produced. It is what catches emitter and platform
faults, and two real ones came from it:

- a rate constant declared `1/h` applied per second, which emptied the depot
  inside one 30-minute step;
- a concentration emitted as a constant parameter, so Jinkō evaluated it once
  at t=0 and it read zero for the whole simulation.

Neither is a parsing mistake, and comparing parsers would never have found
them.

Three things make this comparison mean anything, and each of them was a bug
first.

**Both sides get the model's own inputs.** The dose schedule, the infusion
duration and every covariate default are read back off the created model rather
than assumed. Defaulting a covariate to zero here instead makes a
weight-proportional volume zero, `K = CL/V` divides by it, and the reference
solve produces nothing — while the platform solved a perfectly good model.

**The grid comes from the platform.** `Time` is a requestable series; request
it alongside the output. A recorded dose event inserts its own pre- and
post-trigger points, so a model with a dosing event returns more values than
`tMin`/`tStep` implies. A reconstructed grid then pairs every value with the
wrong time and reports a large difference that is not there.

The check is read-only and uses the model's stored solving window. If that
window does not cover the reference observations, adjust it explicitly before
running the checker; the checker never versions the model itself. Pass the same
`--time-unit` used during conversion so returned platform seconds are translated
back to the NONMEM time basis correctly.

**The relative-error floor scales with the curve.** A lagged model is exactly
zero before absorption starts. One solver's floating-point crumb of `1e-9`
against the other's exact zero is a relative error of `1.0` on identical
curves. The floor is a millionth of the reference peak, which says what is
actually meant — a concentration a millionth of Cmax is not distinguishable
from zero — and still catches a real early-time error, which is orders of
magnitude larger. The worst *absolute* difference and the peak it is measured
against are both reported, so nothing is hidden behind the floor.

## 4. Does the population match, not just the typical individual?

The structural model and the population fail independently, and a check that
holds every random effect at zero cannot see a population fault at all. A
descriptor attached to the wrong component, a variance read as a standard
deviation, or a correlation quietly dropped all leave the typical individual
untouched and every other patient wrong.

Three claims, weakest to strongest, are needed before calling a population
equivalent. The bundled structural checker does not make these claims.

**Distributional.** Do the two populations share a median, a CV and a 95%
interval? Necessary but weak — two different populations can share all three.

**Per-patient.** Solved with the *same* drawn random effects, does every
patient's curve agree? This is the strong claim, and it is available only
because a generated vpop can be downloaded and replayed. It catches a
descriptor wired to the wrong parameter, which distributional agreement hides
completely. Reported as a histogram rather than a single number: one
badly-wired patient shows up as an outlier while leaving the median and the
bands untouched.

**Covariance.** Does the realised population carry the `$OMEGA` that was asked
for? Jinkō reaches a requested correlation matrix iteratively, so this is
measured, not assumed. Compared on an **absolute** scale, because a variance
fixed at zero has no meaningful relative error and the sampling error of a
sample variance is itself proportional to that variance. The tolerance is three
standard errors at the sample size in hand, `3 · σ² · √(2/(n−1))`, rather than
a round number chosen after the fact.

`upload_data_tables.py` validates the generated population-summary schema,
trial outputs, arms, source-table contents, fitness metadata, and overlay
diagnostics. Those checks prevent wiring the wrong data, but they are not an
independent population-equivalence measurement. State that limitation rather
than inferring population equivalence from a successful upload.

## Expected agreement

Below `1e-3` maximum relative error. In practice a converted 2-compartment oral
model agrees to around `5e-6`, the difference being solver tolerances rather
than anything structural. A model with an absorption lag sits nearer `1e-4`,
because the point at the lag boundary is where the two solvers' last bits
differ most and the curve there is at the floor. An error above `1e-3` is a
bug, not noise.

## Comparing against the original run's own output

When the `.lst` or a `$TABLE` file holds NONMEM's own `PRED`/`IPRED`, compare
against those directly. That closes the loop against NONMEM itself rather than
against a second open-source implementation, and is the strongest check
available without a NONMEM licence.
