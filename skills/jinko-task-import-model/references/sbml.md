# SBML

## What the import keeps

Measured on Jinkō on 2026-10-29 with a small SBML level 3 model:

- Component ids stay as in the SBML: species `A` stays `A`, not
  `central.A`.
- Units come from the SBML unit definitions. The model time unit goes on a
  `time` parameter (for example `h`), and `reference` records it.
- A species keeps its unit kind. Jinkō reports a species declared as a
  concentration in a concentration unit, and `run-sbml` then reads `[A]` from
  libRoadRunner. Other species are read as amounts.
- The solving grid is the Jinkō default (one month, daily steps), not a grid
  from the SBML. SBML holds no simulation settings.

With `trust_units=False`, unit checking is off (`NoUnitCheck`) and every
species becomes an amount.

## What Jinkō refuses

From the [SBML import page](https://doc.jinko.ai/docs/platform/features-and-capabilities/modeling/import-an-sbml-document-in-jinko/),
which stays the reference. Check the file for these before you import it, and
tell the user what will fail:

- Any SBML package (arrays, comp, distrib, dyn, fbc, layout, math, multi,
  qual, render, spatial): the upload fails with an error.
- Constraints, lambda expressions, and the `quotient` operator.
- A dimensionless model time unit.

SBML up to L3V2 is accepted; an older level is converted to L3V2 first.
Function definitions, events, `delay`, `rateOf`, and algebraic rules are
supported.

## Check

`run-sbml --dir <dir> --source <file>` simulates the source SBML with
libRoadRunner on the Jinkō time points, then `compare`. When the model has no
`time` parameter, pass the SBML time unit with `--time-unit` (the `timeUnits`
of the `<model>` element; `second` when unset).

If the import renamed an id, `run-sbml` stops and names it. Compare the
series under their source ids.

## Install (optional)

Install it in the Python environment of the SDK, with the package manager of
that environment (pip, uv, conda):

```bash
pip install libroadrunner pint
```
