# Commands and flags

## Model only

```bash
python -m nonmem2jinko convert run1.mod --model-only \
  --ext run1.ext --data data.csv --drug Warfarin
```

Add `--folder <id-or-name> --create-folder --json-out import/model.json --apply`
to create it and record the model SID.

Estimates come from `--ext` when given. For a `.lst` with no `.ext` companion
they are scraped from the listing's `FINAL PARAMETER ESTIMATE` block; without
either, `$THETA` initial estimates are used and the report says so.

## Whole trial

```bash
python -m nonmem2jinko convert run1.mod \
  --ext run1.ext --phi run1.phi --data data.csv --drug Warfarin \
  --population phi --eps-clones 20 \
  --folder "2026-09-04-nonmem-import" --create-folder \
  --json-out import/trial.json --apply --run
```

`--json-out` writes the created items' SIDs and URLs. Every later step needs
them, and reading them out of this script's prose is how a pipeline breaks
without saying so.

`--delete-on-error` removes a model the platform rejects instead of leaving it
in the project. Off by default: a rejected model is usually the most useful
thing to look at, and its diagnostics are readable in the UI. Turn it on for an
unattended run.

## Dosing

`--dosing auto` (the default) uses protocol arms when the data set has an arm
structure and per-patient dose slots when it does not.

A phase-1 study at three dose levels is three arms. A study where every subject
has an individualised history is not ninety arms — one arm per subject would
lose the pairing between a subject's parameters and that subject's schedule,
and multiply the trial by the number of arms. `--dosing per-patient` puts each
patient's own dose times and amounts in the vpop as numbered slots
(`doseAmountOne`, `doseTimeOne`, …), sized to the busiest subject, with unused
slots dosed with zero. It needs `--population phi` or `sampled`, because the
schedule rides on the patient table.

With `--population sampled` a patient takes its covariates *and* its schedule
from one resampled observed subject, so a weight-based dose stays consistent
with the weight it was chosen from.

## Correcting an inference

| Flag | Corrects |
| --- | --- |
| `--time-unit`, `--amount-unit`, `--volume-unit` | The three base units everything follows from |
| `--unit SYMBOL=unit` | One component's inferred unit |
| `--rename NONMEM=jinkoId` | One generated name |
| `--drug` | The stem of every state name |

All repeatable where it makes sense. The report prints the full rename and unit
tables so they can be audited against the control stream.

## Numerical check

```bash
python -m nonmem2jinko check run1.mod \
  --ext run1.ext --model-sid cm-1234-5678 --time-unit h \
  --json-out reports/comparison.json --series-out reports/series.csv \
  --report-out reports/equivalence.md --conversion-report reports/conversion.md \
  --items import/trial.json
```

`--check parse` and `--check solve` select one layer; both run by default.
`--report-out` renders the equivalence report from the measured metrics, with
an overlay plot when `--series-out` is given; see `reporting.md`.

`check --series-out` writes the two compared time
courses as CSV for independent plotting or inspection. A number says how close
two solves are; the series says *where* they differ.
