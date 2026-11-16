# SimBiology

Jinkō has two SimBiology exports. Both need MATLAB with SimBiology to run.

| Export | Target | Content |
| --- | --- | --- |
| SimBiology code | `simbiology-code` | A MATLAB script that builds the model with the SimBiology API, applies the Jinkō solver settings, and simulates. |
| SimBiology XLSX | `simbiology-xlsx` | A workbook for the Model Builder, plus `SimulationSettings_<model>.yaml`. |

Prefer the code: it runs without a manual step. Use the workbook when the user
asks for it or wants to edit the model in the Model Builder.

## Find MATLAB

Look for a MATLAB MCP server first: search the full tool registry, including
tools that load lazily, because an MCP server can be hidden until loaded. Use
it when it can run MATLAB code. Use a local `matlab` command only when no such
server exists. Say which path you use. With no MATLAB at all, for example when the
user works in MATLAB Online, give the user the driver to run and ask for the
file it writes.

## SimBiology code

1. `prepare-matlab --dir <dir>` writes `check_simbiology.m`. It runs the
   exported script, simulates again on the Jinkō time points in seconds, and
   writes `other.json`.
2. Run `check_simbiology.m` in MATLAB with the run directory as the current
   folder: through the MCP server, with `matlab -batch "check_simbiology"`, or
   by the user (copy the exported script and the driver, send back
   `other.json`).
3. Continue with `compare`.

## SimBiology XLSX

The workbook has no import API in SimBiology. The user imports it once:

1. In the Model Builder, create a blank model and delete its default `unnamed`
   compartment, so no extra compartment is carried into the model.
2. **Home → Model → Import Model Components from Excel**, select the workbook.
3. Save the project (`.sbproj`) in the run directory.

Reuse a saved project when the workbook hash in the manifest has not changed.
Do not overwrite the user's project. To check it, adapt `check_simbiology.m`:
replace the `run(...)` line by loading the project into `model`, take
`cs = getconfigset(model, 'default')`, apply the YAML settings to `cs`
(`CompileOptions`, `SolverOptions`, `SolverType`, `TimeUnits`, `StopTime`), and
take `doses = getdose(model)`. If some doses are inactive, ask the user whether
to activate them for this run. Make every change in memory, not in the project.

## What the export changes

From the Jinkō export guide, the export adapts the model to SimBiology:

- Categorical parameters and case expressions take their selected values.
- Conditional expressions become boolean-weighted formulas:
  `(c)*(a) + ~(c)*(b)`. A branch that is infinite or NaN makes the result NaN.
- Unit annotations become constant auxiliary parameters equal to 1.
- Species initial conditions are converted to the extent unit.
- Eligible time events (a species target, no condition, an increment) become
  doses. Other time events become root events with auxiliary parameters.

## Install (optional)

MATLAB and SimBiology need a MathWorks license and a local MATLAB install;
MATLAB Online is not enough for an agent. The
[MATLAB Agentic Toolkit](https://github.com/matlab/matlab-agentic-toolkit)
installs the [MATLAB MCP Server](https://github.com/matlab/matlab-mcp-server)
for the agent, and its `computational-biology` skills
(`simbiology-build-model`, `simbiology-simulate-model`,
`simbiology-fit-model`) help to work on the model once it is in SimBiology.
