# Evidence, OCR, and optional code

The schema and `scripts/paper2model_report.py` enforce the record shape. This
file covers only the judgment they cannot make.

## Supplementary retrieval

Inspect the whole paper: appendices, availability statements, and supplement
links. Visit the DOI or publisher landing page and follow named supplementary
files, data deposits, and author repositories. Use a lawful full-text repository
when the publisher route fails. Follow cited earlier work when the paper
delegates a target-driving equation, value, or experiment to it.

A retrieved landing page is not a retrieved supplement. Name the file or page
inspected and the remaining gap.

Keep the retrieval statuses distinct, because they mean different things:

- `not_found`: searched for and not located.
- `inaccessible`: known to exist and cannot be obtained.
- `awaiting_user_source`: asked the user for it, still waiting.
- `not_attempted`: outside the reproduction scope.

None of these is the same as a paper that reports no supplement, and a failed
retrieval never authorizes a guessed parameter. Seek the evidence or state an
explicit assumption, then reassess adequacy.

When planning a retrieval whose URL is unknown, say the URL is unresolved. Do
not invent a publisher path to fill the record.

After reasonable attempts fail, ask the user for the exact missing source, using
the request format in `report-delivery.md`, and continue independent work.
Access failure does not establish that the evidence is intrinsically absent.

## Source priority

There is no universal precedence. Decide it per conflict, from what the
reproduction claims. A reproduction of the published equations can prefer the
paper; a reproduction of an author's executable result can prefer tagged code.
Record both forms and the decision.

## Figure digitization

Review the rasters after extraction. Reject text, legend, and axis pixels, and
keep missing curve segments missing. Preserve the original extraction and record
a source-quality amendment when a later review changes it. An extraction
correction never changes frozen model choices or tolerances.

## OCR

Use native machine-readable extraction for clean PDFs; PyPDF extraction is not
OCR. For scans, or when extracted equations and tables are unreliable, prefer a
dedicated OCR skill or provider tool if one is available. Get authorization
before sending a confidential or licensed document to an external service.

Keep the packet as `ocr/` with `article.md`, `images/`, `tables/`, and a
`manifest.json` recording the provider and version, the source SHA-256, the
extraction date and page count, the generated paths, and whether a person
reviewed each equation, table, and figure against the source.

Inspect source images for minus signs, decimal points, superscripts, subscripts,
Greek letters, equation continuations, table headers, and footnotes. Downgrade
confidence when unreviewed OCR affects target-driving content.

## Optional code

- Record repository URL, commit or archive hash, license evidence, and retrieval
  date. A public URL is not proof of a reusable license.
- Record environment, dependencies, command, random seed, and outputs for an
  authorized reference run.
- Keep paper agreement and code agreement as separate fidelity results.
- Do not import dead, commented, or unused code as part of the active model.
