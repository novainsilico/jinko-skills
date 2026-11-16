"""Report and plots of the post-calibration uncertainty qualification.

``post_calib_uq.py analyze`` calls this module. The plots follow the Jinkō
API cookbooks ``post_calibration_uq`` and ``quantifying_uncertainty``:

- ``profiles.png``: one row per score (weighted score, then each objective), one
  column per parameter. Blue points are the Sobol patients, the red line is the
  profile, and the green cross is the best patient.
- ``pairs.png``: Sobol patients for each parameter pair, colored by weighted
  score; the diagonal shows the near-optimal values of each parameter.
- ``curvature.png``: eigenvalues of the fitted Hessian, and the fit R2, as the
  fit uses more samples around the best patient.
- ``predictions.png``: model outputs per arm: the best patient and the range of
  the near-optimal patients (prediction uncertainty).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from post_calib_uq import (
    SCORE,
    group_of,
    near_optimal,
    quadratic_fit,
    to_z,
)

MAX_SCORE_ROWS = 6
MAX_OUTPUTS = 6
MAX_ARMS = 6


def read_bands(path: Path) -> list[dict[str, Any]]:
    """Read the prediction bands written by fetch; empty when there are none."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        rows = []
        for row in csv.DictReader(stream):
            values = {
                k: _number(row[k])
                for k in ("time", "best", "low", "q05", "q95", "high")
            }
            if values["time"] is not None:
                rows.append({**row, **values})
        return rows


def _number(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3g}"
    return str(value)


def score_columns(rows: list[dict[str, Any]], ids: list[str]) -> list[str]:
    keys = {key for row in rows for key in row} - {"patientIndex", SCORE, *ids}
    return [SCORE, *sorted(keys)[:MAX_SCORE_ROWS]]


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #


def markdown(
    report: dict[str, Any],
    calibration: dict[str, Any],
    design_info: dict[str, Any],
    record: dict[str, Any] | None,
    images: list[str],
    items: list[dict[str, str]] | None = None,
) -> str:
    """Return the report markdown.

    With ``items``, the report is a Jinkō document: a "Jinkō items" section
    shows each linked project item as a card (its bare URL alone in a
    paragraph). Elsewhere, URLs are labeled links, which Jinkō keeps as links.
    """
    gates = report["gates"]
    ids = [p["id"] for p in calibration["parameters"]]
    delta = report["delta"]
    lines = [
        "# Post-calibration uncertainty qualification",
        "",
        f"- Calibration: [{calibration['calibration']['sid']}]({calibration['calibration']['url']})",
    ]
    if record:
        lines.append(
            f"- Exploration trial: [{record['trial']['sid']}]({record['trial']['url']})"
        )
    lines += [
        f"- Best weighted score: {fmt(report['reference_score'])} (1 is a perfect fit)",
        f"- Near-optimal: weighted score at most {delta} below the best score",
        "",
        f"**Verdict: {report['verdict']}**",
        "",
    ]
    for note in report.get("notes", []):
        lines += [f"> Note: {note}", ""]
    if items:
        lines += ["## Jinkō items", ""]
        for item in items:
            lines += [f"{item['label']}:", "", item["url"], ""]
    lines += [
        "## Gates",
        "",
        "| Gate | Status | Detail |",
        "| --- | --- | --- |",
        f"| Reproduction | {gates['reproduction']['status']} | calibration {fmt(gates['reproduction']['calibration_score'])}, trial {fmt(gates['reproduction']['trial_score'])} |",
        f"| Simulations | {gates['simulations']['status']} | {gates['simulations']['failed']} of {gates['simulations']['total']} failed |",
        f"| Optimum | {gates['optimum']['status']} | best explored improvement {fmt(gates['optimum']['improvement'])} |",
        f"| Priors | {gates['priors']['status']} | {', '.join(f'{k} ({v:+.1f} sd)' for k, v in gates['priors']['far'].items()) or 'all within 3 sd'} |",
        f"| Bounds | {gates['bounds']['status']} | {', '.join(f'{k} ({v})' for k, v in gates['bounds']['at_bound'].items()) or 'none at a bound'} |",
        f"| Identifiability | {gates['identifiability']['status']} | not identifiable: {', '.join(gates['identifiability']['not_identifiable']) or 'none'}; one-sided: {', '.join(gates['identifiability']['one_sided']) or 'none'}; compensated: {', '.join(gates['identifiability']['compensated']) or 'none'} |",
        f"| Correlations | {gates['correlations']['status']} | {len(gates['correlations']['pairs'] or [])} correlated pairs, {len(gates['correlations']['curvature'].get('weak_directions', []))} weak directions |",
        "",
        "## Recommended next steps",
        "",
    ]
    lines += [f"{i}. {step}" for i, step in enumerate(report["next_steps"], start=1)]
    lines += [
        "",
        "## Parameters",
        "",
        f"Slice interval: values whose score stays within {delta} of the best score when "
        "only this parameter moves; it is a lower bound on the uncertainty. Joint "
        "interval: the same when the other parameters adjust, from the local quadratic "
        "fit; along a flat direction it runs to the edge of the explored range. '-' marks "
        "a limit outside the explored range, and 'with' the parameters that compensate. "
        "Largest drop: the largest score loss on each side of the best value over the "
        "slice range.",
        "",
        "| Parameter | Best | Prior (sd) | Slice range | Slice interval | Joint interval | Largest drop (low / high) | Status | At bound |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for identifier, p in report["parameters"].items():
        low, high = p["sides"]["lower"]["max_drop"], p["sides"]["upper"]["max_drop"]
        sigma = "-" if p["prior_sigma"] is None else f"{p['prior_sigma']:+.1f}"
        joint = p.get("joint_interval")
        joint_text = "-" if joint is None else f"[{fmt(joint[0])}, {fmt(joint[1])}]"
        if p.get("compensated_with"):
            joint_text += " with " + ", ".join(p["compensated_with"])
        lines.append(
            f"| {identifier} | {fmt(p['best'])} | {sigma} | [{fmt(p['range'][0])}, {fmt(p['range'][1])}] "
            f"| [{fmt(p['interval'][0])}, {fmt(p['interval'][1])}] | {joint_text} | {fmt(low)} / {fmt(high)} "
            f"| {p['status']} | {p['at_bound'] or '-'} |"
        )
    if report.get("objectives"):
        lines += [
            "",
            "## Objectives",
            "",
            "Score of the best patient on each objective, and the score spread over all "
            "explored patients. A missed objective limits the fit; an insensitive one does "
            "not inform the calibrated parameters.",
            "",
            "| Objective | Best score | Spread | Status |",
            "| --- | --- | --- | --- |",
        ]
        for column, objective in report["objectives"].items():
            lines.append(
                f"| {column} | {fmt(objective['best'])} | {fmt(objective['spread'])} | {objective['status']} |"
            )
    correlations = gates["correlations"]
    lines += ["", "## Correlations", ""]
    if correlations["matrix"] is None:
        lines.append(
            f"Too few near-optimal Sobol patients ({correlations['near_optimal_samples']}) "
            "for a correlation matrix."
        )
    else:
        lines += [
            f"Spearman correlations between parameters over the {correlations['near_optimal_samples']} "
            "near-optimal Sobol patients. A large |rho| shows a compensation.",
            "",
            "| | " + " | ".join(ids) + " |",
            "| --- " * (len(ids) + 1) + "|",
        ]
        for identifier, row in zip(ids, correlations["matrix"], strict=True):
            lines.append(f"| {identifier} | " + " | ".join(fmt(v) for v in row) + " |")
    curvature = correlations["curvature"]
    fit = curvature.get("fit")
    lines += ["", "## Local curvature", ""]
    if fit is None:
        lines.append(f"No quadratic fit: {curvature.get('reason')}.")
    else:
        lines += [
            f"Quadratic fit of the weighted score around the best patient: {fit['samples']} "
            f"patients, R2 {fit['r2']:.2f}. Coordinates are the Sobol box mapped to [-1, 1]. "
            "At a maximum, all eigenvalues are negative. An eigenvalue near zero, or "
            "positive, is a direction that the data do not constrain.",
            "",
        ]
        if curvature.get("reason"):
            lines += [f"The fit is not used: {curvature['reason']}.", ""]
        lines += [
            "| Eigenvalue | " + " | ".join(ids) + " |",
            "| --- " * (len(ids) + 1) + "|",
        ]
        for value, vector in zip(fit["eigenvalues"], fit["eigenvectors"], strict=True):
            lines.append(
                f"| {value:.3g} | " + " | ".join(f"{c:+.2f}" for c in vector) + " |"
            )
    if images:
        lines += ["", "## Plots", ""]
        captions = {
            "profiles": "Scores against each parameter. Blue: Sobol patients. Red: slice "
            "(one parameter varies, the others stay at their best value). Green cross: best "
            "patient. Dashed line: near-optimal threshold. A sharp red peak is an "
            "identifiable parameter; a flat red line is not.",
            "pairs": "Sobol patients for each parameter pair, colored by weighted score. A "
            "diagonal ridge of good scores is a compensation. Diagonal: values of the "
            "near-optimal patients; the nested boxes sample more densely near the best "
            "patient, so read the width of the histograms, not their height.",
            "curvature": "Eigenvalues of the fitted Hessian, and the fit R2, against the "
            "number of patients nearest to the best patient. Stable negative eigenvalues "
            "confirm a local maximum.",
            "predictions": "Model outputs per arm. Line: best patient. Dark band: 5 to 95% "
            "of the near-optimal patients. Light band: their full range. This is the "
            "prediction uncertainty that comes from the parameter uncertainty.",
        }
        for image in images:
            stem = Path(image).stem
            lines += [f"![{stem}]({image})", "", captions.get(stem, ""), ""]
    lines += [
        "## Method",
        "",
        f"- Exploration: the best patient, {design_info['profile_points']} slice points per "
        f"parameter over the explored range (best / {design_info['factor']:g} to best x "
        f"{design_info['factor']:g} unless a range was given, clipped to the prior bounds), "
        f"and {2 ** design_info['sobol_log2']} Sobol patients in each of "
        f"{len(design_info['box_fractions'])} nested boxes (the explored range, then 1/3 "
        "and 1/9 of it around the best value).",
        "- Scores are Jinkō scores: the weighted score is the weighted mean of the "
        "objective scores, and 1 is a perfect fit.",
        "- Identifiability holds only over the explored range. A parameter can be "
        "identifiable outside it.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Plots
# --------------------------------------------------------------------------- #


def plots(
    directory: Path,
    calibration: dict[str, Any],
    design_info: dict[str, Any],
    rows: list[dict[str, Any]],
    series: list[dict[str, Any]],
    report: dict[str, Any],
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = directory / "plots"
    out.mkdir(exist_ok=True)
    images = []
    for name, draw in (
        ("profiles", _profiles),
        ("pairs", _pairs),
        ("curvature", _curvature),
        ("predictions", _predictions),
    ):
        figure = draw(plt, calibration, design_info, rows, series, report)
        if figure is None:
            continue
        path = out / f"{name}.png"
        figure.savefig(path, dpi=110)
        plt.close(figure)
        images.append(str(path.relative_to(directory)))
    return images


def _profiles(plt, calibration, design_info, rows, series, report):
    parameters = calibration["parameters"]
    ids = [p["id"] for p in parameters]
    scores = score_columns(rows, ids)
    reference = report["reference_score"]
    best_row = next((r for r in rows if r["patientIndex"] == "best"), {})
    figure, axes = plt.subplots(
        len(scores),
        len(ids),
        figsize=(2.6 * len(ids) + 1, 2.2 * len(scores) + 0.6),
        sharex="col",
        squeeze=False,
    )
    sobol = [r for r in rows if r["patientIndex"].startswith("sobol-")]
    for j, parameter in enumerate(parameters):
        identifier = parameter["id"]
        profile = sorted(
            (r for r in rows if group_of(r["patientIndex"], ids) == identifier),
            key=lambda r: r[identifier] if r[identifier] is not None else math.inf,
        )
        for i, score in enumerate(scores):
            axis = axes[i][j]
            points = [
                (r[identifier], r.get(score)) for r in sobol if r.get(score) is not None
            ]
            axis.scatter(
                [x for x, _ in points],
                [y for _, y in points],
                s=3,
                alpha=0.35,
                color="tab:blue",
            )
            line = [
                (r[identifier], r.get(score))
                for r in profile
                if r.get(score) is not None
            ]
            axis.plot(
                [x for x, _ in line],
                [y for _, y in line],
                color="tab:red",
                linewidth=1.5,
            )
            if best_row.get(score) is not None:
                axis.plot(
                    [parameter["best"]],
                    [best_row[score]],
                    marker="+",
                    color="tab:green",
                    markersize=12,
                    mew=2,
                )
            values = [y for _, y in points + line]
            if values:
                top = max(values)
                axis.set_ylim(max(min(values), top - 1.0) - 0.02, top + 0.05)
            if i == 0:
                axis.axhline(
                    reference - report["delta"],
                    color="grey",
                    linestyle="--",
                    linewidth=1,
                )
                axis.set_title(identifier, fontsize=9)
            if j == 0:
                axis.set_ylabel(
                    score if len(score) < 28 else score[:25] + "...", fontsize=8
                )
            if design_info["profiles"][identifier]["log"]:
                axis.set_xscale("log")
            axis.tick_params(labelsize=7)
    figure.tight_layout()
    return figure


def _pairs(plt, calibration, design_info, rows, series, report):
    parameters = calibration["parameters"]
    ids = [p["id"] for p in parameters]
    if len(ids) < 2:
        return None
    box = design_info["box"]

    def coordinate(identifier, value):
        return math.log10(value) if box[identifier]["log"] and value > 0 else value

    labels = [f"log10 {i}" if box[i]["log"] else i for i in ids]
    reference, delta = report["reference_score"], report["delta"]
    sobol = sorted(
        (
            r
            for r in rows
            if r["patientIndex"].startswith("sobol-") and r.get(SCORE) is not None
        ),
        key=lambda r: r[SCORE],
    )
    floor = reference - 10 * delta
    shown = [r for r in sobol if r[SCORE] >= floor]
    near = near_optimal(sobol, reference, delta)
    n = len(ids)
    figure, axes = plt.subplots(
        n, n, figsize=(1.9 * n + 1.5, 1.9 * n + 0.5), squeeze=False
    )
    mappable = None
    for i in range(n):
        for j in range(n):
            axis = axes[i][j]
            axis.tick_params(labelsize=6)
            axis.locator_params(nbins=3)
            if j > i:
                axis.axis("off")
                continue
            if i == j:
                values = [coordinate(ids[i], r[ids[i]]) for r in near]
                if values:
                    axis.hist(values, bins=15, color="tab:green", alpha=0.7)
            else:
                mappable = axis.scatter(
                    [coordinate(ids[j], r[ids[j]]) for r in shown],
                    [coordinate(ids[i], r[ids[i]]) for r in shown],
                    c=[r[SCORE] for r in shown],
                    s=5,
                    cmap="viridis",
                    vmin=floor,
                    vmax=reference,
                )
                axis.plot(
                    [coordinate(ids[j], parameters[j]["best"])],
                    [coordinate(ids[i], parameters[i]["best"])],
                    marker="+",
                    color="red",
                    markersize=10,
                )
            if i == n - 1:
                axis.set_xlabel(labels[j], fontsize=7)
            if j == 0:
                axis.set_ylabel(labels[i], fontsize=7)
    if mappable is not None:
        figure.colorbar(mappable, ax=axes, shrink=0.6, label=SCORE)
    return figure


def _curvature(plt, calibration, design_info, rows, series, report):
    parameters = calibration["parameters"]
    ids = [p["id"] for p in parameters]
    box = design_info["box"]
    samples = [
        r
        for r in rows
        if (r["patientIndex"].startswith("sobol-") or r["patientIndex"] == "best")
        and r.get(SCORE) is not None
        and all(r.get(i) is not None for i in ids)
    ]
    center = [to_z(p["best"], box[p["id"]]) for p in parameters]
    z = [[to_z(r[i], box[i]) for i in ids] for r in samples]
    order = sorted(
        range(len(z)), key=lambda k: sum((a - b) ** 2 for a, b in zip(z[k], center))
    )
    d = len(ids)
    minimum = 2 * (1 + d + d * (d + 1) // 2)
    if len(order) < minimum:
        return None
    step = max(1, (len(order) - minimum) // 40)
    counts, eigen, r2 = [], [], []
    for n in range(minimum, len(order) + 1, step):
        chosen = order[:n]
        fit = quadratic_fit(
            [z[k] for k in chosen], [samples[k][SCORE] for k in chosen], center
        )
        if fit is None:
            continue
        counts.append(n)
        eigen.append(fit["eigenvalues"])
        r2.append(fit["r2"])
    if not counts:
        return None
    figure, (left, right) = plt.subplots(1, 2, figsize=(10, 3.5))
    for k in range(d):
        left.plot(counts, [e[k] for e in eigen], label=f"lambda {k + 1}")
    left.axhline(0, color="grey", linewidth=0.8)
    left.set_xlabel("patients nearest to the best patient")
    left.set_ylabel("Hessian eigenvalue")
    left.set_yscale("symlog", linthresh=1e-2)
    left.legend(fontsize=6)
    right.plot(counts, r2, color="tab:purple")
    right.set_ylim(0, 1.05)
    right.set_xlabel("patients nearest to the best patient")
    right.set_ylabel("quadratic fit R2")
    figure.tight_layout()
    return figure


def _predictions(plt, calibration, design_info, rows, series, report):
    """Draw the prediction bands read by read_bands (``series``)."""
    if not series:
        return None
    outputs = list(dict.fromkeys(b["id"] for b in series))[:MAX_OUTPUTS]
    arms = list(dict.fromkeys(b["arm"] for b in series))[:MAX_ARMS]
    figure, axes = plt.subplots(
        len(outputs),
        len(arms),
        figsize=(3 * len(arms) + 1, 2.4 * len(outputs) + 0.5),
        squeeze=False,
    )
    for i, output in enumerate(outputs):
        for j, arm in enumerate(arms):
            axis = axes[i][j]
            axis.tick_params(labelsize=7)
            band = [b for b in series if b["id"] == output and b["arm"] == arm]
            times = [b["time"] for b in band]
            if band:
                axis.fill_between(
                    times,
                    [b["low"] for b in band],
                    [b["high"] for b in band],
                    color="tab:blue",
                    alpha=0.15,
                )
                axis.fill_between(
                    times,
                    [b["q05"] for b in band],
                    [b["q95"] for b in band],
                    color="tab:blue",
                    alpha=0.35,
                )
                line = [(b["time"], b["best"]) for b in band if b["best"] is not None]
                axis.plot(
                    [t for t, _ in line],
                    [v for _, v in line],
                    color="black",
                    linewidth=1.2,
                )
            if i == 0:
                axis.set_title(arm, fontsize=9)
            if j == 0:
                axis.set_ylabel(output, fontsize=8)
            if i == len(outputs) - 1:
                axis.set_xlabel("time", fontsize=8)
    figure.tight_layout()
    return figure
