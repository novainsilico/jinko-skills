# Changelog

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
