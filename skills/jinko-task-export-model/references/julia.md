# Julia

The export is a Julia program, `<model>.jl`, that defines the ODE system and
solves it with DifferentialEquations.jl. Jinkō marks it as beta.

## Check

`run-julia --dir <dir>` writes `check_julia.jl` and runs it. The driver keeps
the exported equations, events, and solver. It drops plotting, sets tight
tolerances, and saves the Jinkō time points. Then run `compare`.

The program saves the ODE states only. Parameters computed by rules are not in
its output; the comparison lists them as not checked. Series ids map from
`Compartment.Species` to `Compartment_Species`.

The first run compiles DifferentialEquations.jl. It can take from several
minutes to about an hour; tell the user before you start it.

## What the export changes

From the Jinkō export guide:

- Not supported: algebraic equations, delays, and advanced events (time events
  with conditions, delays, or priorities).
- Categorical parameters take their default values.
- All reactions become ODEs.
- Recurring events become an explicit list of event times.

## Install (optional)

Install Julia the way the user prefers: the official installer
(<https://julialang.org/downloads/>) or a package manager. Then add the
packages:

```bash
julia -e 'using Pkg; Pkg.add(["DifferentialEquations", "RecursiveArrayTools"])'
```

With Nix, run the same command through `nix shell nixpkgs#julia-bin -c`.
