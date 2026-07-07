---
name: jk-trial
description: >-
  Create, sanity-check, run, poll, and download results for Jinkō in-silico trials via the jinko-sdk. Use this skill whenever the user wants to set up a trial from a computational model and simple output set, optionally attach a vpop, protocol, data table, or advanced scoring output set, launch a trial, wait for completion, inspect completed trials, or download TimeSeries and Scalar results as pandas DataFrames. Do not use this skill for model editing, vpop creation, protocol design authoring, data-table upload, output-set creation/editing, or trial visualization.
compatibility: >-
  Check set-up with the `jk-sdk-setup` skill. Creating/running trials requires write and run permissions in the Jinkō project. Result DataFrame conversion requires pandas; raw ZIP/CSV download works without pandas.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Trial SDK Workflows

Use this skill for trial setup, sanity checks, run/poll, and result download. Keep creation of upstream assets in their dedicated skills: `jk-model`, `jk-vpop`, `jk-protocol`, `jk-data-table`, and `jk-output-set` (simple and advanced output sets).

## Minimum Trial

A minimum trial is composed of:

- A computational model.
- Solving options, using the model defaults unless an override is explicitly provided.
- A simple output set, defined as the list of component time series that should be saved and visualized. Use `model.time_dependent_ids()` as the default output ids when the user has not specified ids.

Optional trial inputs:

- Vpop.
- Protocol design.
- Data table design(s).
- Advanced output set/scoring design.

## Sanity Constraints

Do not launch while trial sanity reports errors. These constraints are checked by Jinkō sanity:

- The computational model cannot have sanity errors.
- All descriptors in the protocol must correspond to model components.
- All descriptors in the vpop must correspond to model components.
- All descriptors in data-table `obsId` columns must correspond to model components.
- All data-table `armScope` values must correspond to protocol arms when a protocol is used.

If sanity errors are reported, show them and ask whether the user wants help fixing the upstream asset.

## Core SDK Methods

- Create simple output set: `client.create_simple_output_set(model, model.time_dependent_ids())` unless explicit output ids were requested. See `jk-output-set` for measure shapes and advanced output sets (constraints/scalars/objectives).
- Create trial: `client.create_trial(model, vpop=..., protocol=..., simple_output_set=..., advanced_output_set=...)`.
- Run trial: `trial.run()`.
- Poll: `trial.wait_until_completed(timeout=1800)`.
- Discover time series: `trial.output_ids()`.
- Discover scalars and arms: `trial.results.summary()`.
- Download time series as pandas when available: `trial.results.timeseries({...}).to_dataframe()`.
- Download scalars as pandas when available: `trial.results.scalars([...]).to_dataframe()`.
- Without pandas, use `TabularDownload.bytes`; result payloads may be CSV or zipped CSV.

When data tables are attached, the current SDK high-level trial helper does not expose a `data_table` argument. Use raw trial creation with `dataTableDesigns` only for that case. Verify each data table reports `metadata.public.validForFitnessFunction: True` before creating the trial; otherwise launch can fail with backend sanity errors.

## Project Folder Hygiene

- Prefer creating output sets and trials inside a dedicated Jinkō folder instead of the project root. At the start of a workflow, ask for or propose a folder name, for example `YYYY-MM-DD-<experiment-name>`.
- Reuse an existing exact-match folder when possible: `client.folders.get_by_name(name, exact_match_only=True)`.
- If the folder does not exist, create it only after user confirmation or when a script is run with `--apply`.
- Resolve one folder object or folder id, then pass `folder=folder` to trial creation calls. For simple output sets, create them first and then move them with `output_set.move_to_folder(folder)`.

## Bundled Scripts

- `scripts/find_completed_trial_results.py`: lists trials, finds the first completed one, prints its summary, and downloads TimeSeries and Scalar results to pandas DataFrames.
- `scripts/setup_and_run_trial.py`: creates a simple output set, creates a trial from model plus optional assets, sanity-checks, optionally runs, polls, and optionally downloads results.

Examples:

```bash
python skills/jk-trial/scripts/find_completed_trial_results.py --limit 20 --output-dir trial-results
python skills/jk-trial/scripts/setup_and_run_trial.py --model-sid cm-...
python skills/jk-trial/scripts/setup_and_run_trial.py --model-sid cm-... --output-id Drug
python skills/jk-trial/scripts/setup_and_run_trial.py --model-sid cm-... --output-id Drug --folder 2026-06-15-trial-run --create-folder --apply --run
python skills/jk-trial/scripts/setup_and_run_trial.py --model-sid cm-... --output-id Drug --vpop-sid vp-... --protocol-design-sid pd-... --data-table-sid dt-... --apply --run --download-results
```

## Reference Routing

- Read `references/trial-setup.md` for trial creation and sanity-check flow.
- Read `references/trial-results.md` for completed-trial discovery and result downloads.
