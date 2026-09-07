#!/usr/bin/env python3
"""Render comparison artifacts into a reviewable Markdown report."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from nonmem2jinko.platform.documents import evidence_errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a NONMEM-to-Jinko equivalence report from measured checks."
    )
    parser.add_argument(
        "--comparison",
        required=True,
        help="JSON written by compare_against_reference.py.",
    )
    parser.add_argument(
        "--series", help="Optional CSV written by compare_against_reference.py."
    )
    parser.add_argument(
        "--conversion-report", help="Optional Markdown written by a conversion script."
    )
    parser.add_argument("--title", default="NONMEM to Jinko equivalence report")
    parser.add_argument("--out", required=True, help="Markdown report to create.")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace --out if it already exists."
    )
    return parser


def _value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render(
    metrics: dict,
    *,
    title: str,
    series: Path | None = None,
    conversion_report: str | None = None,
) -> str:
    checks = [
        name for name in ("parse", "solve") if isinstance(metrics.get(name), dict)
    ]
    problems = evidence_errors(metrics)
    passed = not problems
    lines = [
        f"# {title}",
        "",
        "## Verdict",
        "",
        f"**{'PASS' if passed else 'FAIL'}**",
        "",
        "A pass requires a completed platform solve comparison within tolerance. "
        "A skipped check is not evidence.",
    ]
    if problems:
        lines += ["", "Evidence gate:", ""]
        lines.extend(f"- {problem}" for problem in problems)
    lines += [
        "",
        "## Check status",
        "",
        "| Check | Status | Basis or reason |",
        "| --- | --- | --- |",
    ]
    for name in checks:
        result = metrics[name]
        basis = result.get("reference_basis") or result.get("reason") or ""
        lines.append(f"| {name} | {result.get('status', 'unknown')} | {basis} |")

    solve = metrics.get("solve") or {}
    if solve.get("status") in {"pass", "fail"}:
        lines += [
            "",
            "## Structural-model agreement",
            "",
            f"Reference: `{solve.get('reference', 'unknown')}`.",
            "",
            "| Metric | Measured |",
            "| --- | --- |",
        ]
        for label, key in (
            ("Points", "points"),
            ("Worst relative error", "worst_relative_error"),
            ("Worst absolute error", "worst_absolute_error"),
            ("Cmax relative error", "cmax_relative_error"),
            ("AUC relative error", "auc_relative_error"),
            ("Tolerance", "tolerance"),
        ):
            if key in solve:
                lines.append(f"| {label} | {_value(solve[key])} |")

    if series is not None:
        with series.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        lines += ["", "## Compared series", ""]
        if rows:
            lines.append(
                f"`{series.name}` contains {len(rows)} compared points from "
                f"{rows[0].get('time', '?')} to {rows[-1].get('time', '?')} in "
                "the declared source time unit."
            )
        else:
            lines.append(f"`{series.name}` contains no compared points.")

    lines += [
        "",
        "## Scope",
        "",
        "This report measures the structural model on the platform's stored time "
        "grid. It does not claim population-level equivalence unless separate "
        "population evidence is attached and reviewed.",
    ]
    if conversion_report:
        lines += ["", "## Conversion report", "", conversion_report.rstrip()]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = build_parser().parse_args()
    target = Path(args.out)
    if target.exists() and not args.overwrite:
        print(f"refusing to overwrite {target}; pass --overwrite", file=sys.stderr)
        return 1
    try:
        metrics = json.loads(Path(args.comparison).read_text())
        if not isinstance(metrics, dict):
            raise ValueError("comparison JSON must be an object")
        conversion_report = (
            Path(args.conversion_report).read_text() if args.conversion_report else None
        )
        series = Path(args.series) if args.series else None
        body = render(
            metrics,
            title=args.title,
            series=series,
            conversion_report=conversion_report,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"cannot render report: {error}", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    print(f"report written to {target}")
    return 0 if not evidence_errors(metrics) else 1


if __name__ == "__main__":
    raise SystemExit(main())
