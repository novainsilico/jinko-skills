#!/usr/bin/env python3
"""Create, patch, get, list, and sanity-check Jinkō TrialVisualizations."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

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


def read_json_file(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(payload: Any, *, output_file: str | None = None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if output_file:
        Path(output_file).write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {output_file}")
    else:
        print(text)


def b64_json(value: Any) -> str:
    return base64.b64encode(json.dumps(value).encode("utf-8")).decode("ascii")


def b64_text(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def project_item_headers(args: argparse.Namespace) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    if getattr(args, "name", None):
        headers["X-jinko-project-item-name"] = b64_text(args.name)
    if getattr(args, "description", None):
        headers["X-jinko-project-item-description"] = b64_text(args.description)
    if getattr(args, "version_name", None):
        headers["X-jinko-project-item-version-name"] = b64_text(args.version_name)
    if getattr(args, "version_description", None):
        headers["X-jinko-project-item-version-description"] = b64_text(
            args.version_description
        )
    folder_ids = getattr(args, "folder_id", None) or []
    if folder_ids:
        actions = [{"id": folder_id, "action": "add"} for folder_id in folder_ids]
        headers["X-jinko-project-item-folder-ids"] = b64_json(actions)
    return headers or None


def resolve_trial_id(client: Any, args: argparse.Namespace) -> dict[str, str] | None:
    if getattr(args, "trial_sid", None):
        trial = client.get_trial(args.trial_sid)
        if not trial.core_id or not trial.snapshot_id:
            raise ValueError(
                f"Trial {args.trial_sid} does not expose core/snapshot ids"
            )
        return {"coreItemId": trial.core_id, "snapshotId": trial.snapshot_id}
    if getattr(args, "trial_core_id", None) and getattr(
        args, "trial_snapshot_id", None
    ):
        return {
            "coreItemId": args.trial_core_id,
            "snapshotId": args.trial_snapshot_id,
        }
    return None


def get_trial_viz_ids(client: Any, args: argparse.Namespace) -> tuple[str, str | None]:
    if getattr(args, "trial_viz_sid", None):
        trial_viz = client.get_trial_visualization(args.trial_viz_sid)
        if not trial_viz.core_id:
            raise ValueError(
                f"TrialVisualization {args.trial_viz_sid} does not expose a core id"
            )
        return trial_viz.core_id, trial_viz.snapshot_id
    core_id = getattr(args, "core_item_id", None)
    if core_id:
        return core_id, getattr(args, "snapshot_id", None)
    raise ValueError("Provide --trial-viz-sid or --core-item-id")


def default_timeseries_payload(selectors: list[str]) -> dict[str, Any]:
    return {
        "selectors": selectors,
        "layout": {},
        "dataOptions": {},
        "percentilesOptions": {
            "narrowRangeHighBoundPercentile": 0.75,
            "wideRangeHighBoundPercentile": 0.95,
        },
        "values": "median",
        "showVarianceLegend": True,
    }


def default_scalars_payload(selectors: list[str]) -> dict[str, Any]:
    return {
        "selectors": selectors,
        "layout": {},
        "centralLocationPlotsOptions": {
            "location": "median",
            "showLegend": True,
            "mean": {"barplots": True, "sdRange": 1},
            "median": {"interquantileHighBound": 0.75},
        },
    }


def default_survival_payload(selectors: list[str]) -> dict[str, Any]:
    return {
        "selectors": selectors,
        "layout": {},
        "dataOptions": {},
        "observationWindow": "FromStartUntilEnd",
        "survivalPlotsOptions": {"hasConfidenceInterval": True},
    }


def default_contribution_payload(selectors: list[str]) -> dict[str, Any]:
    return {
        "selectors": selectors,
        "layout": {},
        "quantile": 0.5,
        "baseline": {"tag": "InputBaselineOnly"},
    }


def load_scatter_config(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return {"layout": {}, "scatterPlotConfig": payload}
    if isinstance(payload, dict):
        if "scatterPlotConfig" in payload:
            return payload
        return {"layout": {}, "scatterPlotConfig": [payload]}
    raise ValueError("--scatter-config-file must contain an object or array")


def build_payload(
    client: Any, args: argparse.Namespace, *, include_trial: bool
) -> dict[str, Any]:
    payload = read_json_file(getattr(args, "payload_file", None))
    trial_id = resolve_trial_id(client, args) if include_trial else None
    if trial_id is not None:
        payload["trialId"] = trial_id
    elif include_trial and "trialId" not in payload:
        raise ValueError(
            "Create requires --trial-sid, --trial-core-id with --trial-snapshot-id, "
            "or a payload file containing trialId"
        )

    selected_arms = getattr(args, "selected_arm", None) or []
    if selected_arms:
        payload["selectedArms"] = selected_arms
    elif include_trial and "selectedArms" not in payload:
        payload["selectedArms"] = None

    if getattr(args, "timeseries", None):
        payload["timeseries"] = default_timeseries_payload(args.timeseries)
    if getattr(args, "scalar", None):
        payload["scalars"] = default_scalars_payload(args.scalar)
    if getattr(args, "survival", None):
        payload["survivalAnalysis"] = default_survival_payload(args.survival)
    if getattr(args, "contribution", None):
        payload["contributionAnalysis"] = default_contribution_payload(
            args.contribution
        )
    if getattr(args, "scatter_config_file", None):
        payload["scatterPlots"] = load_scatter_config(args.scatter_config_file)
    if getattr(args, "data_overlay_file", None):
        payload["dataOverlay"] = read_json_file(args.data_overlay_file)
    if getattr(args, "equate_baseline", False):
        payload["equateBaseline"] = True
    return payload


def summarize_project_item_response(payload: Any) -> None:
    if not isinstance(payload, dict):
        write_json(payload)
        return

    project_item = payload.get("projectItem") or {}
    metadata = payload.get("metadata") or {}
    core_value = (
        payload.get("coreItemId")
        or project_item.get("coreItemId")
        or metadata.get("coreItemId")
        or {}
    )
    if isinstance(core_value, dict):
        core_id = core_value.get("id")
        snapshot_id = core_value.get("snapshotId") or payload.get("snapshotId")
    else:
        core_id = core_value
        snapshot_id = payload.get("snapshotId")
    sid = payload.get("sid") or project_item.get("sid") or metadata.get("sid")
    revision = (
        payload.get("revision")
        or project_item.get("revision")
        or metadata.get("revision")
    )

    write_json(payload)
    if sid or core_id or snapshot_id or revision:
        print("Summary:", file=sys.stderr)
        print(f"  sid: {sid or '-'}", file=sys.stderr)
        print(f"  coreItemId: {core_id or '-'}", file=sys.stderr)
        print(f"  snapshotId: {snapshot_id or '-'}", file=sys.stderr)
        print(f"  revision: {revision or '-'}", file=sys.stderr)


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
    core_id, snapshot_id = get_trial_viz_ids(client, args)
    if snapshot_id:
        path = f"/core/v2/result_manager/trial_visualization/{core_id}/snapshots/{snapshot_id}"
    else:
        path = f"/core/v2/result_manager/trial_visualization/{core_id}"
    payload = client.raw_request("GET", path)
    write_json(payload, output_file=args.output_file)
    return 0


def command_create(client: Any, args: argparse.Namespace) -> int:
    payload = build_payload(client, args, include_trial=True)
    response = client.raw_request(
        "POST",
        "/core/v2/result_manager/trial_visualization",
        json_body=payload,
        headers=project_item_headers(args),
    )
    summarize_project_item_response(response)
    return 0


def command_patch(client: Any, args: argparse.Namespace) -> int:
    core_id, snapshot_id = get_trial_viz_ids(client, args)
    payload = build_payload(client, args, include_trial=False)
    if snapshot_id and args.patch_snapshot:
        path = f"/core/v2/result_manager/trial_visualization/{core_id}/snapshots/{snapshot_id}"
    else:
        path = f"/core/v2/result_manager/trial_visualization/{core_id}"
    response = client.raw_request(
        "PATCH",
        path,
        json_body=payload,
        headers=project_item_headers(args),
    )
    summarize_project_item_response(response)
    return 0


def command_sanity(client: Any, args: argparse.Namespace) -> int:
    core_id, snapshot_id = get_trial_viz_ids(client, args)
    if not snapshot_id:
        raise ValueError(
            "Sanity with --core-item-id requires --snapshot-id. "
            "Use --trial-viz-sid when you want the SDK metadata lookup to infer "
            "the snapshot id."
        )
    payload = client.raw_request(
        "GET",
        f"/core/v2/result_manager/trial_visualization/{core_id}/snapshots/{snapshot_id}/sanity",
        params={"only": args.only} if args.only else None,
    )
    write_json(payload, output_file=args.output_file)
    return 0


def add_metadata_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help="Project item name header.")
    parser.add_argument("--description", help="Project item description header.")
    parser.add_argument("--version-name", help="Version name header.")
    parser.add_argument("--version-description", help="Version description header.")
    parser.add_argument(
        "--folder-id",
        action="append",
        default=[],
        help="Folder UUID to add on create or patch. Repeat for multiple folders.",
    )


def add_plot_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--payload-file", help="JSON object to use as base payload.")
    parser.add_argument(
        "--selected-arm",
        action="append",
        default=[],
        help="Arm id to include in selectedArms. Repeat for multiple arms.",
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
        "--scatter-config-file",
        help="JSON object/array for scatterPlotConfig or full scatterPlots payload.",
    )
    parser.add_argument(
        "--data-overlay-file",
        help="JSON object for the dataOverlay section.",
    )
    parser.add_argument(
        "--equate-baseline",
        action="store_true",
        help="Set equateBaseline to true.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Work with Jinkō TrialVisualization raw API endpoints."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List TrialVisualization items.")
    list_parser.add_argument("--name", help="Optional name filter.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--output-file")
    list_parser.set_defaults(func=command_list)

    get_parser = subparsers.add_parser("get", help="Get TrialVisualization content.")
    get_parser.add_argument("--trial-viz-sid", help="TrialVisualization SID.")
    get_parser.add_argument("--core-item-id", help="TrialVisualization core UUID.")
    get_parser.add_argument("--snapshot-id", help="Optional snapshot UUID.")
    get_parser.add_argument("--output-file")
    get_parser.set_defaults(func=command_get)

    create_parser = subparsers.add_parser("create", help="Create a TrialVisualization.")
    create_parser.add_argument("--trial-sid", help="Trial SID, for example tr-...")
    create_parser.add_argument("--trial-core-id", help="Trial core UUID.")
    create_parser.add_argument("--trial-snapshot-id", help="Trial snapshot UUID.")
    add_metadata_args(create_parser)
    add_plot_args(create_parser)
    create_parser.set_defaults(func=command_create)

    patch_parser = subparsers.add_parser("patch", help="Patch a TrialVisualization.")
    patch_parser.add_argument("--trial-viz-sid", help="TrialVisualization SID.")
    patch_parser.add_argument("--core-item-id", help="TrialVisualization core UUID.")
    patch_parser.add_argument("--snapshot-id", help="Optional snapshot UUID.")
    patch_parser.add_argument(
        "--patch-snapshot",
        action="store_true",
        help="Patch the provided snapshot instead of the latest version.",
    )
    add_metadata_args(patch_parser)
    add_plot_args(patch_parser)
    patch_parser.set_defaults(func=command_patch)

    sanity_parser = subparsers.add_parser(
        "sanity", help="Run TrialVisualization sanity checks."
    )
    sanity_parser.add_argument("--trial-viz-sid", help="TrialVisualization SID.")
    sanity_parser.add_argument("--core-item-id", help="TrialVisualization core UUID.")
    sanity_parser.add_argument(
        "--snapshot-id",
        help="TrialVisualization snapshot UUID. Required with --core-item-id.",
    )
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
    sanity_parser.add_argument("--output-file")
    sanity_parser.set_defaults(func=command_sanity)
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
