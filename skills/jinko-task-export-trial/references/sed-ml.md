# Export a trial to SED-ML

The SDK package `jinko_sedml` writes the trial as an OMEX archive: a SED-ML
experiment with the SBML of the trial's model revision. It runs the archive
with a pinned tellurium and compares the results with Jinkō. The host needs
the SDK extra `sedml`. Tellurium runs in its own Python 3.11 environment,
from the requirements file of the package (`jinko_sedml/runtime`). Ask
before you install anything.

1. **Fetch** the completed trial with its original data tables:
   `python -m jinko2julia fetch <trial> --out fetched --original-tables`.
2. **Bind the model.** Download the model revision named in
   `fetched/meta.json` with `download_as_zip(revision=..., cm_in_sbml=True,
   cm_in_json=False, solving_options_in_json=False)`, and keep its SBML
   unchanged as `bound-model.xml`. If the revision cannot be verified, stop.
3. **Export** to a new folder:

   ```bash
   python -m jinko_sedml export-trial fetched exported --sbml bound-model.xml
   ```

   Report the warnings of `exported/conversion.json`. A refusal gives no
   archive. Do not remove inputs or outputs to get one.
4. **License.** The archive takes no license. Write the chosen license with
   `jinko2julia.licensing.bundle_license` as `LICENCE` next to
   `archive.omex`, and tell the recipient to keep both.
5. **Check** with the tellurium interpreter:

   ```bash
   python -m jinko_sedml check exported fetched checked --tellurium-python <tellurium>/bin/python
   ```

   Report the verdict of `checked/comparison.json`, with the solver methods
   from `checked/reproduction.md`. This command starts no Jinkō trial: tight
   evidence comes only from captured Jinkō results (`--jinko-tight`).

## Refusals

A refusal stops the command with a code and the construct. Report both. It
is a limit of the profile, not a partial success.

| Codes | Cause |
| --- | --- |
| `E_TRIAL_INPUT`, `E_TABLE_BINDING` | The fetched folder is incomplete, or its data tables are not bound to the trial revision: fetch again |
| `E_TRIAL_FEATURE` | A trial feature outside the profile, such as muted components, varying stoichiometry, or an arm override of `tMax` or `tStep` |
| `E_EXPORT_CATEGORICAL` | The SBML export fixed an active categorical parameter to one level |
| `E_CATEGORICAL_INPUT`, `E_CATEGORICAL_VARIANT`, `E_OVERRIDE_FORMULA`, `E_OVERRIDE_UNIT`, `E_CONSTANT_EVENT_UPDATE` | An arm formula or categorical level that no reviewed SBML variant can express |
| `E_CONTROL_ARM` | A control link to an arm that is missing or not active |
| `E_MEASURE_REFERENCE`, `E_SCORING_REFERENCE` | A declared measure or scoring has no captured Jinkō value |
| `E_MEASURE_INPUT`, `E_MEASURE_WINDOW`, `E_SCALAR`, `E_SCALAR_FUNCTION`, `E_SCALAR_SCOPE`, `E_SCALAR_SERIES`, `E_SCALAR_UNIT`, `E_OUTPUT_UNIT` | A measure, window, scope, or unit that the profile cannot compute |
| `E_BASELINE_CHANGE`, `E_BASELINE_MODEL`, `E_BASELINE_OUTPUT` | A baseline that the model events cannot reproduce |
| `E_SCORING_ID`, `E_SCORING_INPUT`, `E_SCORING_MODE`, `E_SCORING_SCOPE`, `E_SCORING_SERIES`, `E_SCORING_TIME`, `E_SCORING_UNIT`, `E_TABLE_FORMAT`, `E_TABLE_SLICE`, `E_TABLE_VALUE` | A data table or scoring that the profile cannot compute |
| `E_FIT_EXPORT` | A calibration that cannot become a bounded parameter fit |
| `E_EVENT_RECORDING` | A recorded event without a unique identity or a valid time |
| `E_ARCHIVE_LIMIT`, `E_CONVERSION_LIMIT`, `E_TIME_GRID` | The trial exceeds a size or time-grid limit of the archive |
| `E_CHECK_INPUT`, `E_TIGHT_INPUT` | The archive differs from the fetched inputs, or captured tight results are missing |
| `E_ENGINE`, `E_TIGHT_ENGINE`, `E_RUN_CONSTRUCT`, `E_RESULT_MAPPING`, `E_RESULT_SHAPE`, `E_MISSING_RESULT` | The tellurium run failed or its results do not map: see `tellurium/engine.log` |
| `E_SOLVER`, `E_SOLVER_DAE`, `E_SOLVER_PARAMETER`, `E_SOLVER_RUNTIME` | A solver method or setting that tellurium cannot apply faithfully, or a model that is not ODE-only |
