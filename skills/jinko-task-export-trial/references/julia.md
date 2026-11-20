# Julia

## The bundle

| Path | Content |
| --- | --- |
| `run.jl` | Entry point: `julia --project=. --threads=auto run.jl [results_dir] [--tight] [--resume]` |
| `README.md` | For the people who run the bundle: inputs, outputs, how it solves |
| `LICENCE` | Selected bundle license; Nova In Silico all rights reserved by default |
| `Project.toml`, `Manifest.toml` | Pinned Julia packages: Sundials, SciMLBase, JSON3 |
| `src/TrialModel.jl` | Generated model module: index tables and the `include` of each `src/model/` file |
| `src/model/*.jl` | Generated model, one file per component type (parameters, compartments, species, categoricals, rules, reactions, ODEs, events, outputs), with explicit unit conversion factors; each rule is computed once in `rules.jl` |
| `src/JinkoRuntime.jl` | Fixed runtime, the same for every trial |
| `src/ArmCache.jl` | Saved arms for the tight solves of `check` (`run.jl --reuse-arms`); a plain run does not load it |
| `data/vpop.csv` | One row per patient, values in the unit of each input |
| `data/protocol.csv` | One row per arm; a text cell is a categorical level or a compiled formula |
| `data/trial.json` | Solving options, solving times, outputs, scalar definitions, and scorings (data tables and advanced output set as formula trees) |
| `results/` | Written by `run.jl`: `timeseries.csv`, `metadata.csv`, `scalars.csv`, `cross_arm_scalars.csv`, `errors.csv` |
| `results/partial/<patient>/` | The same files for one patient, written as soon as all its arms finish; `run.jl` prints `patient k/N <id> done at <s> s` |
| `results/run.log` | Julia output of a `check` run |
| `results/run-summary.json` | Patient and run counts for the Julia invocation, and `failed_runs`: the runs that failed in the solver (listed in `errors.csv`) |

The runtime computes a patient's cross-arm measures before it releases that
patient's arrays. It assembles the final CSV files from complete patient
files, in patient-id order; `--resume` keeps the patients that
an earlier run into the same folder completed. The check reads matching
patients in a common order and keeps its content-validated partitions in
`results/.comparison/`.

Tight runs select one patient and one arm. With `--reuse-arms`, their raw
outputs are cached under `results/confirm/<patient>/tight/states/`, so
cross-arm measures can reuse completed tight arms. Resume accepts these
caches only when the bundle and reference fingerprints match. Patient names with unsafe path characters use
an injective encoded folder name; the CSV retains the original patient ID.

The user can swap `data/vpop.csv` for another population with the same
columns, or edit an arm row, and run again. A new column or a new formula
needs a new export.

The export API accepts `license_type="all-rights-reserved"` (default),
`"mit"`, `"nc"` (CC BY-NC 4.0), or `"source"`. For `"source"`, pass the
original full text as `source_license`, or supply a source license file in the
fetched-input folder. The CLI equivalents are `--license` and
`--source-license-file`. Ask the user's choice before generating the bundle.

## Install

Install Julia 1.13.1, the version that the bundle pins and the tests
validate, the way the user prefers: the official installer
(<https://julialang.org/downloads/>) or `juliaup add 1.13.1`, then
`juliaup default 1.13.1` (or call `julia +1.13.1`). Another version runs
with a warning from `run.jl` and can give other numbers; `run-summary.json`
records the version that ran. The bundle installs its own packages on the
first run. With Nix, use the nixpkgs revision that has Julia 1.13.1:

```bash
nix shell github:NixOS/nixpkgs/fe13242281a67641c0102cdb1087f0ebe586c7df#julia-bin -c julia --version
```

On NixOS, `uv` downloads a Python that cannot run, and NumPy wheels miss
`libstdc++`. Use a Nix Python and the library path:

```bash
nix shell nixpkgs#uv github:NixOS/nixpkgs/fe13242281a67641c0102cdb1087f0ebe586c7df#julia-bin nixpkgs#python311 -c env \
  UV_PYTHON_DOWNLOADS=never \
  LD_LIBRARY_PATH="$(nix build --no-link --print-out-paths nixpkgs#stdenv.cc.cc.lib)/lib" \
  uv run --python python3.11 --extra jinko2julia python -m jinko2julia ...
```

Point the check at a Julia that is not on `PATH` with `--julia PATH` or the
`JINKO2JULIA_JULIA` variable. A path that does not exist is an error. The first run compiles Sundials and SciMLBase:
expect several minutes, then seconds for later runs. Tell the user before the
first run.

## How the bundle follows Jinkō

- Solver: CVODE BDF with a dense linear solver, the trial relative tolerance,
  an absolute tolerance per state of `atol * tolerance * scale` (Jinkō solves
  `x / scale`), the first step, and 10 error-test failures, as in the core.
- Units: species are amounts in the extent unit; a species name in a formula
  means that amount. Every formula carries explicit conversion factors to the
  unit of its target. A bare number next to a dimensionless quantity is a
  plain number.
- Overrides: model value, then vpop, then arm. An override of a rule replaces
  it for the whole simulation.
- Time grid: the Jinkō construction (repeated addition in seconds, fuzzy
  de-duplication, arm `tMax` and `tStep`).
- Events: recurring events become explicit times; condition events fire on
  false to true; all updates of one event read one state; priorities,
  persistence, and cascades as in the core. A recorded event writes a row
  before and a row after.
- Scalars: standard scalars, `.tmin` baselines, measure functions, and
  cross-arm comparisons, with the core's numerics (trapezoid, linear
  interpolation with the post-event value).
- Switches: with `AddAuxiliaryEvents` (the default), the solver stops and
  restarts where an `if`, `max`, `min`, `abs`, `floor`, `ceil`, `round`, or
  `mod` of the equations changes. The core also freezes the branch between
  roots; restarting gives the same result within solver tolerance.
- Event-only inputs (changed by events, no ODE) stay exact between events.
- Scorings: data tables and the advanced output set become objectives,
  measures, and constraints, merged and weighted as in the core. They are
  evaluated on the written time series (seconds, output units) with the core's
  primitives (`inRangeV2`, trapezoid, linear interpolation, slices, centered
  differences). A scoring on one arm is written on that arm; across arms, in
  `cross_arm_scalars.csv`, with `optimizationWeightedScore`. Scoring times
  known before solving (data table times, `x[t]`, slice bounds) join the solve
  times, at most 100, the farthest from the grid first. A scalar with no value
  holds the reason, as in Jinkō: `ConditionNotMet` or the evaluation error.

## Known gaps

The SUNDIALS build and the root finder differ from the core, so agreement is
at tolerance level, not bit for bit. `fetch` reads data tables with the
`fitnessFunction` mapping, as the core does. Creating a trial whose data table
design has a `timeTolerance` fails in the SDK (jinko-workbench#585); reading
one works. Read each trial component at the revision
the trial is bound to (`fetch` does); the latest revision can differ.
