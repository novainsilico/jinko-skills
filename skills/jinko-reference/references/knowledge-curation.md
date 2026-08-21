# Collaborative Knowledge Curation

Use Jinkō References and Extracts to make the scientific foundations of a model
or trial inspectable by R&D colleagues, trial managers, external experts, and
auditors. Preserve the chain `Reference → Extract → Highlight`; report stable
SIDs and Jinkō links in the handoff.

## Knowledge Objects

- A **Reference** is a source PDF and its bibliography metadata. The SDK exposes
  `reference.bibliography` and `reference.doi` after PDF upload.
- An **Extract** is a selected textual, rectangular, formula, or data-table
  object from one Reference. Its `.source` identifies the originating Reference.
- A **Highlight** is a piece of evidence inside an Extract. Inspect
  `extract.highlights`; every `highlight.url` links directly to that highlight in
  its source Reference.
- `extract.formulation` is the stored wording, if present. Retain a distinction
  between that formulation and what was selected in the original PDF.

## Human Review and Classification

Classify evidence only after reviewing the source and record why the selected
level is appropriate. The SDK accepts:

- `Statement`: scientific information asserted by the source.
- `Hypothesis`: a proposed explanation based on limited evidence.
- `Data`: experimental values, parameters, figures, or tables.

The optional classification levels are `Weak`, `Medium`, `Strong`, and
`Excellent`. A classification type without a level is unevaluated; a
`Hypothesis` cannot use `Excellent`. The SDK defines these values, not a
scientific scoring rubric, so ask the user for their evidence grid or review
criteria when it is not already established.

```python
for extract in reference.iter_extracts(
    kind="Textual",
    classification_type="Statement",
    classification_level="Strong",
):
    print(extract.sid, extract.formulation)
    for highlight in extract.highlights:
        print(highlight.url)
```

## Linking Knowledge to Project Work

Use a Reference or Extract Jinkō URL when documenting an assumption, parameter,
equation, or observed datum. This makes the evidence verifiable without copying
an untraceable claim into a model or report. Use `jinko-document` for document
authoring and the relevant model workflow for model component metadata.

## Composing and Inspecting Extracts

Inspect `extract.highlights` to review the evidence carried by an Extract and
use each `highlight.url` when a reader needs to verify its exact location in the
source. For a multi-line textual selection, supply multiple anchors when
creating the Extract. Preserve the resulting Extract and Highlight links when
connecting the curated knowledge to a document or model.
