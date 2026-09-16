#!/usr/bin/env python3
"""Check a converted model against independent references.

Two checks, and they prove different things:

- **parse**  compares the converter's reading of the control stream against
  nonmem2rx's. Agreement means the model was *read* correctly. Needs R with
  nonmem2rx; skipped with a clear message when R is absent.
- **solve**  compares a Jinko model's output against a local integration of the
  same equations. Agreement means the emitted model and the platform reproduce
  what was read. It says nothing about whether the reading was right.

Run both. Neither substitutes for the other.

Read-only: this script creates and modifies nothing.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from nonmem2jinko import platform
from nonmem2jinko.convert import load_estimates

#: Jinko exposes the solver's own time grid as a requestable series.
TIME_SERIES = "Time"


def _load_estimates(control: Path, ext: str | None):
    """Final estimates from an .ext, or scraped from a listing when that is all.

    Without this the check compares a Jinkō model built from *final* estimates
    against a local solve using ``$THETA`` *initial* ones, and reports a large
    difference that is only a difference of basis. Since the skill requires this
    check to pass, that reads as a broken conversion when nothing is wrong.
    """
    estimates, note = load_estimates(control, ext)
    if note:
        print(f"note: {note}", file=sys.stderr)
    return estimates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a converted NONMEM model against independent references."
    )
    parser.add_argument(
        "control_stream", help="Path to the .mod, .ctl, .cfl or .lst file."
    )
    parser.add_argument("--ext", help="Path to the .ext final estimates file.")
    parser.add_argument(
        "--check",
        action="append",
        choices=["parse", "solve"],
        help="Which checks to run. Defaults to both. Repeatable.",
    )
    parser.add_argument(
        "--model-sid", help="Jinko model SID to solve, for example cm-1234-5678."
    )
    parser.add_argument("--dose", type=float, default=None, help="Dose to simulate.")
    parser.add_argument(
        "--time-unit",
        type=_time_unit,
        default="h",
        help=(
            "Unit used by NONMEM times and model dose parameters. The platform "
            "Time series is returned in seconds and converted to this unit. "
            "Defaults to h."
        ),
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Maximum relative error on the concentration time course.",
    )
    parser.add_argument(
        "--concentration-id",
        help="Timeseries id to pull from Jinko. Defaults to the model's first output.",
    )
    parser.add_argument(
        "--json-out",
        help="Write the checks' metrics here as JSON, for a pipeline to read.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing --json-out or --series-out files.",
    )
    parser.add_argument(
        "--reference",
        choices=["scipy", "rxode2", "nonmem"],
        default="scipy",
        help=(
            "What to compare Jinkō against. scipy (default) integrates this "
            "converter's own reading of the equations, which isolates the "
            "platform. rxode2 solves nonmem2rx's independent translation with "
            "an independent integrator, which checks the reading and the "
            "emitting too. nonmem reads PRED/IPRED out of a $TABLE the "
            "original run wrote, which is the reference implementation itself "
            "and needs no licence -- only the output file."
        ),
    )
    parser.add_argument(
        "--nonmem-table",
        help="$TABLE output file, for --reference nonmem.",
    )
    parser.add_argument(
        "--nonmem-column",
        default="PRED",
        help=(
            "Column to compare against, for --reference nonmem. PRED (default) "
            "is NONMEM's population prediction -- the typical individual, every "
            "ETA at zero, which is what the platform solves with its own "
            "descriptors left alone. IPRED uses each subject's own empirical "
            "Bayes estimates, so comparing it against a typical-individual "
            "solve measures the subject's random effects: it read 2.1e-01 here "
            "where PRED reads 2.9e-05."
        ),
    )
    parser.add_argument(
        "--subject",
        help=(
            "Subject whose rows to use from the $TABLE. Defaults to the first. "
            "A table holds every subject's rows in sequence, so reading TIME "
            "straight through gives a sawtooth nothing can match."
        ),
    )
    parser.add_argument(
        "--series-out",
        help=(
            "Write the two compared time courses here as CSV. A number says "
            "how close they are; the overlay says where they differ, which is "
            "what tells a reader whether the difference matters."
        ),
    )
    args = parser.parse_args()
    checks = set(args.check or ["parse", "solve"])
    outputs = [Path(path) for path in (args.json_out, args.series_out) if path]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.overwrite:
        print(
            "refusing to overwrite: "
            + ", ".join(str(path) for path in existing)
            + "\nPass --overwrite to replace them.",
            file=sys.stderr,
        )
        return 1

    from nonmem2jinko.ir import build

    control = Path(args.control_stream)
    model = build(control)
    estimates = _load_estimates(control, args.ext)

    metrics: dict[str, object] = {"source": str(control)}
    failures = 0

    if "parse" in checks:
        failures += _check_parse(model, estimates, args, metrics)

    if "solve" in checks:
        failures += _check_solve(model, estimates, args, metrics)

    statuses = {
        name: (metrics.get(name) or {}).get("status")
        for name in checks
        if isinstance(metrics.get(name), dict)
    }
    completed = [
        name for name, status in statuses.items() if status in {"pass", "fail"}
    ]
    unavailable_solve = "solve" in checks and statuses.get("solve") == "skipped"
    if not completed or unavailable_solve:
        reason = (
            "the requested solve check did not run"
            if unavailable_solve
            else "none of the requested checks ran"
        )
        print(f"FAILED: {reason}", file=sys.stderr)
        metrics["gate"] = {"status": "fail", "reason": reason}
        failures += 1

    metrics["failures"] = failures
    if args.json_out:
        import json

        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(metrics, indent=2, default=str) + "\n"
        )

    return 1 if failures else 0


def _check_parse(model, estimates, args, metrics: dict) -> int:
    from nonmem2jinko.validate import rxode

    print("== parse: our reading vs nonmem2rx ==")
    if not rxode.available():
        print("  skipped: Rscript is not on PATH")
        metrics["parse"] = {"status": "skipped", "reason": "no Rscript"}
        return 0
    missing = rxode.check_packages()
    if missing:
        print(f"  skipped: R cannot load {', '.join(missing)}")
        metrics["parse"] = {"status": "skipped", "reason": f"missing {missing}"}
        return 0
    try:
        reference = rxode.parse_with_nonmem2rx(args.control_stream)
    except rxode.RNotAvailable as error:
        print(f"  skipped: {error}")
        metrics["parse"] = {"status": "skipped", "reason": str(error)}
        return 0

    agreement = rxode.compare(model, reference, estimates=estimates)
    print(rxode.describe(agreement))
    metrics["parse"] = {
        "status": "pass" if agreement.agrees else "fail",
        "notes": list(getattr(agreement, "notes", ()) or ()),
        "differences": list(getattr(agreement, "differences", ()) or ()),
    }
    return 0 if agreement.agrees else 1


def _numeric(jinko_model, identifier: str) -> float | None:
    """A parameter's default value, or None when it is not a plain number."""
    try:
        component = jinko_model.components.get_parameter(identifier)
    except Exception:  # noqa: BLE001 - absence is the common case
        return None
    if component is None:
        return None
    try:
        return float(component.formula)
    except (TypeError, ValueError):
        return None


def _time_unit(value: str) -> str:
    """An accepted unit for translating the platform's seconds."""
    normalized = value.strip().lower()
    aliases = {
        "s": "s",
        "sec": "s",
        "second": "s",
        "seconds": "s",
        "min": "min",
        "minute": "min",
        "minutes": "min",
        "h": "h",
        "hr": "h",
        "hour": "h",
        "hours": "h",
        "d": "d",
        "day": "d",
        "days": "d",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise argparse.ArgumentTypeError(
            "time unit must be s, min, h, or d (common long forms are accepted)"
        ) from error


def _seconds_per_time_unit(unit: str) -> float:
    return {"s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0}[unit]


def _platform_grid(
    times: list[float], values: list[float], time_unit: str
) -> tuple[list[float], list[float]]:
    """Pair values with the platform's returned grid in the source time unit."""
    if not times or len(times) != len(values):
        raise ValueError(
            "the platform returned no usable Time series; the grid cannot be "
            "reconstructed safely because recorded events insert additional points"
        )
    divisor = _seconds_per_time_unit(time_unit)
    converted = [float(time) / divisor for time in times]
    paired = sorted(
        {round(when, 9): value for when, value in zip(converted, values)}.items()
    )
    return [when for when, _ in paired], [value for _, value in paired]


def _dosing_compartment(jinko_model, model) -> int:
    """Recover the compartment the emitted dose event actually targets."""
    from nonmem2jinko.naming import Naming

    events = jinko_model.components.list_events()
    described = {
        int(match.group(1))
        for event in events
        if (
            match := re.search(
                r"\binto compartment (\d+)\b",
                getattr(event, "description", None) or "",
                re.IGNORECASE,
            )
        )
    }
    if len(described) == 1:
        return described.pop()

    # Older or manually edited models may not retain the emitted description.
    naming = Naming(advan=model.advan)
    naming.register_states(model.states)
    updated = {target for event in events for target in event.updates}
    matched = [
        state.number
        for state in model.states
        if naming.state_by_number(state.number) in updated
        or f"infusionRate{naming.compartment_role(state.number)}" in updated
    ]
    return matched[0] if len(matched) == 1 else model.dosing_compartment


def _dosing_from_model(
    jinko_model, model, args
) -> tuple[list[tuple[float, float]], int]:
    """Read the dose schedule back off the created model.

    Guessing the dose is what makes a comparison meaningless: the local solve
    must be given exactly what the platform was given. Three shapes exist, and
    the model itself says which one it is -- numbered per-patient slots, a
    protocol-parameterised repeat, or a single dose.
    """
    slots: list[tuple[float, float]] = []
    index = 1
    while True:
        from nonmem2jinko.naming import dose_slot

        amount = _numeric(jinko_model, dose_slot("amount", index))
        time = _numeric(jinko_model, dose_slot("time", index))
        if amount is None or time is None:
            break
        slots.append((time, amount))
        index += 1

    # The duration is deliberately not read off the model: "D1 = THETA(4)" is a
    # reference, not a number, and falling back to a bolus when it cannot be
    # parsed disagrees with the platform by most of the peak. The reference
    # solve resolves it from the IR's own properties instead.
    compartment = _dosing_compartment(jinko_model, model)
    if compartment != model.dosing_compartment:
        print(
            f"  dosing compartment read from the model: {compartment} "
            f"(control-stream default is {model.dosing_compartment})"
        )

    if slots:
        print(f"  dosing read from the model: {len(slots)} per-patient slot(s)")
        return [pair for pair in slots if pair[1]], compartment

    dose = args.dose
    if dose is None:
        dose = _numeric(jinko_model, "dose")
    if dose is None:
        dose = 100.0
        print("  no dose parameter and no --dose; assuming 100")
    else:
        print(f"  dose read from the model: {dose:g}")

    interval = _numeric(jinko_model, "doseInterval") or 0.0
    count = int(_numeric(jinko_model, "doseCount") or 1)
    schedule = [(step * interval, dose) for step in range(max(count, 1))]
    if count > 1:
        print(f"  repeated {count} times every {interval:g}")
    return schedule, compartment


def _prediction_id(jinko_model) -> str | None:
    """The output to compare: the converter's prediction, not any old series.

    Choosing by name prefix picked up a $DES intermediate called ``center``
    instead of the concentration. The converter tags what it means as an
    output, so ask for that; the "Observed" variant is skipped because its
    residual terms are zero by default and only add noise to a structural
    comparison.
    """
    available = set(jinko_model.time_dependent_ids())
    tagged = [
        parameter.id
        for parameter in jinko_model.components.list_parameters()
        if parameter.has_tag("output") and parameter.id in available
    ]
    for candidate in tagged:
        if not candidate.endswith("Observed"):
            return candidate
    if tagged:
        return tagged[0]
    # No tags: fall back to the naming convention, then to anything at all.
    concentrations = sorted(i for i in available if i.startswith("c"))
    for candidate in concentrations:
        if not candidate.endswith("Observed"):
            return candidate
    return next(iter(concentrations), None) or next(iter(sorted(available)), None)


def _covariates_from_model(jinko_model, model) -> dict[str, float]:
    """Covariate values read back off the created model.

    Both sides must be given the same inputs or the comparison measures the
    inputs rather than the model. The emitter defaults a covariate to the
    observed median; defaulting it to zero here instead makes a
    weight-proportional volume zero, and the reference solve then divides by it
    and produces nothing at all.
    """
    from nonmem2jinko.naming import Naming

    naming = Naming(advan=model.advan)
    naming.register_states(model.states)
    values: dict[str, float] = {}
    for name in model.covariates:
        value = _numeric(jinko_model, naming.parameter(name))
        if value is None:
            print(
                f"  WARNING: covariate {name} has no numeric default in the "
                "model; the reference solve will use zero and the two may "
                "disagree for that reason alone",
                file=sys.stderr,
            )
            continue
        values[name] = value
    if values:
        print(
            "  covariates read from the model: "
            + ", ".join(f"{k}={v:g}" for k, v in sorted(values.items()))
        )
    return values


def _without_discontinuities(
    grid: list[float],
    observed: list[float],
    reference: list[float],
    schedule: list[tuple[float, float]],
    duration: float | None,
    tolerance: float = 1e-9,
) -> tuple[list[float], list[float], list[float], int]:
    """Drop grid points that land exactly on a bolus.

    A bolus is a step in the state, so the value reported *at* its time depends
    on whether the reporter looks before it or after -- a convention, not
    physics. NONMEM orders a dose record before an observation at the same time
    and so reports post-dose; the platform's grid value there is pre-dose.
    Comparing the two measures the convention and nothing else, and the gap is
    the whole dose over the volume, which dwarfs any real disagreement.

    An infusion has no such step -- the rate changes, the state does not -- so
    nothing is dropped for one.
    """
    if duration or not schedule:
        return grid, observed, reference, 0
    doses = [time for time, amount in schedule if amount]
    keep = [
        index
        for index, when in enumerate(grid)
        if not any(abs(when - time) <= tolerance for time in doses)
    ]
    dropped = len(grid) - len(keep)
    if not dropped:
        return grid, observed, reference, 0
    return (
        [grid[i] for i in keep],
        [observed[i] for i in keep],
        [reference[i] for i in keep],
        dropped,
    )


def _reference_series(
    model,
    args,
    *,
    estimates,
    covariates: dict[str, float],
    schedule: list[tuple[float, float]],
    duration: float | None,
    compartment: int,
    grid: list[float],
    observed: list[float],
) -> tuple[list[float], list[float], list[float], str]:
    """The series to compare Jinkō against, and a sentence saying what it is.

    Three references, and they are not interchangeable. Naming which one ran
    in the report matters: "agrees to 5e-06" means something different for
    each.
    """
    from nonmem2jinko.validate import local

    if args.reference == "scipy":
        reference = local.solve(
            model,
            dose=schedule[0][1] if schedule else 0.0,
            times=grid,
            estimates=estimates,
            covariates=covariates,
            compartment=compartment,
            schedule=schedule,
            duration=duration,
        ).values["concentration"]
        return (
            grid,
            observed,
            reference,
            "this converter's own equations, integrated with scipy -- "
            "isolates the platform, and says nothing about the reading",
        )

    if args.reference == "rxode2":
        from nonmem2jinko.validate import rxode

        if covariates:
            raise RuntimeError(
                "the rxode2 reference cannot yet apply covariate overrides; "
                "use --reference nonmem for this model"
            )
        if not rxode.available():
            raise RuntimeError("Rscript is not on PATH, so rxode2 cannot solve")
        missing = rxode.check_packages()
        if missing:
            raise RuntimeError(f"R cannot load {', '.join(missing)}")
        solved = rxode.solve_with_nonmem2rx(
            args.control_stream,
            times=grid,
            schedule=schedule or [(0.0, 0.0)],
            compartment=compartment,
            duration=duration,
            estimates=estimates,
        )
        reference = _align_reference(solved.times, solved.values, grid)
        return (
            grid,
            observed,
            reference,
            f"nonmem2rx's own translation solved in rxode2 (its {solved.column}) "
            "-- an independent parser and an independent integrator, so this "
            "covers the reading and the emitting as well as the platform",
        )

    # NONMEM itself, through the output it already wrote.
    from nonmem2jinko.estimates.table import parse_file as parse_table

    if not args.nonmem_table:
        raise RuntimeError("--reference nonmem needs --nonmem-table")
    table = parse_table(args.nonmem_table)
    column = args.nonmem_column
    if not table.has(column):
        alternative = "PRED" if column != "PRED" else "IPRED"
        if not table.has(alternative):
            raise RuntimeError(
                f"the table has neither {column} nor {alternative}; it has "
                + ", ".join(table.columns)
            )
        print(f"  {column} is not in the table; using {alternative}")
        column = alternative
    subject = args.subject or next(iter(table.subjects()), None)
    times, values = table.series(column, subject=subject)

    # The table's times are observation records, not a solver grid, so Jinkō's
    # series is interpolated onto them rather than the other way round.
    picked = [
        (time, value)
        for time, value in zip(times, values)
        if grid[0] <= time <= grid[-1]
    ]
    if len(picked) < 2:
        raise RuntimeError(
            f"only {len(picked)} of the table's times fall inside the solved "
            f"model solving window {grid[0]:g}-{grid[-1]:g}; widen the model's "
            "stored solving options before running this read-only check"
        )
    at = [time for time, _ in picked]
    # Say which happened. When the grid was chosen from these times nothing is
    # interpolated, and claiming otherwise understates the result.
    on_grid = sum(1 for time in at if any(abs(time - g) < 1e-9 for g in grid))
    how = (
        "read straight off the solved grid"
        if on_grid == len(at)
        else f"interpolated onto its observation times ({len(at) - on_grid} "
        f"of {len(at)} points fell between grid points)"
    )
    return (
        at,
        _interpolate(grid, observed, at),
        [value for _, value in picked],
        f"NONMEM's own {column} for subject {subject} from "
        f"{Path(args.nonmem_table).name} -- the reference implementation, {how}",
    )


def _interpolate(
    grid: list[float], values: list[float], at: list[float]
) -> list[float]:
    """Linear interpolation of a solved series onto other times."""
    out: list[float] = []
    for target in at:
        if target <= grid[0]:
            out.append(values[0])
            continue
        if target >= grid[-1]:
            out.append(values[-1])
            continue
        index = next(i for i, time in enumerate(grid) if time >= target)
        before, after = grid[index - 1], grid[index]
        span = after - before
        weight = 0.0 if span == 0 else (target - before) / span
        out.append(values[index - 1] * (1 - weight) + values[index] * weight)
    return out


def _align_reference(
    times: list[float], values: list[float], grid: list[float]
) -> list[float]:
    """Interpolate a finite reference series without extrapolating it."""
    if len(times) != len(values) or len(times) < 2:
        raise RuntimeError(
            f"rxode2 returned {len(times)} times and {len(values)} values"
        )
    if not all(math.isfinite(value) for value in [*times, *values]):
        raise RuntimeError("rxode2 returned non-finite times or values")
    pairs = sorted(zip(times, values))
    reference_times = [time for time, _ in pairs]
    if len(set(reference_times)) != len(reference_times):
        raise RuntimeError("rxode2 returned duplicate time points")
    if grid[0] < reference_times[0] or grid[-1] > reference_times[-1]:
        raise RuntimeError(
            "rxode2 did not cover the platform's complete solved time window"
        )
    return _interpolate(reference_times, [value for _, value in pairs], grid)


def _check_solve(model, estimates, args, metrics: dict) -> int:
    from nonmem2jinko.validate import local

    print("\n== solve: Jinko vs a local integration of the same equations ==")
    if not args.model_sid:
        print("  skipped: pass --model-sid to compare against a Jinko model")
        metrics["solve"] = {"status": "skipped", "reason": "no --model-sid"}
        return 0

    client = platform.try_client_from_env()
    if client is None:
        metrics["solve"] = {"status": "skipped", "reason": "no Jinkō client"}
        return 0

    jinko_model = client.get_model(args.model_sid)

    schedule, compartment = _dosing_from_model(jinko_model, model, args)
    covariates = _covariates_from_model(jinko_model, model)
    try:
        resolved = local.resolve_parameters(
            model, estimates=estimates, covariates=covariates
        )
        duration = local.infusion_duration(
            model,
            resolved,
            compartment,
            schedule[0][1] if schedule else 0.0,
        )
    except (RuntimeError, ValueError) as error:
        print(f"  FAILED: {error}", file=sys.stderr)
        metrics["solve"] = {"status": "fail", "reason": str(error)}
        return 1

    identifier = args.concentration_id or _prediction_id(jinko_model)
    if not identifier:
        print("  FAILED: the model exposes no time-dependent output to compare")
        metrics["solve"] = {"status": "fail", "reason": "no output to compare"}
        return 1
    if not args.concentration_id:
        print(f"  comparing timeseries: {identifier}")

    # No overrides: both sides use the model's own defaults, so a disagreement
    # is a disagreement about the model rather than about its inputs.
    #
    # "Time" is a requestable series and the grid must come from it, never be
    # reconstructed from tMin/tStep. A recorded event inserts its own pre- and
    # post-trigger points, so a model with a dosing event returns more values
    # than the step count implies -- and a reconstructed grid then pairs every
    # value with the wrong time and reports a difference that is not there.
    overrides = {"dose": f"{args.dose:g}"} if args.dose is not None else {}
    output = jinko_model.simple_solve(
        timeseries_ids=[TIME_SERIES, identifier], overrides=overrides or None
    )
    if output.error:
        print(f"  FAILED: Jinko reported {output.error}", file=sys.stderr)
        metrics["solve"] = {"status": "fail", "reason": str(output.error)}
        return 1
    series = next((s for s in output.results if s.id == identifier), None)
    clock = next((s for s in output.results if s.id == TIME_SERIES), None)
    values = list(series.values) if series else []
    times = list(clock.values) if clock else []
    if len(values) < 2:
        print(
            "  FAILED: Jinko returned a constant series. A concentration that "
            "reads constant usually means its parameter was emitted as "
            "constant and evaluated once at t=0.",
            file=sys.stderr,
        )
        metrics["solve"] = {"status": "fail", "reason": "constant series"}
        return 1

    try:
        # Results come back in seconds whatever the model's declared time unit.
        grid, observed = _platform_grid(times, values, args.time_unit)
    except ValueError as error:
        print(f"  FAILED: {error}", file=sys.stderr)
        metrics["solve"] = {"status": "fail", "reason": str(error)}
        return 1

    try:
        grid, observed, reference, basis = _reference_series(
            model,
            args,
            estimates=estimates,
            covariates=covariates,
            schedule=schedule,
            duration=duration,
            compartment=compartment,
            grid=grid,
            observed=observed,
        )
    except (RuntimeError, ValueError) as error:
        print(f"  FAILED: {error}", file=sys.stderr)
        metrics["solve"] = {"status": "fail", "reason": str(error)}
        return 1
    print(f"  reference: {basis}")

    grid, observed, reference, dropped = _without_discontinuities(
        grid, observed, reference, schedule, duration
    )
    if dropped:
        print(
            f"  {dropped} point(s) coinciding with a bolus excluded: the value "
            "*at* a discontinuity is a reporting convention, not physics"
        )
    if len(grid) < 2:
        print("  FAILED: nothing left to compare after excluding dose times")
        metrics["solve"] = {"status": "fail", "reason": "no comparable points"}
        return 1

    comparison = local.compare(observed, reference, grid, tolerance=args.tolerance)
    if args.series_out:
        target = Path(args.series_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = ["time,jinko,reference"]
        rows += [
            f"{when:.10g},{got:.10g},{want:.10g}"
            for when, got, want in zip(grid, observed, reference)
        ]
        target.write_text("\n".join(rows) + "\n")
        print(f"  series written to {target}")
    print("  " + comparison.describe())
    if comparison.note:
        print(f"  {comparison.note}")
    metrics["solve"] = {
        "status": "pass" if comparison.passes else "fail",
        "reference": args.reference,
        "reference_basis": basis,
        "timeseries": identifier,
        "points": len(observed),
        "worst_relative_error": comparison.max_relative_error,
        "worst_absolute_error": comparison.max_absolute_error,
        "reference_peak": comparison.reference_peak,
        "cmax_relative_error": comparison.cmax_relative_error,
        "auc_relative_error": comparison.auc_relative_error,
        "tolerance": args.tolerance,
        "note": comparison.note or "",
    }
    metrics["worst_relative_error"] = comparison.max_relative_error
    return 0 if comparison.passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
