# Diagnostics and Vpop Generation

## Validate first

`design.diagnostics` is the subsampling-design sanity check.
It is a fresh, typed view that can be filtered and rendered with resolved source-Trial context:

```python
diagnostics = design.diagnostics
if diagnostics.errors():
    raise RuntimeError(diagnostics.errors().explain())
print(diagnostics.warnings().explain())
```

Fix errors before calling `generate_vpop`.
A clean design only confirms the platform can interpret its references; it does not establish that the input population covers the desired distribution or that the match is scientifically acceptable.

## Generate

Jinkō's default subsampling algorithm is simulated annealing (GNU Scientific Library implementation): a probabilistic search that selects, at each iteration, which patients to swap in or out of the candidate subset to minimize a cost function.
That cost function is the weighted sum of Kolmogorov–Smirnov distances between target and subsampled marginal distributions, plus the difference between target and achieved correlations.
It only selects existing patients; it never creates new ones, so the filtered Vpop must already cover the target distributions (see `references/inspection.md` for reading back the achieved fit).

```python
vpop = design.generate_vpop(
    num_samples=100,
    seed=42,
    num_iterations=100,
    iters_fixed_temperature=10,
    replacement_rate=0.01,
    boltzmann_constant=1e-3,
    folder=folder,
    name="matched-vpop",
)
```

All six algorithm arguments are explicit in the SDK:

| Argument | Meaning |
| --- | --- |
| `num_samples` | Desired number of patients; it must be below the filtered Vpop size. |
| `seed` | Random-number seed for reproducibility. |
| `num_iterations` | Total simulated-annealing iterations; default 100, up to ~80k for heavily constrained designs. |
| `iters_fixed_temperature` | Iterations at each temperature level; it must not exceed `num_iterations`. |
| `replacement_rate` | Proportion of samples swapped per iteration, between 0 and 1. |
| `boltzmann_constant` | The `kT` term in the annealing acceptance probability `p = exp((Ea - Eb) / kT)`; controls how readily an uphill (worse-cost) move is accepted. |

The generated Vpop is an immutable artifact.
Adjust the design and generate a new Vpop rather than attempting to edit its patients.
