#!/usr/bin/env python3
"""Create a Jinko document from markdown, with optional image and reference prep."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jinko import JinkoClient

REFERENCE_PLACEHOLDER = "<!-- jinko:references -->"
LOCAL_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Document name")
    parser.add_argument(
        "--markdown-file",
        required=True,
        help="Path to the markdown file to upload",
    )
    parser.add_argument(
        "--folder",
        "--parent-folder-id",
        dest="folder",
        help="Optional destination Jinko folder id",
    )
    parser.add_argument(
        "--description",
        help="Optional document description",
    )
    parser.add_argument(
        "--version-name",
        help="Optional version name",
    )
    parser.add_argument(
        "--version-description",
        help="Optional version description",
    )
    parser.add_argument(
        "--reference-manifest",
        help="Optional JSON manifest describing references to create or reuse",
    )
    return parser.parse_args()


def build_version_payload(args: argparse.Namespace) -> str | dict[str, str] | None:
    if args.version_name and args.version_description:
        return {
            "name": args.version_name,
            "description": args.version_description,
        }
    if args.version_name:
        return args.version_name
    return None


def is_remote_url(target: str) -> bool:
    return target.startswith(("http://", "https://"))


def is_special_markdown_target(target: str) -> bool:
    return target.startswith(("data:", "#"))


def upload_local_images(
    client: JinkoClient,
    markdown: str,
    *,
    markdown_dir: Path,
) -> tuple[str, list[tuple[str, str]]]:
    uploaded: dict[str, str] = {}
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        raw_target = match.group(2).strip()

        if is_remote_url(raw_target) or is_special_markdown_target(raw_target):
            return match.group(0)

        if raw_target not in uploaded:
            image_path = (markdown_dir / raw_target).resolve()
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"Referenced image does not exist: {raw_target} -> {image_path}"
                )
            image = client.upload_image(image_file_path=image_path)
            uploaded[raw_target] = image.url
            replacements.append((raw_target, image.url))

        return f"![{alt_text}]({uploaded[raw_target]})"

    rewritten = LOCAL_IMAGE_RE.sub(replace, markdown)
    return rewritten, replacements


def load_reference_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("references"), list):
        entries = payload["references"]
    else:
        raise ValueError(
            "Reference manifest must be a list or an object with a 'references' list"
        )

    if not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("Each reference manifest entry must be an object")
    return entries


def resolve_reference(
    client: JinkoClient,
    entry: dict[str, Any],
    *,
    base_dir: Path,
    folder: str | None,
):
    sid = entry.get("sid")
    if isinstance(sid, str) and sid:
        return client.get_reference(sid)

    url = entry.get("url")
    if isinstance(url, str) and url:
        return url

    pdf_path_value = entry.get("pdf_path")
    if not isinstance(pdf_path_value, str) or not pdf_path_value:
        raise ValueError("Reference entries must provide one of: sid, url, or pdf_path")

    pdf_path = (base_dir / pdf_path_value).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Reference PDF does not exist: {pdf_path_value} -> {pdf_path}"
        )

    item_name = entry.get("title") or pdf_path.stem
    candidates = client.list_references(name=item_name, folder=folder, limit=10)
    exact_matches = [item for item in candidates if item.name == item_name]
    if exact_matches:
        exact_matches.sort(key=lambda item: item.updated_at, reverse=True)
        return exact_matches[0]

    return client.create_reference_from_pdf(
        pdf_file_path=pdf_path,
        name=item_name,
        folder=folder,
    )


def build_references_block(
    client: JinkoClient,
    manifest_path: Path,
    *,
    folder: str | None,
) -> tuple[str, list[str]]:
    entries = load_reference_entries(manifest_path)
    lines = ["## References", ""]
    actions: list[str] = []

    for index, entry in enumerate(entries, start=1):
        resolved = resolve_reference(
            client,
            entry,
            base_dir=manifest_path.parent,
            folder=folder,
        )
        citation = entry.get("citation") or f"[{index}]"
        title = entry.get("title")

        if isinstance(resolved, str):
            link_url = resolved
            link_title = title or citation
            actions.append(f"{citation} -> reused URL {link_url}")
        else:
            link_url = resolved.url
            link_title = title or resolved.name
            actions.append(f"{citation} -> {resolved.sid}")

        lines.append(f"- {citation} [{link_title}]({link_url})")

    lines.append("")
    return "\n".join(lines), actions


def inject_references(markdown: str, references_block: str) -> str:
    if REFERENCE_PLACEHOLDER in markdown:
        return markdown.replace(REFERENCE_PLACEHOLDER, references_block)
    stripped = markdown.rstrip()
    return f"{stripped}\n\n{references_block}\n"


def main() -> None:
    args = parse_args()
    markdown_path = Path(args.markdown_file).resolve()
    markdown_dir = markdown_path.parent

    client = JinkoClient()
    markdown = markdown_path.read_text(encoding="utf-8")

    markdown, image_replacements = upload_local_images(
        client,
        markdown,
        markdown_dir=markdown_dir,
    )

    reference_actions: list[str] = []
    if args.reference_manifest:
        references_block, reference_actions = build_references_block(
            client,
            Path(args.reference_manifest).resolve(),
            folder=args.folder,
        )
        markdown = inject_references(markdown, references_block)

    document = client.create_document_from_markdown(
        markdown,
        name=args.name,
        folder=args.folder,
        description=args.description,
        version=build_version_payload(args),
    )

    print(f"Resource SID: {document.sid}")
    print(f"Resource link: {document.url}")
    for source_path, image_url in image_replacements:
        print(f"Uploaded image: {source_path} -> {image_url}")
    for action in reference_actions:
        print(f"Reference: {action}")


if __name__ == "__main__":
    main()
