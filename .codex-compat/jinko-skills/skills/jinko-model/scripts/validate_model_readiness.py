#!/usr/bin/env python3
"""Check whether a Jinkō model is ready: diagnostics plus simple_solve."""

from __future__ import annotations

import argparse
import sys

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
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return None
    return JinkoClient, JinkoError


SIMPLE_SOLVE_TIMESERIES_LIMIT = 10


def select_timeseries_ids(timeseries_ids: list[str]) -> list[str]:
    if len(timeseries_ids) <= SIMPLE_SOLVE_TIMESERIES_LIMIT:
        return timeseries_ids

    preselected = timeseries_ids[:SIMPLE_SOLVE_TIMESERIES_LIMIT]
    print(
        "simple_solve accepts at most "
        f"{SIMPLE_SOLVE_TIMESERIES_LIMIT} time series ids; "
        f"{len(timeseries_ids)} time-dependent variables were found."
    )

    if not sys.stdin.isatty():
        print(
            "Non-interactive shell: using the first 10 variables returned by the model."
        )
        return preselected

    by_number = {
        str(index): value for index, value in enumerate(timeseries_ids, start=1)
    }
    by_id = {value: value for value in timeseries_ids}

    while True:
        for index, value in enumerate(timeseries_ids, start=1):
            mark = "x" if value in preselected else " "
            print(f"[{mark}] {index}. {value}")
        raw = input(
            "Select up to 10 variables by comma-separated number or id "
            "(press Enter to accept preselection): "
        ).strip()
        if not raw:
            return preselected

        selected: list[str] = []
        unknown: list[str] = []
        for token in [part.strip() for part in raw.split(",") if part.strip()]:
            value = by_number.get(token) or by_id.get(token)
            if value is None:
                unknown.append(token)
            elif value not in selected:
                selected.append(value)

        if unknown:
            print("Unknown selection: " + ", ".join(unknown), file=sys.stderr)
            continue
        if not selected:
            print("Select at least one variable.", file=sys.stderr)
            continue
        if len(selected) > SIMPLE_SOLVE_TIMESERIES_LIMIT:
            print(
                f"Select no more than {SIMPLE_SOLVE_TIMESERIES_LIMIT} variables.",
                file=sys.stderr,
            )
            continue
        return selected


def report_expected_series_changes(result, expected_ids: list[str]) -> bool:
    """Return True when an expected event-affected series did not change."""
    results_by_id = {series.id: series for series in result.results}
    failed = False
    for component_id in expected_ids:
        series = results_by_id.get(component_id)
        if series is None:
            print(
                f"simple_solve did not return expected series: {component_id}",
                file=sys.stderr,
            )
            failed = True
            continue
        if len(series.values) < 2 or all(
            value == series.values[0] for value in series.values[1:]
        ):
            print(
                f"Expected event-driven change was not observed in {component_id}: "
                f"{series.values}",
                file=sys.stderr,
            )
            failed = True
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate model diagnostics and simple_solve."
    )
    parser.add_argument(
        "--model-sid", required=True, help="Computational model SID, for example cm-..."
    )
    parser.add_argument(
        "--timeseries-id",
        action="append",
        help=(
            "Timeseries/component id to request from simple_solve. May be repeated. "
            "Defaults to the model's statically time-dependent variables."
        ),
    )
    parser.add_argument(
        "--expect-series-change",
        action="append",
        default=[],
        help=(
            "Event-affected series expected to change in simple_solve output. "
            "May be repeated; each id must also be selected with --timeseries-id."
        ),
    )
    args = parser.parse_args()

    load_env()
    sdk = load_sdk()
    if sdk is None:
        return 1
    JinkoClient, JinkoError = sdk

    try:
        client = JinkoClient()
        model = client.get_model(args.model_sid)
        diagnostics = model.diagnostics.errors()
        has_error = False

        if diagnostics:
            has_error = True
            print("Model diagnostics contain errors:", file=sys.stderr)
            for entry in diagnostics:
                diagnostic = entry.diagnostic
                print(
                    f"- {entry.component.id}: {diagnostic.code} ({diagnostic.severity}) {diagnostic.message}",
                    file=sys.stderr,
                )

        timeseries_ids = args.timeseries_id or model.time_dependent_ids()
        missing_expected_ids = set(args.expect_series_change) - set(timeseries_ids)
        if missing_expected_ids:
            has_error = True
            print(
                "Expected changing series must be requested with --timeseries-id: "
                + ", ".join(sorted(missing_expected_ids)),
                file=sys.stderr,
            )
        timeseries_ids = select_timeseries_ids(timeseries_ids)
        if not timeseries_ids:
            has_error = True
            print(
                "No time-dependent variables found for simple_solve.", file=sys.stderr
            )
        else:
            print("simple_solve time series: " + ", ".join(timeseries_ids))
            result = model.simple_solve(timeseries_ids=timeseries_ids)
            if result.error:
                has_error = True
                print(f"simple_solve failed: {result.error}", file=sys.stderr)
            elif report_expected_series_changes(result, args.expect_series_change):
                has_error = True

        if has_error:
            print("model is not ready")
            return 2

        print("model is ready")
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
