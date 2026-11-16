# SBML

The export is one SBML document, `CM_<model>.xml`, level 3 version 2 by
default. Use another level only when the user's tool needs it: the API accepts
`L1V1` to `L3V2`. For SimBiology, the Jinkō guide recommends `L2V4`, but the
SimBiology code export is the better path to SimBiology.

## Check

`run-sbml --dir <dir>` simulates the document with libRoadRunner on the Jinkō
time points, then `compare`. Series ids map from `Compartment.Species` to
`Compartment_DOT_Species`.

## What the export changes

- Categorical parameters take the model's default values.
- Some reactions become plain ODEs.
- Recurring events become periodic triggers.
- `rnorm` and `runif` cannot be exported: the export fails with an error.
- No solver settings or simulation description (SED-ML) are included.

## Install (optional)

Install it in the Python environment of the SDK, with the package manager of
that environment (pip, uv, conda):

```bash
pip install libroadrunner
```
