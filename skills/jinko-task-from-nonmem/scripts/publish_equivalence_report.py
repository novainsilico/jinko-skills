#!/usr/bin/env python3
"""Publish an equivalence report into Jinkō as a document.

A report that lives only on someone's laptop cannot be reviewed by the team who
will rely on the converted model. This uploads it as a Jinkō document, with the
plots uploaded as images and the converted project items embedded as cards, so
the evidence sits next to the thing it is evidence about.

Local image references in the markdown are rewritten to their uploaded Jinkō
URLs. Anything already an https URL is left alone.

Dry-run by default. Pass --apply to create the document.

The renderer accommodations -- what happens to a table's header row, and why
the item list is cards rather than a table -- live in
``nonmem2jinko.platform.documents``, next to the tests that pin them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from nonmem2jinko import platform
from nonmem2jinko.platform.documents import (
    LINKED_ITEMS,
    build_body,
    find_local_images,
    tables_for_jinko,
    title_of,
)

# Re-exported for the tests, which pin both renderer defects against this
# script by name.
__all__ = ["build_body", "tables_for_jinko", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish an equivalence report into Jinkō as a document."
    )
    parser.add_argument("report", help="Path to the Markdown report.")
    parser.add_argument(
        "--comparison",
        required=True,
        help="Comparison JSON used to render the report.",
    )
    parser.add_argument("--name", help="Document name. Defaults to the report title.")
    parser.add_argument("--model", help="Computational model SID to link.")
    parser.add_argument("--vpop", help="Vpop SID to link.")
    parser.add_argument("--protocol", help="Protocol design SID to link.")
    parser.add_argument("--trial", help="Trial SID to link.")
    parser.add_argument(
        "--trial-visualization",
        dest="trial_visualization",
        help="Trial visualization SID to link.",
    )
    parser.add_argument(
        "--data-table", dest="data_table", help="Data table SID to link."
    )
    parser.add_argument("--folder", help="Existing folder id or exact folder name.")
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument(
        "--parent-folder",
        help=(
            "Folder to nest --folder inside, created alongside it. Used to "
            "keep one run's items together: a dated run folder holding one "
            "subfolder per model."
        ),
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Do not upload images; leave their references as written.",
    )
    parser.add_argument("--out", help="Write the assembled markdown here as well.")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace --out if it exists."
    )
    parser.add_argument(
        "--json-out",
        help="Write the created document's SID and URL here as JSON.",
    )
    parser.add_argument(
        "--approve-digest",
        help=(
            "Digest printed by the dry run. Apply is refused unless it matches "
            "the report, local images, name, and linked item SIDs."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Create the document.")
    return parser


def approval_digest(
    markdown: str,
    images: list[tuple[str, Path]],
    *,
    name: str,
    sids: dict[str, object],
) -> str:
    digest = hashlib.sha256()
    digest.update(markdown.encode())
    digest.update(name.encode())
    digest.update(json.dumps(sids, sort_keys=True).encode())
    for target, path in images:
        digest.update(target.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    args = build_parser().parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 1
    outputs = [Path(path) for path in (args.out, args.json_out) if path]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.overwrite:
        print(
            "refusing to overwrite: "
            + ", ".join(str(path) for path in existing)
            + "\nPass --overwrite to replace them.",
            file=sys.stderr,
        )
        return 1
    markdown = report_path.read_text()
    comparison_path = Path(args.comparison)
    try:
        comparison_bytes = comparison_path.read_bytes()
        metrics = json.loads(comparison_bytes)
        if not isinstance(metrics, dict):
            raise ValueError("comparison JSON must be an object")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"cannot read comparison evidence: {error}", file=sys.stderr)
        return 1
    evidence_problems = platform.documents.evidence_errors(metrics)
    if evidence_problems:
        print("comparison evidence does not support publication:", file=sys.stderr)
        for problem in evidence_problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    try:
        images = (
            [] if args.skip_images else find_local_images(markdown, report_path.parent)
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    missing = [str(path) for _, path in images if not path.exists()]
    if missing:
        print("image referenced but not found:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    name = args.name or title_of(markdown, report_path.stem)

    print(f"report  {report_path}  ({len(markdown):,} characters)")
    print(f"metrics {comparison_path}")
    print(f"name    {name}")
    print(f"images  {len(images)}")
    for target, path in images:
        print(f"        {target}  ({path.stat().st_size:,} bytes)")

    sids = {
        attribute: getattr(args, attribute, None) for attribute, _, _ in LINKED_ITEMS
    }
    linked = [attribute for attribute, sid in sids.items() if sid]
    print(
        "links   "
        + (
            ", ".join(f"{attribute}={sids[attribute]}" for attribute in linked)
            if linked
            else "none supplied"
        )
    )
    approval_context = {
        **sids,
        "folder": args.folder,
        "parent_folder": args.parent_folder,
        "create_folder": args.create_folder,
        "comparison_sha256": hashlib.sha256(comparison_bytes).hexdigest(),
    }
    digest = approval_digest(markdown, images, name=name, sids=approval_context)
    print(f"digest  {digest}")

    if not args.apply:
        print(
            f"\nRun again with --apply --approve-digest {digest} to create the document."
        )
        return 0
    if args.approve_digest != digest:
        print(
            "refusing to publish: --approve-digest does not match this report, "
            "its images, and linked items. Run the dry run again.",
            file=sys.stderr,
        )
        return 1
    if approval_digest(markdown, images, name=name, sids=approval_context) != digest:
        print("report inputs changed after approval validation", file=sys.stderr)
        return 1

    client = platform.try_client_from_env()
    if client is None:
        return 1
    items = platform.documents.resolve_items(client, sids)
    if len(items) != len(linked) or any(item is None for _, item in items):
        print(
            "refusing to publish: one or more supplied linked-item SIDs did not resolve",
            file=sys.stderr,
        )
        return 1
    folder = platform.nested_folder(
        client, args.parent_folder, args.folder, create=args.create_folder
    )
    print()
    document, body = platform.documents.publish(
        client,
        markdown,
        name=name,
        folder=folder,
        items=items,
        images=images,
    )

    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {"document": {"sid": document.sid, "url": document.url, "name": name}},
                indent=2,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
