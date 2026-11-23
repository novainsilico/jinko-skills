# Changelog

## 1.19.0 (2026-11-23)

### Highlights

- Population calibrations in the SDK now report their run status and their pre-launch sanity checks, and can be waited on until the run ends.

### SDK

#### Added

- `PopCalibration.status()` returns the run state and the number of iterations done, as a typed model.
- `PopCalibration.get_sanity()` returns the pre-launch sanity report for the calibration, the data tables, the model, and the options.
- `PopCalibration.diagnostics` gives a filterable, printable view over the sanity report. Call `has_errors()` before `run()`, or print the view to see every entry. `diagnostics_at(revision)` returns the same view for a past revision.
- `PopCalibration.wait_until_completed(timeout=..., poll_interval=...)` polls the status until the run is completed, stopped, or in error, and raises `TimeoutError` when the timeout passes first.

Skills in this release require `jinko-sdk>=1.19,<2.0`.

## 1.18.0 (2026-11-20)

### Highlights

- Push a local file or a web app to a Jinkō project as a raw file, and run a zip bundle as an embedded application.

### Skills

#### Added

- `jinko-task-import-model`: imports a Heta platform into Jinkō, with a check of the imported model against HetaSimulator.jl.
- `jinko-task-export-trial`: now published. Exports a whole Jinkō trial to a standalone program (Julia and Heta for now), runs it, and checks that it reproduces the Jinkō results.
- `jinko-task-ichm15-evidence-submission`: now published. Evaluates model outcomes and writes the Model Analysis Report for the ICH M15 evidence submission stage.
- `jinko-webapp`: new skill that pushes a local file or a web app (one HTML file, a directory, or a zip archive) to a Jinkō project as a raw file, pushes a new version of an existing raw file, sets how Jinkō displays it, and returns the Jinkō link. It bundles a web app as an embedded application with its manifest, corrects root-absolute links in the copy it writes, applies the Jinkō checks and the 210 MB limit, and asks for a yes before each device or data permission.

#### Changed

- `jinko-task-export-model`: the comparison reads its tolerance, its floor, and its time match from the shared Jinkō gate, so model imports, model exports, and trial exports apply one rule.
- `jinko-task-export-trial`: adds the Heta target, names the patient verdicts of the check, and follows the new check options.
- `jinko-task-export-trial`: a model with `delay(...)` now exports to the Julia target. The Heta target refuses it, says that the Heta runtime has no state history, and points to the Julia target.
- `jinko`: routes whole-trial export to `jinko-task-export-trial`, and ICH M15 work to `jinko-task-ichm15-planning` for the planning stage and to `jinko-task-ichm15-evidence-submission` once model outcomes exist.
- `jinko`: routes raw files and web apps pushed to Jinkō (HTML report, app, image, video, any other file) to `jinko-webapp`.

### SDK

#### Added

- `jinko2heta`: export a Jinkō trial to a Heta platform and check it against the Jinkō results.
- `heta2jinko`: convert a Heta platform to a Jinkō computational model, and check the imported model against HetaSimulator.jl.
- `jinko_trial_check`: the trial comparison, the agreement metrics, and the report, shared by the export targets.
- `jinko2julia`: models that use `delay(expression, duration)` now export and solve, with the state history of the Jinkō core: linear interpolation, constant values outside the history, separate left and right values at events, and delayed rules evaluated at the delayed time. A delay written directly inside another delay merges with it, and each duration is checked once per patient and arm, so a negative duration fails that patient. `rateOf` and delays in event schedules stay unsupported.
- `jinko2heta`: a model that uses `delay` is refused with its reason, that the Heta runtime does not implement the state history of the Jinkō core.

#### Changed

- The exported Julia bundle is reproducible and traceable: the copyright year comes from the trial run, `data/trial.json` and the bundle README record the generator version and the id, name, revision, and snapshot of each Jinkō input, and the runtime pins Julia 1.13.1.
- A trial time series is accepted on its integrated agreement: the area of the absolute difference over the area of the Jinkō curve, at most 1e-4. Above it, the same ratio applies to the two tight solves. Point-wise and signed-AUC values stay as diagnostics.
- `jinko2julia check` solves the suspect pairs again at tight tolerances in both tools: Julia, and Jinkō through a temporary copy of the trial that the check deletes after use. An item above the strict gate passes only when the two tight solves agree.
- `jinko2julia run`: `--arm` can be repeated to solve several arms in one run, `--resume` keeps the patients that an interrupted run into the same folder completed, and the runtime refuses to resume or to reuse saved arms from another bundle, tolerance mode, or arm selection.
- `jinko2julia check --stop-above inf` replaces `--no-stop`: it compares every patient and never stops, not even on a structural difference.
- A run fails loudly: a run that fails in the solver goes to `errors.csv` and the other runs go on, counted in `failed_runs`; any other error stops the run with a non-zero exit code.
- The runtime follows the core more closely for `round`, powers, logarithms in a base, trigonometric functions at infinity, and the roots of the floor, ceil, mod, and round switches.
- `Duration` is declared as an ISO 8601 duration in the OpenAPI spec, so calibrations and trials take and return durations in that form.
- `client.create_raw_file(...)` creates a raw file from a file path or from bytes, with a name, a folder, a description, and a version name. `raw_file.replace_content(...)` saves a new version on the same SID and URL. The content type defaults to the type that the file name extension indicates.
- `raw_file.settings()`, `raw_file.update_settings({...})`, and `raw_file.reset_settings()` read and change how Jinkō displays a raw file, for example to run a zip raw file as an embedded application.

#### Fixed

- A scalar unit that does not convert, a vpop or protocol column that is not a model input, and a `--julia` path that does not exist are now errors instead of silent fallbacks.
- The result files are assembled in patient-id order, by the runtime alone.
- Python and Julia give the same folder name to a patient, for every patient id.

Skills in this release require `jinko-sdk>=1.18,<2.0`.

## 1.17.0 (2026-11-16)

### Highlights

- Import a model from another tool into Jinkō with the new `jinko-task-import-model` skill: SBML, SimBiology, Monolix, and NONMEM. Each import is checked numerically: against the source tool for SBML and SimBiology, against a CSV of results for Monolix, and against an independent reference solve for NONMEM.
- Export a Jinkō model to SBML, SimBiology, Julia, or nlmixr2 with `jinko-task-export-model`, and check the export point by point against Jinkō.
- `jinko-task-cmaes` now offers a post-calibration uncertainty qualification: slice and joint intervals per parameter, pass/fail gates, and a Jinkō document with plots.
- Breaking: two skills are replaced. Use `jinko-task-import-model` instead of `jinko-task-from-nonmem`, and `jinko-task-export-model` instead of `jinko-task-export-to-matlab`.

### Skills

#### Added

- `jinko-task-import-model`: import a model from SBML, SimBiology XLSX, Monolix, or NONMEM into Jinkō, then check the import against the source tool (libRoadRunner, MATLAB, or a CSV of reference values) and write an optional comparison report.
- `jinko-task-cmaes`: offer an uncertainty qualification after a completed CMA-ES run. It explores the parameter space around the best patient in one trial, then reports a verdict with gates on reproduction, simulations, optimum, priors, bounds, identifiability, and correlations, with slice and joint intervals per parameter. The report is published as a Jinkō document with plots and cards for the linked project items.
- `jinko-task-debug-solving-errors`: investigate a failing solve, with inspection helpers for models and trials.
- `jinko-model`: `references/unit-pitfalls.md` lists unit errors that pass creation and fail later, and `scripts/sync_model_to_target.py` syncs an existing model to a declarative JSON target, committing only real changes.
- `jinko-model`: import a model file (SBML, SimBiology XLSX, Monolix structural model), import a Monolix project as a trial, and replace an existing model's content from such a file.
- `jinko-reference`: create figure and table extracts automatically from a PDF with `auto_extract_from_ocr=True`, and rename, move, delete, describe, or reclassify an extract.
- `jinko-task-literature-search`: validate shortlist citations against the retrieved records.
- `jinko-context`: a reference table of the update path for each project item type, and the rule to iterate on the same item with named versions.
- `jinko-data-table`: update an existing data table in place, with `replace_csv` or the `--data-table-sid` mode of the creation script.

#### Changed

- `jinko-task-export-model` replaces `jinko-task-export-to-matlab`. It exports to SBML, SimBiology code, SimBiology XLSX, Julia, and nlmixr2, checks each export against Jinkō with a point-wise tolerance, and writes an optional comparison report with plots.
- All skills: prefer `JINKO_API_KEY` for the SDK connection. A session code is used only when no API key is available, which removes one `get_session_code` call per SDK command. When `JINKO_PROJECT_ID` is not set, the skills ask which project to use.
- `jinko-task-paper2model`: publish the reproduction report as a Jinkō document in the model folder by default, first once the specification validates and then updated as results arrive.
- `jinko-trial`, `jinko-calibration-cmaes`, `jinko-task-cmaes`: after an upstream edit, update the existing trial or calibration with `set_components` instead of creating a new one.
- `jinko-document`: how to write a list inside a table cell.
- `jinko-calibration-cmaes`: `sorted_patients` takes a bare scalar id and returns patient ids without values; the reference shows how to download the scores and sort them locally.
- `jinko-model`: the dosing examples now use the species molar mass, so they pass the unit check under the default unit mode.
- `jinko-model`: a new section, "Keep piecewise outputs continuous," explains how a `?:` formula that jumps where its condition flips turns solver noise into large output differences, with the log floor as the worked example and the fix.

#### Fixed

- `jinko-sdk-setup`: the credentials page said that `JinkoClient()` reads a local `.env`. It reads the environment only. The SDK commands load a local `.env` when `python-dotenv` is installed, except `create_document_from_markdown`. The page now shows how to export the variables of `.env`, or how to call `load_dotenv()` before `JinkoClient()` in your own script.

#### Removed

- Breaking: `jinko-task-export-to-matlab` is removed. Use `jinko-task-export-model`, which also exports to MATLAB with SimBiology.
- Breaking: `jinko-task-from-nonmem` is removed. Its NONMEM conversion now lives in `jinko-task-import-model`. The upload of the simulated population as data tables with its trial overlay, and the converter's own document publisher, are gone; publish the report with `jinko-document`.

### SDK

#### Added

- `jinko2julia` exports a whole trial, with its model, virtual population, protocol arms, output set, and solving options, to a standalone Julia program: `pip install "jinko-sdk[jinko2julia]"`, then `python -m jinko2julia fetch|export|run|check|report`. The bundle runs with Julia 1.11 or later and no access to Jinkō, and writes its time series and scalars in the format of the SDK result downloads. `check` runs the bundle and compares each patient and arm with the Jinkō results, with a tight-tolerance solve for the pairs the strict gate does not resolve, and `report` writes a reproduction report with plots.
- The exported Julia code is readable on its own: each parameter, compartment, species, categorical parameter, reaction, ODE state, and event carries a comment with its Jinkō id, display name, description, tags, links, unit, and role in the code, and each event says which triggers it has. Unit conversions are named constants in `src/model/units.jl`, each with its source and target units and the exact ratio it comes from. The bundle header names the model, the trial, their revisions, and the generator version, and the README explains how to read the code. Two exports of the same trial give the same files, byte for byte.
- Each exported Julia bundle ships a `README.md` with prerequisites, pinned dependency versions, run instructions, and the folder tree, plus a `LICENCE`. Choose the terms with `--license all-rights-reserved|mit|nc|source` (`export_trial(..., license_type=...)` in Python); `source` keeps the original model's terms and attribution.
- `client.create_model_from_file()` creates a model from an SBML, SimBiology XLSX, or Monolix structural model file, and `model.replace_from_file()` replaces an existing model's content from such a file.
- `client.import_monolix_project()` imports a Monolix project as a trial, with its model and a simple output set.
- `Extract.set_classification()` changes the type and level of an existing extract.
- `Model.download_as_zip(cm_in_simbiology_code=True)` adds the SimBiology code, a MATLAB script that builds and simulates the model.
- `SimpleSolveOutput.compare()` compares series from another solver with the Jinkō results.
- `Trial.set_components()` and `Calibration.set_components()` point an existing trial or calibration to newer component snapshots, on the same SID. `DataTable.replace_csv()` and `DataTable.replace_sqlite()` replace a data table's content.
- Update modes in the CLIs: `setup_and_run_trial --trial-sid`, `create_data_table --data-table-sid`, and `create_simple_output_set --output-set-sid`, each with `--version-name`.
- `jinko.plotting.comparison_figure` and `jinko.comparison_report` draw and render a comparison between a Jinkō solve and another solver's.
- Inspection helpers for debugging a failing solve, with the `jinko.cli.debug_solving` command.
- `python -m nonmem2jinko convert|check` is the converter's own command line.

#### Changed

- `download_as_zip` now names the exported model after the model itself, instead of a placeholder, when no name is given. It also emits conversion warnings as Python warnings and raises when a requested format cannot be converted.
- Refreshed the API contract: trial sanity checks accept four new codes, and a pop calibration without a model or data table now loads. In `jinko.openapi_types`, `CalibrationOptionsJson` is renamed `CalibrationOptionsOverride`, and `Void` is removed.

#### Fixed

- A protocol design keeps its linked model when its arms change.
- A constant series from `simple_solve` is expanded before a comparison instead of failing.
- A Monolix project file (`.mlxtran`) passed to `create_model_from_file` now raises a clear error pointing to `import_monolix_project`.

#### Removed

- `nonmem2jinko`: the modules `platform.data_tables`, `platform.documents`, and `emit.data_tables` are removed, with the upload of the simulated population as data tables. Publish reports with `jinko.cli.create_document_from_markdown`. `validate.local.Comparison` is removed; use `jinko.types.SimpleSolveOutput.compare()`.

Skills in this release require `jinko-sdk>=1.17,<2.0`.

## 1.16.0 (2026-10-23)

### Highlights

- `jinko-vpop` and `jinko-calibration-subsampling` now state which distribution parameters are on the log scale and which are physical values, so generated Vpops land at the right order of magnitude.

### Skills

#### Changed

- `jinko-vpop`: states the scale of every log-scale distribution parameter. `LogUniform` bounds and `LogNormal` mean and standard deviation are `log_base(value)`; only the `LogNormalTruncated` bounds `posLowBound` and `posHighBound` are physical values. The skill gives a step-by-step procedure to compute the parameters, state the physical range back, and check the result, plus examples and new evaluations. `assets/distrib.json` carries the same information in its field descriptions.
- `jinko-vpop`: documents that `Mixture` weights are relative weights that do not have to sum to 1, with round integers such as `2` and `1` for a 2:1 split.
- `jinko-calibration-subsampling`: states that `scalar.log_normal` takes its mean and standard deviation on the log scale, that the source Vpop design `LogUniform` bounds are log values, and that `scalar.mixture` weights are relative weights.

Skills in this release require `jinko-sdk>=1.16,<2.0`.

## 1.15.1 (2026-10-16)

### Highlights

- `jinko-task-literature-search` no longer creates empty Jinkō References: a paper reaches Jinkō only with its PDF, and the agent asks you for the PDFs it cannot download.

### Skills

#### Changed

- `jinko-task-literature-search`: each angle directory now holds `references.json` and `manifest.json` only. Add `--keep-raw` to also write the raw PubMed and Crossref payloads.
- `jinko-task-literature-search`: a paper goes to Jinkō only with its PDF. When a download fails, the agent lists the missing papers with their citation and link, asks you to put the PDFs in a local folder, then reports the papers still missing and the files that match no paper. In an autonomous run it skips the missing papers and continues instead of waiting.
- `jinko-reference`: states both ways to create a Reference, from a PDF or from a verified DOI. After a PDF upload it compares the DOI that Jinkō detected with the expected DOI, and on a mismatch it gives you the Reference URL and the DOI to set.

#### Fixed

- The Claude Code marketplace entry and the plugin manifest are now separate files, so the plugin installs and lists correctly.

#### Removed

- `jinko-task-literature-search`: the interactive selection prompt, the `--enable-publication-download` option, and the `summary_table.json`, `selected_references.json`, `references_ama.txt`, and per-angle `README.md` files. Download the references you selected with `publication_download.py`.

Skills in this release require `jinko-sdk>=1.15,<2.0`.

## 1.15.0 (2026-10-15)

### Highlights

- Combining two models no longer leaves you stuck: the SDK reads the conflicts of a combined model and resolves them, and `jinko-model` explains the whole flow.

### Skills

#### Added

- Every published Jinkō skill now ships display metadata for the OpenAI plugin, so each skill shows a display name, a short description, and a starting prompt.
- `jinko-task-export-to-matlab` and `jinko-task-ichm15-planning` now carry this plugin metadata too, and the agent can call them without an explicit mention.
- `jinko-model`: a new "Model combination and conflicts" reference covers `combine_with`, how to record the snapshot to roll back to, how to read differing and identical conflicts, how to resolve them one by one or in bulk, and how to validate the combined model.

#### Changed

- `jinko-context`: the folder management reference now shows how to delete a folder by ID with `client.delete_folder(folder_id)`, next to `folder.delete()`.
- `jinko-reference`: the knowledge curation reference now states that `extract.set_description(text)` sets both the description and the formulation.
- `jinko-reference`: the skill now looks up the DOI with `client.find_references_by_doi(doi)` before it creates a Reference. It reuses a single match, asks you which SID to use when there are several matches, and creates a Reference only when there is no match.
- `jinko-document`: a new "Extracts in documents" reference explains how each line form renders. Cite an extract with its bare URL at the end of the sentence line, reword or merge extract sentences without creating new extracts, and keep the badges intact through `document.content()` round trips.
- The Jinkō plugin manifest now follows the open Agent Plugins schema, and it also defines a dark-mode brand color and dark icons.
- The Jinkō plugin now points to the SDK and skills documentation as its support page.
- Installing the Jinkō plugin now starts with `jinko-sdk-setup` as the onboarding skill, so you configure and verify your connection first.
- `jinko-context`: the domain language now says "Reference" for the project item that holds a source PDF and its bibliography metadata, names `Source` only as the API type, defines Highlight, and calls the trace back to evidence a "Traceability Link."
- `jinko-model`: step 6 now puts new References in the folder that the project's folder convention gives, instead of a fixed literature subfolder.

### SDK

#### Added

- `JinkoClient.delete_folder(folder)` deletes a folder, its descendant folders, and every project item they contain. Pass a `Folder` or a folder ID; use it when you only hold the ID.
- `JinkoClient.find_references_by_doi(doi)` returns the non-deleted references of the project with that DOI, or an empty list. The comparison ignores case, surrounding whitespace, a `doi:` prefix, and a `doi.org` or `dx.doi.org` URL prefix. The lookup reads each reference of the project, so call it once per DOI and keep the result.
- `Model.conflicts` returns the unresolved collisions that `combine_with` creates on the model head. Filter the view with `differing()`, `identical()`, `for_kind(...)`, `by_kind()`, `ids()`, and `get(id)`, and read each side of a collision through `from_` and `to`.
- `model.conflicts.resolve(...)` settles conflicts and returns the model at the new snapshot. Pass one strategy for the whole view, `"AcceptCurrent"`, `"AcceptIncoming"`, or `"AcceptBoth"`, or a mapping keyed by component id. Keeping both versions takes `incoming_new_name`, and optionally `current_new_name`.
- `Model.snapshot_before_combine()` returns the snapshot the model was on before its last combination, or `None` when it was never combined.

#### Changed

- The check for a newer `jinko-sdk` release on PyPI now runs once a day instead of once a week, so the upgrade notice appears sooner.
- `jinko check-jinko-connection` no longer calls PyPI itself. It reports the installed version, and the version notice comes from the single check that runs when you import the SDK.

#### Fixed

- `Extract.set_description()` now sets the description instead of raising `NotImplementedError`. The API also copies the text into the extract formulation, so `formulation` returns the new text after the call.
- `Extract.rename()` and `Extract.move_to_folder()` now work instead of raising `NotImplementedError`. A name you set by hand is kept, because automatic naming only replaces the default `Untitled` name.
- `jinko check-markdown-structure` now counts bare Jinkō project item URLs, such as an extract badge at the end of a sentence. A dropped URL is reported as a loss; moving a URL to another line is not.

Skills in this release require `jinko-sdk>=1.15,<2.0`.

## 1.14.0 (2026-10-12)

### Highlights

- Figures now match the Jinkō web app: the SDK ships the Jinkō plot style and turns trial plot data into tidy pandas frames, and `jinko-trial` adds ready-made recipes for time series, distributions, tornado, survival, and scatter plots.
- The SDK accepts a session code from a connected Jinkō MCP server, so a script can authenticate without an API key.
- The SDK now waits and resends a request that the server rate-limits, so long model-building or simulation loops no longer stop on the first rate-limit error.

### Skills

#### Added

- `jinko-trial`: new plotting recipes (`references/trial-plots.md`) that draw trial results in the Jinkō style, with one worked example per plot type and rules for colors, axis labels, and figure captions.

#### Changed

- Skills that authenticate against Jinkō now describe the session code path: when a Jinkō MCP server is connected, export the code it returns for the current process instead of writing an API key to `.env`.
- `jinko-document`, `jinko-task-cmaes`, `jinko-task-from-nonmem`, and `jinko-task-paper2model`: figures use the Jinkō plot style by default and point to the `jinko-trial` plotting recipes.
- `jinko-sdk-setup`: tells you to import only the clients and exceptions, and to read method signatures with `help()` on the objects the client returns. It also explains how to check a key's declared project scope before working across several projects.
- `jinko-model`: repeats that the SDK has no `jinko.model` module and that `help()` gives the method signatures.
- `jinko-trial`: to change only a few solving options, create the trial without the `solving_*` arguments, then call `trial.edit_solving_options({...})`.
- `jinko-context`: documents folder rename, recolor, move, and deletion, and asks for explicit confirmation before a folder is deleted with its contents.
- `jinko-task-ichm15-planning`: the ICH M15 link now points to the ICH guidelines page, and the dependencies are stated in the compatibility note instead of a separate section.

### SDK

#### Added

- `jinko.plotting` with the Jinkō palette, opacities, `axis_label`, and `jinko_style`, so figures match the Jinkō web app. Trial plot-data responses are typed and each one has `to_dataframe()` that returns a tidy frame. The `plot` extra installs matplotlib and pandas.
- Session code authentication: set `JINKO_SESSION_CODE` instead of `JINKO_API_KEY`. A session code can be exchanged only once, so get a new one for each process. The connection check and the error messages cover this path.
- Rate-limited requests are resent up to 4 times, waiting for the server's `Retry-After` delay when given, otherwise 1, 2, 4, then 8 seconds, capped at 60 seconds per wait. Set `rate_limit_retries=0` on a custom transport to turn this off.
- `Folder.delete()` and `Folder.update()` to delete a folder with its contents, or to rename, recolor, and move it. Folders carry a color, which `create_folder` accepts.
- `JinkoOrgClient.auth_check()` validates credentials and reads key metadata without a project ID.
- Crabbit gains the assignment and subsampling workers and the subsampling result dashboard: `CrabbitAssignmentWorker`, `CrabbitSubsampleWorker`, and `CrabbitSubsampleResultServer`.

#### Changed

- `JinkoClient.auth_check()` now raises `AuthenticationError` when the configured project is outside the key's declared scope. A successful check does not prove that the project exists or is accessible; request a project resource for that.
- `content()` docstrings explain that several item types return a typed pydantic object, which `json.dump` rejects: call `.model_dump(mode="json")`, or `download_as_zip` for a model.

#### Fixed

- Creating tagged components inside a components batch read the whole model once per tag, which hit the API rate limit on large batches. A batch now resolves every tag from its single initial read.
- Solving times that the API refuses are now rejected before the request, with an error naming the period and the rule it breaks, instead of an opaque HTTP error. Unparsable duration strings get an error that states the expected form, with examples.
- Passing only some `solving_*` arguments to `create_trial` now names the missing arguments and points to `trial.edit_solving_options()` and `trial.set_solving_times()`.

Skills in this release require `jinko-sdk>=1.14,<2.0`.

## 1.13.0 (2026-10-07)

### Highlights

- Organization API keys now reach several projects: `JinkoOrgClient` lists the projects a key sees and opens a project client for any of them, and the connection check works without a project id.
- `jinko-model` can now tag model components by scale, phenomenon, module, and readout, so a model is easier to navigate and visualize.

### Skills

#### Added

- `jinko-model`: optional scientific scoped tags, `granularity::*`, `phenomenon::*`, `module::*`, and `readout::*`, with a reference that gives the selection rules, the family colors, and a catalog of QSP, PBPK, and PK/PD examples.

#### Changed

- `jinko-sdk-setup`: tells you when to use `JinkoClient` and when to use `JinkoOrgClient`, describes what the connection check reports with and without `JINKO_PROJECT_ID`, and marks the project id as optional in the example `.env`.

### SDK

#### Added

- `JinkoOrgClient`, a client for the organization routes that needs no project id. It lists the projects an API key sees, opens a regular `JinkoClient` for one of them, creates a project in a group, and lists, reads, creates, and renames groups.

#### Changed

- `python -m jinko.cli.check_jinko_connection` no longer requires `JINKO_PROJECT_ID`. Without it, the check lists the projects the key sees. With it, the success line also names the key type.
- `PopCalibration.pwres()` and `PopCalibration.npde()` now take the distribution sample count, which the Jinkō core requires.
- Model interface diff types now carry `from`, `to`, and `isIdentical` instead of `current` and `incoming`.

#### Fixed

- Supplementary material uploaded to a reference now comes back as the matching project item type instead of always a raw file.

Skills in this release require `jinko-sdk>=1.13,<2.0`.
