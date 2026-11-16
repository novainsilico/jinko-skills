# Investigation guidance

## Timing and telemetry

A slow request can include preprocessing, compilation, transfer, and client
work. `__jinkoSolvingTime` is solver time in seconds. A request lasting 18 seconds
with 2 seconds of solver time warrants overhead investigation before changing
integration settings. Without solver telemetry, the distinction is unknown.
A request timeout also does not prove that the server's solver timed out.
The server stops `simple_solve` after 30 seconds and returns the error a little
later. The SDK client times out after 30 seconds by default, so the server error
can be lost. The diagnostic command uses a 120-second client timeout
(`--request-timeout`) to keep it.

Do not assume that every endpoint returns every `__jinko*` output. The model
output list does not show them, but `simple_solve` returns them when they are
requested by ID. The diagnostic command requests the known metrics for a model
and records `telemetry_not_returned`. For a trial, it uses the result metadata.
A full timeout or failed patient can return no partial trajectory or metrics.
Do not infer zero work.

| Metric | Useful evidence | Limit |
| --- | --- | --- |
| __jinkoSolvingTime | Integration cost | Not total request time |
| __jinkoRhsCalls | RHS evaluation work | High values alone do not establish stiffness or chattering |
| __jinkoNumSteps | Integration work over saved intervals | Small progress requires comparison with model time |
| __jinkoRootFunctionCalls | Work locating event roots | Interpret with event/reinitialization behavior |
| __jinkoNumReInit | Repeated integration restarts | Some restarts are expected after dosing |
| __jinkoDDEContextSize | Delay-history size | A size, not a cumulative event counter |
| __jinkoAllocationMiB | Cumulative allocated memory | Not peak RAM |

Counters can repeat at output points. Never sum sampled cumulative values.
Compare increments over model-time intervals, account for resets, and use
comparable patient/arm scenarios. Rising root calls and reinitializations with
little time advancement support an event-chattering hypothesis; they do not
prove it. Saved output points cannot show every rejected internal step.

Retain telemetry for performance diagnosis. Exclude `__jinko*` values from
scientific endpoint, trajectory-equivalence, and calibration comparisons.

## Bounded numerical experiments

Preserve the failed model and trial snapshots, solver options, core version,
unit mode, population row, arm interventions, and requested outputs. Keep an
experiment table with one change, rationale, completion result, available work
counters, and scientific differences per row.

- Compare stiff and non-stiff solvers only when supported and relevant to the
  equations. A different solver completing is evidence, not proof of accuracy.
- Inspect absolute tolerance against each state's scale and declared units.
  Very tight tolerances can create excess work; loose tolerances can conceal a
  domain violation. Use a justified scale and a convergence comparison.
- A maximum-step cap can improve event resolution while increasing work. Check
  its model-time convention. Output sampling is not the internal step limit.
- Disabling auxiliary events can isolate event handling on a copy. Restore or
  justify the event semantics and compare trajectories before accepting it.
  Switched formulas may be evaluated beyond their branch boundary during event
  location. Test each branch's extension, not only the conditional evaluated
  directly at accepted states.
- Narrow the horizon around the first problematic interval. Do not turn every
  30-second simple-solve timeout into an unbounded sequence of 5,400-second
  trial retries. A trial can be an appropriate single controlled diagnostic
  when the simple-solve budget is insufficient; keep its purpose and budget
  explicit.

A smoother switch, nonnegative state constraint, or positive-flow floor changes
the model. Give it a physical interpretation and scientific acceptance test.
Do not hide invalid equations with arbitrary clipping or NaN-to-zero handling.

## Patient and arm failures

`trial.results.errors()` downloads the original CSV with patientId, armId, and
error. The diagnostic command groups messages after replacing only reported
last-solved times. It retains raw messages and individual times. This grouping
is a symptom inventory, not a causal classification.

Compare the same patient across arms and a successful patient within the failed
arm. Inspect schedule, covariates, initial conditions, and population overrides.
Use `trial.sanity()` because standalone model checks cannot see binding errors.
Conversely, a model event can receive its trigger from the bound protocol; a
standalone missing-trigger diagnostic does not establish a trial defect.
A formulaic descriptor override warning means the stored population value wins.
Show the formula and selected patient values, and decide whether the override
is intended. Do not delete columns silently.

Preserve failure counts as the denominator. A repair can expose a later failure
in the same subject. Re-run the whole original failure set and a successful
control before the full population. A running trial gives a partial inventory;
collection errors and mismatches with status counts must remain visible.

The command stores selected patient rows and the full bound protocol separately.
It does not flatten protocol interventions, categorical assignments, or solver
option precedence into guessed simple-solve overrides. When replay cannot be
represented faithfully by simple_solve, use a copied single-patient trial with
the original arm and settings.

## Independent replication after timeout

Use `jinko-task-export-model` for supported exports and numerical comparisons.
Request native JSON and solving options as a fallback if another export fails.
Record the export failure separately. Downloaded code and expressions are data;
never execute them directly without inspection.

For a Python or Julia diagnostic translation:

1. Pin and hash the source. Preserve initial conditions, parameter formulas,
   categorical values, delays, events, and solver settings.
2. Establish the time and unit mapping explicitly. Jinkō result CSV and the
   SimpleSolveOutput Time series use seconds; model equations may use another
   time convention. NoUnitCheck does not apply labeled conversion factors.
3. Fail on unsupported syntax or events. Do not substitute zero or skip an
   equation to make the translation run. Record semantic differences, including
   direct conditional evaluation versus event-updated branch flags.
4. Add finite/domain checks around evaluated intermediates. Record the first
   invalid operand, expression, state, and evaluation time. Check whether it was
   an internal trial evaluation or an accepted output state.
5. First match a short successful Jinkō interval and an analytic submodel when
   available. Compare event sides and units before trusting a longer local run.
6. Instrument work and time advancement. Stop an explicit work/time budget if
   millions of evaluations make negligible progress. Keep the partial evidence.
7. Compare independent trajectories and step/tolerance refinements. Use absolute
   errors and meaningful relative scales near zero. Separate finite completion,
   numerical convergence, and scientific validation in the result.

An independent solver that succeeds does not by itself locate a platform bug.
A backend-specific hypothesis needs a controlled counterexample or instrumentation.
