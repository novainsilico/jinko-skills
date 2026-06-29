---
name: jk-document
description: >-
  Create or update a Jinkō document from markdown through the jinko-sdk, including
  headings, tables, code blocks, links to Jinkō project items, uploaded images,
  and optional reference-PDF ingestion. Use this skill whenever the user wants
  to turn local markdown into a Jinkō document, refresh an existing document from
  edited markdown, prepare markdown so Jinkō renders cards and images correctly,
  or attach paper PDFs as Jinkō references alongside the document. Do not use it
  for slide generation, extract authoring, or literature search.
compatibility: >-
  Check set-up with the `jk-sdk-setup` skill. Document and reference creation
  requires write access to the target Jinkō project.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Document SDK Workflows

Use this skill for SDK-backed document creation and updates. Stay on the typed SDK
surface whenever possible.

## Core Rules

- Prefer `document.update_markdown(...)` or `document.update_markdown_from_file(...)` when updating an existing document.
- Use `document.download_latex_zip()` when the user wants to fetch a Jinkō document back out; this is the only supported way for now to pull a Jinkō document.
- Keep long Python out of chat output. Use the bundled script or a short, task-specific snippet only when needed.
- Treat markdown as the current supported authoring format. Do not promise DOCX, PDF, or notebook conversion unless the user explicitly asks for a custom preprocessing step.
- If the user wants project-item cards, place each Jinkō project-item URL alone in its own paragraph.
- If the user wants local images in the final Jinkō document, upload them first with `client.upload_image(...)` and replace the markdown image target with the returned Jinkō file URL.
- If the user wants paper references available in Jinkō, create or reuse Jinkō Reference items with `client.create_reference_from_pdf(...)` and link them from the markdown bibliography.

## Default Workflow

1. Load credentials and construct `JinkoClient()`.
2. Resolve one destination folder when the user wants the document organized under a specific Jinkō folder.
3. Read the local markdown file.
4. Rewrite local image paths to uploaded Jinkō image URLs when needed.
5. Optionally create or reuse Jinkō Reference items for cited papers.
6. Create the document with `client.create_document_from_markdown(...)`, update an existing document with `document.update_markdown(...)`, or export it later with `document.download_latex_zip()`.
7. Return the resulting document SID and URL.

## Bundled Script

- `scripts/create_document_from_markdown.py`: creates a Jinkō document from a local markdown file, uploads local images, and can inject a generated Jinkō-linked bibliography from a reference manifest.

Examples:

```bash
python skills/jk-document/scripts/create_document_from_markdown.py \
  --name "PK summary" \
  --markdown-file skills/jk-document/assets/example_document.md

python skills/jk-document/scripts/create_document_from_markdown.py \
  --name "PK summary" \
  --markdown-file report/main.md \
  --folder 2026-06-25-program-review

python skills/jk-document/scripts/create_document_from_markdown.py \
  --name "PK summary with refs" \
  --markdown-file report/main.md \
  --reference-manifest skills/jk-document/assets/reference_manifest.example.json
```

## Reference Routing

- Read `references/document-workflow.md` for markdown rendering rules, image handling, and bibliography guidance.
- Read `references/sdk-surface.md` for the typed SDK methods and when to use each one.
- Use `assets/example_document.md` as the default sample markdown layout.
- Use `assets/reference_manifest.example.json` when the user needs Jinkō reference creation tied to bibliography entries.
