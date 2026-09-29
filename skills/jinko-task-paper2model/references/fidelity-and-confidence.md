# Fidelity and confidence

`scripts/paper2model_report.py validate` enforces every consistency rule between
outcome, confidence, execution, targets, and conflicts, and its errors state the
rule that failed. Run it instead of restating those rules from memory.

## Report the layers separately

Never collapse these into one score.

| Layer | Minimum evidence |
| --- | --- |
| Source | Coverage counts for states, parameters, equations, initial conditions, events, scenarios, and unresolved source conflicts |
| Implementation | Source-to-Jinkō map, symbol closure, repairs, omissions, unit policy, and dynamic-versus-constant semantics |
| Execution | Diagnostics, solve status, time grid, finite values, applicable constraints, event checks, and numerical refinement |
| Numerical | Per-target metric, tolerance, measured value, pass state, and coverage |
| Code parity | Optional comparison with identified and authorized code, separate from publication agreement |
| Curated implementation agreement | Separate target basis and assessment against a hashed, fixed reference implementation |

## Choosing between permitted confidence levels

The validator decides which levels are permitted. Choosing among them is a
judgment about the evidence: `moderate` rather than `high` when reviewed OCR, a
source inconsistency, or dependence on author code materially affects the claim;
`low` when the model executes but numerical support is absent, incomplete, or
materially assumption-dependent.

Confidence applies only to the declared reproduction scope. It is not a claim of
clinical credibility, predictive validity, or validity in another scenario.
Source-supported corrections do not automatically reduce confidence. Judge the
strength of their evidence and verification. Reviewed assumptions remain
assumptions. Follow `interpretation-policy.md` for automatic corrections,
acceptable alternatives, target dependencies, and superseded decisions.

## Numerical comparisons

Fix the metric before simulating. For a curve, report coverage plus at least an
absolute and a scale-aware error. For a scalar range, report the simulated value
and the range. For a categorical behavior, state a falsifiable condition and
whether it occurred. Visual similarity is never the only quantitative result.
