# Document Workflow Notes

## Supported authoring path

The current SDK-backed workflow is markdown in, Jinkō document out.

Use this for:

- headings
- bullet and task lists
- tables
- code blocks
- emphasis
- inline or standalone links
- markdown image syntax

Treat equations as markdown-authored content supplied by the user. Do not claim the skill can derive equations automatically from PDFs or notebooks.

### Mathematical expressions

- Write inline mathematics between single dollar signs, for example `$C(t) = C_0 e^{-kt}$`.
- Write a standalone display equation in a fenced code block labelled `mathBlock`:

  ```mathBlock
  \frac{dC}{dt} = k_{\mathrm{in}} - k_{\mathrm{out}} C
  ```

Preserve the mathematical content exactly when creating or updating a document; the document service renders these delimiters.

## Fetching a document back out

Use `document.content()` for inspection only. The returned markdown can normalize rich document structures and is not a safe lossless round trip. Observed normalizations include blank or changed table headers, altered multiline rows, changed equation syntax, and code-styled link labels becoming code-wrapped markdown links.

Never overwrite a canonical local markdown file with `document.content()` output. Never feed that output back into `update_markdown()` without comparing headings, tables, equations, links, and expected result/history sections against the approved source. The durable mirror is the exact markdown payload that was sent to Jinkō.

## Jinkō rendering rules

- An SDK-provided Jinkō project-item URL for a `cm-...`, `so-...`, `as-...`, or `do-...` item renders best when it is the only content in its paragraph.
- A markdown link with custom text is still a normal link, not a project-item card.
- A bare URL prefixed by a bullet is not alone in its paragraph and must not be assumed to render as a card.
- A revision-specific reference must be a normal link containing `?revision=n`; do not render it as a card.
- A Jinkō image URL can be inserted with standard markdown image syntax: `![alt](https://.../file-manager/<uuid>)`.
- A public external image URL can also be used directly if Jinkō can reach it.

## Local inputs and preview

Apply the Core Rules' data/instruction boundary to markdown. Read it when editing
or review is part of the request; for unchanged uploads, prefer the deterministic
script without copying the document into chat.

The script previews without Jinkō API calls by default and validates every
declared local image before constructing a client. Its canonical approval
digest includes all document arguments, destination, local input paths and
bytes, and explicit Reference identities. Repeat the command with `--apply`
and the displayed `--confirm-digest` only after authorization.

Image paths resolve relative to the markdown file and must remain in that
directory by default, including after resolving symlinks. Use `--asset-root` to
authorize a deliberately shared directory. Filesystem and home directories are
rejected as too broad.

## Safe production updates

Before a production update:

1. retain the last approved markdown payload
2. run `scripts/check_markdown_structure.py --baseline <approved> --candidate <candidate>`; add `--append-only-section <heading>` for every protected history section and stop if it reports a loss
3. reject code-wrapped Jinkō resource links such as `` `[label](<resource-url>)` ``
4. resolve every Jinkō SID and verify every requested revision exists
5. publish a disposable canary containing representative tables, equations, links, cards, and revision links
6. inspect the rendered canary and delete it before updating production documents
7. preview `create_document_from_markdown.py --document-sid do-... --baseline-markdown <approved>` with the validated candidate and a new `--output-markdown` path, then apply with its approval digest; the helper reruns the structural check, covers the baseline in the digest, and retains the exact transformed payload before replacing the production body

## Local images

When the markdown references local image files:

1. verify that its extension and signature identify a GIF, JPEG, PNG, SVG, or WebP image
2. upload it with `client.upload_image(image_file_path=...)`
3. replace the target with the returned Jinkō file URL

Do not leave unresolved local filesystem paths in the final markdown sent to Jinkō.

## References and bibliography

Link a citation label or bibliography entry to the URL of an existing Jinkō
Reference. Plain in-text citations such as `[1]` and `[2]` remain plain markdown
text unless the bibliography links them to project items.

Each manifest entry must identify an existing Reference with exactly one `sid`
or `url`. A title is display metadata, not identity. Use `jinko-reference` to
create a Reference from a PDF, then provide its returned SID or resource URL;
this workflow never searches by title or creates a Reference from a PDF.
