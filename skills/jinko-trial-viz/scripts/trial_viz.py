#!/usr/bin/env python3
"""Create, update, inspect, and sanity-check Jinkō TrialVisualizations.

Uses the SDK's typed TrialVisualization API: create_empty_trial_visualization
plus the `timeseries`/`scalars`/`scatter_plots`/`survival_analysis`/
`contribution_analysis`/`data_overlay` subservices and `.sanity`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

OVERLAY_LABEL_RE = re.compile(r"^[A-Za-z0-9_:-]+$")

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None


def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def load_sdk():
    try:
        from jinko import JinkoClient
        from jinko.exceptions import JinkoError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def write_json(payload: Any, *, output_file: str | None = None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if output_file:
        Path(output_file).write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {output_file}")
    else:
        print(text)


def resolve_folder(client: Any, folder_ref: str | None) -> Any | None:
    if folder_ref is None:
        return None
    folder = client.get_folder(folder_ref)
    if folder is not None:
        return folder
    folder = client.get_folder_by_name(folder_ref, exact_match_only=True)
    if folder is None:
        raise ValueError(f"Folder {folder_ref!r} was not found.")
    return folder


def parse_scatter_xvsy(spec: str) -> dict[str, Any]:
    # "x_id,y_id,arm1,arm2,..."
    parts = [part.strip() for part in spec.split(",") if part.strip()]
    if len(parts) < 3:
        raise ValueError(
            f"--scatter-xvsy must be 'x_id,y_id,arm1[,arm2,...]', got {spec!r}"
        )
    x_id, y_id, *arms = parts
    return {"x": x_id, "y": y_id, "arms": arms}


def parse_scatter_xvsx(spec: str) -> dict[str, Any]:
    # "variable,reference_arm,compare_arm1,compare_arm2,..."
    parts = [part.strip() for part in spec.split(",") if part.strip()]
    if len(parts) < 3:
        raise ValueError(
            "--scatter-xvsx must be 'variable,reference_arm,compare_arm1[,compare_arm2,...]', "
            f"got {spec!r}"
        )
    variable, reference_arm, *compare_arms = parts
    return {
        "variable": variable,
        "reference_arm": reference_arm,
        "compare_arms": compare_arms,
    }


def prepare_local_sections(args: argparse.Namespace) -> dict[str, list[Any]]:
    overlay_label = getattr(args, "data_overlay_label", None)
    if overlay_label is not None and not OVERLAY_LABEL_RE.fullmatch(overlay_label):
        raise ValueError(
            "Data overlay label must contain only letters, digits, dash '-', "
            "underscore '_', or colon ':'."
        )
    return {
        "scatter_xvsy": [
            parse_scatter_xvsy(spec)
            for spec in getattr(args, "scatter_xvsy", None) or []
        ],
        "scatter_xvsx": [
            parse_scatter_xvsx(spec)
            for spec in getattr(args, "scatter_xvsx", None) or []
        ],
    }


def prepare_sections(client: Any, args: argparse.Namespace) -> dict[str, list[Any]]:
    prepared = prepare_local_sections(args)
    prepared["data_overlay_tables"] = [
        client.get_data_table(table_sid)
        for table_sid in getattr(args, "data_overlay_table_sid", None) or []
    ]
    return prepared


def apply_sections(
    viz: Any,
    args: argparse.Namespace,
    prepared: dict[str, list[Any]],
) -> Any:
    applied: list[str] = []
    try:
        if getattr(args, "selected_arm", None):
            viz = viz.set_selected_arms(args.selected_arm)
            applied.append("selected-arms")
        if getattr(args, "equate_baseline", False):
            viz = viz.set_equate_baseline(True)
            applied.append("equate-baseline")
        if getattr(args, "timeseries", None):
            viz = viz.timeseries.set_selectors(args.timeseries)
            applied.append("timeseries")
        if getattr(args, "scalar", None):
            viz = viz.scalars.set_selectors(args.scalar)
            applied.append("scalars")
        if getattr(args, "survival", None):
            viz = viz.survival_analysis.set_selectors(args.survival)
            applied.append("survival-analysis")
        if getattr(args, "contribution", None):
            viz = viz.contribution_analysis.set_selectors(args.contribution)
            applied.append("contribution-analysis")
        for plot in prepared["scatter_xvsy"]:
            viz = viz.scatter_plots.add_x_vs_y_plot(
                plot["x"], plot["y"], arms=plot["arms"]
            )
            applied.append("scatter-x-vs-y")
        for plot in prepared["scatter_xvsx"]:
            viz = viz.scatter_plots.add_x_vs_x_plot(
                plot["variable"],
                reference_arm=plot["reference_arm"],
                compare_arms=plot["compare_arms"],
            )
            applied.append("scatter-x-vs-x")
        for table in prepared["data_overlay_tables"]:
            viz = viz.data_overlay.add_table(
                table, label=getattr(args, "data_overlay_label", None)
            )
            applied.append(f"data-overlay:{table.sid}")
    except Exception:
        print(
            f"Trial visualization {viz.sid} may be partially configured; "
            f"completed sections: {', '.join(applied) or '<none>'}.",
            file=sys.stderr,
        )
        raise
    return viz


def print_mutation_plan(action: str, target: str, args: argparse.Namespace) -> None:
    sections = []
    for argument in (
        "selected_arm",
        "timeseries",
        "scalar",
        "survival",
        "contribution",
        "scatter_xvsy",
        "scatter_xvsx",
        "data_overlay_table_sid",
    ):
        if getattr(args, argument, None):
            sections.append(argument.replace("_", "-"))
    if getattr(args, "equate_baseline", False):
        sections.append("equate-baseline")
    print(f"Would {action} trial visualization {target}.")
    print(f"Sections/options: {', '.join(sections) or '<none>'}")
    print("Run again with --apply to mutate the project item.")


def print_sanity(viz: Any) -> int:
    diagnostics = viz.sanity
    print("Trial visualization diagnostics:")
    print(str(diagnostics))
    return 1 if diagnostics.has_errors() else 0


def command_list(client: Any, args: argparse.Namespace) -> int:
    page = client.list_trial_visualizations(name=args.name, limit=args.limit)
    items = [
        {
            "sid": item.sid,
            "name": item.name,
            "coreItemId": item.core_id,
            "snapshotId": item.snapshot_id,
            "url": item.url,
        }
        for item in page.items
    ]
    write_json(items, output_file=args.output_file)
    return 0


def command_get(client: Any, args: argparse.Namespace) -> int:
    viz = client.get_trial_visualization(args.trial_viz_sid)
    content = viz.content(revision=args.revision)
    write_json(
        content.model_dump(mode="json", by_alias=True, exclude_none=True),
        output_file=args.output_file,
    )
    return 0


def command_create(client: Any, args: argparse.Namespace) -> int:
    if not args.apply:
        prepare_local_sections(args)
        print_mutation_plan("create", repr(args.name or "<unnamed>"), args)
        return 0
    prepared = prepare_sections(client, args)
    trial = client.get_trial(args.trial_sid)
    folder = resolve_folder(client, args.folder)
    viz = trial.create_empty_trial_visualization(
        folder=folder,
        name=args.name,
        description=args.description,
        version=args.version,
    )
    try:
        viz = apply_sections(viz, args, prepared)
    except Exception:
        print(
            f"Created trial visualization {viz.sid} before configuration failed.",
            file=sys.stderr,
        )
        raise
    print(f"Created trial visualization {viz.sid}")
    if getattr(viz, "url", None):
        print(viz.url)
    return print_sanity(viz)


def command_update(client: Any, args: argparse.Namespace) -> int:
    if not args.apply:
        prepare_local_sections(args)
        print_mutation_plan("update", args.trial_viz_sid, args)
        return 0
    prepared = prepare_sections(client, args)
    viz = client.get_trial_visualization(args.trial_viz_sid)
    viz = apply_sections(viz, args, prepared)
    print(f"Updated trial visualization {viz.sid}")
    return print_sanity(viz)


def command_sanity(client: Any, args: argparse.Namespace) -> int:
    viz = client.get_trial_visualization(args.trial_viz_sid)
    view = viz.sanity_at(args.revision, only=args.only) if args.revision else viz.sanity
    if args.only and not args.revision:
        view = view.for_field(*args.only)
    print(str(view))
    return 1 if view.has_errors() else 0


def add_section_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--selected-arm",
        action="append",
        default=[],
        help="Arm id to include in selectedArms. Repeat for multiple arms.",
    )
    parser.add_argument(
        "--equate-baseline", action="store_true", help="Set equateBaseline to true."
    )
    parser.add_argument(
        "--timeseries",
        action="append",
        default=[],
        help="Time-series selector id. Repeat for multiple selectors.",
    )
    parser.add_argument(
        "--scalar",
        action="append",
        default=[],
        help="Scalar selector id. Repeat for multiple selectors.",
    )
    parser.add_argument(
        "--survival",
        action="append",
        default=[],
        help="Survival-analysis selector id. Repeat for multiple selectors.",
    )
    parser.add_argument(
        "--contribution",
        action="append",
        default=[],
        help="Contribution-analysis selector id. Repeat for multiple selectors.",
    )
    parser.add_argument(
        "--scatter-xvsy",
        action="append",
        default=[],
        help="X-vs-Y scatter plot as 'x_id,y_id,arm1[,arm2,...]'. Repeat for multiple plots.",
    )
    parser.add_argument(
        "--scatter-xvsx",
        action="append",
        default=[],
        help=(
            "X-vs-X scatter plot as 'variable,reference_arm,compare_arm1[,compare_arm2,...]'. "
            "Repeat for multiple plots."
        ),
    )
    parser.add_argument(
        "--data-overlay-table-sid",
        action="append",
        default=[],
        help="DataTable SID to add to the data overlay. Repeat for multiple tables.",
    )
    parser.add_argument(
        "--data-overlay-label",
        help="Label applied to data overlay tables added in this run.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Work with Jinkō TrialVisualization project items via the typed SDK API."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List TrialVisualization items.")
    list_parser.add_argument("--name", help="Optional name filter.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--output-file")
    list_parser.set_defaults(func=command_list)

    get_parser = subparsers.add_parser("get", help="Get TrialVisualization content.")
    get_parser.add_argument(
        "--trial-viz-sid", required=True, help="TrialVisualization SID."
    )
    get_parser.add_argument("--revision", type=int, help="Optional revision number.")
    get_parser.add_argument("--output-file")
    get_parser.set_defaults(func=command_get)

    create_parser = subparsers.add_parser(
        "create",
        help="Create an empty TrialVisualization bound to a trial, then configure it.",
    )
    create_parser.add_argument(
        "--trial-sid", required=True, help="Trial SID, for example tr-..."
    )
    create_parser.add_argument("--name")
    create_parser.add_argument("--description")
    create_parser.add_argument("--version")
    create_parser.add_argument(
        "--folder", help="Existing folder id or exact folder name."
    )
    create_parser.add_argument(
        "--apply", action="store_true", help="Actually create the visualization."
    )
    add_section_args(create_parser)
    create_parser.set_defaults(func=command_create)

    update_parser = subparsers.add_parser(
        "update", help="Configure sections on an existing TrialVisualization."
    )
    update_parser.add_argument(
        "--trial-viz-sid", required=True, help="TrialVisualization SID."
    )
    update_parser.add_argument(
        "--apply", action="store_true", help="Actually update the visualization."
    )
    add_section_args(update_parser)
    update_parser.set_defaults(func=command_update)

    sanity_parser = subparsers.add_parser(
        "sanity", help="Run TrialVisualization sanity checks."
    )
    sanity_parser.add_argument(
        "--trial-viz-sid", required=True, help="TrialVisualization SID."
    )
    sanity_parser.add_argument("--revision", type=int, help="Optional revision number.")
    sanity_parser.add_argument(
        "--only",
        action="append",
        choices=[
            "selectedArms",
            "groups",
            "filters",
            "overlay",
            "dataOverlay",
            "timeseries",
            "scalars",
            "scatterPlots",
            "contributionAnalysis",
            "survivalAnalysis",
        ],
        help="Restrict sanity to one section. Repeat for multiple sections.",
    )
    sanity_parser.set_defaults(func=command_sanity)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command in {"create", "update"} and not args.apply:
        return args.func(None, args)
    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        return args.func(client, args)
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - command-line diagnostics
        print(f"TrialVisualization command failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
