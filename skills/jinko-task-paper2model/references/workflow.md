# Workflow and artifacts

## Gates

| Gate | Pass condition | If it fails |
| --- | --- | --- |
| Scope | Paper, model variant, scenario, and outputs are explicit | Ask one focused question |
| Sources | Every source has identity, hash, access note, and extraction method | Stop interpretation |
| Reconciliation | Conflicts have explicit alternatives; source-supported corrections have evidence and passed checks | Resolve evidence or record an assumption for approval |
| Evidence | After reconciliation, states, equations or reactions, values or approved assumptions, initial conditions, time basis, and interventions close the target-driving model | Report `blocked_evidence`; do not mutate Jinkō |
| Specification | Symbols resolve, identifiers are unique, locators exist, and comparison rules are frozen | Correct the specification |
| Model | Applied revision has no error diagnostics and solves requested outputs | Report `failed_validation` |
| Reproduction | Every required target has a measured result | Report pass, failure, or unavailable evidence |
| Delivery | Artifacts and fixed Jinkō revisions are recorded; report is rendered | Workflow is incomplete |

## Artifact layout

```text
paper2model-run/
├── source/
│   ├── source-manifest.json
│   └── ocr/
├── specification/
│   ├── reproduction-spec.json
│   └── interpretation-ledger.json
├── results/
│   ├── model-validation.json
│   ├── jinko-timeseries.csv
│   └── reproduction-comparison.json
├── reproduction-report.md
└── delivery-manifest.json
```

Keep immutable source material separate from generated artifacts. Do not put
credentials, licensed PDFs, or unauthorized source code in a deliverable.
The interpretation ledger is an export of the specification's `interpretations`.
Follow `interpretation-policy.md` for decision history and comparison rounds.

## Evidence matrix

Before implementation, write one row per state, parameter, equation, initial
condition, event, output, and target:

| Kind | Identifier | Value or expression | Unit | Source locator | Extraction | Status |
| --- | --- | --- | --- | --- | --- | --- |

Status is `direct`, `derived`, `assumed`, `conflicted`, `missing`, or
`not_applicable`. An assumption states its effect and its approver.

The validator checks identifiers and bindings. It does not parse ODE
expressions, verify symbol closure, or derive coverage counts from a model
export. Keep the evidence matrix and the exported model for those checks.

## Experiment bindings

`validate` enforces the structural rules: every target bound to an experiment,
a Trial needing an output set, an executed arm needing a Protocol, executed
variability needing a Vpop, and a control that cannot score a publication
target. It cannot choose the variability kind, so choose it from the evidence:

- `biological_variability` needs explicit subject, cell-line, or distribution
  evidence.
- `initial_condition_sweep` is for a fixed grid of deterministic scenario
  points, even when stored as Vpop rows. It is no evidence of prevalence,
  probability weights, or clinical variability.
- `analytical_control` is for verification-only rows. Keep them in their own
  experiment records.
- `none` is for no variability. Do not generate arbitrary patients to avoid it.
  A single fixed source case can use a one-row Vpop.

One experiment has one variability kind, and a note cannot override it.

Doses, schedules, routes, and treatment flags go in Protocol arm overrides, over
model-defined inputs and dosing events built through `jinko-model` and
`jinko-protocol`. Use `jinko-vpop` for measured subject values or a
source-supported distribution, preserving row identity, units, source, and any
stated correlation. Cross shared arms with those rows; duplicating subject
identity in the Protocol creates redundant runs.

Map each target to one arm, row subset, observable, unit, and time
transformation, and record both the full Trial cross-product and the smaller
comparison subset. Before remote creation keep planned IDs with null item IDs;
after execution replace them with the exact returned identifiers.

## Creation receipts and resume

Record each remote creation immediately: destination project and folder, local
operation ID, artifact kind, SID, version, SDK `url`, and fixed-revision URL
where supported. On resume, fetch the recorded SID. After an interrupted create
with no receipt, inspect only the authorized destination and reconcile the exact
item before retrying; a matching title alone is not enough. There is no remote
transaction helper.

## Numerical execution checks

- Preserve the paper's state semantics and time basis.
- Set solving times from the paper. Read the horizon and the sampling resolution
  off each reported figure and record them with the target. Correct equations on
  the wrong time grid give entirely different summary values, because `min`,
  `max`, `tend`, and `timeofmax` are all grid-dependent. Solving times live on
  the trial, not the model, so set them explicitly every time.
- Jinkō solves time in seconds. Verify one known-rate decay over a physical-time
  interval; a dimensionally valid per-day parameter can still run at the wrong
  numeric time scale under `UnitCheckWithNoUnitConversion`.
- Translate impulsive or discontinuous inputs as events, and declare whether a
  target point at an event uses the pre-event or post-event value.
- Check that algebraic quantities depending on states are dynamic in Jinkō.
- Make every repair to source syntax or undefined behavior explicit.
- Test the smallest closed subsystem first, and compare initial values,
  derivatives, and event jumps before long simulations.
- Use a convergence or refinement check when a target is sensitive to output
  resolution.
- Record model SID, fixed revision, version label, unit policy, and the actual
  series Jinkō returned.
