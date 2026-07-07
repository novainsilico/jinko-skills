# Trial Setup

A minimum trial uses a computational model, model solving options by default, and a simple output set listing the component time series to save.

## High-Level Create Pattern

```python
model = client.get_model("cm-...")
folder = client.folders.get_by_name("2026-06-15-trial-run", exact_match_only=True)
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

For creating and editing the advanced output set itself (constraints, scalars, objectives, diagnostics), see `jk-output-set`.

## Data Tables

The high-level helper does not currently expose data-table attachment. For data tables, use raw trial creation with `dataTableDesigns` and project item refs.

Before creating the trial, inspect each data table and require `metadata.public.validForFitnessFunction` to be `True`. A table can upload successfully and still fail trial launch sanity if this metadata is false.

## Sanity Before Run

Do not launch while sanity reports errors. Typical upstream problems are model sanity errors, protocol override keys missing from the model, vpop descriptors missing from the model, data-table `obsId` missing from the model, or data-table `armScope` values missing from the protocol arms.

## Run And Poll

```python
trial.run()
status = trial.wait_until_completed(timeout=1800)
```

The default polling interval in `wait_until_completed()` is 5 seconds.
