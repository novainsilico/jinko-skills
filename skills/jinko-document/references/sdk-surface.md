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
- Export a document as a LaTeX ZIP, which is the only supported way for now to pull a Jinkō document:
  - `document.download_latex_zip()`
- Upload an image for document embedding:
  - `client.upload_image(image_file_path=...)`
- Create a Jinkō Reference item from a PDF:
  - `client.create_reference_from_pdf(pdf_file_path=..., name=..., folder=...)`

Useful item URLs:

- `document.url` gives the Jinkō app URL for the document.
- `reference.url` gives the Jinkō app URL for the uploaded paper/reference.
- `image.url` gives the Jinkō file-manager URL that can be used inside markdown image syntax.
