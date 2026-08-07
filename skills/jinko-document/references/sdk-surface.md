# SDK Surface

Prefer these typed methods:

- Create a document from markdown text or a markdown file:
  - `client.create_document_from_markdown(markdown_content=..., name=..., folder=..., description=..., version=...)`
  - `client.create_document_from_markdown(markdown_file_path=..., ...)`
- Retrieve an existing document:
  - `client.get_document("do-...")`
- Update an existing document:
  - `document.update_markdown(markdown_text)`
  - `document.update_markdown_from_file(path)`
- Inspect a Jinkō document's exported markdown (not guaranteed to be a lossless authoring round trip):
  - `document.content()`
- Export a document as a LaTeX ZIP, for when a LaTeX archive is specifically wanted instead of markdown:
  - `document.download_latex_zip()`
- Upload an image for document embedding:
  - `client.upload_image(image_file_path=...)`
- Create a Jinkō Reference item from a PDF:
  - `client.create_reference_from_pdf(pdf_file_path=..., name=..., folder=...)`

Useful item URLs:

- `document.url` gives the Jinkō app URL for the document.
- `reference.url` gives the Jinkō app URL for the uploaded paper/reference.
- `image.url` gives the Jinkō file-manager URL that can be used inside markdown image syntax.

## Round-trip warning

Do not use `document.content()` output as the canonical source for a later
`update_markdown(...)` call or as a repository mirror without a semantic diff.
Preserve the exact input payload used for creation/update as the durable mirror.
When retrieving a historical revision, verify that the SDK/API actually returns
revision-specific content before relying on it; do not assume that passing
`revision=n` makes the content response historical.
