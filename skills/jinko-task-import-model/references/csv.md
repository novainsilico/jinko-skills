# Results of another tool as CSV

Use this path for Monolix and for any tool that this skill cannot run. Ask the
user for a CSV of the source tool's simulation of the same scenario: Simulx or
the Monolix plots export for a Monolix project, or the tool's own export.

The CSV needs one time column and one column per compared series. Ask for
time points that fall on the Jinkō grid: `compare` reads only the source
points that match a Jinkō time point, and reports `NO SHARED TIMES` when none
does.

```bash
python scripts/import_check.py from-csv --dir <dir> --csv <file> \
    --time-unit h --column Cc=CONC --unit Cc="mg / L"
```

- `--time-unit`: the unit of the time column (for example `h`, `day`, `s`).
- `--column JINKO_ID=COLUMN`: when a column name is not the Jinkō id.
- `--unit JINKO_ID=UNIT`: when the CSV unit is not the Jinkō unit. Without
  it, the values are taken in the Jinkō unit.
- `--time-column`: when the time column is not named `time`.

A compared series with no column is reported as not checked. Monolix sets the
input values in the project, not in the structural model: compare a Monolix
project import, or a structural model whose inputs the user has set in Jinkō.
