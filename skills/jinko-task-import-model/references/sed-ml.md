# Import a SED-ML experiment

The SDK package `jinko_sedml` reads an OMEX archive, or a SED-ML file with
its local SBML, and proposes the Jinkō items: model, protocol, output set,
population, data tables, and parameter fit. The preview is local; only the
approved upload writes to Jinkō. The host needs the SDK extra `sedml`; the
optional numerical check also needs the pinned tellurium environment of the
package. Ask before you install anything.

1. **Preview** in a new folder. For a SED-ML file, keep its SBML at the
   relative path it names, and use the second command:

   ```bash
   python -m jinko_sedml plan-import study.omex preview
   python -m jinko_sedml plan-import study.sedml preview --sedml
   ```

   From `preview/conversion.json` and `preview/mapping.json`, account for
   every source output, unit, observation time, patient, and arm, and for the
   solver settings and warnings. If the scope differs from the source, stop.
   Do not import the SBML alone: it would lose the experiment.
2. **Review the destination** (project and folder UUIDs):

   ```bash
   python -m jinko_sedml review-upload preview --project-id PROJECT --folder FOLDER --name "Imported study"
   ```

   Show the destination, the actions, and `approval_sha256`, and wait for
   the user's approval of this exact plan.
3. **Upload** with the same arguments and that approval:
   `python -m jinko_sedml upload preview --project-id PROJECT --folder FOLDER --name "Imported study" --approve APPROVAL_SHA256`.
   It creates the reviewed items and starts no simulation. Report the item
   IDs. After an uncertain write, read the journal and the destination
   before any retry.
4. **Numerical check, on request.** In an isolated environment, run the
   source with tellurium:
   `python -m jinko_sedml run preview/source.omex source-run --mapping preview/mapping.json --tellurium-python <tellurium>/bin/python`.
   Compare it with the results of the imported trial through
   `jinko_sedml.comparison.compare_results`. A Jinkō trial run needs its own
   approval. Without Jinkō results, the check is NOT RUN.

## Refusals

A refusal stops the command with a code and the construct. Report both. It
is a limit of the profile, not a partial success.

| Codes | Cause |
| --- | --- |
| `E_ZIP`, `E_MANIFEST`, `E_MASTER`, `E_NO_SEDML`, `E_MISSING_FILE`, `E_DUPLICATE_PATH`, `E_UNSAFE_PATH`, `E_EXTERNAL_SOURCE`, `E_ARCHIVE_LIMIT` | The archive is malformed, unsafe, too large, or names a file it does not hold |
| `E_XML`, `E_XML_DTD`, `E_XML_ENCODING`, `E_SEDML_INVALID`, `E_SEDML_NAMESPACE`, `E_SEDML_VERSION` | The SED-ML document is not valid UTF-8 SED-ML without a DTD |
| `E_MODEL_CYCLE`, `E_MODEL_FORMAT`, `E_MODEL_LANGUAGE`, `E_MODEL_SOURCE`, `E_SBML`, `E_SBML_CONSTRUCT`, `E_SBML_ID`, `E_SBML_PACKAGE` | A model that is not plain, local SBML |
| `E_DESCRIPTOR`, `E_XPATH`, `E_OVERRIDE`, `E_OVERRIDE_PRECEDENCE` | A change that does not target one SBML value, or patient and arm changes that collide |
| `E_IMPORT_DOCUMENTS`, `E_IMPORT_CONSTRUCT`, `E_IMPORT_MODELS`, `E_TASK_REFERENCE`, `E_REPEAT_NESTING`, `E_REPEAT_POPULATION`, `E_REPEAT_RANGE`, `E_REPEAT_RESET` | A simulation or repeated task outside the time-course profile |
| `E_DATA_GENERATOR`, `E_OUTPUTS` | A report or plot expression that does not map to a trial output |
| `E_IMPORT_EVENTS`, `E_IMPORT_BASELINES`, `E_IMPORT_CATEGORICAL`, `E_IMPORT_MEASURES`, `E_IMPORT_SCORINGS` | Events, baselines, categorical variants, measures, or scorings that the import cannot rebuild |
| `E_TABLE_MAPPING`, `E_TABLE_REFERENCE`, `E_FIT` | A data table or parameter fit outside the profile |
| `E_IDENTITIES`, `E_ARM_WEIGHT`, `E_CONVERSION_VALUE`, `E_TIME_UNIT`, `E_TIME_GRID`, `E_CONVERSION_LIMIT` | Duplicate names, invalid values, or a time grid or size outside the limits |
| `E_SOLVER`, `E_SOLVER_DAE`, `E_SOLVER_PARAMETER` | A solver method or setting that Jinkō cannot apply, or a model that is not ODE-only |
| `E_UPLOAD_TARGET`, `E_UPLOAD_CLIENT`, `E_UPLOAD_REVIEW`, `E_UPLOAD_APPROVAL`, `E_UPLOAD_EXISTS` | The upload stopped before any write: wrong destination, no client, changed review, or approval already used |
| `E_UPLOAD_CONCENTRATION`, `E_UPLOAD_EVENTS`, `E_TABLE_OPTIONS` | A reviewed item that the Jinkō routes cannot create faithfully |
| `E_UPLOAD_CHECK`, `E_UPLOAD_STOPPED`, `E_FIT_CREATE` | A write stopped or is uncertain: read the journal before any retry |
