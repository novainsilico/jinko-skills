#!/usr/bin/env python3
"""Create, sanity-check, run, poll, and download a Jinkō trial.

Dry-run by default. Pass --apply to create project items and --run to launch.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
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
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv pandas",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def ref(item: Any) -> dict[str, str]:
    if not item.core_id or not item.snapshot_id:
        raise ValueError(f"Project item {item.sid} is missing core_id or snapshot_id")
    return {"coreItemId": item.core_id, "snapshotId": item.snapshot_id}


def load_json_file(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("solving options override JSON must be an object")
    return data


def resolve_output_ids(model: Any, explicit_output_ids: list[str] | None) -> list[str]:
    output_ids = explicit_output_ids or model.time_dependent_ids()
    if not output_ids:
        raise RuntimeError(
            "No output ids provided and no time-dependent variables found."
        )
    return output_ids


def resolve_folder(client: Any, folder_ref: str | None, *, create: bool) -> Any | None:
    if folder_ref is None:
        return None

    folder = client.folders.get_by_id(folder_ref)
    if folder is not None:
        return folder

    folder = client.folders.get_by_name(folder_ref, exact_match_only=True)
    if folder is not None:
        return folder

    if not create:
        raise ValueError(
            f"Folder {folder_ref!r} was not found. Pass --create-folder to create it."
        )

    return client.folders.create(folder_ref)


def create_trial_with_data_tables(
    client: Any,
    *,
    model: Any,
    output_set: Any,
    vpop: Any | None,
    protocol: Any | None,
    scoring: Any | None,
    data_tables: list[Any],
    solving_options_override: dict[str, Any] | None,
    folder: Any | None,
    name: str,
    description: str,
) -> Any:
    payload: dict[str, Any] = {
        "computationalModelId": ref(model),
        "measureDesignId": ref(output_set),
        "dataTableDesigns": [
            {
                "dataTableId": ref(data_table),
                "include": True,
                "options": {"weight": 1},
            }
            for data_table in data_tables
        ],
    }
    if vpop is not None:
        payload["vpopId"] = ref(vpop)
    if protocol is not None:
        payload["protocolDesignId"] = ref(protocol)
    if scoring is not None:
        payload["scoringDesignId"] = ref(scoring)
    if solving_options_override is not None:
        payload["solvingOptionsOverride"] = solving_options_override
    return client.create_raw_trial(
        payload,
        folder=folder,
        name=name,
        description=description,
    )


def valid_for_fitness_from_content(content: Any) -> bool | None:
    if isinstance(content, dict):
        public = (content.get("metadata") or {}).get("public") or {}
        return public.get("validForFitnessFunction")

    metadata = getattr(content, "metadata", None)
    public = getattr(metadata, "public", None)
    return getattr(public, "validForFitnessFunction", None)


def ensure_data_tables_can_attach(data_tables: list[Any]) -> None:
    invalid: list[str] = []
    for data_table in data_tables:
        valid = valid_for_fitness_from_content(data_table.content())
        if valid is False:
            invalid.append(data_table.sid)
    if invalid:
        raise RuntimeError(
            "Data tables attached through dataTableDesigns must report "
            "metadata.public.validForFitnessFunction=True: " + ", ".join(invalid)
        )


def collect_sanity_errors(value: Any) -> list[str]:
    errors: list[str] = []

    def walk(item: Any, path: str) -> None:
        if isinstance(item, dict):
            severity = str(item.get("severity") or item.get("level") or "").lower()
            code = item.get("code") or item.get("message") or item.get("warning")
            if severity in {"error", "critical", "alert", "emergency"} and code:
                errors.append(f"{path}: {code}")
            for key, child in item.items():
                if key.lower() in {
                    "sanity",
                    "sanitychecks",
                    "diagnostics",
                    "errors",
                } or isinstance(child, (dict, list)):
                    walk(child, f"{path}.{key}" if path else key)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")

    walk(value, "")
    return errors


def ensure_trial_sane(trial: Any) -> None:
    status = trial.status()
    errors = collect_sanity_errors(status)
    if errors:
        raise RuntimeError(
            "Trial sanity errors:\n" + "\n".join(f"- {error}" for error in errors)
        )


def extract_arms(summary: dict[str, Any]) -> list[str]:
    return [str(arm) for arm in summary.get("arms", [])]


def extract_scalar_ids(summary: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in summary.get("scalars", []) or []:
        if isinstance(item, dict) and item.get("id"):
            result.append(str(item["id"]))
        elif isinstance(item, str):
            result.append(item)
    return result


def extract_timeseries_ids(output_ids: Any) -> list[str]:
    candidates = output_ids
    if isinstance(output_ids, dict):
        candidates = (
            output_ids.get("timeseries")
            or output_ids.get("timeSeries")
            or output_ids.get("outputs")
            or []
        )
    if isinstance(candidates, dict):
        candidates = candidates.values()
    result: list[str] = []
    for item in candidates or []:
        if isinstance(item, dict):
            value = item.get("id") or item.get("timeseriesId") or item.get("timeseries")
            if value:
                result.append(str(value))
        elif isinstance(item, str):
            result.append(item)
    return result


def write_tabular_download(download: Any, output_dir: Path, stem: str) -> None:
    try:
        df = download.to_dataframe()
    except Exception as exc:  # noqa: BLE001 - fallback is intentionally dependency driven
        if "pandas" not in str(exc).lower():
            raise
        payload = download.bytes
        raw_path = output_dir / f"{stem}.bin"
        raw_path.write_bytes(payload)
        if zipfile.is_zipfile(io.BytesIO(payload)):
            extract_dir = output_dir / stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                archive.extractall(extract_dir)
            print(f"Pandas unavailable; extracted {stem} ZIP results to {extract_dir}")
        else:
            csv_path = output_dir / f"{stem}.csv"
            csv_path.write_bytes(payload)
            print(f"Pandas unavailable; wrote {stem} CSV results: {csv_path}")
        print(f"Wrote raw {stem} payload: {raw_path}")
        return

    csv_path = output_dir / f"{stem}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Wrote {stem} results: {csv_path}")


def download_results(
    trial: Any, output_dir: Path, requested_timeseries_ids: list[str]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = trial.results.summary()
    arms = extract_arms(summary)
    available_timeseries_ids = set(extract_timeseries_ids(trial.output_ids()))
    timeseries_ids = [
        timeseries_id
        for timeseries_id in requested_timeseries_ids
        if timeseries_id in available_timeseries_ids
    ]
    scalar_ids = extract_scalar_ids(summary)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    if timeseries_ids and arms:
        ts_selector = {timeseries_id: arms for timeseries_id in timeseries_ids}
        write_tabular_download(
            trial.results.timeseries(ts_selector), output_dir, "timeseries"
        )
    else:
        print("No TimeSeries ids or arms found; skipping TimeSeries download.")

    if scalar_ids:
        write_tabular_download(trial.results.scalars(scalar_ids), output_dir, "scalars")
    else:
        print("No Scalar ids found; skipping Scalar download.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set up and optionally run a Jinkō trial."
    )
    parser.add_argument(
        "--model-sid", required=True, help="Computational model SID, for example cm-..."
    )
    parser.add_argument(
        "--output-id",
        action="append",
        help=(
            "Component time series id to save. May be repeated. Defaults to the "
            "model's statically time-dependent variables."
        ),
    )
    parser.add_argument("--vpop-sid", help="Optional Vpop SID.")
    parser.add_argument("--protocol-design-sid", help="Optional ProtocolDesign SID.")
    parser.add_argument(
        "--data-table-sid",
        action="append",
        default=[],
        help="Optional DataTable SID. May be repeated.",
    )
    parser.add_argument("--scoring-sid", help="Optional advanced ScoringDesign SID.")
    parser.add_argument(
        "--solving-options-json", help="Optional solvingOptionsOverride JSON file."
    )
    parser.add_argument("--name", default="sdk-trial")
    parser.add_argument("--description", default="Trial created with the Jinkō SDK.")
    parser.add_argument(
        "--folder",
        help="Existing folder id or exact folder name for the new trial items.",
    )
    parser.add_argument(
        "--create-folder",
        action="store_true",
        help="Create --folder when missing. Treats --folder as a folder name.",
    )
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument(
        "--apply", action="store_true", help="Create the output set and trial."
    )
    parser.add_argument(
        "--run", action="store_true", help="Launch the trial after creation."
    )
    parser.add_argument(
        "--download-results",
        action="store_true",
        help="Download results after successful completion.",
    )
    parser.add_argument(
        "--output-dir",
        default="trial-results",
        help="Directory for downloaded result CSVs.",
    )
    args = parser.parse_args()

    if args.create_folder and not args.folder:
        print("--create-folder requires --folder", file=sys.stderr)
        return 1

    try:
        solving_options_override = load_json_file(args.solving_options_json)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid solving options override: {exc}", file=sys.stderr)
        return 1

    print(f"Model: {args.model_sid}")
    if args.output_id:
        print(f"Simple output set time series: {', '.join(args.output_id)}")
    else:
        print("Simple output set time series: <model time-dependent variables>")
    print(f"Vpop: {args.vpop_sid or '<none>'}")
    print(f"Protocol: {args.protocol_design_sid or '<none>'}")
    print(
        f"Data tables: {', '.join(args.data_table_sid) if args.data_table_sid else '<none>'}"
    )
    print(f"Advanced scoring: {args.scoring_sid or '<none>'}")
    print(f"Folder: {args.folder or '<none>'}")
    print(f"Run after create: {args.run}")

    if not args.apply:
        print(f"Would create simple output set and trial named {args.name!r}.")
        print("Run again with --apply to create project items; add --run to launch.")
        return 0

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        folder = resolve_folder(client, args.folder, create=args.create_folder)
        model = client.get_model(args.model_sid)
        vpop = client.get_vpop(args.vpop_sid) if args.vpop_sid else None
        protocol = (
            client.get_protocol_design(args.protocol_design_sid)
            if args.protocol_design_sid
            else None
        )
        scoring = client.get_scoring(args.scoring_sid) if args.scoring_sid else None
        data_tables = [client.get_data_table(sid) for sid in args.data_table_sid]
        ensure_data_tables_can_attach(data_tables)
        output_ids = resolve_output_ids(model, args.output_id)
        print("Resolved simple output set time series: " + ", ".join(output_ids))

        output_set = client.create_simple_output_set(model, output_ids)
        if folder is not None:
            output_set = output_set.move_to_folder(
                folder,
                version="move simple output set to folder",
            )
        if data_tables:
            trial = create_trial_with_data_tables(
                client,
                model=model,
                output_set=output_set,
                vpop=vpop,
                protocol=protocol,
                scoring=scoring,
                data_tables=data_tables,
                solving_options_override=solving_options_override,
                folder=folder,
                name=args.name,
                description=args.description,
            )
        else:
            trial = client.create_trial(
                model,
                vpop=vpop,
                protocol=protocol,
                output_set=output_set,
                scoring=scoring,
                solving_options_override=solving_options_override,
                folder=folder,
                name=args.name,
                description=args.description,
            )

        print(f"Created output set {output_set.sid}")
        print(f"Created trial {trial.sid}")
        if folder is not None:
            print(f"Folder: {client.folders.get_path(folder)}")
        print(trial.url)

        ensure_trial_sane(trial)
        print("Trial sanity check did not report errors.")

        if not args.run:
            print("Trial was not launched. Add --run to launch after creation.")
            return 0

        trial.run()
        final_status = trial.wait_until_completed(timeout=args.timeout)
        print("Final status:")
        print(json.dumps(final_status, indent=2, sort_keys=True))
        if isinstance(final_status, dict) and final_status.get("status") != "completed":
            print(
                "Trial did not complete successfully; skipping result download.",
                file=sys.stderr,
            )
            return 3
        if args.download_results:
            download_results(trial, Path(args.output_dir), output_ids)
        return 0
    except (ValueError, RuntimeError, TimeoutError, JinkoError) as exc:
        print(f"Trial setup/run failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep result download diagnostics concise
        print(f"Trial workflow failed: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
