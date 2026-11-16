# NONMEM

Convert a NONMEM run into a working Jinkō trial. This route creates the
computational model, the virtual population, the protocol design, the output
set, and the trial, and it runs its own numerical check: the sanity check and
the comparison of `SKILL.md` do not apply here.

The converter is the `nonmem2jinko` package. It ships inside `jinko-sdk` and
is imported separately. Its numerical extra does not install by default:

```bash
pip install "jinko-sdk[nonmem2jinko]"
```

The extra adds scipy, which the numerical check integrates the reference solve
with. Without it every script still runs, and `--check solve` raises a message
naming the extra. The independent-parse check needs R with `nonmem2rx` and
`rxode2`; without them that check is unavailable rather than passed.

Use `JINKO_API_KEY` when it is set. Only without a key, call
`get_session_code` again before each script's own SDK process, because a
session code can be exchanged only once.

## Core Rules

- Run the commands. Never hand-translate `$PK`; only the commands' output is verified.
- Always check the numbers, and report the measured agreement. Never claim a
  conversion succeeded without one, and never publish a report whose verdict
  has no result in it.
- Say which reference the numbers came from. `--reference scipy` isolates the
  platform; `rxode2` covers the reading too; `nonmem` compares against a
  `$TABLE` the original run wrote and needs no licence, only that file. They
  are not interchangeable. The `rxode2` numerical reference currently refuses
  models needing covariate overrides rather than comparing unequal inputs.
- Blocking error means stop. Do not pass `--allow-issues` without telling the
  user what is lost.
- Read the report before applying. Units and names are inferred, and some
  inferences will be wrong for a given data set.
- Wrong time unit changes the kinetics silently. Jinkō accepts arbitrary time
  units but solves and returns results in seconds. Confirm amount, volume and
  time against the data set.
- Compare on the platform's own time grid. `Time` is a requestable series;
  request it. A recorded event inserts its own points, so a grid rebuilt from
  `tMin`/`tStep` pairs values with the wrong times.

## Commands

The converter's command line ships with the SDK: `python -m nonmem2jinko`.

| Command | Does |
| --- | --- |
| `convert` | NONMEM run to model, vpop, protocol design, output set, and trial. `--model-only` stops after the model |
| `check` | The numerical check. Not optional. `--report-out` renders the equivalence report |

Project writes are dry-run by default and gated by `--apply`. Local outputs are
explicit path arguments, and an existing file is replaced only with
`--overwrite`.

## Orchestration

1. Ask for `.ext`, `.phi` and the data set. Each improves the conversion; the
   control stream alone is enough to start.
2. Convert dry-run. Resolve what the report raises: `--time-unit`,
   `--amount-unit`, `--volume-unit`, `--unit SYMBOL=unit`,
   `--rename NONMEM=jinkoId`.
3. Apply, then run.
4. Check numerically using the same `--time-unit` as conversion. A skipped solve
   is a failure, not evidence. Report the number and its reference.
5. Render the equivalence report (`check --report-out`) whenever anyone other
   than the person running the conversion will rely on the model, and offer to
   publish it next to the model with `jinko-document`.

`convert` takes `--folder NAME --create-folder`, which keeps one run's items
together, and `--json-out FILE`, which is how the next step gets the SIDs. Do not scrape them out of the prose.

`--parent-folder NAME` nests that folder inside another one. Use it when a
project accumulates several conversions: a folder named for the day holding one
subfolder per model keeps each run's evidence together, and the runs sort
chronologically. Without it a project's root fills up with model names and
nothing says which run each belongs to.

## Decisions

**Population** (`convert`). `--population design` (default) is editable
in Jinkō afterwards. `phi` replays the fitted subjects. `sampled` draws from the
full multivariate normal represented by `$OMEGA`; a finite sample's realised
covariance has sampling error and must be measured rather than called exact.

**Random effects** (`convert`). `--vpop-mode etas` (default) represents
the target `$OMEGA` covariance through ETA marginals and correlations.
`parameters` puts marginals on the derived parameters instead: it reads better
in the UI but is equivalent only without covariate effects.

**Dosing** (`convert`). `--dosing auto` (default) uses arms when the
data set has an arm structure and per-patient slots when it does not. A study
where every subject has an individualised history — neonatal phenobarbital,
weight-banded single doses — has no arm structure, and `per-patient` puts each
patient's own dose times and amounts in the vpop. Needs `--population phi` or
`sampled`, because the schedule rides on the patient table.

**Uncertainty** (`convert`). `--eps-clones N` gives a per-patient
predictive cone. Needs `--population phi` or `sampled`. Not a VPC — see
`references/nonmem/residual-error.md`.

**Refused, with the record named:** steady-state (`SS`) dosing, `$MIX`, nested
random effects, `$OMEGA`/`$SIGMA` as SD, correlation or Cholesky, `$PRED`-only
models, abbreviated code that cannot be read (`MPAST`, a variable `ETA()`
subscript, `CALL`, `include`), a parameter the kinetics need that reads a
record-level data item such as `DV` or `EVID`, and `IF(AMT.GT.0) TDOS = TIME`
— which is refused precisely because substituting simulation time for it looks
right and silently gives zero time-since-dose.

**Reported, not refused:** `$PRIOR` and `$NONPARAMETRIC` shaped the estimation,
not the forward model, so the estimates convert as given.

**Converted with a stated approximation:** `DOSE = AMT` points at the model's
dose parameter, so a subject whose doses differ in amount reads only the first;
time-varying covariates keep their baseline only; a covariate selecting *which* random effect applies cannot be
one vpop marginal; a combined error model written through a weight
(`Y = F + W*EPS(1)`, `W = F*θ + θ`) is diagnosed with its coefficients but the
observable is emitted without residual error.

## References

- `references/nonmem/workflow.md` — commands, flags, worked sequence
- `references/nonmem/validation.md` — the numerical checks and what each proves
- `references/nonmem/reporting.md` — the equivalence report and how to publish it
- `references/nonmem/conversion-map.md` — what each NONMEM construct becomes
- `references/nonmem/residual-error.md` — `$ERROR`, `$SIGMA`, the clone approximation

Generic mechanics belong to the lower-level skills: `jinko-model` for
components, `jinko-vpop` for populations, `jinko-protocol` for arms,
`jinko-trial` for runs, `jinko-data-table` for tables, `jinko-trial-viz` for
visualisations, `jinko-document` for documents.
