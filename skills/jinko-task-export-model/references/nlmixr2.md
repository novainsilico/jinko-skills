# nlmixr2 and rxode2

The export is an R program, `<model>.R`, that defines the model for nlmixr2 and
solves it with rxode2. Jinkō marks it as beta.

## Check

`run-nlmixr2 --dir <dir>` writes `check_nlmixr2.R` and runs it with `Rscript`.
The driver keeps the exported model definition, drops the export's own solve
and plots, and solves with rxode2 on the Jinkō time points with tight
tolerances. Then run `compare`. Series ids map from `Compartment.Species` to
`Compartment_Species`.

## What the export changes

From the Jinkō export guide:

- Not supported: algebraic equations, delays, and events. Doses and other
  events of the model are not in the export, so a dosed model cannot match.
- Categorical parameters take their default values.
- All reactions become ODEs.

## Install (optional)

Install R the way the user prefers: CRAN (<https://cran.r-project.org/>) or a
package manager. Then add the packages:

```bash
Rscript -e 'install.packages(c("nlmixr2", "rxode2"))'
```

With Nix, build an R that already has the packages, then pass its `bin/Rscript`
to `run-nlmixr2 --rscript`. The first build compiles the packages and takes a
while:

```bash
nix build --impure --no-link --print-out-paths --expr 'let pkgs = import (builtins.getFlake "nixpkgs") {}; in pkgs.rWrapper.override { packages = with pkgs.rPackages; [ rxode2 nlmixr2 ]; }'
```
