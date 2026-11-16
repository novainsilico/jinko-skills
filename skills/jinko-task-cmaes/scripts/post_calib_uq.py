#!/usr/bin/env python3
"""Qualify the parameter uncertainty of a completed Jinkō calibration.

The skill calls these commands for deterministic data handling and maths. They
are an implementation detail, not a CLI for users to learn.

One run directory holds one calibration revision:

- ``calibration.json``: inputs, priors, and best patient (``best``).
- ``design.csv`` and ``design.json``: the exploration Vpop (``design``).
- ``trial.json``: the exploration Vpop and Trial in Jinkō (``trial``).
- ``results.csv``: one row per patient, parameters and scores (``fetch``).
- ``bands.csv``: prediction bands of the near-optimal patients per model
  output, arm, and time (``fetch``).
- ``report.json``, ``report.md``, and ``plots/``: gates, analyses, and next
  steps (``analyze``).
- ``items.json``, ``document.md``, and ``document.upload.md``: the Jinkō
  document of the report, with cards of the linked project items (``publish``).

The exploration Vpop has three groups of patients, named by ``patientIndex``:

- ``best``: the best calibration patient, to check that the trial reproduces
  its score.
- ``profile-<i>-<k>``: one-at-a-time slices of parameter ``i`` over the
  explored range, all other parameters at their best value.
- ``sobol-<b>-<k>``: Sobol samples of three nested boxes around the best
  patient (joint landscape): the explored range, then 1/3 and 1/9 of it.
  Smaller boxes put patients near the best patient, where the near-optimal
  region of a well-identified parameter can be narrow.

The explored range is best / 2 to best x 2 by default (``--factor``), clipped
to the prior bounds. ``--mode prior`` explores the prior bounds, and
``--ranges`` takes ranges per parameter, for example from biological knowledge.

Scores are Jinkō scores: ``optimizationWeightedScore`` is the weighted mean of
the objective scores, and 1 is a perfect fit. A patient is near-optimal when
its score is at most ``delta`` below the best score.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CALIBRATION = "calibration.json"
DESIGN_CSV = "design.csv"
DESIGN = "design.json"
TRIAL = "trial.json"
RESULTS = "results.csv"
BANDS = "bands.csv"
BAND_COLUMNS = ["id", "arm", "time", "best", "low", "q05", "q95", "high", "patients"]
REPORT_JSON = "report.json"
REPORT_MD = "report.md"
ITEMS = "items.json"
DOCUMENT_MD = "document.md"
DOCUMENT_UPLOAD = "document.upload.md"
SCORE = "optimizationWeightedScore"
TRIAL_INPUT_KEYS = (
    "computationalModelId",
    "protocolDesignId",
    "dataTableDesigns",
    "solvingOptions",
    "scoringDesignId",
    "measureDesignId",
)

# Gate defaults, on the Jinkō score scale (1 is a perfect fit).
DELTA = 0.05
OPTIMUM_TOLERANCE = 0.01
REPRODUCE_TOLERANCE = 1e-3
MAX_FAILED_FRACTION = 0.05
BOUND_MARGIN = 0.01
PRIOR_SIGMA_LIMIT = 3.0
CORRELATION_LIMIT = 0.8
MIN_CORRELATION_SAMPLES = 10
CONDITION_LIMIT = 1e-2
MIN_R2 = 0.5
FIT_WINDOW = 4.0  # in units of delta
# Sobol boxes: the explored range, then 1/3 and 1/9 of it around the best value,
# so that a well-identified parameter still has near-optimal patients.
BOX_FRACTIONS = (1.0, 1 / 3, 1 / 9)
MISSED_SCORE = 0.5
MAX_PARAMETERS = 10  # above this, the joint (quadratic) check needs too many samples
GOOD_FIT_R2 = 0.9


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run the previous step first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def refuse_overwrite(paths: list[Path], *, overwrite: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"{', '.join(existing)} exists; pass --overwrite to replace it"
        )


def as_float(value: Any) -> float | None:
    """Return a finite float, or None for a missing, infinite, or invalid value."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def jinko_client():
    try:
        from jinko import JinkoClient
    except ImportError as error:  # pragma: no cover - environment specific
        raise SystemExit("jinko-sdk is not installed: run jinko-sdk-setup") from error
    return JinkoClient()


# --------------------------------------------------------------------------- #
# best: read the calibration and its best patient
# --------------------------------------------------------------------------- #


def pick_revision(calibration: Any, label: str | None) -> int | None:
    if label is None:
        return None
    for version in calibration.versions.iter(only_labeled=True):
        if version.label == label:
            return version.revision
    raise ValueError(f"no calibration version has the label {label!r}")


def best_patient(calibration: Any, arms: list[str]) -> dict[str, Any]:
    """Return the best patient's iteration, number, scores, and descriptors."""
    # The API sorts by descending score. It rejects "<id> desc".
    ranked = calibration.results.sorted_patients(sort_by=SCORE)
    if not ranked:
        raise ValueError("the calibration has no scored patient")
    top = ranked[0]
    raw = calibration.results.scalars_per_patient(
        patient_number=top["patientNumber"],
        scalars=[],
        arms=[*arms, "crossArms"],
        iteration=int(top["iteration"]),
    )
    scores: dict[str, float] = {}
    descriptors: dict[str, float] = {}
    for output in raw.get("outputs", []):
        arm = output.get("scenarioArm")
        for scalar in output.get("res", []):
            kind = (scalar.get("type") or {}).get("type")
            value = as_float(scalar.get("value"))
            if value is None:
                continue
            if kind == "BaselineInput" and arm == "crossArms":
                descriptors[scalar["id"]] = value
            elif arm == "crossArms" or scalar["id"] not in scores:
                scores[scalar["id"]] = value
    if SCORE not in scores:
        raise ValueError(f"the best patient has no {SCORE}")
    return {
        "patient_number": top["patientNumber"],
        "iteration": int(top["iteration"]),
        "score": scores[SCORE],
        "scores": scores,
        "descriptors": descriptors,
    }


def parameter_records(
    priors: list[dict[str, Any]], descriptors: dict[str, float]
) -> list[dict[str, Any]]:
    records = []
    for prior in priors:
        identifier = prior["id"]
        best = descriptors.get(f"{identifier}.tmin", descriptors.get(identifier))
        if best is None:
            raise ValueError(f"the best patient has no value for {identifier}")
        records.append({
            "id": identifier,
            "log": bool(prior.get("logTransform")),
            "best": best,
            "min_bound": as_float(prior.get("minBound")),
            "max_bound": as_float(prior.get("maxBound")),
            "mean": as_float(prior.get("mean")),
            "std": as_float(prior.get("std")),
        })
    return records


def best(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    refuse_overwrite([directory / CALIBRATION], overwrite=args.overwrite)
    client = jinko_client()
    calibration = client.get_calibration(args.calibration)
    revision = (
        args.revision
        if args.revision is not None
        else pick_revision(calibration, args.label)
    )
    if revision is not None:
        calibration = client.get_calibration(args.calibration, revision=revision)
    status = (calibration.status() or {}).get("status")
    if status != "completed":
        raise ValueError(f"the calibration status is {status!r}, not 'completed'")
    content = calibration.content(revision=revision)
    arms = list(calibration.results_summary().get("arms", []))
    top = best_patient(calibration, arms)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "calibration": {
            "sid": calibration.sid,
            "revision": revision,
            "core_id": calibration.core_id,
            "snapshot_id": calibration.snapshot_id,
            "url": calibration.url_with_fixed_revision(revision),
            "card_url": calibration.url,
        },
        "trial_inputs": {
            key: content[key]
            for key in TRIAL_INPUT_KEYS
            if content.get(key) is not None
        },
        "objectives": calibration.objective_weights() or {},
        "arms": arms,
        "best": {
            key: top[key] for key in ("patient_number", "iteration", "score", "scores")
        },
        "parameters": parameter_records(content["parameters"], top["descriptors"]),
    }
    write_json(directory / CALIBRATION, payload)
    print(
        json.dumps(
            {
                "calibration": payload["calibration"]["url"],
                "best_score": top["score"],
                "parameters": {p["id"]: p["best"] for p in payload["parameters"]},
            },
            indent=2,
        )
    )
    return 0


# --------------------------------------------------------------------------- #
# design: the exploration Vpop
# --------------------------------------------------------------------------- #


def transform(value: float, log: bool) -> float:
    if log:
        if value <= 0:
            raise ValueError(f"log-transformed value must be positive, got {value}")
        return math.log10(value)
    return value


def untransform(value: float, log: bool) -> float:
    return 10.0**value if log else value


def explore_range(
    parameter: dict[str, Any],
    *,
    mode: str,
    factor: float,
    custom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an explored range of one parameter, in physical units.

    ``local`` explores [best / factor, best * factor], clipped to the prior
    bounds. ``prior`` explores the prior bounds, or mean +/- 3 std where a bound
    is missing. A custom entry (``min``, ``max``, ``log``) wins over both.
    ``log`` tells whether the range is sampled in log10(x).
    """
    log = bool((custom or {}).get("log", parameter["log"]))
    best_value = parameter["best"]
    low_bound, high_bound = parameter["min_bound"], parameter["max_bound"]
    if custom and custom.get("min") is not None and custom.get("max") is not None:
        low, high = float(custom["min"]), float(custom["max"])
    elif mode == "local":
        if best_value <= 0:
            raise ValueError(
                f"{parameter['id']}: best value {best_value} is not positive; "
                "use --mode prior or a custom range"
            )
        low, high = best_value / factor, best_value * factor
        if low_bound is not None:
            low = max(low, low_bound)
        if high_bound is not None:
            high = min(high, high_bound)
    elif mode == "prior":
        mean, std = parameter["mean"], parameter["std"]
        spread = (
            None if mean is None or std is None else (mean - 3 * std, mean + 3 * std)
        )
        if low_bound is not None:
            low = low_bound
        elif spread is not None:
            low = untransform(spread[0], parameter["log"])
        else:
            raise ValueError(f"{parameter['id']}: no lower bound and no prior")
        if high_bound is not None:
            high = high_bound
        elif spread is not None:
            high = untransform(spread[1], parameter["log"])
        else:
            raise ValueError(f"{parameter['id']}: no upper bound and no prior")
    else:
        raise ValueError(f"unknown mode {mode!r}")
    if not low < high:
        raise ValueError(f"{parameter['id']}: empty range [{low}, {high}]")
    low, high = min(low, best_value), max(high, best_value)
    if log and low <= 0:
        raise ValueError(
            f"{parameter['id']}: log range must be positive, got [{low}, {high}]"
        )
    return {"min": low, "max": high, "log": log}


def profile_range(box: dict[str, Any]) -> dict[str, Any]:
    """Return the slice range: the explored range, log-spaced when it is positive."""
    return {"min": box["min"], "max": box["max"], "log": box["min"] > 0}


def nested_box(
    parameter: dict[str, Any], box: dict[str, Any], fraction: float
) -> dict[str, Any]:
    """Shrink an explored range around the best value, in its own coordinates.

    In log coordinates, a fraction of 1/3 turns best / f to best x f into
    best / f^(1/3) to best x f^(1/3).
    """
    log = box["log"]
    center = transform(parameter["best"], log)
    low, high = transform(box["min"], log), transform(box["max"], log)
    return {
        "min": untransform(center - (center - low) * fraction, log),
        "max": untransform(center + (high - center) * fraction, log),
        "log": log,
    }


def profile_grid(center: float, low: float, high: float, points: int) -> list[float]:
    """Return profile points, dense near the best value: offsets grow as (k / n)^2."""
    spans = [center - low, high - center]
    sides = [s > 1e-12 for s in spans]
    per_side = (
        [(points - 1) // 2] * 2
        if all(sides)
        else [points - 1 if s else 0 for s in sides]
    )
    grid = [center]
    for direction, span, count in (
        (-1, spans[0], per_side[0]),
        (1, spans[1], per_side[1]),
    ):
        grid += [
            center + direction * span * (k / count) ** 2 for k in range(1, count + 1)
        ]
    return sorted(grid)


def build_design(
    parameters: list[dict[str, Any]],
    boxes: list[dict[str, dict[str, Any]]],
    profiles: dict[str, dict[str, Any]],
    *,
    sobol_log2: int,
    profile_points: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Return patients as {"patientIndex": ..., <parameter id>: value}."""
    from scipy.stats import qmc

    ids = [p["id"] for p in parameters]
    best_values = {p["id"]: p["best"] for p in parameters}

    def edges(rng: dict[str, Any]) -> tuple[float, float]:
        return transform(rng["min"], rng["log"]), transform(rng["max"], rng["log"])

    patients = [{"patientIndex": "best", **best_values}]
    for i, identifier in enumerate(ids):
        grid = profile_grid(
            transform(best_values[identifier], profiles[identifier]["log"]),
            *edges(profiles[identifier]),
            profile_points,
        )
        for k, t in enumerate(grid):
            patients.append({
                "patientIndex": f"profile-{i}-{k}",
                **best_values,
                identifier: untransform(t, profiles[identifier]["log"]),
            })
    for b, box in enumerate(boxes):
        sampler = qmc.Sobol(len(ids), scramble=True, seed=seed + b)
        for k, unit in enumerate(sampler.random_base2(sobol_log2)):
            values = {}
            for identifier, u in zip(ids, unit, strict=True):
                low, high = edges(box[identifier])
                values[identifier] = untransform(
                    low + (high - low) * float(u), box[identifier]["log"]
                )
            patients.append({"patientIndex": f"sobol-{b}-{k}", **values})
    return patients


def group_of(patient_index: str, ids: list[str]) -> str:
    """Return ``best``, ``sobol``, or the swept parameter id."""
    if patient_index.startswith("profile-"):
        return ids[int(patient_index.split("-")[1])]
    return patient_index.split("-")[0]


def range_summary(box: dict[str, dict[str, Any]]) -> dict[str, list[float]]:
    return {identifier: [rng["min"], rng["max"]] for identifier, rng in box.items()}


def design(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    refuse_overwrite(
        [directory / DESIGN_CSV, directory / DESIGN], overwrite=args.overwrite
    )
    if args.profile_points < 3:
        raise ValueError("--profile-points must be at least 3")
    calibration = read_json(directory / CALIBRATION)
    parameters = calibration["parameters"]
    custom = json.loads(Path(args.ranges).read_text()) if args.ranges else {}
    unknown = sorted(set(custom) - {p["id"] for p in parameters})
    if unknown:
        raise ValueError(f"custom ranges for unknown parameters: {unknown}")
    if args.factor <= 1:
        raise ValueError("--factor must be greater than 1")
    box = {
        p["id"]: explore_range(
            p, mode=args.mode, factor=args.factor, custom=custom.get(p["id"])
        )
        for p in parameters
    }
    boxes = [
        {p["id"]: nested_box(p, box[p["id"]], fraction) for p in parameters}
        for fraction in BOX_FRACTIONS
    ]
    profiles = {p["id"]: profile_range(box[p["id"]]) for p in parameters}
    patients = build_design(
        parameters,
        boxes,
        profiles,
        sobol_log2=args.sobol_log2,
        profile_points=args.profile_points,
        seed=args.seed,
    )
    write_csv(
        directory / DESIGN_CSV,
        patients,
        ["patientIndex", *[p["id"] for p in parameters]],
    )
    write_json(
        directory / DESIGN,
        {
            "mode": args.mode,
            "factor": args.factor,
            "box_fractions": list(BOX_FRACTIONS),
            "sobol_log2": args.sobol_log2,
            "profile_points": args.profile_points,
            "seed": args.seed,
            "box": box,
            "boxes": boxes,
            "profiles": profiles,
            "patients": len(patients),
        },
    )
    print(
        json.dumps({"patients": len(patients), "ranges": range_summary(box)}, indent=2)
    )
    return 0


# --------------------------------------------------------------------------- #
# trial: create and run the exploration trial
# --------------------------------------------------------------------------- #


def trial(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    calibration = read_json(directory / CALIBRATION)
    design_info = read_json(directory / DESIGN)
    if not (directory / DESIGN_CSV).exists():
        raise FileNotFoundError(
            f"{directory / DESIGN_CSV} is missing: run design first"
        )
    name = args.name or f"UQ {calibration['calibration']['sid']}"
    arms = max(1, len(calibration.get("arms", [])))
    plan = {
        "vpop": f"{name} vpop ({design_info['patients']} patients)",
        "simulations": design_info["patients"] * arms,
        "arms": arms,
        "explored_ranges": range_summary(design_info["box"]),
        "trial": name,
        "folder": args.folder,
        "inputs": sorted(calibration["trial_inputs"]),
    }
    if not args.apply:
        print(json.dumps({"dry_run": True, **plan}, indent=2))
        return 0
    refuse_overwrite([directory / TRIAL], overwrite=args.overwrite)
    client = jinko_client()
    vpop = client.create_vpop_from_csv(
        csv_file_path=directory / DESIGN_CSV, name=f"{name} vpop", folder=args.folder
    )
    payload = {
        **calibration["trial_inputs"],
        "vpopId": {"coreItemId": vpop.core_id, "snapshotId": vpop.snapshot_id},
    }
    created = client.create_trial_from_json(
        json_content=payload, name=name, folder=args.folder
    )
    created.run()
    record = {
        "created_at": datetime.now(UTC).isoformat(),
        "folder": args.folder,
        "vpop": {"sid": vpop.sid, "url": vpop.url},
        "trial": {"sid": created.sid, "url": created.url},
    }
    write_json(directory / TRIAL, record)
    print(json.dumps(record, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# fetch: download the trial results
# --------------------------------------------------------------------------- #


def wide_results(
    rows: list[dict[str, Any]], parameter_ids: list[str], score_ids: list[str]
) -> list[dict[str, Any]]:
    """Pivot tidy scalar rows (patientId, scalarId, armId, value) to one row per patient.

    Scores come from ``crossArms`` when present, otherwise from the only arm.
    An objective that exists on several arms only gets one column per arm,
    named ``<id>@<arm>``.
    """
    descriptor_of = {f"{identifier}.tmin": identifier for identifier in parameter_ids}
    arms_of: dict[str, set[str]] = {}
    for row in rows:
        if row["scalarId"] in score_ids:
            arms_of.setdefault(row["scalarId"], set()).add(row["armId"])
    table: dict[str, dict[str, Any]] = {}
    for row in rows:
        patient = table.setdefault(row["patientId"], {"patientIndex": row["patientId"]})
        scalar, arm = row["scalarId"], row["armId"]
        value = as_float(row["value"])
        if scalar in descriptor_of:
            patient.setdefault(descriptor_of[scalar], value)
        elif scalar in score_ids:
            arms = arms_of[scalar]
            if "crossArms" in arms:
                if arm == "crossArms":
                    patient[scalar] = value
            elif len(arms) == 1:
                patient[scalar] = value
            else:
                patient[f"{scalar}@{arm}"] = value
    return list(table.values())


def output_ids(summary: dict[str, Any]) -> list[str]:
    """Return the model time series of a trial, without Time and solver counters."""
    return [
        series["id"]
        for series in summary.get("timeseries", [])
        if series["id"] != "Time" and not series["id"].startswith("__")
    ]


def near_optimal_ids(rows: list[dict[str, Any]], delta: float) -> set[str]:
    """Return the patients at most delta below the best patient's score."""
    best_score = next((r.get(SCORE) for r in rows if r["patientIndex"] == "best"), None)
    if best_score is None:
        return set()
    return {
        r["patientIndex"]
        for r in rows
        if r.get(SCORE) is not None and best_score - r[SCORE] <= delta
    }


def prediction_bands(frame: Any, near: set[str]) -> list[dict[str, Any]]:
    """Summarize model outputs per output, arm, and time: best line and near-optimal range.

    ``frame`` holds the trial time series (Patient Id, Arm, Descriptor, Time,
    Value). Storing the bands, not the series, keeps the run directory small.
    """
    order = {key: i for i, key in enumerate(dict.fromkeys(frame["Descriptor"]))}
    arm_order = {key: i for i, key in enumerate(dict.fromkeys(frame["Arm"]))}
    keys = ["Descriptor", "Arm", "Time"]
    values = frame[frame["Patient Id"].isin(near)].groupby(keys)["Value"]
    summary = values.agg(
        low="min",
        q05=lambda v: v.quantile(0.05),
        q95=lambda v: v.quantile(0.95),
        high="max",
        patients="count",
    )
    best = frame[frame["Patient Id"] == "best"].set_index(keys)["Value"]
    bands = [
        {
            "id": descriptor,
            "arm": arm,
            "time": time,
            "best": best.get((descriptor, arm, time)),
            **{k: row[k] for k in ("low", "q05", "q95", "high")},
            "patients": int(row["patients"]),
        }
        for (descriptor, arm, time), row in summary.iterrows()
    ]
    return sorted(bands, key=lambda b: (order[b["id"]], arm_order[b["arm"]], b["time"]))


def fetch(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    refuse_overwrite([directory / RESULTS, directory / BANDS], overwrite=args.overwrite)
    calibration = read_json(directory / CALIBRATION)
    record = read_json(directory / TRIAL)
    client = jinko_client()
    exploration = client.get_trial(record["trial"]["sid"])
    final = (
        exploration.wait_until_completed(timeout=args.timeout) or exploration.status()
    )
    status = final.get("status")
    if status != "completed":
        raise ValueError(f"the trial status is {status!r}, not 'completed'")
    parameter_ids = [p["id"] for p in calibration["parameters"]]
    score_ids = [SCORE, *calibration["objectives"]]
    frame = exploration.results.scalars([
        *score_ids,
        *[f"{identifier}.tmin" for identifier in parameter_ids],
    ]).to_dataframe()
    rows = wide_results(frame.to_dict("records"), parameter_ids, score_ids)
    columns = ["patientIndex", *parameter_ids]
    columns += sorted({key for row in rows for key in row} - set(columns))
    write_csv(directory / RESULTS, rows, columns)
    bands = []
    if not args.no_timeseries:
        summary = exploration.results.summary()
        ids = output_ids(summary)
        if ids:
            arms = list(summary.get("arms", []))
            frame = exploration.results.timeseries({
                identifier: arms for identifier in ids
            }).to_dataframe()
            bands = prediction_bands(frame, near_optimal_ids(rows, DELTA))
            write_csv(directory / BANDS, bands, BAND_COLUMNS)
    print(
        json.dumps(
            {
                "trial": record["trial"]["url"],
                "patients": len(rows),
                "band_rows": len(bands),
            },
            indent=2,
        )
    )
    return 0


# --------------------------------------------------------------------------- #
# analyze: gates and next steps
# --------------------------------------------------------------------------- #


def read_results(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return [
            {
                key: (value if key == "patientIndex" else as_float(value))
                for key, value in row.items()
            }
            for row in csv.DictReader(stream)
        ]


def to_z(value: float, rng: dict[str, Any]) -> float:
    """Map a physical value to [-1, 1] over an explored range."""
    low, high = transform(rng["min"], rng["log"]), transform(rng["max"], rng["log"])
    return 2.0 * (transform(value, rng["log"]) - low) / (high - low) - 1.0


def from_z(z: float, rng: dict[str, Any]) -> float:
    low, high = transform(rng["min"], rng["log"]), transform(rng["max"], rng["log"])
    return untransform(low + (z + 1.0) / 2.0 * (high - low), rng["log"])


def crossing(
    z: list[float], drop: list[float], z_best: float, delta: float, side: int
) -> float | None:
    """Return the first z beyond z_best (side -1 or +1) where drop reaches delta.

    Near a maximum the drop grows as the square of the distance, so the point
    is interpolated linearly in sqrt(drop). None means the drop stays below
    delta over the explored range on that side.
    """
    points = sorted(
        ((zi, di) for zi, di in zip(z, drop, strict=True) if (zi - z_best) * side > 0),
        key=lambda item: abs(item[0] - z_best),
    )
    previous_z, previous_drop = z_best, 0.0
    for zi, di in points:
        if di >= delta:
            low, high = math.sqrt(previous_drop), math.sqrt(di)
            if high == low:
                return zi
            fraction = (math.sqrt(delta) - low) / (high - low)
            return previous_z + fraction * (zi - previous_z)
        previous_z, previous_drop = zi, max(di, 0.0)
    return None


def profile_gate(
    parameter: dict[str, Any],
    rng: dict[str, Any],
    profile: list[dict[str, Any]],
    best_score: float,
    delta: float,
) -> dict[str, Any]:
    finite = [row for row in profile if row.get(SCORE) is not None]
    z = [to_z(row[parameter["id"]], rng) for row in finite]
    drop = [best_score - row[SCORE] for row in finite]
    z_best = to_z(parameter["best"], rng)
    sides = {}
    for name, side in (("lower", -1), ("upper", 1)):
        on_side = [
            d for zi, d in zip(z, drop, strict=True) if (zi - z_best) * side > 1e-12
        ]
        hit = crossing(z, drop, z_best, delta, side)
        sides[name] = {
            "explored": bool(on_side),
            "max_drop": max(on_side) if on_side else None,
            "limit": None if hit is None else from_z(hit, rng),
        }
    found = [sides[name]["limit"] is not None for name in ("lower", "upper")]
    status = {2: "identifiable", 1: "one-sided", 0: "not identifiable"}[sum(found)]
    return {
        "status": status,
        "interval": [sides["lower"]["limit"], sides["upper"]["limit"]],
        "sides": sides,
        "points": len(finite),
    }


def bound_gate(parameter: dict[str, Any], margin: float) -> str | None:
    """Return ``min`` or ``max`` when the best value sits on a prior bound."""
    low, high = parameter["min_bound"], parameter["max_bound"]
    log = parameter["log"]

    def usable(bound: float | None) -> bool:
        return bound is not None and (not log or bound > 0)

    width = (
        transform(high, log) - transform(low, log)
        if usable(low) and usable(high)
        else None
    )
    for name, bound in (("min", low), ("max", high)):
        if not usable(bound):
            continue
        distance = abs(transform(parameter["best"], log) - transform(bound, log))
        scale = width if width else max(abs(transform(bound, log)), 1.0)
        if distance <= margin * scale:
            return name
    return None


def prior_sigma(parameter: dict[str, Any]) -> float | None:
    """Return the distance of the best value to the prior mean, in prior standard deviations."""
    mean, std = parameter["mean"], parameter["std"]
    if mean is None or not std:
        return None
    if parameter["log"] and parameter["best"] <= 0:
        return None
    return (transform(parameter["best"], parameter["log"]) - mean) / std


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman correlation, or None when a variable is constant."""
    import warnings

    from scipy.stats import spearmanr

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # constant input: scipy warns and returns nan
        rho = float(spearmanr(x, y).statistic)
    return None if math.isnan(rho) else rho


def correlated_pairs(
    ids: list[str], z_rows: list[list[float]], limit: float, minimum: int
) -> dict[str, Any]:
    """Spearman correlations between parameters among near-optimal patients."""
    if len(z_rows) < minimum:
        return {"samples": len(z_rows), "pairs": None, "matrix": None}
    matrix = [
        [1.0 if i == j else None for j in range(len(ids))] for i in range(len(ids))
    ]
    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            rho = spearman([row[i] for row in z_rows], [row[j] for row in z_rows])
            matrix[i][j] = matrix[j][i] = rho
            if rho is not None and abs(rho) >= limit:
                pairs.append({"parameters": [ids[i], ids[j]], "rho": rho})
    return {"samples": len(z_rows), "pairs": pairs, "matrix": matrix}


def quadratic_fit(
    z_rows: list[list[float]], scores: list[float], center: list[float]
) -> dict[str, Any] | None:
    """Fit score = c + g.x + x.A.x with x = z - center; return the Hessian 2A."""
    import numpy as np

    x = np.asarray(z_rows, dtype=float) - np.asarray(center, dtype=float)
    y = np.asarray(scores, dtype=float)
    n, d = x.shape
    pairs = [(i, j) for i in range(d) for j in range(i, d)]
    if n < 2 * (1 + d + len(pairs)):
        return None
    design_matrix = np.column_stack([
        np.ones(n),
        x,
        *[x[:, i] * x[:, j] for i, j in pairs],
    ])
    coefficients, *_ = np.linalg.lstsq(design_matrix, y, rcond=None)
    residual = y - design_matrix @ coefficients
    total = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((residual**2).sum()) / total if total > 0 else 0.0
    hessian = np.zeros((d, d))
    for (i, j), c in zip(pairs, coefficients[1 + d :], strict=True):
        if i == j:
            hessian[i, i] = 2.0 * c
        else:
            hessian[i, j] = hessian[j, i] = c
    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    return {
        "samples": n,
        "r2": r2,
        "gradient": [float(g) for g in coefficients[1 : 1 + d]],
        "eigenvalues": [float(v) for v in eigenvalues],
        "eigenvectors": [[float(v) for v in eigenvectors[:, k]] for k in range(d)],
    }


def valley_reach(center: list[float], direction: list[float]) -> tuple[float, float]:
    """Return how far (t < 0, t > 0) one can move along a direction inside the box."""
    negative, positive = -math.inf, math.inf
    for c, w in zip(center, direction, strict=True):
        if abs(w) < 1e-12:
            continue
        a, b = (-1 - c) / w, (1 - c) / w
        negative, positive = max(negative, min(a, b)), min(positive, max(a, b))
    return min(negative, 0.0), max(positive, 0.0)


def joint_intervals(
    parameters: list[dict[str, Any]],
    box: dict[str, dict[str, Any]],
    curvature: dict[str, Any],
    delta: float,
    condition_limit: float = CONDITION_LIMIT,
    loading: float = 0.3,
) -> dict[str, dict[str, Any]]:
    """Return each parameter's joint interval from the fitted Hessian.

    A slice moves one parameter with the others fixed, so it misses
    compensations. In the quadratic model score = s0 + x.H.x / 2, the
    strong directions bound the near-optimal region by an ellipsoid; its
    half-width along parameter i is sqrt(2 delta sum_k v_ik^2 / -lambda_k).
    Along a weak direction (flat or positive curvature) the score stays
    near-optimal until a parameter reaches the edge of the explored box, so
    parameter i moves by its share of that valley. A limit outside the widest
    Sobol box is None.

    A parameter is compensated when its joint interval reaches the box edge
    and it loads on a weak direction with other parameters (its partners).
    """
    ids = [p["id"] for p in parameters]
    result = {i: {"joint_interval": None, "compensated_with": []} for i in ids}
    fit = curvature.get("fit")
    if fit is None or curvature["status"] == "inconclusive":
        return result
    eigen = list(zip(fit["eigenvalues"], fit["eigenvectors"], strict=True))
    largest = max(abs(value) for value, _ in eigen) or 1.0
    is_weak = [value >= 0 or -value / largest < condition_limit for value, _ in eigen]
    center = [to_z(p["best"], box[p["id"]]) for p in parameters]
    reaches = [
        valley_reach(center, v) if weak else None
        for (_, v), weak in zip(eigen, is_weak, strict=True)
    ]
    for k, identifier in enumerate(ids):
        half = math.sqrt(
            2
            * delta
            * sum(
                v[k] ** 2 / -value
                for (value, v), weak in zip(eigen, is_weak, strict=True)
                if not weak
            )
        )
        low, high = center[k] - half, center[k] + half
        partners: list[str] = []
        for (_, v), reach in zip(eigen, reaches, strict=True):
            if reach is None:
                continue
            ends = sorted((v[k] * reach[0], v[k] * reach[1]))
            low, high = low + ends[0], high + ends[1]
            if abs(v[k]) >= loading:
                partners += [
                    ids[j]
                    for j, c in enumerate(v)
                    if j != k and abs(c) >= loading and ids[j] not in partners
                ]
        edge = 1 - 1e-6
        result[identifier]["joint_interval"] = [
            from_z(low, box[identifier]) if low > -edge else None,
            from_z(high, box[identifier]) if high < edge else None,
        ]
        if (low <= -edge or high >= edge) and partners:
            result[identifier]["compensated_with"] = partners
    return result


def curvature_gate(
    ids: list[str], fit: dict[str, Any] | None, *, condition_limit: float, min_r2: float
) -> dict[str, Any]:
    if fit is None:
        return {
            "status": "inconclusive",
            "reason": "too few near-optimal samples",
            "weak_directions": [],
        }
    if fit["r2"] < min_r2:
        return {
            "status": "inconclusive",
            "reason": f"quadratic fit R2 {fit['r2']:.2f} < {min_r2}",
            "fit": fit,
            "weak_directions": [],
        }
    eigenvalues = fit["eigenvalues"]
    largest = max(abs(v) for v in eigenvalues) or 1.0
    weak = []
    for value, vector in zip(eigenvalues, fit["eigenvectors"], strict=True):
        if value >= 0 or abs(value) / largest < condition_limit:
            loads = sorted(
                ((ids[i], c) for i, c in enumerate(vector) if abs(c) >= 0.3),
                key=lambda item: -abs(item[1]),
            )
            weak.append({
                "eigenvalue": value,
                "direction": [{"parameter": p, "weight": c} for p, c in loads],
            })
    return {"status": "fail" if weak else "pass", "weak_directions": weak, "fit": fit}


def near_optimal(
    rows: list[dict[str, Any]], reference: float, window: float
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get(SCORE) is not None and reference - row[SCORE] <= window
    ]


def analyze_results(
    calibration: dict[str, Any],
    design_info: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    delta: float = DELTA,
    optimum_tolerance: float = OPTIMUM_TOLERANCE,
    reproduce_tolerance: float = REPRODUCE_TOLERANCE,
    max_failed_fraction: float = MAX_FAILED_FRACTION,
    bound_margin: float = BOUND_MARGIN,
    prior_sigma_limit: float = PRIOR_SIGMA_LIMIT,
    correlation_limit: float = CORRELATION_LIMIT,
    condition_limit: float = CONDITION_LIMIT,
    min_r2: float = MIN_R2,
) -> dict[str, Any]:
    parameters = calibration["parameters"]
    ids = [p["id"] for p in parameters]
    box, profiles = design_info["box"], design_info["profiles"]
    calibration_score = calibration["best"]["score"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(group_of(row["patientIndex"], ids), []).append(row)
    gates: dict[str, dict[str, Any]] = {}

    best_rows = groups.get("best", [])
    trial_score = best_rows[0].get(SCORE) if best_rows else None
    gap = None if trial_score is None else abs(trial_score - calibration_score)
    gates["reproduction"] = {
        "status": "pass"
        if gap is not None
        and gap <= reproduce_tolerance * max(1.0, abs(calibration_score))
        else "fail",
        "calibration_score": calibration_score,
        "trial_score": trial_score,
    }
    reference = trial_score if trial_score is not None else calibration_score

    failed = [row["patientIndex"] for row in rows if row.get(SCORE) is None]
    fraction = len(failed) / len(rows) if rows else 1.0
    gates["simulations"] = {
        "status": "pass" if fraction <= max_failed_fraction else "fail",
        "failed": len(failed),
        "total": len(rows),
    }

    scored = [row for row in rows if row.get(SCORE) is not None]
    top = max(scored, key=lambda row: row[SCORE]) if scored else None
    improvement = (top[SCORE] - reference) if top else 0.0
    gates["optimum"] = {
        "status": "pass" if improvement <= optimum_tolerance else "fail",
        "improvement": improvement,
        "better_patient": None
        if improvement <= optimum_tolerance
        else {
            "patientIndex": top["patientIndex"],
            "score": top[SCORE],
            "values": {identifier: top[identifier] for identifier in ids},
        },
    }

    per_parameter = {}
    for parameter in parameters:
        identifier = parameter["id"]
        profile = profile_gate(
            parameter,
            profiles[identifier],
            groups.get(identifier, []),
            reference,
            delta,
        )
        profile["at_bound"] = bound_gate(parameter, bound_margin)
        profile["prior_sigma"] = prior_sigma(parameter)
        profile["best"] = parameter["best"]
        profile["range"] = [profiles[identifier]["min"], profiles[identifier]["max"]]
        per_parameter[identifier] = profile
    gates["priors"] = {
        "status": "fail"
        if any(
            p["prior_sigma"] is not None and abs(p["prior_sigma"]) > prior_sigma_limit
            for p in per_parameter.values()
        )
        else "pass",
        "far": {
            k: v["prior_sigma"]
            for k, v in per_parameter.items()
            if v["prior_sigma"] is not None
            and abs(v["prior_sigma"]) > prior_sigma_limit
        },
    }
    gates["bounds"] = {
        "status": "fail"
        if any(p["at_bound"] for p in per_parameter.values())
        else "pass",
        "at_bound": {
            k: v["at_bound"] for k, v in per_parameter.items() if v["at_bound"]
        },
    }
    near = [
        row
        for row in near_optimal(scored, reference, FIT_WINDOW * delta)
        if all(row.get(i) is not None for i in ids)
    ]
    z_near = [[to_z(row[i], box[i]) for i in ids] for row in near]
    center = [to_z(p["best"], box[p["id"]]) for p in parameters]
    fit = quadratic_fit(z_near, [row[SCORE] for row in near], center) if near else None
    curvature = curvature_gate(ids, fit, condition_limit=condition_limit, min_r2=min_r2)
    acceptable = [
        [to_z(row[i], box[i]) for i in ids]
        for row in near_optimal(groups.get("sobol", []), reference, delta)
    ]
    correlation = correlated_pairs(
        ids, acceptable, correlation_limit, MIN_CORRELATION_SAMPLES
    )
    if len(ids) < 2:
        correlation_status = "pass"
    elif correlation["pairs"] is None:
        correlation_status = "inconclusive"
    else:
        correlation_status = "fail" if correlation["pairs"] else "pass"
    statuses = {curvature["status"], correlation_status}
    gates["correlations"] = {
        "status": "fail"
        if "fail" in statuses
        else ("inconclusive" if "inconclusive" in statuses else "pass"),
        "pairs": correlation["pairs"],
        "matrix": correlation["matrix"],
        "near_optimal_samples": correlation["samples"],
        "curvature": curvature,
    }

    joint = joint_intervals(parameters, box, curvature, delta, condition_limit)
    for identifier, profile in per_parameter.items():
        profile.update(joint[identifier])
        if profile["status"] == "identifiable" and profile["compensated_with"]:
            profile["status"] = "compensated"
    gates["identifiability"] = {
        "status": "pass"
        if all(p["status"] == "identifiable" for p in per_parameter.values())
        else "fail",
        "not_identifiable": [
            k for k, v in per_parameter.items() if v["status"] == "not identifiable"
        ],
        "one_sided": [
            k for k, v in per_parameter.items() if v["status"] == "one-sided"
        ],
        "compensated": [
            k for k, v in per_parameter.items() if v["status"] == "compensated"
        ],
    }

    objectives = objective_summary(rows, ids, delta)
    statuses = [gate["status"] for gate in gates.values()]
    verdict = (
        "FAIL"
        if "fail" in statuses
        else ("INCONCLUSIVE" if "inconclusive" in statuses else "PASS")
    )
    return {
        "verdict": verdict,
        "delta": delta,
        "reference_score": reference,
        "gates": gates,
        "parameters": per_parameter,
        "objectives": objectives,
        "notes": limit_notes(len(ids), gates["correlations"]["curvature"]),
        "next_steps": next_steps(gates, per_parameter, delta, objectives),
    }


def limit_notes(dimension: int, curvature: dict[str, Any]) -> list[str]:
    """Return the notes on the reliability of the joint check, when it is limited."""
    notes = []
    if dimension > MAX_PARAMETERS:
        notes.append(
            f"The calibration has {dimension} parameters. Above {MAX_PARAMETERS}, the "
            "local quadratic fit has too few samples per coefficient: weak directions "
            "and joint intervals become unreliable. Calibrate at most "
            f"{MAX_PARAMETERS} parameters at a time, in successive steps."
        )
    fit = curvature.get("fit")
    if fit is not None and fit["r2"] < GOOD_FIT_R2:
        notes.append(
            f"The local quadratic fit is approximate (R2 {fit['r2']:.2f} < {GOOD_FIT_R2}): "
            "some weak directions, and so some compensated parameters, can be noise. "
            "Check them against the slices and the pairs plot."
        )
    return notes


def band_notes(bands: list[dict[str, Any]]) -> list[str]:
    """Flag outputs that go negative for near-optimal patients but not for the best one.

    A concentration below zero is a solver artifact: the absolute tolerance is
    too loose for the scale of that output.
    """
    flagged: dict[str, set[str]] = {}
    for band in bands:
        best, low = band.get("best"), band.get("low")
        if best is not None and low is not None and best >= 0 and low < 0:
            flagged.setdefault(band["id"], set()).add(band["arm"])
    return [
        f"Some near-optimal patients give negative values of {output} "
        f"(arms: {', '.join(sorted(arms))}). For a concentration or an amount, "
        "this is a solver artifact: tighten the absolute tolerance of the "
        "solving options before relying on the prediction bands."
        for output, arms in flagged.items()
    ]


def objective_summary(
    rows: list[dict[str, Any]], ids: list[str], delta: float
) -> dict[str, dict[str, Any]]:
    """Return the best-patient score and the explored score range of each objective.

    An objective is ``missed`` when the best patient scores below MISSED_SCORE on it,
    and ``insensitive`` when no explored patient moves its score by delta / 10.
    """
    best_row = next((r for r in rows if r["patientIndex"] == "best"), {})
    columns = sorted({k for r in rows for k in r} - {"patientIndex", SCORE, *ids})
    summary = {}
    for column in columns:
        values = [r[column] for r in rows if r.get(column) is not None]
        if not values:
            continue
        best_value = best_row.get(column)
        spread = max(values) - min(values)
        if best_value is not None and best_value < MISSED_SCORE:
            status = "missed"
        elif spread < delta / 10:
            status = "insensitive"
        else:
            status = "fit"
        summary[column] = {"best": best_value, "spread": spread, "status": status}
    return summary


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def next_steps(
    gates: dict[str, Any],
    per_parameter: dict[str, Any],
    delta: float,
    objectives: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    steps = []
    if gates["reproduction"]["status"] == "fail":
        steps.append(
            "The trial does not reproduce the calibration best score. Compare the trial "
            "and calibration inputs (solving options, protocol, data tables) before "
            "trusting the other gates."
        )
    if gates["simulations"]["status"] == "fail":
        steps.append(
            "Too many exploration patients failed to simulate. Narrow the explored "
            "ranges or check solver tolerances, then rerun the exploration."
        )
    better = gates["optimum"]["better_patient"]
    if better:
        values = ", ".join(f"{k}={v:.4g}" for k, v in better["values"].items())
        steps.append(
            f"A better point exists (score +{gates['optimum']['improvement']:.3g}: {values}). "
            "The calibration did not converge: relaunch it with priors centered on this "
            "point or with more iterations."
        )
    for identifier, sigma in gates["priors"]["far"].items():
        steps.append(
            f"{identifier} is {sigma:+.1f} prior standard deviations from its prior mean. "
            "Check the prior source, or look for a model or data issue that the fit "
            "compensates for."
        )
    for identifier, side in gates["bounds"]["at_bound"].items():
        steps.append(
            f"{identifier} sits on its prior {side} bound. Widen the bound if it is "
            "biologically plausible, otherwise look for a missing or mis-specified "
            "parameter that the fit compensates for."
        )
    for identifier in gates["identifiability"]["not_identifiable"]:
        sides = per_parameter[identifier]["sides"]
        drops = [s["max_drop"] for s in sides.values() if s["max_drop"] is not None]
        largest = max(drops) if drops else 0.0
        if largest < delta / 2:
            steps.append(
                f"{identifier} has no effect on the score over the explored range "
                f"(largest drop {largest:.2g}). Fix it to a literature value, or add data "
                "from a scenario (dose, timepoint, washout) that is sensitive to it."
            )
        else:
            steps.append(
                f"{identifier} changes the score (largest drop {largest:.2g}) but stays "
                f"within {delta} of the best score. Widen the profile range "
                "(--factor or --ranges) to find its limits, or add data that constrains it."
            )
    for identifier in gates["identifiability"]["one_sided"]:
        sides = per_parameter[identifier]["sides"]
        open_side = "lower" if sides["lower"]["limit"] is None else "upper"
        if not sides[open_side]["explored"]:
            steps.append(
                f"{identifier}: the best value is at the edge of the profile range. "
                f"Extend it on the {open_side} side to close the interval."
            )
        else:
            closed = "an upper" if open_side == "lower" else "a lower"
            steps.append(
                f"{identifier} has only {closed} limit. Report the one-sided bound, "
                f"or add data that constrains its {open_side} values."
            )
    for pair in gates["correlations"]["pairs"] or []:
        a, b = pair["parameters"]
        steps.append(
            f"{a} and {b} compensate each other (rho={pair['rho']:.2f}). Fix one of them, "
            "reparameterize (ratio or product), or add data that decouples them."
        )
    compensated = gates["identifiability"]["compensated"]
    if compensated:
        order = list(per_parameter)
        involved = sorted(
            set(compensated).union(
                *(per_parameter[c]["compensated_with"] for c in compensated)
            ),
            key=order.index,
        )
        steps.append(
            f"{join_names(involved)} compensate each other: the data constrain "
            "combinations of them, not each value, and slice intervals understate "
            f"their uncertainty. The joint {'interval' if len(compensated) == 1 else 'intervals'} "
            f"of {join_names(compensated)} {'reaches' if len(compensated) == 1 else 'reach'} "
            "the edge of the explored range: widen it (--factor or --ranges) to see how "
            "far they go. Then fix some of these parameters to literature values, "
            "reparameterize, or add data that separates them. The local curvature table "
            "lists the combinations."
        )
    if gates["correlations"]["status"] == "inconclusive":
        steps.append(
            "The joint landscape check is inconclusive: increase --sobol-log2 or "
            "add a smaller box (--factor), then rerun."
        )
    for column, objective in (objectives or {}).items():
        if objective["status"] == "missed":
            steps.append(
                f"The best patient misses the objective {column} (score "
                f"{objective['best']:.2g}). The intervals describe this imperfect fit: "
                "check the model, the data, or the objective before relying on them."
            )
        elif objective["status"] == "insensitive":
            steps.append(
                f"No calibrated parameter moves the objective {column}. It does not "
                "inform this calibration: check its observable and time window."
            )
    if not steps:
        steps.append(
            "All gates pass. Report the slice and joint intervals with the calibration "
            "results."
        )
    return steps


def analyze(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import uq_report

    directory = Path(args.dir)
    calibration = read_json(directory / CALIBRATION)
    design_info = read_json(directory / DESIGN)
    rows = read_results(directory / RESULTS)
    record = read_json(directory / TRIAL) if (directory / TRIAL).exists() else None
    report = analyze_results(calibration, design_info, rows, delta=args.delta)
    bands = uq_report.read_bands(directory / BANDS)
    report["notes"] += band_notes(bands)
    images = []
    if not args.no_plots:
        images = uq_report.plots(
            directory, calibration, design_info, rows, bands, report
        )
        report["plots"] = images
    write_json(directory / REPORT_JSON, report)
    (directory / REPORT_MD).write_text(
        uq_report.markdown(report, calibration, design_info, record, images),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"verdict": report["verdict"], "report": str(directory / REPORT_MD)},
            indent=2,
        )
    )
    return 0


# --------------------------------------------------------------------------- #
# publish: the report as a Jinkō document
# --------------------------------------------------------------------------- #


def linked_items(
    client: Any, calibration: dict[str, Any], record: dict[str, Any]
) -> list[dict[str, str]]:
    """Return the project items to show as cards: calibration, its inputs, and the exploration."""
    source = calibration["calibration"]
    revision = source.get("revision")
    items = [
        {
            "label": "Source calibration"
            + (f", revision {revision}" if revision is not None else ""),
            "sid": source["sid"],
            "url": source.get("card_url") or source["url"].split("?")[0],
        }
    ]
    exploration = client.get_trial(record["trial"]["sid"])
    components = [
        ("Computational model", exploration.model),
        ("Protocol", exploration.protocol_design),
        *[("Data table", table) for table in exploration.data_tables],
        ("Advanced output set", exploration.advanced_output_set),
        ("Simple output set", exploration.simple_output_set),
    ]
    items += [
        {"label": label, "sid": item.sid, "url": item.url}
        for label, item in components
        if item is not None
    ]
    items += [
        {
            "label": "Exploration Vpop",
            "sid": record["vpop"]["sid"],
            "url": record["vpop"]["url"],
        },
        {
            "label": "Exploration trial",
            "sid": record["trial"]["sid"],
            "url": record["trial"]["url"],
        },
    ]
    return items


def run_document_cli(command: list[str]) -> int:
    """Run the jinko-document creation script (dry run, or apply with a digest)."""
    import subprocess

    return subprocess.run(command, check=False).returncode


def publish(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import uq_report

    directory = Path(args.dir)
    calibration = read_json(directory / CALIBRATION)
    design_info = read_json(directory / DESIGN)
    record = read_json(directory / TRIAL)
    report = read_json(directory / REPORT_JSON)
    upload = directory / DOCUMENT_UPLOAD
    if upload.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"{upload} exists; pass --overwrite to publish a new document"
            )
        if args.apply:
            upload.unlink()
    items = linked_items(jinko_client(), calibration, record)
    write_json(directory / ITEMS, items)
    text = uq_report.markdown(
        report, calibration, design_info, record, report.get("plots", []), items=items
    )
    (directory / DOCUMENT_MD).write_text(text, encoding="utf-8")
    source = calibration["calibration"]
    name = args.name or (
        f"UQ report {source['sid']}"
        + (
            f" revision {source['revision']}"
            if source.get("revision") is not None
            else ""
        )
    )
    command = [
        sys.executable,
        "-m",
        "jinko.cli.create_document_from_markdown",
        "--name",
        name,
        "--markdown-file",
        str(directory / DOCUMENT_MD),
        "--output-markdown",
        str(upload),
    ]
    folder = args.folder or record.get("folder")
    if folder:
        command += ["--folder", folder]
    if args.apply:
        command += ["--apply", "--confirm-digest", args.confirm_digest or ""]
    return run_document_cli(command)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = root.add_subparsers(dest="command", required=True)

    command = commands.add_parser(
        "best", help="read the calibration and its best patient"
    )
    command.add_argument("calibration", help="calibration SID")
    command.add_argument("--dir", required=True)
    choice = command.add_mutually_exclusive_group()
    choice.add_argument("--revision", type=int)
    choice.add_argument("--label")
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=best)

    command = commands.add_parser("design", help="write the exploration Vpop")
    command.add_argument("--dir", required=True)
    command.add_argument("--mode", choices=["local", "prior"], default="local")
    command.add_argument(
        "--factor",
        type=float,
        default=2.0,
        help="explored range: best / factor to best * factor, clipped to the prior bounds",
    )
    command.add_argument(
        "--ranges", help='JSON file: {"<id>": {"min": .., "max": .., "log": ..}}'
    )
    command.add_argument(
        "--sobol-log2", type=int, default=9, help="Sobol sample size is 2**N"
    )
    command.add_argument("--profile-points", type=int, default=21)
    command.add_argument("--seed", type=int, default=0)
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=design)

    command = commands.add_parser("trial", help="create and run the exploration trial")
    command.add_argument("--dir", required=True)
    command.add_argument("--folder", help="destination folder ID")
    command.add_argument("--name")
    command.add_argument(
        "--apply",
        action="store_true",
        help="create and run; without it, print the plan",
    )
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=trial)

    command = commands.add_parser(
        "fetch", help="wait for the trial and download results"
    )
    command.add_argument("--dir", required=True)
    command.add_argument("--timeout", type=float, default=None, help="seconds")
    command.add_argument(
        "--no-timeseries", action="store_true", help="skip the prediction bands"
    )
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=fetch)

    command = commands.add_parser(
        "publish", help="publish the report as a Jinkō document"
    )
    command.add_argument("--dir", required=True)
    command.add_argument(
        "--folder", help="destination folder ID (default: the trial's folder)"
    )
    command.add_argument("--name")
    command.add_argument(
        "--apply", action="store_true", help="create the document; without it, preview"
    )
    command.add_argument(
        "--confirm-digest", help="approval digest printed by the preview"
    )
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=publish)

    command = commands.add_parser("analyze", help="compute gates and write the report")
    command.add_argument("--dir", required=True)
    command.add_argument(
        "--delta", type=float, default=DELTA, help="near-optimal score drop"
    )
    command.add_argument(
        "--no-plots", action="store_true", help="skip plots/ (they need matplotlib)"
    )
    command.set_defaults(handler=analyze)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
