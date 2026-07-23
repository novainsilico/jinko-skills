# Trial Setup

A minimum trial uses a computational model, model solving options by default, and a simple output set listing the component time series to save.

## High-Level Create Pattern

```python
model = client.get_model("cm-...")
folder = client.get_folder_by_name("2026-06-15-trial-run", exact_match_only=True)
output_set = client.create_simple_output_set(model, ["Drug"])
output_set = output_set.move_to_folder(folder)
trial = client.create_trial(model, simple_output_set=output_set, folder=folder)
```

Optional inputs can be added when they already exist:

```python
trial = client.create_trial(
    model,
    vpop=client.get_vpop("vp-..."),
    protocol=client.get_protocol_design("pd-..."),
    simple_output_set=output_set,
    advanced_output_set=client.get_advanced_output_set("sc-..."),
    folder=folder,
)
```

For creating and editing the advanced output set itself (constraints, scalars, objectives, diagnostics), see `jinko-output-set`.

## Data Tables

The high-level helper does not currently expose data-table attachment. For data tables, use raw trial creation with `dataTableDesigns` and project item refs.

Before creating the trial, inspect each data table and require `metadata.public.validForFitnessFunction` to be `True`. A table can upload successfully and still fail trial launch sanity if this metadata is false.

## Sanity Before Run

Do not launch while sanity reports errors. Call `trial.sanity()` — this is the same trial-context check the UI runs before launch, and it is the only reliable way to know a scoring design or output set is compatible with *this* trial. Standalone checks from `jinko-output-set` (`validate_scoring_formula`, `scoring_design.diagnostics`) validate an asset in isolation and cannot substitute for this step.

`trial.sanity()` returns a plain `dict` (the raw JSON response, no typed wrapper) — index into it with string keys rather than attribute access.

```python
report = trial.sanity()
for name in ("model", "protocol", "vpop", "outputSet", "scorings", "solvingTimes"):
    detail = report[name]
    errors = detail["sanity"]["errors"]
    if errors:
        print(name, [(e["code"], e["reason"], e["items"]) for e in errors])

for table_detail in report["dataTables"]:
    errors = table_detail["sanity"]["errors"]
    if errors:
        print("dataTables", [(e["code"], e["reason"], e["items"]) for e in errors])
```

Typical upstream problems: model sanity errors, protocol override keys missing from the model, vpop descriptors missing from the model, data-table `obsId` missing from the model, data-table `armScope` values missing from the protocol arms, or an advanced output set whose formulas don't resolve against this trial's model/simple-output-set (`ADVANCED_OUTPUTS_ERRORS` under `report["scorings"]`).

### Safe Workflow: Simple + Advanced Output Set → Trial → Sanity

This is the sequence that avoids launching (or approving) a trial whose advanced output set fails in context:

```python
# 1. Create or inspect the simple output set (see jinko-output-set)
simple_output_set = client.create_simple_output_set(model, model.time_dependent_ids())

# 2. Create the advanced output set (standalone validation only — see jinko-output-set)
advanced_output_set = client.create_advanced_output_set(
    scalars=[{"id": "auc", "formula": "AUC_drug", "unit": "mg/L*h"}],
    objectives=[...],
)

# 3. Attach both to a trial
trial = client.create_trial(
    model,
    simple_output_set=simple_output_set,
    advanced_output_set=advanced_output_set,
)

# 4. Run trial sanity before launch — this is the trial-context check
report = trial.sanity()
scoring_errors = report["scorings"]["sanity"]["errors"]
output_set_errors = report["outputSet"]["sanity"]["errors"]
if scoring_errors or output_set_errors:
    raise RuntimeError(f"trial sanity failed: {scoring_errors + output_set_errors}")

trial.run()
```

Steps 1–2 passing does not imply step 4 will pass — a scalar/objective formula can be syntactically valid and reference ids that exist in isolation, yet still fail to resolve once bound to this trial's model outputs and simple output set.

### Troubleshooting: "The following advanced outputs have errors"

This is the UI error shown when `trial.sanity()`'s `scorings` component reports errors — most commonly code `ADVANCED_OUTPUTS_ERRORS` (or `SIMPLE_OUTPUTS_ERRORS` for the simple output set, under `outputSet`). To reproduce and fix it from the SDK:

```python
report = trial.sanity()
for check in report["scorings"]["sanity"]["errors"]:
    print(
        check["code"], check["reason"], check["items"]
    )  # items: affected component ids

for component in report["scorings"]["sanity"]["componentsSanity"]:
    if component["sanity"]:
        print(component["id"], component["sanity"])  # per-scalar/objective diagnostics
```

If this reports errors while `advanced_output_set.diagnostics` (standalone, see `jinko-output-set`) reports none, the formula is syntactically valid but does not resolve correctly in this trial's context. The most common cause: the formula references a simple-output-set measure name (e.g. a measure you named `T_auc`) instead of a raw model descriptor id. Advanced-output-set formulas only resolve against model descriptors (species, parameters, compartments, reactions, ODE rates) — never simple-output-set measure names — and must reduce time series to a scalar themselves using the formula language's own time-reduction functions (`auc(T)`, `lastValue(T)`, `gmax(T)`, ...), not the simple output set's `AcrossTime`/`PointAtTime` measures. See `jinko-output-set`'s `references/formula-language.md` for the grammar. A component whose formula references an unresolvable name surfaces the same two diagnostics either way — `"<name> is a timeseries..."` and `"...does not match any model species, parameter, compartment, reaction or ODE rate: <name>"` — regardless of whether `<name>` was a typo or a measure name that simply lives in the wrong asset. Fix the formula or the upstream asset, then re-run `trial.sanity()` — do not rely on standalone diagnostics alone to declare it fixed.

## Run And Poll

```python
trial.run()
status = trial.wait_until_completed(timeout=1800)
```

The default polling interval in `wait_until_completed()` is 5 seconds.
