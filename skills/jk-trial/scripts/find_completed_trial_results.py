#!/usr/bin/env python3
"""Find a completed Jinkō trial and download TimeSeries/Scalar results."""

from __future__ import annotations

import argparse
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
            "Cannot import jinko. Install the SDK: pip install jinko python-dotenv pandas",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


def trial_is_completed(status: Any) -> bool:
    return isinstance(status, dict) and status.get("status") == "completed"


def extract_arms(summary: dict[str, Any]) -> list[str]:
    arms = summary.get("arms") or []
    return [str(arm) for arm in arms]


def extract_scalar_ids(summary: dict[str, Any]) -> list[str]:
    scalars = summary.get("scalars") or []
    result: list[str] = []
    for item in scalars:
        if isinstance(item, dict) and item.get("id"):
            result.append(str(item["id"]))
        elif isinstance(item, str):
            result.append(item)
    return result


def extract_timeseries_ids(output_ids: Any) -> list[str]:
    if isinstance(output_ids, dict):
        candidates = (
            output_ids.get("timeseries")
            or output_ids.get("timeSeries")
            or output_ids.get("outputs")
            or []
        )
    else:
        candidates = output_ids or []
    result: list[str] = []
    if isinstance(candidates, dict):
        candidates = candidates.values()
    for item in candidates:
        if isinstance(item, dict):
            value = item.get("id") or item.get("timeseriesId") or item.get("timeseries")
            if value:
                result.append(str(value))
        elif isinstance(item, str):
            result.append(item)
    return result


def write_or_report_dataframe(df, *, label: str, output_dir: Path | None) -> None:
    if output_dir is None:
        print(f"{label} dataframe: rows={len(df)}, columns={list(df.columns)}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{label}.csv"
    df.to_csv(path, index=False)
    print(f"Wrote {label} dataframe: {path}")


def download_results(trial, *, output_dir: Path | None) -> None:
    summary = trial.results.summary()
    arms = extract_arms(summary)
    output_ids = trial.output_ids()
    timeseries_ids = extract_timeseries_ids(output_ids)
    scalar_ids = extract_scalar_ids(summary)

    print("Summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if timeseries_ids and arms:
        ts_selector = {timeseries_id: arms for timeseries_id in timeseries_ids}
        ts_df = trial.results.timeseries(ts_selector).to_dataframe()
        write_or_report_dataframe(ts_df, label="timeseries", output_dir=output_dir)
    else:
        print("No TimeSeries ids or arms found; skipping TimeSeries download.")

    if scalar_ids:
        scalar_df = trial.results.scalars(scalar_ids).to_dataframe()
        write_or_report_dataframe(scalar_df, label="scalars", output_dir=output_dir)
    else:
        print("No Scalar ids found; skipping Scalar download.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find a completed trial and download results."
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Number of trials to list."
    )
    parser.add_argument(
        "--output-dir", help="Directory where result DataFrames are written as CSV."
    )
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        trials = client.list_trials(limit=args.limit)
        for trial in trials:
            status = trial.status()
            if not trial_is_completed(status):
                continue

            print(f"Trial: {trial.name} ({trial.sid})")
            print(f"URL: {trial.url}")
            download_results(
                trial,
                output_dir=Path(args.output_dir) if args.output_dir else None,
            )
            return 0

        print("No completed trial found in the listed trials.", file=sys.stderr)
        return 1
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep result download diagnostics concise
        print(f"Completed trial result download failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
