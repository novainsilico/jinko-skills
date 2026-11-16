# The equivalence report

## When to prepare it

Whenever the converted model will be relied on by someone who did not run the
conversion. A report that lives only on one laptop cannot be reviewed by the
team that depends on the model.

`check --report-out` renders it from the measured metrics, never from prose.
Its verdict is PASS only when the platform solve ran and passed within
tolerance. It says what each check proves. With `--series-out`, it draws the
two solves and their difference next to the report (needs matplotlib).
`--items` links the converted items as cards, from the `--json-out` of
`convert`. `--conversion-report` appends the report that `convert` wrote.

The report covers the structural model, with every random effect at zero.
Population equivalence is a separate claim and needs separate measured
evidence (see `validation.md`).

## Publishing it

Publish the report with `jinko-document`
(`python -m jinko.cli.create_document_from_markdown`), in the folder of the
converted items. It uploads the plot and asks for approval of a digest before
it writes. Pass `--items` so the report links every item that exists: a report
that links the model but not the trial it was checked on is harder to trust.
