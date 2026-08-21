# Reference SDK Workflow

## Retrieve PDFs and Extracts

Resolve an existing Reference with `client.get_reference(reference_sid)`. Inspect
`reference.bibliography`, `reference.doi`, and `reference.iter_extracts()` before
creating a duplicate. Download the attached PDF to an authorized path with
`reference.file.save_content_to_file(path)`; use `reference.file.content()` only
when bytes are needed in memory.

```python
pdf_bytes = reference.file.content()
reference.file.save_content_to_file("downloads/nova-study.pdf")
```

Retrieve an Extract as a typed project item, then inspect its structured content,
formulation, and highlights. Preserve the Extract and Highlight URLs when
sharing curated knowledge.

```python
extract = client.get_extract("as-EXAMPLE")
extract_payload = extract.content()
print(extract.formulation)
for highlight in extract.highlights:
    print(highlight.url, highlight.text)
```

Use `reference.iter_extracts()` to retrieve all extracts attached to one source;
filter by kind or classification when reviewing a large collection.

## Upload a PDF

Create a new Reference from exactly one local file path or byte payload:

```python
import jinko

client = jinko.JinkoClient()
reference = client.create_reference_from_pdf(
    pdf_file_path="papers/nova-2021.pdf",
    name="Nova 2021",
    folder="literature",
)

reference = client.get_reference("so-EXAMPLE")
reference.file.save_content_to_file("downloads/nova-2021.pdf")
```

`save_content_to_file` creates missing parent directories, but its destination
must be a file path, not a directory.

## Textual Extracts

Create a textual highlight from a distinctive quote copied from the PDF's native
text layer. `page_hints` accepts a one-based page number or sequence of pages.

```python
extract = reference.create_extract_from_pdf_quote(
    "Tumor volume was assessed every two weeks.",
    page_hints=4,
    classification_type="Data",
    classification_level="Strong",
    name="Tumor-volume assessment schedule",
)
print(extract.sid)
```

The matcher tolerates common encoding and whitespace differences and can bridge
page breaks or intervening table content. It can locate many mathematical
expressions, but complex formatting may still fail.

## Manual, Formula, and Rectangular Extracts

Use the JSON anchor examples in `../assets/manual-anchors.example.json` as the
payload shape. Anchors use one-based `page` values and top-left-origin `x`, `y`,
`width`, and `height`; use multiple anchors for multi-line text and one for a
rectangular crop.

```python
text_extract = reference.create_extract(
    anchors=anchors,
    text="The study-reported statement.",
    classification_type="Statement",
)

figure_extract = reference.create_extract(
    anchors=rectangular_anchors,
    name="Figure 2",
)
```

Quote matching can also create a formula, data-table, or rectangular extract:
pass `latex` (with optional `mathjs`), `data_table`, or `kind="Rectangular"`.
Provide at most one of `text`, `latex`, and `data_table`.

## Failure Handling

- **Missing PDF extra:** install `jinko-sdk[pdf]` in the environment that runs
  the SDK.
- **Quote not found:** use a longer distinctive quote from the native text layer,
  then add page hints.
- **Ambiguous quote:** use a longer quote or narrow the one-based page hints; do
  not choose an occurrence arbitrarily.
- **Scanned PDF:** quote matching cannot OCR it. Obtain user-approved anchors or
  use a separately approved OCR workflow.
- **Figure/table crop:** create a rectangular extract with a validated anchor.
  Jinkō may supply automatic image extraction separately. Inspect existing
  rectangular extracts first, but do not promise or invoke that background UI
  capability from this SDK workflow.
