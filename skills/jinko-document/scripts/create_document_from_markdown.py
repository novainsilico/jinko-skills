#!/usr/bin/env python3
"""Create a Jinko document from markdown, with optional image and reference prep.

Dry-run by default. Pass --apply to upload files and create the document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jinko import JinkoClient

REFERENCE_PLACEHOLDER = "<!-- jinko:references -->"
LOCAL_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
IMAGE_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"})


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
    parser.add_argument(
        "--asset-root",
        help=(
            "Optional allowed root for local Markdown images. Paths still resolve "
            "relative to the Markdown file."
        ),
    )
    parser.add_argument(
        "--reference-root",
        help=(
            "Optional allowed root for manifest PDF paths. Paths still resolve "
            "relative to the manifest."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upload local files and create the Jinko document",
    )
    parser.add_argument(
        "--confirm-sha256",
        metavar="SHA256",
        help="SHA-256 shown by the dry run; required with --apply",
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


def markdown_sha256(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def is_remote_url(target: str) -> bool:
    return target.startswith(("http://", "https://"))


def is_special_markdown_target(target: str) -> bool:
    return target.startswith(("data:", "#"))


def resolve_local_file(
    raw_path: str,
    *,
    base_dir: Path,
    allowed_root: Path | None = None,
    label: str,
) -> Path:
    """Resolve a local upload path without allowing it to escape its input directory."""
    resolved_root = (allowed_root or base_dir).resolve()
    # Resolve before checking containment so ../ paths and symlink escapes are rejected.
    resolved_path = (base_dir / raw_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(
            f"Referenced {label} is outside its allowed directory: "
            f"{raw_path} -> {resolved_path} (allowed: {resolved_root})"
        ) from error

    if not resolved_path.is_file():
        raise FileNotFoundError(
            f"Referenced {label} does not exist: {raw_path} -> {resolved_path}"
        )
    return resolved_path


def resolve_allowed_root(raw_path: str | None, *, default: Path, label: str) -> Path:
    """Resolve and validate an explicitly authorized local upload root."""
    root = Path(raw_path).resolve() if raw_path else default.resolve()
    if not root.is_dir():
        raise NotADirectoryError(
            f"{label} does not exist or is not a directory: {root}"
        )
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise ValueError(
            f"{label} must be narrower than a filesystem or home directory"
        )
    return root


def validate_image_file(path: Path) -> None:
    """Require a supported image extension and matching file signature."""
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        accepted = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(
            f"Unsupported local image type for {path}; accepted extensions: {accepted}"
        )

    with path.open("rb") as image_file:
        header = image_file.read(4096)
    valid = {
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": (
            len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        ),
        ".svg": b"<svg" in header.lstrip(b"\xef\xbb\xbf \t\r\n").lower(),
    }[suffix]
    if not valid:
        raise ValueError(f"Local image content does not match its extension: {path}")


def validate_pdf_file(path: Path) -> None:
    """Require a .pdf extension and PDF header before upload."""
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Reference file must use the .pdf extension: {path}")
    with path.open("rb") as pdf_file:
        header = pdf_file.read(5)
    if header != b"%PDF-":
        raise ValueError(f"Reference file does not start with a PDF header: {path}")


def resolve_image_file(
    raw_path: str,
    *,
    base_dir: Path,
    allowed_root: Path,
) -> Path:
    path = resolve_local_file(
        raw_path,
        base_dir=base_dir,
        allowed_root=allowed_root,
        label="image",
    )
    validate_image_file(path)
    return path


def resolve_pdf_file(
    raw_path: str,
    *,
    base_dir: Path,
    allowed_root: Path,
) -> Path:
    path = resolve_local_file(
        raw_path,
        base_dir=base_dir,
        allowed_root=allowed_root,
        label="PDF",
    )
    validate_pdf_file(path)
    return path


def upload_local_images(
    client: JinkoClient,
    markdown: str,
    *,
    markdown_dir: Path,
    asset_root: Path,
) -> tuple[str, list[tuple[str, str]]]:
    uploaded: dict[str, str] = {}
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        raw_target = match.group(2).strip()

        if is_remote_url(raw_target) or is_special_markdown_target(raw_target):
            return match.group(0)

        if raw_target not in uploaded:
            image_path = resolve_image_file(
                raw_target,
                base_dir=markdown_dir,
                allowed_root=asset_root,
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
    reference_root: Path,
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

    pdf_path = resolve_pdf_file(
        pdf_path_value,
        base_dir=base_dir,
        allowed_root=reference_root,
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
    reference_root: Path,
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
            reference_root=reference_root,
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


def build_dry_run_actions(
    markdown: str,
    *,
    markdown_dir: Path,
    asset_root: Path,
    manifest_path: Path | None,
    reference_root: Path | None,
) -> list[str]:
    actions: list[str] = []
    uploaded_images: set[str] = set()

    for match in LOCAL_IMAGE_RE.finditer(markdown):
        raw_target = match.group(2).strip()
        if (
            raw_target in uploaded_images
            or is_remote_url(raw_target)
            or is_special_markdown_target(raw_target)
        ):
            continue
        image_path = resolve_image_file(
            raw_target,
            base_dir=markdown_dir,
            allowed_root=asset_root,
        )
        uploaded_images.add(raw_target)
        actions.append(f"Would upload image: {image_path}")

    if manifest_path is None:
        return actions
    if reference_root is None:
        raise ValueError("reference_root is required with a reference manifest")

    for index, entry in enumerate(load_reference_entries(manifest_path), start=1):
        citation = entry.get("citation") or f"[{index}]"
        sid = entry.get("sid")
        if isinstance(sid, str) and sid:
            actions.append(f"Would reuse reference: {citation} -> {sid}")
            continue

        url = entry.get("url")
        if isinstance(url, str) and url:
            actions.append(f"Would reuse URL: {citation} -> {url}")
            continue

        pdf_path_value = entry.get("pdf_path")
        if not isinstance(pdf_path_value, str) or not pdf_path_value:
            raise ValueError(
                "Reference entries must provide one of: sid, url, or pdf_path"
            )
        pdf_path = resolve_pdf_file(
            pdf_path_value,
            base_dir=manifest_path.parent,
            allowed_root=reference_root,
        )
        actions.append(f"Would create or reuse reference: {citation} -> {pdf_path}")

    return actions


def inject_references(markdown: str, references_block: str) -> str:
    if REFERENCE_PLACEHOLDER in markdown:
        return markdown.replace(REFERENCE_PLACEHOLDER, references_block)
    stripped = markdown.rstrip()
    return f"{stripped}\n\n{references_block}\n"


def main() -> None:
    args = parse_args()
    markdown_path = Path(args.markdown_file).resolve()
    markdown_dir = markdown_path.parent
    markdown = markdown_path.read_text(encoding="utf-8")
    markdown_digest = markdown_sha256(markdown)
    asset_root = resolve_allowed_root(
        args.asset_root,
        default=markdown_dir,
        label="Asset root",
    )

    manifest_path = (
        Path(args.reference_manifest).resolve() if args.reference_manifest else None
    )
    if args.reference_root and manifest_path is None:
        raise ValueError("--reference-root requires --reference-manifest")
    reference_root = (
        resolve_allowed_root(
            args.reference_root,
            default=manifest_path.parent,
            label="Reference root",
        )
        if manifest_path
        else None
    )
    dry_run_actions = build_dry_run_actions(
        markdown,
        markdown_dir=markdown_dir,
        asset_root=asset_root,
        manifest_path=manifest_path,
        reference_root=reference_root,
    )
    if not args.apply:
        print("Dry run: no Jinko API calls will be made.")
        print(f"Would create document: {args.name}")
        print(f"Markdown source: {markdown_path}")
        print(f"Markdown SHA-256: {markdown_digest}")
        print(f"Destination folder: {args.folder or 'project root'}")
        print(f"Allowed image root: {asset_root}")
        if reference_root:
            print(f"Allowed reference root: {reference_root}")
        for action in dry_run_actions:
            print(action)
        print(
            "After approving this exact source and destination, run again with "
            f"--apply --confirm-sha256 {markdown_digest}."
        )
        return

    if not args.confirm_sha256:
        raise ValueError("--apply requires --confirm-sha256 from a dry run")
    if args.confirm_sha256.lower() != markdown_digest:
        raise ValueError(
            "Markdown does not match the approved SHA-256; run a dry run and "
            "approve the current source."
        )

    client = JinkoClient()

    markdown, image_replacements = upload_local_images(
        client,
        markdown,
        markdown_dir=markdown_dir,
        asset_root=asset_root,
    )

    reference_actions: list[str] = []
    if manifest_path:
        if reference_root is None:
            raise ValueError("reference_root is required with a reference manifest")
        references_block, reference_actions = build_references_block(
            client,
            manifest_path,
            reference_root=reference_root,
            folder=args.folder,
        )
        markdown = inject_references(markdown, references_block)

    document = client.create_document_from_markdown(
        markdown_content=markdown,
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
