---
name: jk-mistral-ocr
description: Run one PDF through Mistral OCR with bbox annotations and high-resolution image crops.
compatibility: Requires MISTRAL_API_KEY. Uses requests and pdf2image.
metadata:
  author: Nova In Silico
license: MIT
---

# Minimal Mistral OCR

## When To Use

Use this skill when you have one scientific PDF and need a self-contained OCR artifact folder with Mistral annotations, markdown, tables, provider image crops, and high-resolution image crops from annotated bounding boxes.


## Run

```bash
python ./path/to/skills/jk-mistral-ocr/scripts/mistral_ocr_pdf.py path/to/paper.pdf
```

Default behavior:

- model: `mistral-ocr-latest`
- high-resolution crop target: `600` DPI
- output directory: `path/to/paper_mistral_ocr/`

Optional overrides:

```bash
python ./path/to/skills/jk-mistral-ocr/scripts/mistral_ocr_pdf.py path/to/paper.pdf \
  --output-dir path/to/output \
  --high-res-dpi 600 \
  --model mistral-ocr-latest
```

## Outputs

The output folder contains:

- `submission.json`: request settings without secrets.
- `response.json`: Mistral response with image base64 removed.
- `output.md`: merged markdown with local links.
- `images/`: OCR image assets replaced by high-resolution PDF crops when bboxes are usable.
- `tables/`: extracted table files.
- `manifest.json`: artifact counts and high-resolution crop summary.

## Validation

After a run, check:

- `output.md` exists and is non-empty.
- `response.json` has `pages`.
- `manifest.json` reports expected `page_count`, `image_count`, and `high_res_replaced_count`.
- Image links in `output.md` resolve under `images/`.
