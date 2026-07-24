# Bundled Script Examples

## Create a Design

```bash
python skills/jinko-calibration-subsampling/scripts/create_subsampling_design.py --trial-sid tr-... --numeric-filter age:Gte:18:treated --marginal-normal endpoint:12:2.5:treated
python skills/jinko-calibration-subsampling/scripts/create_subsampling_design.py --trial-sid tr-... --numeric-filter age:Gte:18:treated --marginal-normal endpoint:12:2.5:treated --folder 2026-07-22-subsampling --create-folder --apply
```

## Generate a Vpop

```bash
python skills/jinko-calibration-subsampling/scripts/generate_subsampled_vpop.py --subsampling-design-sid sd-... --num-samples 100 --seed 42 --num-iterations 100 --iters-fixed-temperature 10 --replacement-rate 0.01 --boltzmann-constant 0.001 --apply
```

## Inspect a Design and Its Outputs

```bash
python skills/jinko-calibration-subsampling/scripts/inspect_subsampling_design.py --subsampling-design-sid sd-... --content --diagnostics --generated-vpops
```
