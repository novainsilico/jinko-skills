# Changelog

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
