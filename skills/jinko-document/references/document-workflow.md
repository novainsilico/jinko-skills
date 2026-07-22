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

## Jinkō rendering rules

- A Jinkō project-item URL such as `cm-...`, `so-...`, `as-...`, or `do-...` renders best when it is the only content in its paragraph.
- A markdown link with custom text is still a normal link, not a project-item card.
- A Jinkō image URL can be inserted with standard markdown image syntax: `![alt](https://.../file-manager/<uuid>)`.
- A public external image URL can also be used directly if Jinkō can reach it.

## Local image policy

When the markdown references local image files:

1. resolve each path relative to the markdown file
2. upload it with `client.upload_image(image_file_path=...)`
3. replace the markdown target with the returned Jinkō file URL

Do not leave unresolved local filesystem paths in the final markdown sent to Jinkō.

## Reference / bibliography policy

Plain in-text citations such as `[1]` and `[2]` remain plain markdown text unless the bibliography section links them to Jinkō Reference items.

When the user wants cited papers added to Jinkō:

1. create or reuse one Jinkō Reference item per paper with `client.create_reference_from_pdf(...)`
2. add a bibliography section that links each citation label to the resulting `reference.url`

The bundled script supports a `<!-- jinko:references -->` placeholder. If present, it is replaced with a generated bibliography block. Otherwise the generated bibliography is appended to the end of the markdown.
