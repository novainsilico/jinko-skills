#!/usr/bin/env python3
"""Minimal standalone Mistral OCR extraction for one PDF."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from pdf2image import convert_from_path

MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"
DEFAULT_MODEL = "mistral-ocr-latest"
DEFAULT_HIGH_RES_DPI = 600

IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
TABLE_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_default_env() -> None:
    """Load .env from the current directory or its parents."""
    for folder in [Path.cwd(), *Path.cwd().parents]:
        env_path = folder / ".env"
        if env_path.exists():
            load_env_file(env_path)
            return


def bbox_annotation_format() -> dict[str, Any]:
    """Return a compact bbox annotation schema for scientific figure triage."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "bbox_triage_digitization",
            "schema": {
                "type": "object",
                "properties": {
                    "asset_type": {
                        "type": "string",
                        "enum": [
                            "plot",
                            "table_like",
                            "equation",
                            "scheme",
                            "chromatogram",
                            "photo",
                            "diagram",
                            "other",
                        ],
                    },
                    "figure_label": {"type": "string"},
                    "is_scientific_plot": {"type": "boolean"},
                    "likely_digitizable": {"type": "boolean"},
                    "recommended_action": {
                        "type": "string",
                        "enum": ["digitize_now", "digitize_if_needed", "skip"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "skip"],
                    },
                    "data_nature": {
                        "type": "string",
                        "enum": [
                            "absolute",
                            "normalized",
                            "derived",
                            "sensitivity",
                            "schematic",
                            "unknown",
                        ],
                    },
                    "pk_relevance_score": {"type": "number"},
                    "qsp_relevance_score": {"type": "number"},
                    "panels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "panel_id": {"type": "string"},
                                "x_scale": {
                                    "type": "string",
                                    "enum": [
                                        "linear",
                                        "log10",
                                        "log2",
                                        "ln",
                                        "unknown",
                                    ],
                                },
                                "y_scale": {
                                    "type": "string",
                                    "enum": [
                                        "linear",
                                        "log10",
                                        "log2",
                                        "ln",
                                        "unknown",
                                    ],
                                },
                                "x_axis_label": {"type": "string"},
                                "y_axis_label": {"type": "string"},
                                "x_unit": {"type": "string"},
                                "y_unit": {"type": "string"},
                                "target_variables": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "series_candidates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string"},
                                            "style_hint": {"type": "string"},
                                            "semantic_id_guess": {"type": "string"},
                                            "semantic_name_guess": {"type": "string"},
                                        },
                                        "required": ["label"],
                                    },
                                },
                            },
                            "required": [
                                "panel_id",
                                "x_scale",
                                "y_scale",
                                "x_axis_label",
                                "y_axis_label",
                                "x_unit",
                                "y_unit",
                                "target_variables",
                                "series_candidates",
                            ],
                        },
                    },
                    "target_experiments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "experiment_id": {"type": "string"},
                                "label": {"type": "string"},
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "treatment_regimen",
                                        "population_subgroup",
                                        "species",
                                        "experimental_setting",
                                        "other",
                                    ],
                                },
                                "factors": {"type": "object"},
                                "applies_to_panels": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "notes": {"type": "string"},
                            },
                            "required": ["experiment_id", "label", "kind"],
                        },
                    },
                    "reasoning": {"type": "string"},
                },
                "required": [
                    "asset_type",
                    "figure_label",
                    "is_scientific_plot",
                    "likely_digitizable",
                    "recommended_action",
                    "priority",
                    "data_nature",
                    "pk_relevance_score",
                    "qsp_relevance_score",
                    "panels",
                    "target_experiments",
                    "reasoning",
                ],
            },
        },
    }


def document_annotation_format() -> dict[str, Any]:
    """Return a document-level annotation schema for quick paper triage."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "document_summary_for_triage",
            "schema": {
                "type": "object",
                "properties": {
                    "paper_title": {"type": "string"},
                    "pk_focus": {"type": "boolean"},
                    "qsp_focus": {"type": "boolean"},
                    "plot_panels_mentioned": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "table_ids_mentioned": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "digitization_priority_notes": {"type": "string"},
                },
                "required": [
                    "paper_title",
                    "pk_focus",
                    "qsp_focus",
                    "plot_panels_mentioned",
                    "table_ids_mentioned",
                    "digitization_priority_notes",
                ],
            },
        },
    }


def document_annotation_prompt() -> str:
    """Return a document annotation prompt for QSP modeling workflows."""
    return (
        "Summarize this paper for potential pharmacometric and QSP plot digitization "
        "workflow support. Extract which figures/panels and tables appear to carry "
        "quantitative concentration-time, longitudinal biological data, biomarker dynamics, "
        "or PK/PD parameter information, and highlight likely calibration or validation "
        "sources when building PKPD, PBPK, or QSP models."
    )


def encode_pdf_as_data_url(pdf_path: Path) -> str:
    """Encode a local PDF as a data URL for Mistral OCR."""
    encoded = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    return f"data:application/pdf;base64,{encoded}"


def decode_data_url_payload(data_url: str) -> bytes:
    """Decode a base64 data URL payload."""
    encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
    return base64.b64decode(encoded)


def sanitize_filename(value: str, *, default_name: str) -> str:
    """Return a safe local filename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    if not cleaned:
        cleaned = default_name
    if not Path(cleaned).suffix:
        cleaned = f"{cleaned}.jpg"
    return Path(cleaned).name


def dedupe_filename(filename: str, used_names: set[str]) -> str:
    """Return a unique filename within one output folder."""
    stem = Path(filename).stem or "asset"
    suffix = Path(filename).suffix or ".jpg"
    candidate = f"{stem}{suffix}"
    index = 2
    while candidate in used_names:
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    used_names.add(candidate)
    return candidate


def short_uuid_filename(*, suffix: str = ".jpg") -> str:
    """Return a short random asset filename."""
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{uuid4().hex[:8]}{ext.lower()}"


def rewrite_asset_links(
    markdown_text: str, replacements: dict[str, str], *, folder: str
) -> str:
    """Rewrite markdown links to local output assets."""
    link_re = IMAGE_LINK_RE if folder == "images" else TABLE_LINK_RE

    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        raw_path = match.group(2).strip()
        no_query = raw_path.split("?", 1)[0].strip()
        file_name = Path(no_query).name
        replacement = (
            replacements.get(raw_path)
            or replacements.get(no_query)
            or replacements.get(file_name)
        )
        if replacement is None:
            return match.group(0)
        if folder == "images":
            return f"![{label}]({folder}/{replacement})"
        return f"[{label}]({folder}/{replacement})"

    return link_re.sub(replace, markdown_text)


def append_inline_tables(
    markdown_text: str, table_entries: list[tuple[str, str]]
) -> str:
    """Append extracted table payloads to the page markdown."""
    if not table_entries:
        return markdown_text
    chunks = ["", "### Inline Table Expansions", ""]
    for table_name, table_content in table_entries:
        chunks.extend([f"#### {table_name}", "", table_content.strip(), ""])
    return f"{markdown_text.rstrip()}\n\n" + "\n".join(chunks).rstrip() + "\n"


def submit_pdf_ocr(
    pdf_path: Path,
    *,
    model: str,
    table_format: str,
    include_annotations: bool,
) -> dict[str, Any]:
    """Submit a PDF to Mistral OCR and return the JSON response."""
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is required")

    payload: dict[str, Any] = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": encode_pdf_as_data_url(pdf_path),
        },
        "include_image_base64": True,
        "extract_header": False,
        "extract_footer": False,
        "table_format": table_format,
    }
    if include_annotations:
        payload.update({
            "bbox_annotation_format": bbox_annotation_format(),
            "document_annotation_format": document_annotation_format(),
            "document_annotation_prompt": document_annotation_prompt(),
        })

    response = requests.post(
        MISTRAL_OCR_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=600,
    )
    response.raise_for_status()
    return response.json()


def materialize_response(
    response_payload: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Write markdown, image assets, and table assets from the OCR response."""
    images_dir = output_dir / "images"
    tables_dir = output_dir / "tables"
    images_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    used_image_names: set[str] = set()
    used_table_names: set[str] = set()
    markdown_chunks: list[str] = []
    image_paths: list[Path] = []
    table_paths: list[Path] = []
    table_count = 0

    pages = response_payload.get("pages", [])
    if not isinstance(pages, list):
        pages = []

    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue

        page_markdown = str(page.get("markdown", ""))
        image_replacements: dict[str, str] = {}
        table_replacements: dict[str, str] = {}
        inline_table_entries: list[tuple[str, str]] = []

        images = page.get("images", [])
        if isinstance(images, list):
            for image_index, image_payload in enumerate(images, start=1):
                if not isinstance(image_payload, dict):
                    continue
                original_id = str(image_payload.get("id", "")).strip()
                if not original_id:
                    original_id = f"img-{page_index}-{image_index}.jpg"

                suffix = Path(original_id).suffix or ".jpg"
                filename = dedupe_filename(
                    sanitize_filename(
                        short_uuid_filename(suffix=suffix),
                        default_name=f"img-{page_index}-{image_index}.jpg",
                    ),
                    used_image_names,
                )
                image_path = images_dir / filename
                image_base64 = image_payload.get("image_base64")
                if isinstance(image_base64, str) and image_base64:
                    image_path.write_bytes(decode_data_url_payload(image_base64))
                if image_path.exists():
                    image_paths.append(image_path)

                image_payload["id"] = filename
                image_replacements[original_id] = filename
                image_replacements[Path(original_id).name] = filename

        tables = page.get("tables", [])
        if isinstance(tables, list):
            for table_index, table_payload in enumerate(tables, start=1):
                if not isinstance(table_payload, dict):
                    continue
                table_id = str(table_payload.get("id", "")).strip()
                table_format = (
                    str(table_payload.get("format", "markdown")).strip().lower()
                )
                default_ext = ".html" if table_format == "html" else ".md"
                if not table_id:
                    table_id = f"tbl-{page_index}-{table_index}{default_ext}"

                filename = dedupe_filename(
                    sanitize_filename(
                        table_id,
                        default_name=f"tbl-{page_index}-{table_index}{default_ext}",
                    ),
                    used_table_names,
                )
                table_content = str(table_payload.get("content", "")).strip()
                table_path = tables_dir / filename
                table_path.write_text(
                    f"{table_content}\n" if table_content else "", encoding="utf-8"
                )
                table_paths.append(table_path)
                table_count += 1

                table_replacements[table_id] = filename
                table_replacements[Path(table_id).name] = filename
                if table_content:
                    inline_table_entries.append((filename, table_content))

        if image_replacements:
            page_markdown = rewrite_asset_links(
                page_markdown, image_replacements, folder="images"
            )
        if table_replacements:
            page_markdown = rewrite_asset_links(
                page_markdown, table_replacements, folder="tables"
            )
        if inline_table_entries:
            page_markdown = append_inline_tables(page_markdown, inline_table_entries)
        if page_markdown.strip():
            markdown_chunks.append(page_markdown.strip())

    markdown_text = "\n\n".join(markdown_chunks)
    if markdown_text:
        markdown_text = f"{markdown_text}\n"
    (output_dir / "output.md").write_text(markdown_text, encoding="utf-8")

    return {
        "markdown_text": markdown_text,
        "image_paths": image_paths,
        "table_paths": table_paths,
        "table_count": table_count,
    }


def strip_image_base64(response_payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied OCR response without embedded image payloads."""
    redacted = deepcopy(response_payload)
    pages = redacted.get("pages", [])
    if not isinstance(pages, list):
        return redacted
    for page in pages:
        if not isinstance(page, dict):
            continue
        images = page.get("images", [])
        if not isinstance(images, list):
            continue
        for image_payload in images:
            if isinstance(image_payload, dict):
                image_payload.pop("image_base64", None)
    return redacted


def crop_high_res_images(
    *,
    source_pdf: Path,
    output_dir: Path,
    response_payload: dict[str, Any],
    target_dpi: int,
) -> dict[str, int]:
    """Replace OCR images with high-resolution crops rendered from source pages."""
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    pages = response_payload.get("pages", [])
    if not isinstance(pages, list):
        return {"replaced": 0, "skipped": 0}

    rendered_pages: dict[int, Any] = {}
    replaced = 0
    skipped = 0

    for fallback_page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        page_images = page.get("images", [])
        if not isinstance(page_images, list) or not page_images:
            continue

        page_index = int(page.get("index", fallback_page_index))
        if page_index not in rendered_pages:
            rendered = convert_from_path(
                str(source_pdf),
                dpi=target_dpi,
                first_page=page_index + 1,
                last_page=page_index + 1,
            )
            if not rendered:
                skipped += len(page_images)
                continue
            rendered_pages[page_index] = rendered[0]

        full_page_img = rendered_pages[page_index]
        dimensions = page.get("dimensions", {})
        if not isinstance(dimensions, dict):
            skipped += len(page_images)
            continue
        response_width = float(dimensions.get("width", 0) or 0)
        response_height = float(dimensions.get("height", 0) or 0)
        rendered_width = float(getattr(full_page_img, "width", 0) or 0)
        rendered_height = float(getattr(full_page_img, "height", 0) or 0)
        if not (
            response_width > 0
            and response_height > 0
            and rendered_width > 0
            and rendered_height > 0
        ):
            skipped += len(page_images)
            continue

        scale_x = rendered_width / response_width
        scale_y = rendered_height / response_height

        for image_payload in page_images:
            if not isinstance(image_payload, dict):
                skipped += 1
                continue
            image_id = str(image_payload.get("id", "")).strip()
            if not image_id:
                skipped += 1
                continue

            left_src = float(image_payload.get("top_left_x", 0.0) or 0.0)
            top_src = float(image_payload.get("top_left_y", 0.0) or 0.0)
            right_src = float(image_payload.get("bottom_right_x", 0.0) or 0.0)
            bottom_src = float(image_payload.get("bottom_right_y", 0.0) or 0.0)
            if left_src >= right_src or top_src >= bottom_src:
                skipped += 1
                continue

            left = int(math.floor(left_src * scale_x))
            top = int(math.floor(top_src * scale_y))
            right = int(math.ceil(right_src * scale_x))
            bottom = int(math.ceil(bottom_src * scale_y))

            left = max(0, min(left, full_page_img.width - 1))
            top = max(0, min(top, full_page_img.height - 1))
            right = max(left + 1, min(right, full_page_img.width))
            bottom = max(top + 1, min(bottom, full_page_img.height))

            cropped_img = full_page_img.crop((left, top, right, bottom))
            if cropped_img.mode in ("RGBA", "P"):
                cropped_img = cropped_img.convert("RGB")
            cropped_img.save(
                images_dir / Path(image_id).name, format="JPEG", quality=95
            )
            replaced += 1

    return {"replaced": replaced, "skipped": skipped}


def count_annotated_images(response_payload: dict[str, Any]) -> int:
    """Count image entries with Mistral annotation payloads."""
    pages = response_payload.get("pages", [])
    if not isinstance(pages, list):
        return 0
    count = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        images = page.get("images", [])
        if not isinstance(images, list):
            continue
        for image_payload in images:
            if not isinstance(image_payload, dict):
                continue
            if image_payload.get("image_annotation") not in (None, ""):
                count += 1
    return count


def run_extraction(
    *,
    source_pdf: Path,
    output_dir: Path,
    model: str,
    table_format: str,
    high_res_dpi: int,
    include_annotations: bool,
    disable_high_res: bool,
) -> dict[str, Any]:
    """Run OCR and persist all artifacts."""
    source_pdf = source_pdf.resolve()
    output_dir = output_dir.resolve()
    if not source_pdf.exists():
        raise FileNotFoundError(f"PDF not found: {source_pdf}")
    if source_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source_pdf}")
    if table_format not in {"markdown", "html"}:
        raise ValueError(f"Unsupported table format: {table_format}")
    if high_res_dpi <= 0:
        raise ValueError("--high-res-dpi must be > 0")

    output_dir.mkdir(parents=True, exist_ok=True)
    request_summary = {
        "provider": "mistral",
        "source_pdf": str(source_pdf),
        "model": model,
        "table_format": table_format,
        "include_image_base64": True,
        "annotations_enabled": include_annotations,
        "high_res_enabled": not disable_high_res,
        "high_res_dpi": high_res_dpi,
    }
    (output_dir / "submission.json").write_text(
        json.dumps(request_summary, indent=2), encoding="utf-8"
    )

    response_payload = submit_pdf_ocr(
        source_pdf,
        model=model,
        table_format=table_format,
        include_annotations=include_annotations,
    )
    materialized = materialize_response(response_payload, output_dir)

    high_res_summary = {"replaced": 0, "skipped": 0}
    if not disable_high_res:
        high_res_summary = crop_high_res_images(
            source_pdf=source_pdf,
            output_dir=output_dir,
            response_payload=response_payload,
            target_dpi=high_res_dpi,
        )

    redacted_response = strip_image_base64(response_payload)
    (output_dir / "response.json").write_text(
        json.dumps(redacted_response, indent=2),
        encoding="utf-8",
    )

    pages = response_payload.get("pages", [])
    page_count = len(pages) if isinstance(pages, list) else 0
    image_count = len(materialized["image_paths"])
    table_count = int(materialized["table_count"])
    manifest = {
        "provider": "mistral",
        "source_pdf": str(source_pdf),
        "model": response_payload.get("model", model),
        "page_count": page_count,
        "image_count": image_count,
        "table_count": table_count,
        "annotated_image_count": count_annotated_images(response_payload),
        "high_res_enabled": not disable_high_res,
        "high_res_dpi": high_res_dpi,
        "high_res_replaced_count": high_res_summary["replaced"],
        "high_res_skipped_count": high_res_summary["skipped"],
        "usage_info": response_payload.get("usage_info", {}),
        "artifacts": [
            "submission.json",
            "response.json",
            "output.md",
            "images/",
            "tables/",
            "manifest.json",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return {
        "status": "completed",
        "output_dir": str(output_dir),
        "output_md": str(output_dir / "output.md"),
        "response_json": str(output_dir / "response.json"),
        **manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Run Mistral OCR on one PDF and write self-contained artifacts.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Artifact directory. Defaults to a sibling '<pdf_stem>_mistral_ocr' folder.",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="Mistral OCR model name."
    )
    parser.add_argument(
        "--table-format",
        choices=["markdown", "html"],
        default="markdown",
        help="Table format requested from Mistral.",
    )
    parser.add_argument(
        "--high-res-dpi",
        type=int,
        default=DEFAULT_HIGH_RES_DPI,
        help="DPI for PDF rendering used to replace image crops.",
    )
    parser.add_argument(
        "--disable-annotations",
        action="store_true",
        help="Disable Mistral bbox and document annotation schemas.",
    )
    parser.add_argument(
        "--disable-high-res",
        action="store_true",
        help="Keep provider image crops instead of replacing them from PDF bboxes.",
    )
    return parser


def main() -> int:
    """Run the command-line entrypoint."""
    load_default_env()
    args = build_parser().parse_args()
    output_dir = args.output_dir or args.pdf.with_name(f"{args.pdf.stem}_mistral_ocr")
    summary = run_extraction(
        source_pdf=args.pdf,
        output_dir=output_dir,
        model=args.model,
        table_format=args.table_format,
        high_res_dpi=args.high_res_dpi,
        include_annotations=not args.disable_annotations,
        disable_high_res=args.disable_high_res,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
