# SDK Script Examples

These are on `PATH` as console scripts once the SDK is installed, and also
runnable via `python -m` as shown below.

## Create a Design

```bash
python -m jinko.cli.create_subsampling_design --trial-sid tr-... --numeric-filter age:Gte:18:treated --marginal-normal endpoint:12:2.5:treated
python -m jinko.cli.create_subsampling_design --trial-sid tr-... --numeric-filter age:Gte:18:treated --marginal-normal endpoint:12:2.5:treated --folder 2026-07-22-subsampling --create-folder --apply
```

## Generate a Vpop

```bash
python -m jinko.cli.generate_subsampled_vpop --subsampling-design-sid sd-... --num-samples 100 --seed 42 --num-iterations 100 --iters-fixed-temperature 10 --replacement-rate 0.01 --boltzmann-constant 0.001 --apply
```

## Inspect a Design and Its Outputs

```bash
python -m jinko.cli.inspect_subsampling_design --subsampling-design-sid sd-... --content --diagnostics --generated-vpops
```
