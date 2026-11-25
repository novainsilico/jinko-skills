---
name: jinko-task-export-trial
description: >-
  Export a whole Jinkō trial (model, virtual population, protocol arms, output
  set, and solving options) to a standalone program in another language, run
  it, and check that it reproduces the Jinkō trial results. Targets: Julia
  (Sundials CVODE BDF), and Heta (a Heta platform run with HetaSimulator.jl).
  The program writes time series and scalars in the
  format of the Jinkō SDK result downloads, so analysis scripts written for
  Jinkō results run on it unchanged. Use this skill whenever the user wants to
  export, download, convert, or rerun a Jinkō trial outside Jinkō, give a
  regulator or a partner a program that reproduces a trial independently, run
  a trial in Julia or Heta, check that an exported trial matches Jinkō, or write a
  reproduction report for an exported trial. Use it even when the user gives
  only a trial link or short ID. For one model without its trial, use
  jinko-task-export-model.
compatibility: >-
  Check set-up with the `jinko-sdk-setup` skill. Needs the SDK extra
  `jinko2julia` (Julia) or `jinko2heta` (Heta). Running and checking a bundle
  needs Julia 1.13.1 (the bundle pins it); the first run installs its pinned
  packages, which takes several minutes. A Heta export also needs the Heta
  compiler 0.12.1 (Node.js).
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.20,<2.0"
license: MIT
---

# Export a Jinkō trial

> **PREREQUISITE:** This skill needs an initialized `jinko-sdk` connection and
> an SDK satisfying its `metadata.requires_sdk` range. Run the `jinko-sdk-setup`
> skill (`../jinko-sdk-setup/SKILL.md`) and proceed only once its check passes.
> If that skill is not found, install it from `novainsilico/jinko-skills`.

The user gets three things: the bundle (a folder that runs the trial alone),
an honest statement of how far it reproduces Jinkō, and, on request, a
reproduction report in Jinkō. A bundle that was not run is not a checked
bundle. Say which one the user has.

## Targets

| User asks for | Target | Run | Read |
| --- | --- | --- | --- |
| Julia | `julia` | Julia 1.13.1 | `references/julia.md` |
| Heta, HetaSimulator.jl | `heta` | Julia 1.13.1 and HetaSimulator.jl; the Heta compiler for the export | `references/heta.md` |

Read the reference of the target before the first command. For any other
language, say that Julia and Heta are the trial targets today, and offer `jinko-task-export-model` for a model-only export to SBML, SimBiology,
or nlmixr2.

## Unsupported features

The export refuses a trial that uses one of these, for both targets. The
`CompileError` names the construct. Tell the user before the fetch when the
trial shows one. The Heta target refuses more features: see
`references/heta.md`, "Not supported".

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

Supported by the Julia target and checked on the test corpus: general and mass action
reactions, stoichiometries written as formulas (such as a `case` on a
categorical), ODEs, `delay` with the core's history on CVODE (including doses,
pre-start history, and zero delay), events (time, condition, recurring, priorities,
persistence, recorded), switches (`if`, `max`, `min`, `abs`, `floor`, `ceil`,
`round`, `mod`), unit literals, molar mass, varying compartments,
categorical parameters, vpop values and categoricals, arm values, formulas,
and categorical levels, arm `tMax` and `tStep`, several solving periods,
standard scalars, `.tmin` baselines, simple measures, cross-arm measures,
data tables (`-from-table` scores, ranges, row and table weights, time
tolerance, log-scaled wide bounds, arm scopes, weight 0), advanced output sets
(objectives, measures, and constraints on one arm, one named arm, or across
arms, with filters), and `optimizationWeightedScore`.

Known differences: the text of a scoring evaluation error can differ from
Jinkō's for errors inside time series functions (Jinkō writes the reason in
the value column). A scoring time that depends on a model state is not added
to the solve times (Jinkō evaluates it with the states at 0).

## Bundle license

The two targets take the same license choices. Before generating a bundle,
ask the user to choose its license through the question tool. Put **All rights reserved to Nova In Silico (default)** first.
Honor a license the user already selected for this bundle.

| Choice | Export argument | LICENCE content |
| --- | --- | --- |
| All rights reserved to Nova In Silico (default) | `--license all-rights-reserved` | Nova In Silico copyright and all-rights-reserved notice |
| MIT | `--license mit` | MIT terms with Nova In Silico copyright |
| Noncommercial (CC BY-NC 4.0) | `--license nc` | Full CC BY-NC 4.0 terms with Nova In Silico attribution |
| Same as the source model | `--license source` | Original source license and attribution, copied verbatim |

For the source-model choice, use its actual license text. The exporter reads
`model.LICENCE`, `model.LICENSE`, `LICENCE`, or `LICENSE` in the fetched-input
folder, or accepts `--source-license-file PATH`. If that text is missing,
ask the user for it before exporting. A literature citation does not identify
the model's license. Keep the original copyright holders and terms.

For the Nova In Silico licenses, the copyright year is the year the Jinkō
run of the trial completed; set another with `--copyright-year YEAR`. The
source-model choice keeps its own notice and takes no year.

The bundle includes a `README.md` with **Prerequisites** and **How-to** as its
two main sections. It lists dependency minimums and pinned versions, run
instructions, result locations, and the package folder tree. The selected
license is in `LICENCE` and is recorded in `data/trial.json`.

## Workflow

The package of the target does the work: `jinko2julia` for Julia,
`jinko2heta` for Heta. The steps below give the Julia commands; the Heta
commands have the same arguments (`references/heta.md`, "Commands"). For
Heta, read "Julia" as "HetaSimulator.jl", and "the Julia run" as "the run of
the bundle". Use the commands; do not present them to the user as a tool to
learn. One working folder per trial, such as
`exports/<trial-sid>/`, unless the user named one.

1. **Fetch.** `python -m jinko2julia fetch <trial> --out <dir>/trial`. The
   trial must be completed in Jinkō: the scalar ids and units come from its
   results. If it is not, say so and stop. A large trial (results of hundreds
   of MB) exceeds the SDK default timeout of 30 s: pass `--timeout 600`.
2. **Export.** `python -m jinko2julia export <dir>/trial --bundle <dir>/bundle --license <choice>`.
   Use the license selected above. Add `--source-license-file PATH` when needed.
   Report every export warning. A refused construct is a `CompileError` that
   names it. Read the named component before you call it a limit: when the
   construct is in the table above, report it as a limit of the export and
   stop; when Jinkō solves it and the table does not list it, it is an export
   defect: report it, and offer to fix or log it. Do not edit the model to get
   around it without the user's consent.
3. **Check.** `python -m jinko2julia check <dir>/trial --bundle <dir>/bundle`.
   For Heta, the verdict lines come after the run of the bundle, not during
   it (`references/heta.md`, "Commands").
   It runs the bundle, compares it with the Jinkō results, and solves only the
   unresolved patient-arm pairs again at tight tolerances, in Julia and in
   Jinkō. The Jinkō tight solve is a temporary copy of the trial in a
   `tight-solve` folder next to it, deleted after use: it needs the Jinkō
   key and project of the trial, with write access. If Julia is missing, say what to install
   (`references/julia.md` or `references/heta.md`, "Install") and ask. Do not install anything without consent.
   Run it in the background and follow it. Results stream per patient: the
   check prints a line per finished patient, with its verdict:
   - PASS: every item within the strict gate.
   - GAP: an item above the strict gate, but within solver tolerance or
     below `--stop-above` (default 0.1).
   - SUSPECT: an item above `--stop-above`, with tight solves still to come.
     With `--no-tight`, none come: a SUSPECT patient stops the check at once.
   - DIVERGES: a failed run, mismatched rows or units, or an item above
     `--stop-above` that the tight solves do not explain.
   - NO JINKO RESULTS: Jinkō did not solve the patient; it is not
     compared, but its Julia errors still count.

   The check stops the run at the first patient that diverges; the
   STOPPED line gives the reason and the results folder. A crash of the
   Julia run stops the check with the path of `run.log`. Report
   the first patients' verdicts and the time per patient as soon as they
   come, with an estimate of the end. On a stop, debug that patient from
   `<bundle>/results/partial/<patient>/` before you run again. A suspect
   (above `--stop-above`) gets tight solves of its patient-arm pairs in Julia
   and in its own Jinkō trial first: the run stops only if the two tight
   solves do not agree. The other patients share one Jinkō trial when the
   Julia run ends. A Jinkō tight solve takes hours: tell the user before the
   check starts. When an output is
   undefined where it differs (for example `c <= 0 ? -5 : log10(c)` at a zero
   concentration), report the formula as a modeling issue (see
   `jinko-model`, "Keep piecewise outputs continuous"), and, with the
   user's consent, rerun with `--exclude <series>` (repeatable), or with
   `--select <series>` to compare only named series; the two are exclusive,
   and a scalar `<series>.<kind>` follows its series. The report names what
   was not compared. A large model
   (hundreds of states) compiles for minutes before the first patient.
   Use `--resume` only with the same bundle and reference files; fingerprints
   reject changed inputs and legacy runs without fingerprints. `--no-tight`
   skips all tight solves. `--stop-above inf` (formerly `--no-stop`) never
   stops the run, not even on a structural difference (a failed run,
   mismatched rows, or another unit); it keeps the final failing verdict.
4. **Report the verdict** from `comparison.json`: PASS, PASS WITHIN SOLVER
   TOLERANCE, or FAIL, with the worst items. With many outputs, lead with the
   10 largest point-wise absolute differences
   (`top_absolute_differences` of the time series and of the scalars): item,
   unit, patient, arm, time, both values, absolute and relative difference.
   An absolute difference compares only within one unit; give the relative
   difference next to it.
5. **Reproduction report, when the user asks for one.**
   `python -m jinko2julia report <dir>/trial --bundle <dir>/bundle --out <dir>/report/report.md`,
   then publish it next to the trial with `jinko-document`
   (`python -m jinko.cli.create_document_from_markdown`, `--asset-root <dir>/report`,
   in the trial's folder). Return the document link.
6. **Hand over the bundle.** Point to its `README.md`: it says how to run it
   and what each file holds.

## Rules for the check

- **Same rules for every target.** The SDK package `jinko_trial_check` holds
  them, so a PASS means the same for Julia and for Heta.
- **Time-series agreement.** For each patient-arm curve, require
  `AUC(abs(Jinkō - bundle)) / AUC(abs(Jinkō)) <= 1e-4` (0.01%). Use
  trapezoids of absolute samples on the union time grid, preserving pre/post
  event limits. Above the threshold, solve that pair at tight tolerances in
  both tools and apply the same ratio and threshold to the tight pair. Without
  both tight results, the ordinary failure remains unresolved.
- **Scalar agreement.** Retain the largest relative error at most 1e-3,
  with the existing absolute and cohort floors. Above that threshold, require
  tight scalar agreement within 1e-3 of the output peak.
- **Structural checks.** Rows match one to one, event rows included. Interior
  event times retain the time tolerance; start and end times match exactly.
  Missing coverage, nonfinite inputs, and unit mismatches fail. The early-stop
  threshold uses the integrated ratio for series and relative error for scalars;
  it does not replace either acceptance threshold.
- **Evidence stays local.** Evaluate the gate for each patient and arm before
  aggregating. A tight solve on one pair cannot confirm another pair. Cached
  evidence requires matching bundle and reference fingerprints.
- **A failure has a cause to find.** Structural differences (missing rows,
  unit strings, failed runs) are export defects. A numerical gap that the
  tight solve does not explain is an export defect too. Report it with the
  worst series, patient, and arm, and offer to log it.
- **Not converged.** When a scalar of Jinkō or of the bundle at the trial tolerances
  is more than 10 % from its own tight solve, the trial tolerances do not give
  a converged result. Say so, with both distances: it is a finding about the
  model's solving options, not about the export.
- **An export that does not run is the finding.** Do not repair the generated
  files to make them pass.
- **Report what is true.** Name the items that were not compared.
