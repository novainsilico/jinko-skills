# Commands and flags

## Model only

```bash
python skills/jinko-task-from-nonmem/scripts/convert_model.py run1.mod \
  --ext run1.ext --data data.csv --drug Warfarin
```

Add `--folder <id-or-name> --create-folder --json-out import/model.json --apply`
to create it and record the model SID. A generated `--script` is also dry-run by
default and requires its own explicit `--apply` before it writes.

Estimates come from `--ext` when given. For a `.lst` with no `.ext` companion
they are scraped from the listing's `FINAL PARAMETER ESTIMATE` block; without
either, `$THETA` initial estimates are used and the report says so.

## Whole trial

```bash
python skills/jinko-task-from-nonmem/scripts/convert_trial.py run1.mod \
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
python skills/jinko-task-from-nonmem/scripts/compare_against_reference.py run1.mod \
  --ext run1.ext --model-sid cm-1234-5678 --time-unit h \
  --json-out reports/comparison.json --series-out reports/series.csv
```

`--check parse` and `--check solve` select one layer; both run by default.

## Population overlay

```bash
python skills/jinko-task-from-nonmem/scripts/upload_data_tables.py \
  --trial-sid tr-1234-5678 --output cDrugCentral --output cDrugCentralObserved \
  --folder "2026-09-04-nonmem-import" --create-visualization --apply
```

Pass `--output` once per output the visualisation displays. `--summary-table-sid`
attaches an already-uploaded table instead of making another. `--json-out`
writes the table and visualisation SIDs; `--timeout` matters here because an
individual table runs to tens of thousands of rows and the SDK's default is
30 s.

`--max-individual-rows` (default 20000) skips the individual table when it
would be larger than the upload survives — one row per patient, per arm, per
time, per output, so a trial with a fine solving grid reaches tens of thousands
of rows *per output*. The skip names the row count; `--max-individual-rows 0`
tries regardless. `--skip-individual` skips it unconditionally.

## Equivalence report

```bash
python skills/jinko-task-from-nonmem/scripts/render_equivalence_report.py \
  --comparison reports/comparison.json --series reports/series.csv \
  --conversion-report reports/conversion.md --out reports/equivalence.md

python skills/jinko-task-from-nonmem/scripts/publish_equivalence_report.py \
  reports/equivalence.md --comparison reports/comparison.json \
  --model cm-1234-5678 --vpop vp-1234-5678 \
  --trial tr-1234-5678 --trial-visualization tv-1234-5678 \
  --folder "2026-09-04-nonmem-import"

# Review the files, links, and digest printed by the dry run, then repeat with:
# --apply --approve-digest <printed-digest>
```

The renderer consumes the measured public-script outputs and fails its verdict
unless the platform solve passed. It describes structural-model evidence only;
do not call it population equivalence without a separate measured population
comparison.

## Running a whole corpus

`sdk/tests/corpus/corpus_run.py` drives all four stages over every
pinned reference model, one folder per model, and keeps a resumable ledger. It
is the harness that found most of the converter's real defects, and it is
development tooling rather than part of the skill.

```bash
python sdk/tests/corpus/corpus_run.py --size 60 --summary reports/corpus-summary.md
python sdk/tests/corpus/corpus_run.py --only warfarin-lag --stage compare --force
```

A `--dry-run` stage is recorded as a dry run and never satisfies a live one.

`compare_against_reference.py --series-out` writes the two compared time
courses as CSV for independent plotting or inspection. A number says how close
two solves are; the series says *where* they differ.
