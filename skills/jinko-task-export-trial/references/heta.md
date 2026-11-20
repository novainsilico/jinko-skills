# Heta

The Heta target writes the model of a trial as a Heta platform
(<https://hetalang.github.io/>), with the runs of the trial: each patient on
each active arm. HetaSimulator.jl runs them and writes the time series in the
format of the Jinkō result downloads. The package is `jinko2heta`.

## Commands

| Step | Command |
| --- | --- |
| Fetch | `python -m jinko2heta fetch <trial> --out <dir>/trial`: the fetch of the Julia target |
| Export | `python -m jinko2heta export <dir>/trial --bundle <dir>/bundle --license <choice>` |
| Build | `python -m jinko2heta build <dir>/bundle`: only when the export could not build `julia/model.jl` |
| Run | `python -m jinko2heta run <dir>/bundle [--tight] [--patient ID --arm ARM]` |
| Check | `python -m jinko2heta check <dir>/trial --bundle <dir>/bundle` |
| Report | `python -m jinko2heta report <dir>/trial --bundle <dir>/bundle --out <dir>/report/report.md [--no-plots]` |

`check` takes the options of the Julia check: `--julia PATH`, `--select` or
`--exclude`, `--no-tight`, `--stop-above X`, and `--resume`; also
`--results DIR`, `--no-run` to check existing results, and `--jinko-tight DIR`
to reuse the Jinkō tight results of an earlier check. It writes
`comparison.json`, or `comparison-stopped.json` on a stop, in the bundle.

One difference with the Julia check: a Heta bundle writes its results at the
end of the run, so the per-patient verdict lines (PASS, GAP, SUSPECT,
DIVERGES, NO JINKO RESULTS) come after the run, not during it. The verdicts,
the tight solves on both sides, and the stop rule are the same.

`export` takes the license arguments of the Julia target: `--license`,
`--source-license-file`, and `--copyright-year`. It exits with code 2 and
prints `refused:` with each feature and component that Heta cannot express.
It builds `julia/model.jl` with the Heta compiler; without the compiler, it
warns, and `build` does it later.

## Not supported

The export refuses a trial that uses one of these features. The `refused:`
line names the feature and its component. Tell the user before the fetch
when the trial shows one.

| Error text contains | Reason |
| --- | --- |
| `categorical parameter` | Heta has no categorical value: a scenario sets numbers only |
| `event priority` | Heta switchers have no priority order |
| `solver stop` | the export writes no Heta `@StopSwitcher` yet |
| `formula stoichiometry` | a Heta actor takes a number |
| `switcher time from a dynamic value` | a Heta time switcher takes numbers and constants |
| `NaN or infinite number` | a Heta expression has neither |
| `function sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh` | Heta has no hyperbolic functions |
| `function round` | Heta has no rounding function |
| `function mod` | Heta has no modulo function |
| `function delay` | The Heta runtime does not implement the core delay history. Use the Julia target. |

The refusals of the Julia target apply too, because the analysis of the model
is the same (`SKILL.md`, "Unsupported features").

The scalars, the scorings, and the weighted score come from the runtime of
the Julia bundle, which the Heta runtime gives the Heta series of each run:
the same measures, baselines, and result files. The scoring times known
before the solve join the output times, as in Jinkō.

Kept with a warning: an event update of a constant, which Jinkō ignores and so
does the platform; and a condition event that is not persistent.

## The bundle

| Path | Content |
| --- | --- |
| `platform.yml`, `src/index.heta` | The Heta platform of the model |
| `julia/model.jl` | The Julia model that the Heta compiler builds, and HetaSimulator.jl loads |
| `data/runs.json` | The runs: patient, arm, parameter values, solving times, outputs, solver |
| `data/vpop.csv`, `data/protocol.csv` | The patients and the arms, as fetched |
| `data/trial.json` | Inputs, solving options and times, the id map, the warnings, and the license |
| `run.jl`, `runtime/HetaRun.jl` | The fixed runtime |
| `runtime/JinkoRuntime.jl` | The runtime of the Julia bundle, for the scalars and the scorings |
| `Project.toml`, `Manifest.toml` | Pinned Julia packages: HetaSimulator.jl 0.8.8, DataFrames, JSON3, and SciMLBase and Sundials for the runtime of the Julia bundle |
| `README.md`, `LICENCE` | For the people who run the bundle, and the selected license |
| `results/` | Written by `run`: `timeseries.csv`, `metadata.csv`, `scalars.csv`, `cross_arm_scalars.csv`, `errors.csv`, `run-summary.json` |
| `comparison.json` | Written by `check`: the verdict and its evidence |

## How the bundle follows Jinkō

- **Model.** The analysis of the Julia export: the same constants, rules,
  states, and unit conversions. The expressions carry the unit conversions of
  Jinkō as numeric factors (`F_*` constants), so the platform computes the
  numbers of Jinkō without the Heta unit check.
- **Species.** `isAmount: true`: a species name means the amount in the extent
  unit, as in a Jinkō formula.
- **Ids.** An id that Heta does not accept (`Central.IL6`) becomes a close Heta
  id (`Central_IL6`); `aux.jinkoId` keeps the Jinkō id, and the results use it.
- **Inputs.** A parameter with a number is a `@Const` that each run sets. Any
  other input that a patient or an arm sets has two constants,
  `<id>__mode` and `<id>__value`, as the slots of the Julia bundle.
- **Events.** A recurring event stops at `first + (count - 1) * every`,
  because Heta includes its `stop`. At an event time, a series has the row
  before the events and the row after them, as in the Jinkō results.
- **Solver.** Rodas5P at the tolerances of the trial. CVODE BDF, the solver of
  Jinkō, cannot run under the events of HetaSimulator.jl. So a Heta bundle
  can differ from Jinkō within the solver tolerance where a Julia bundle
  does not: say so when a gap is near the gate.

## Install

- Julia 1.13.1, as for the Julia target (`references/julia.md`, "Install").
  Point to another Julia with `--julia PATH` or `JINKO2JULIA_JULIA`, as for
  the Julia target. The first run installs and
  compiles HetaSimulator.jl: several minutes.
- The Heta compiler 0.12.1, for `export` and `build` only:
  `npm install -g heta-compiler@0.12.1` (Node.js 18 or later), or the command
  in `JINKO2HETA_HETA`. Running a built bundle needs no Node.js.
- The SDK extra: `pip install "jinko-sdk[jinko2heta]"`.
