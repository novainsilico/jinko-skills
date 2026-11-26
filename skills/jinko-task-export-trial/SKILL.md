---
name: jinko-task-export-trial
description: >-
  Export a whole Jinkō trial (model, virtual population, protocol arms, output
  set, and solving options), run it outside Jinkō, and check that it
  reproduces the Jinkō results. Targets: SED-ML (an OMEX archive run with
  tellurium), Julia, and Heta (HetaSimulator.jl). Use this skill whenever the
  user wants to export, convert, or rerun a Jinkō trial outside Jinkō, give a
  regulator or a partner a program that reproduces a trial independently,
  check that an exported trial matches Jinkō, or write a reproduction report
  for an exported trial, even when the user gives only a trial link or short
  ID. For one model without its trial, use jinko-task-export-model.
compatibility: >-
  Check set-up with the `jinko-sdk-setup` skill. SED-ML needs the SDK extra
  `sedml` and a pinned tellurium environment. Julia needs the extra
  `jinko2julia`, and Heta needs `jinko2heta`; both run with Julia 1.13.1, and
  the first run installs pinned packages for several minutes. A Heta export
  also needs the Heta compiler 0.12.1 (Node.js).
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.22,<2.0"
license: MIT
---

# Export a Jinkō trial

> **PREREQUISITE:** This skill needs an initialized `jinko-sdk` connection and
> an SDK satisfying its `metadata.requires_sdk` range. Run the `jinko-sdk-setup`
> skill (`../jinko-sdk-setup/SKILL.md`) and proceed only once its check passes.
> If that skill is not found, install it from `novainsilico/jinko-skills`.

The user gets the exported trial, an honest verdict on how far it reproduces
Jinkō, and, on request, a reproduction report in Jinkō. An export that was
not run is not checked: say which one the user has.

## Targets

| User asks for | Read before the first command |
| --- | --- |
| Julia | `references/julia.md` |
| Heta, HetaSimulator.jl | `references/heta.md` |
| SED-ML, OMEX, or COMBINE archive | `references/sed-ml.md`, which replaces the workflow below |

For another language, list these three and offer `jinko-task-export-model`
for a model-only export to SBML, SimBiology, or nlmixr2.

## Unsupported features

Julia and Heta refuse a trial that uses one of these, with a `CompileError` that
names the construct. Tell the user before the fetch when the trial shows one.
Heta refuses more: see `references/heta.md`, "Not supported".

| Area | Not supported | Error text contains |
| --- | --- | --- |
| Trial | Trial not completed in Jinkō (no results summary) | `has no results summary` |
| Solving options | Solver other than BDF | `solver` |
| Solving options | Unit check `NoUnitCheck` or `UnitCheckWithNoUnitConversion` | `unitCheck` |
| Model | Random functions (`rnorm`, `runif`, `nextSeed`), `rateOf` (including inside `delay`), and functions unknown to the export | `unsupported functions` |
| Model | Algebraic rules | `algebraic rules` |
| Model | Species `conversionFactor` | `conversionFactor` |
| Model | Reaction kinetics other than general and mass action | `kinetics` |
| Model | Event option `useValuesFromTriggerTime` | `useValuesFromTriggerTime` |
| Model | `delay` inside an event schedule expression | `delay in event schedules` |
| Model | Power of a quantity with a unit to an exponent that is not constant and has no default value | `non constant exponent` |
| Protocol | Arm override of a component that refers to itself | `refers to itself` |
| Protocol | Arm override of a component that the trial's model revision does not have | `does not have` |
| Output set | Measure function or time point that the export does not read | `not understood` |
| Scorings | A data table or scoring that refers to an arm the protocol does not have, or mixes references with and without an arm | `refers to arm`, `mixes references` |
| Scorings | More than one data table observable written as a formula (its scalar name is a hash that only the Jinkō results give) | `is a formula` |

## Bundle license

Before an export, ask the user to choose the license through the question
tool, with the default first. Keep a license the user already chose.

| Choice | Julia and Heta argument |
| --- | --- |
| All rights reserved to Nova In Silico (default) | `--license all-rights-reserved` |
| MIT | `--license mit` |
| Noncommercial (CC BY-NC 4.0) | `--license nc` |
| Same as the source model | `--license source` |

For the source-model choice, use the actual license text: the exporter reads
`model.LICENCE`, `model.LICENSE`, `LICENCE`, or `LICENSE` in the fetched
folder, or `--source-license-file PATH`. If there is none, ask the user for
it. A citation does not identify a license. A Nova In Silico license takes
the year the Jinkō run completed, or `--copyright-year YEAR`.

## Workflow for Julia and Heta

The commands below are those of `jinko2julia`. Heta takes the same arguments
with `jinko2heta` (`references/heta.md`, "Commands"). Use one working folder
per trial, such as `exports/<trial-sid>/`. Run the commands yourself; do not
teach them to the user.

1. **Fetch.** `python -m jinko2julia fetch <trial> --out <dir>/trial`. The
   trial must be completed in Jinkō. Add `--timeout 600` for results of
   hundreds of MB.
2. **Export.** `python -m jinko2julia export <dir>/trial --bundle <dir>/bundle --license <choice>`.
   Report every warning. For a `CompileError`, read the named component: a
   construct in the table above is a limit of the export, so stop. A
   construct that Jinkō solves and the table does not list is an export
   defect: report it, and offer to fix or log it. Do not edit the model
   without the user's consent.
3. **Check.** `python -m jinko2julia check <dir>/trial --bundle <dir>/bundle`.
   It runs the bundle, compares it with Jinkō, and solves the unresolved
   patient-arm pairs again at tight tolerances in both tools. The Jinkō tight
   solve is a temporary trial copy that needs write access and can take
   hours: tell the user before the check starts. If Julia is missing, say
   what to install and ask. Run the check in the background, and report the
   first verdicts with an estimate of the end. `references/julia.md`,
   "Check", explains the verdicts, the stop, and the options.
4. **Report the verdict** from `comparison.json`: PASS, PASS WITHIN SOLVER
   TOLERANCE, or FAIL. Lead with the 10 largest absolute differences
   (`top_absolute_differences`), each with its unit, patient, arm, time, both
   values, and the relative difference.
5. **Reproduction report, on request.** `python -m jinko2julia report <dir>/trial --bundle <dir>/bundle --out <dir>/report/report.md`,
   then publish it in the trial's folder with `jinko-document`
   (`--asset-root <dir>/report`). Return the document link.
6. **Hand over the bundle.** Its `README.md` says how to run it.

## Rules for the check

- **One gate for every target**, in the SDK package `jinko_trial_check`. A
  curve passes when its integrated relative error is at most 1e-4 **OR** its
  largest absolute difference is at most 1e-12 in the output unit. A scalar
  passes at a relative error of at most 1e-3. Above that, only tight solves
  of the same patient-arm pair in both tools can resolve it. An event shift
  larger than the time tolerance passes only with one unambiguous recorded
  event and agreeing tight runs.
- **Not converged.** When a scalar at the trial tolerances is more than 10 %
  from its own tight solve, report it as a finding on the model's solving
  options, not on the export.
- **A failure has a cause to find.** Structural differences and gaps that the
  tight solves do not explain are export defects. Report the worst series,
  patient, and arm, and offer to log it.
- **Do not repair the generated files** to make them pass.
- **Report what is true.** Name the items that were not compared.
