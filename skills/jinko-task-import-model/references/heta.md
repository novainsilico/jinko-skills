# Heta

Import a Heta platform (https://hetalang.github.io/hetacompiler/) into Jinkō.
The route always creates a model. When the platform declares `@Scenario`
rows, it also creates a protocol design with one arm per scenario, a simple
output set, and a trial. This route has its own steps: the workflow of
`SKILL.md` does not apply here.

The converter is the `heta2jinko` package. It ships inside `jinko-sdk` and
converts offline:

```bash
pip install "jinko-sdk[heta2jinko]"
```

`scripts/heta_import.py` drives the route. Use it; do not present it to the
user as a tool to learn.

## Rules

- **Run the converter.** Never translate a Heta platform into Jinkō by hand.
  Never edit its output to make it pass a check: convert again.
- **The report comes before Jinkō.** Nothing reaches Jinkō before the user has
  seen the conversion report and said yes.
- **A refusal stops the route.** A construct outside the converter's subset
  stops the conversion with an `E_*` code, and the converter writes nothing.
  Name the construct and its code to the user, say that nothing reached
  Jinkō, and propose to change the platform. Do not work around it.
- **Say which claim holds.** After the import, the claim is "Jinkō accepts
  and solves the model". Only a PASS of the check (step 6) supports "the
  Jinkō results reproduce the Heta run". A FAIL, or a check that did not run,
  leaves the first claim.

## Input

The route reads the table export of the Heta compiler: XLSX (`format: XLSX`)
or CSV (`format: Table`, `bookType: csv`). When the user gives the Heta source
files, build the export with the Heta compiler, then convert it:

```bash
heta build <platform-dir> --export '{format:XLSX,filepath:table}'
```

If the Heta compiler is not installed, say so and ask before you install it
(`npm install -g heta-compiler`).

## Steps

1. **Agree the inputs.** Confirm the export, the model name, and a dedicated
   destination folder. Confirm the output grid:
   - With a `@Scenario`, the platform states its grid in `tspan` and `saveat`.
     Use it; do not type another one over it.
   - Without a `@Scenario`, the platform states no grid. Ask the user for the
     end and the step, in days. Keep the grid at 1000 points or fewer.

   A platform may keep its scenarios in a HetaSimulator.jl table
   (`scenarios.csv`, often in `julia/`) instead of `@Scenario` rows. Ask
   whether the platform has one, and pass it with `--scenarios`: the
   converter then makes one arm per row, and the check runs the same rows.
2. **Convert, offline.**

   ```bash
   python scripts/heta_import.py convert <export> --dir <run-dir> \
       [--scenarios <scenarios.csv>] [--t-max-days 10 --t-step-days 0.125]
   ```

   Exit 1 with `STOPPED` is a refusal: apply the refusal rule above.
   On success, the command lists the items that `apply` creates.
3. **Review the report with the user.** Walk `<run-dir>/conversion-report.md`
   section by section: the solving options and the time unit, the units, the
   components with each `heta -> Jinkō` expression pair, the protocol design
   and its arms, the warnings, "Needs a human decision", and the rows that
   produced no component. Point out these known gaps:
   - A platform without a `t { units: … }` row is converted in seconds
     (`W_TIME_UNIT_ASSUMED`). Confirm the time unit: it changes every dose
     time and every scenario grid.
   - `events_save` of a scenario does not convert. The report lists it.
   - A switcher that `active: false` or a scenario's `events_active` names
     gets a parameter `<switcher>_active` and an override per arm
     (`W_EVENT_GATED`). The converter adds them, even when no arm turns the
     event off. Remove them if the user needs no such switch. At 0 a time
     switcher still fires and changes nothing, so the solver adds a time
     point there. The check of step 6 drops those points.

   Then show the list of items to create, and wait for the user's yes.
4. **Create the items.**

   ```bash
   python scripts/heta_import.py apply --dir <run-dir> \
       --folder <name> --create-folder [--parent-folder <name>] [--run]
   ```

   The command creates the model with its tags and solving options, then runs
   the sanity check: no diagnostic error, and a solve that returns each
   `output` series. With scenarios, and only when the sanity check passes, it
   creates the protocol design, the output set, and the trial. Pass `--run`
   when the user wants the trial to run. `<run-dir>/items.json` records the
   created items, also after a failure: a partial model stays in the project,
   and its deletion is the user's decision.
5. **Report.** Link each item. Say PASS or FAIL for the sanity check, and the
   trial status when it ran. On a failure, give the diagnostic, the likely
   cause, and a recommendation; when the cause is the converter, recommend a
   fix of the converter, not of the model. Say the claim: "Jinkō accepts and
   solves the model". Offer `jinko-model` for the `s::*` source tags: the
   converter applies `output` and `i::protocol` only, because a Heta platform
   records no evidence source. Offer the check with HetaSimulator.jl.
6. **Check against HetaSimulator.jl, when the user asks.**

   ```bash
   python scripts/heta_import.py check --dir <run-dir> --platform <platform-dir> \
       [--series <id> ...]
   ```

   The check runs the platform in HetaSimulator.jl, one run per scenario on
   the grid of its Jinkō arm, and compares each arm with the Jinkō results,
   with the rules of the trial export (the SDK package `jinko_trial_check`):
   a series passes when its integrated relative difference is at most 1e-4.
   In an arm where a time switcher is switched off, the check first drops
   the Jinkō points of its times, and the report lists them.
   A unit that Jinkō writes differently (`nanomol / L` for
   `nmole * liter ** -1`) is the same unit: the check compares the
   quantities, and the report lists each such series.
   With a trial, the trial must have run. Without scenarios, it compares one
   run of the platform as declared with a solve of the model.
   It compares the `output` series and the measured series: Heta records,
   and species of a compartment of constant volume, as amounts. With a
   trial, it also compares the scalars of the output set: the scalar layer of
   the Heta export computes them from the HetaSimulator.jl series. A verdict
   is given per arm, and for the whole trial (with the cross-arm scalars).

   It needs Julia, the pinned Heta compiler, and the HetaSimulator.jl runtime
   of `jinko2heta` (`pip install "jinko-sdk[heta2jinko,jinko2heta]"`).
   It builds the platform from its source modules (`src/index.heta`, else
   `index.heta`), not from its platform file. The first run installs the Julia
   environment, which takes several minutes. Ask before you install Julia.

   Report the verdict of each arm, then the claim that the command prints. A
   FAIL is a finding: say which arm and which series fail, and do not edit
   the model or the platform to make it pass. `NOT RUN` gives no verdict.

## What the conversion does

`sdk/src/heta2jinko/README.md` in the SDK describes the package. In short:

- A Heta species symbol is a concentration, and Heta integrates the amount.
  The Jinkō species state is that amount: its initial condition is
  `(S0) * V`, and each species symbol in a formula becomes `(S / V)`. Keep the
  unit mode `UnitCheckAndConvertAllSpeciesToExtentUnits`: `apply` refuses
  a mode that breaks this rewrite.
- A `@Record` becomes a non-constant parameter. `output: true` gives it the
  `output` tag.
- A `@TimeSwitcher` becomes a model event with a time trigger.
- A `@Scenario` becomes one arm. Its `parameters` become overrides, rewritten
  as the model rewrote the component, and its `tspan` and `saveat` become the
  arm's `tMax` and `tStep`. Its `observables` become the measures of the
  output set. Its `events_active` becomes an override of the activation
  parameter of each gated switcher.
- A `@CSwitcher` becomes a model event with a condition trigger.
- The converter refuses `@DSwitcher`, `@StopSwitcher`,
  `@ReferenceDefinition`, `@TimeScale`, explicit namespaces, a `@Process` on a
  species, and a function with no exact Jinkō equivalent.
