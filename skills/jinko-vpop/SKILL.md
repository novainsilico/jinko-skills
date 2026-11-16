---
name: jinko-vpop
description: >-
  Create, generate, inspect, or work with Jinkō virtual populations (vpops) and vpop designs via the jinko-sdk. Use this skill whenever the user wants to upload a vpop from CSV or pandas DataFrame, create a vpop generator from marginal distributions, generate a vpop from a vpop design, inspect vpop content/statistics, or edit an existing vpop design. Vpops generated or uploaded as Vpop project items are not editable; edit the vpop design instead and regenerate.
compatibility: >-
   Check set-up with the `jinko-sdk-setup` skill. Creating vpops or vpop designs requires write access to the Jinkō project. DataFrame creation requires pandas.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.17,<2.0"
license: MIT
---

# Jinkō Vpop SDK Workflows

Use this skill for technical vpop and vpop-design workflows through the SDK. Use the allowed distribution shapes in `assets/distrib.json` and defer deeper distribution design to a dedicated distribution skill when available.

> **PREREQUISITE:** This skill needs an initialized `jinko-sdk` connection and
> an SDK satisfying its `metadata.requires_sdk` range. Run the `jinko-sdk-setup`
> skill (`../jinko-sdk-setup/SKILL.md`) and proceed only once its check passes.
> Use `JINKO_API_KEY` when it is set. Only without a key, call
> `get_session_code` again before this skill's own SDK process, because a
> session code can be exchanged only once. If that skill is not found, install
> it from `novainsilico/jinko-skills`.

## Core Rules

- Use `client.create_vpop_from_csv()` or `client.create_vpop_from_dataframe()` for direct vpop upload.
- Use `client.create_vpop_design_from_design()` for marginal-distribution vpop designs.
- Use `design.generate_vpop()` to generate an immutable Vpop from a `VpopDesign`.
- Check `design.diagnostics` (or `design.get_sanity()`) before generating, and fix reported errors first.
- Edit an existing design's descriptors/correlations with `design.descriptors` (`create*`/`set_distribution*`) and `design.correlations`, not by replacing the raw payload.
- Treat Vpop project items as generated/uploaded artifacts that are not edited in place.
- Edit vpop designs, not generated vpops, then regenerate a new vpop.
- Require explicit confirmation or script `--apply` before creating or updating project items.
- Descriptor IDs in CSV headers and marginal designs must match real model component IDs when the vpop will be used with that model.
- Reject duplicate descriptor IDs in marginal lists; converting duplicates to a mapping would otherwise silently discard earlier entries.
- Follow "Log-scale distributions" below for every `LogUniform`, `LogNormal`, or `LogNormalTruncated` payload, and "Mixture distributions" for `Mixture` weights.

## Project Folder Hygiene

- Prefer creating vpops and vpop designs inside a dedicated Jinkō folder instead of the project root. At the start of a workflow, ask for or propose a folder name, for example `YYYY-MM-DD-<experiment-name>`.
- Reuse an existing exact-match folder when possible: `client.get_folder_by_name(name, exact_match_only=True)`.
- If the folder does not exist, create it only after user confirmation or when a script is run with `--apply`.
- Resolve one folder object or folder id, then pass `folder=folder` to SDK creation calls that support it.

## Bundled Assets

- `assets/toy_vpop.csv`: two-patient vpop CSV using the toy model descriptors `Dose` and `k_elim`.
- `assets/toy_marginals.json`: list-of-marginals vpop design for `Dose` and `k_elim`.
- `assets/distrib.json`: source of truth for admissible marginal distribution shapes.

## SDK Scripts

Use scripts rather than embedding long Python examples in chat. These are on
`PATH` as console scripts once the SDK is installed, and also runnable via
`python -m` as shown below.

- `jinko.cli.create_vpop_from_csv`: uploads a CSV directly, or via pandas DataFrame with `--method dataframe`.
- `jinko.cli.create_vpop_design_from_design`: creates a vpop design from a list of unique `{ "id": ..., "distribution": ... }` entries and can optionally generate a vpop after diagnostics pass.
- `jinko.cli.inspect_vpop`: inspects content, description, or statistics for an existing vpop.
- `jinko.cli.edit_vpop_design`: updates or adds descriptors sequentially, reports already-applied IDs if a later edit fails, and runs post-edit diagnostics before success.

Examples:

```bash
python -m jinko.cli.create_vpop_from_csv --csv skills/jinko-vpop/assets/toy_vpop.csv
python -m jinko.cli.create_vpop_from_csv --csv skills/jinko-vpop/assets/toy_vpop.csv --apply
python -m jinko.cli.create_vpop_from_csv --csv skills/jinko-vpop/assets/toy_vpop.csv --folder 2026-06-15-vpop-study --create-folder --apply
python -m jinko.cli.create_vpop_design_from_design --design skills/jinko-vpop/assets/toy_marginals.json --model-sid cm-... --apply --generate
python -m jinko.cli.inspect_vpop --vpop-sid vp-... --statistics --correlations
python -m jinko.cli.edit_vpop_design --vpop-design-sid vd-... --design skills/jinko-vpop/assets/toy_marginals.json --apply
```

## CSV Upload Pattern

The minimal CSV shape is one row per patient:

```csv
patientIndex,Dose,k_elim
1,1.0,0.08
2,1.2,0.12
```

Use actual component IDs, not biological labels such as `age` or `weight`, when the vpop is meant to drive a model.

## Marginal Design Pattern

Use a list of marginal entries in skill assets and scripts:

```json
[
  {"id": "Dose", "distribution": {"tag": "Uniform", "lowBound": 0.8, "highBound": 1.2}},
  {"id": "k_elim", "distribution": {"tag": "NormalTruncated", "mean": 0.1, "stdev": 0.02, "lowBound": 0.01, "highBound": 0.3}}
]
```

The script converts this list to the SDK mapping expected by `create_vpop_design_from_design(marginal_distributions=...)`.

## Log-scale distributions

Agents often put the physical min and max of a descriptor into `LogUniform` `lowBound` and `highBound`. Jinkō then samples between `base**min` and `base**max`. For a physical range of 0.001 to 10 with `base: 10`, that gives values between about 1 and 1e10. The design diagnostics accept this payload, so the error shows up only in the generated Vpop.

| Field | Scale | Physical range 1e-4 to 1e-2, `base: 10` |
| --- | --- | --- |
| `LogUniform` `lowBound`, `highBound` | `log_base(value)` | `-4`, `-2` |
| `LogNormal`, `LogNormalTruncated` `mean`, `stdev` | `log_base(value)` | median 1e-3: `mean: -3` |
| `LogNormalTruncated` `posLowBound`, `posHighBound` | physical value | `1e-4`, `1e-2` |

Write each log-scale payload in this order:

1. Write down the physical range or median in the descriptor unit, from the source.
2. Compute the log-scale parameters with code, not by hand: `math.log(value, base)`. For `base: 10`, use `math.log10(value)`. A physical bound of 0 or less has no logarithm: use a positive lower bound or a different distribution.
3. Convert back and state the physical result in your reply before you create the design: "`LogUniform(lowBound=-4, highBound=-2, base=10)` samples 1e-4 to 1e-2."
4. Stop if the round trip does not give the source range. A typical sign of physical values in log fields: `lowBound` and `highBound` are both positive for a parameter smaller than 1.

```json
[
  {"id": "k_on", "distribution": {"tag": "LogUniform", "lowBound": -4, "highBound": -2, "base": 10}},
  {"id": "k_elim", "distribution": {"tag": "LogNormalTruncated", "mean": -1, "stdev": 0.3, "posLowBound": 0.01, "posHighBound": 1, "base": 10}}
]
```

The `k_on` entry samples 1e-4 to 1e-2. The `k_elim` entry has a median of 0.1 before truncation and keeps values between 0.01 and 1.

Other Jinkō objects use other conventions. A CMA-ES calibration with `log_transform=True` takes `mean` and `std` in `log10(x)` but `min_bound` and `max_bound` as physical values (`jinko-calibration-cmaes`). Do not copy bounds between a calibration prior and a vpop design without conversion.

After generating a Vpop with a log-scale marginal, read back the descriptor statistics and compare the minimum, maximum, and median with the physical range from step 1:

```bash
python -m jinko.cli.inspect_vpop --vpop-sid vp-... --statistics
```

## Mixture distributions

Each `mixture` item is a `[weight, distribution]` pair. The weights are relative weights, not probabilities. They do not have to sum to 1: Jinkō normalizes them. Use positive round integers that are easy to read. For a 2:1 split, write `2` and `1`, not `0.6666667` and `0.3333333`. For a published 13.5% subgroup, write `27` and `173`, or round to `1` and `6` if that precision is enough.

```json
{"id": "k_elim", "distribution": {"tag": "Mixture", "mixture": [
  [2, {"tag": "LogNormal", "mean": -1, "stdev": 0.2, "base": 10}],
  [1, {"tag": "LogNormal", "mean": -0.5, "stdev": 0.2, "base": 10}]
]}}
```

The `k_elim` entry puts two thirds of the patients in the first component. Each component follows its own scale rules, including the log-scale rules above.

## Reference Routing

- Read `references/csv-vpop.md` for direct CSV/DataFrame upload details.
- Read `references/vpop-design.md` for marginal vpop design and generation details.
- Read `assets/distrib.json` before adding or changing marginal distribution shapes.
