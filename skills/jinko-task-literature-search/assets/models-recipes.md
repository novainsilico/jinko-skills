# Reusable Model Search Recipe

Use Models searches for mathematical or computational models that may supply
structure, equations, parameter values, or code. Establish the desired
granularity, such as PK, PBPK, Pop-PK, QSP, ODE, or another mechanistic form.

## Angles

Build at least three angles, varying model terminology:

- `<ENTITY>[tiab] AND ("mathematical model"[tiab] OR "computational model"[tiab])`;
- `<ENTITY>[tiab] AND "mechanistic model"[tiab]`;
- `<ENTITY>[tiab] AND (QSP[tiab] OR PBPK[tiab] OR ODE[tiab])`;
- treatment-specific PK, PBPK, or population-PK terminology when relevant.

Use `NOT (animals[mh] NOT humans[mh])` for human-model questions. Exclude pure
animal analogues, risk scores, and machine-learning predictors unless requested.
Retain hybrids when the same record also shows mechanistic, QSP, PBPK, PK/PD,
ODE, compartmental, mass-balance, or state-variable content.

## Priority

Verify reusable-model evidence in the title, abstract, full text, or supplement:

- equations, ODE/PDE systems, compartments, state variables, or mass balances;
- parameter tables, estimates, priors, posteriors, or sensitivity analysis;
- SBML/BioModels records, code repositories, archived artifacts, or supplements;
- calibration or validation against data.

Exclude a record only when its non-mechanistic nature is clear; otherwise retain
it at lower priority with the uncertainty stated in `verification_note`.
