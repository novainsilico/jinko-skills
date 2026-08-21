#!/usr/bin/env python3
"""Create or update a Jinko document from markdown and retain the upload payload.

Dry-run by default. Pass --apply to upload files and create or update the document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from check_markdown_structure import HEADING_RE, inspect_markdown, structural_losses
from jinko import JinkoClient

REFERENCE_PLACEHOLDER = "<!-- jinko:references -->"
LOCAL_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
IMAGE_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="New document name (required for creation)")
    parser.add_argument(
        "--document-sid",
        help="Existing Document SID to update instead of creating a document",
    )
    parser.add_argument(
        "--baseline-markdown",
        help="Last approved upload payload (required for updates)",
    )
    parser.add_argument(
        "--append-only-section",
        action="append",
        default=[],
        help="Heading whose existing non-empty content must remain an exact prefix",
    )
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
        help="Optional JSON manifest of existing Reference SIDs or URLs",
    )
    parser.add_argument(
        "--asset-root",
        help=(
            "Optional allowed root for local Markdown images. Paths still resolve "
            "relative to the Markdown file."
        ),
    )
    parser.add_argument(
        "--output-markdown",
        required=True,
        help="New path where the exact transformed upload payload will be retained",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upload local files and create or update the Jinko document",
    )
    parser.add_argument(
        "--confirm-digest",
        metavar="SHA256",
        help="Approval digest shown by the dry run; required with --apply",
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


def bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_record(path: Path) -> dict[str, str | int]:
    content = path.read_bytes()
    return {
        "path": str(path),
        "size": len(content),
        "sha256": bytes_sha256(content),
    }


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
    for entry in entries:
        identities = [
            key
            for key in ("sid", "url")
            if isinstance(entry.get(key), str) and entry[key]
        ]
        if len(identities) != 1:
            raise ValueError(
                "Each reference entry must provide exactly one explicit sid or url; "
                "create PDF References with jinko-reference first"
            )
    return entries


def resolve_reference(
    client: JinkoClient,
    entry: dict[str, Any],
):
    sid = entry.get("sid")
    if isinstance(sid, str) and sid:
        return client.get_reference(sid)

    url = entry.get("url")
    if isinstance(url, str) and url:
        return url
    raise ValueError("Reference entry has no explicit sid or url")


def build_references_block(
    client: JinkoClient,
    manifest_path: Path,
) -> tuple[str, list[str]]:
    entries = load_reference_entries(manifest_path)
    lines = [REFERENCE_PLACEHOLDER, "## References", ""]
    actions: list[str] = []

    for index, entry in enumerate(entries, start=1):
        resolved = resolve_reference(
            client,
            entry,
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
        raise ValueError("Reference entry has no explicit sid or url")

    return actions


def build_approval_manifest(
    args: argparse.Namespace,
    *,
    markdown_path: Path,
    markdown: str,
    asset_root: Path,
    manifest_path: Path | None,
    output_path: Path,
    baseline_path: Path | None,
) -> dict[str, Any]:
    api_key = os.getenv("JINKO_API_KEY")
    images: dict[str, dict[str, Any]] = {}
    for match in LOCAL_IMAGE_RE.finditer(markdown):
        raw_target = match.group(2).strip()
        if is_remote_url(raw_target) or is_special_markdown_target(raw_target):
            continue
        image_path = resolve_image_file(
            raw_target,
            base_dir=markdown_path.parent,
            allowed_root=asset_root,
        )
        images[str(image_path)] = {"target": raw_target, **file_record(image_path)}

    inputs: dict[str, Any] = {
        "markdown": file_record(markdown_path),
        "images": sorted(images.values(), key=lambda item: str(item["path"])),
    }
    if manifest_path:
        entries = load_reference_entries(manifest_path)
        inputs["reference_manifest"] = {
            **file_record(manifest_path),
            "identities": [
                {key: entry[key] for key in ("sid", "url") if entry.get(key)}
                for entry in entries
            ],
        }
    if baseline_path:
        inputs["baseline_markdown"] = file_record(baseline_path)

    return {
        "schema": "jinko-document-approval-v1",
        "arguments": {
            "operation": "update" if args.document_sid else "create",
            "document_sid": args.document_sid,
            "append_only_sections": args.append_only_section,
            "name": args.name,
            "folder": args.folder,
            "description": args.description,
            "version": build_version_payload(args),
            "asset_root": str(asset_root),
            "output_markdown": str(output_path),
            "jinko_destination": {
                "project_id": os.getenv("JINKO_PROJECT_ID"),
                "base_url": os.getenv("JINKO_BASE_URL", "https://api.jinko.ai"),
                "app_url": os.getenv("JINKO_URL"),
                "api_key_sha256": (
                    bytes_sha256(api_key.encode("utf-8")) if api_key else None
                ),
            },
        },
        "inputs": inputs,
    }


def approval_digest(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        manifest,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return bytes_sha256(canonical)


def inject_references(markdown: str, references_block: str) -> str:
    lines = markdown.splitlines()
    marker_indexes = [
        index
        for index, line in enumerate(lines)
        if line.strip() == REFERENCE_PLACEHOLDER
    ]
    if len(marker_indexes) > 1:
        raise ValueError("Markdown contains more than one Jinko references marker")
    if marker_indexes:
        start = marker_indexes[0]
        end = start + 1
        heading_index = end
        while heading_index < len(lines) and not lines[heading_index].strip():
            heading_index += 1
        heading = (
            HEADING_RE.match(lines[heading_index])
            if heading_index < len(lines)
            else None
        )
        if (
            heading
            and len(heading.group(1)) == 2
            and heading.group(2).strip().casefold() == "references"
        ):
            end = heading_index + 1
            while end < len(lines):
                next_heading = HEADING_RE.match(lines[end])
                if next_heading and len(next_heading.group(1)) <= 2:
                    break
                end += 1
        replaced = [*lines[:start], *references_block.splitlines(), *lines[end:]]
        return "\n".join(replaced).rstrip() + "\n"
    stripped = markdown.rstrip()
    return f"{stripped}\n\n{references_block}\n"


def main() -> None:
    args = parse_args()
    if args.document_sid:
        if not args.baseline_markdown:
            raise ValueError("Document updates require --baseline-markdown")
        unsupported = [
            flag
            for flag, value in (
                ("--name", args.name),
                ("--folder", args.folder),
                ("--description", args.description),
                ("--version-name", args.version_name),
                ("--version-description", args.version_description),
            )
            if value
        ]
        if unsupported:
            raise ValueError(
                "Document updates do not accept creation metadata: "
                + ", ".join(unsupported)
            )
    elif not args.name:
        raise ValueError("Document creation requires --name")
    elif args.baseline_markdown or args.append_only_section:
        raise ValueError(
            "--baseline-markdown and --append-only-section apply only to updates"
        )
    markdown_path = Path(args.markdown_file).resolve()
    markdown_dir = markdown_path.parent
    markdown = markdown_path.read_text(encoding="utf-8")
    asset_root = resolve_allowed_root(
        args.asset_root,
        default=markdown_dir,
        label="Asset root",
    )

    manifest_path = (
        Path(args.reference_manifest).resolve() if args.reference_manifest else None
    )
    baseline_path = (
        Path(args.baseline_markdown).resolve() if args.baseline_markdown else None
    )
    if baseline_path:
        baseline_structure = inspect_markdown(
            baseline_path, ignore_generated_references=manifest_path is not None
        )
        candidate_structure = inspect_markdown(
            markdown_path, ignore_generated_references=manifest_path is not None
        )
        losses = structural_losses(
            baseline_structure,
            candidate_structure,
            args.append_only_section,
        )
        if losses:
            raise ValueError("Structural losses detected: " + "; ".join(losses))
    output_path = Path(args.output_markdown).resolve()
    if not output_path.parent.is_dir():
        raise NotADirectoryError(
            f"Output Markdown parent directory does not exist: {output_path.parent}"
        )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite output Markdown: {output_path}")
    dry_run_actions = build_dry_run_actions(
        markdown,
        markdown_dir=markdown_dir,
        asset_root=asset_root,
        manifest_path=manifest_path,
    )
    approval_manifest = build_approval_manifest(
        args,
        markdown_path=markdown_path,
        markdown=markdown,
        asset_root=asset_root,
        manifest_path=manifest_path,
        output_path=output_path,
        baseline_path=baseline_path,
    )
    digest = approval_digest(approval_manifest)
    if not args.apply:
        print("Dry run: no Jinko API calls will be made.")
        if args.document_sid:
            print(f"Would update document: {args.document_sid}")
        else:
            print(f"Would create document: {args.name}")
        print(f"Markdown source: {markdown_path}")
        if not args.document_sid:
            print(f"Destination folder: {args.folder or 'project root'}")
        print(f"Final payload output: {output_path}")
        print(f"Allowed image root: {asset_root}")
        for action in dry_run_actions:
            print(action)
        print(
            "Approval manifest: "
            + json.dumps(approval_manifest, ensure_ascii=True, sort_keys=True)
        )
        print(f"Approval digest: {digest}")
        print(
            "After approving these exact inputs and arguments, run again with "
            f"--apply --confirm-digest {digest}."
        )
        return

    if not args.confirm_digest:
        raise ValueError("--apply requires --confirm-digest from a dry run")
    if args.confirm_digest.lower() != digest:
        raise ValueError(
            "Inputs or arguments do not match the approved digest; run a dry run "
            "and approve the current manifest."
        )
    if not os.getenv("JINKO_API_KEY") or not os.getenv("JINKO_PROJECT_ID"):
        raise ValueError(
            "--apply requires JINKO_API_KEY and JINKO_PROJECT_ID in the approved environment"
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
        references_block, reference_actions = build_references_block(
            client,
            manifest_path,
        )
        markdown = inject_references(markdown, references_block)

    with output_path.open("x", encoding="utf-8") as output_file:
        output_file.write(markdown)
    payload_digest = bytes_sha256(markdown.encode("utf-8"))

    if args.document_sid:
        document = client.get_document(args.document_sid)
        document.update_markdown(markdown)
    else:
        document = client.create_document_from_markdown(
            markdown_content=markdown,
            name=args.name,
            folder=args.folder,
            description=args.description,
            version=build_version_payload(args),
        )

    print(f"Resource SID: {document.sid}")
    print(f"Resource link: {document.url}")
    print(f"Retained upload payload: {output_path}")
    print(f"Upload payload SHA-256: {payload_digest}")
    for source_path, image_url in image_replacements:
        print(f"Uploaded image: {source_path} -> {image_url}")
    for action in reference_actions:
        print(f"Reference: {action}")


if __name__ == "__main__":
    main()
